from contextlib import asynccontextmanager
import asyncio
import csv
import io
import logging
from uuid import uuid4
from zoneinfo import ZoneInfo
import httpx
from datetime import datetime, timezone
from pathlib import Path
import json, re
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from telethon import TelegramClient
from telethon.errors import AuthRestartError, FloodWaitError, SessionPasswordNeededError
from telethon.tl.types import Channel, Chat
from .db import SessionLocal, upgrade_database
from .models import User, Profile, Resume, Source, Message, Job, JobSource, Application, Notification, NotificationPreference
from .config import settings
from .services.intelligence import SKILLS, is_job, extract, score_job, likely_duplicate, check_eligibility, suspicious_reasons
from .services.resume_parser import parse_resume
from .security import hash_password, verify_password, create_token, read_token

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global MONITOR_WAKE_EVENT
    MONITOR_WAKE_EVENT=asyncio.Event()
    upgrade_database()
    tasks=[asyncio.create_task(background_monitor()),asyncio.create_task(bot_poll())]
    yield
    for task in tasks: task.cancel()
    for task in tasks:
        try: await task
        except asyncio.CancelledError: pass
    if telegram_client and telegram_client.is_connected():
        async with TELEGRAM_LOCK:
            await telegram_client.disconnect()
    MONITOR_WAKE_EVENT=None
def require_auth(request:Request):
    public_paths={"/","/favicon.ico","/api/health","/api/auth/status","/api/auth/register","/api/auth/login","/docs","/openapi.json","/redoc"}
    if request.url.path in public_paths: return None
    header=request.headers.get("authorization","")
    token=header[7:] if header.lower().startswith("bearer ") else ""
    user_id=read_token(token) if token else None
    if user_id is None: raise HTTPException(401,"Sign in to use Job Intelligence")
    request.state.user_id=user_id

app=FastAPI(title="Job Intelligence", version="1.0.0", lifespan=lifespan,dependencies=[Depends(require_auth)])
configured_origins=[origin.strip().rstrip("/") for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", *configured_origins],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):(517[0-9]|8080)$",
    allow_methods=["*"],
    allow_headers=["*"],
)
telegram_client: TelegramClient | None = None

@app.get("/")
def root():
    return {
        "name": "Job Intelligence API",
        "status": "ok",
        "dashboard": "http://127.0.0.1:5173",
        "api_docs": "/docs",
        "health": "/api/health",
    }

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

def db():
    s=SessionLocal()
    try: yield s
    finally: s.close()
def profile(s):
    p=s.scalar(select(Profile).limit(1))
    if not p: p=Profile(); s.add(p); s.commit(); s.refresh(p)
    return p
def apply_resume_text(p,text):
    p.resume_text=text
    p.skills=json.dumps(sorted({x for x in SKILLS if re.search(r"(?<![\w])"+re.escape(x)+r"(?![\w])",text,re.I)}))
    parsed=parse_resume(text)
    for key in ("name","graduation_year","education","college","degree","cgpa"):
        setattr(p,key,parsed.get(key))
    for key in ("experience_json","projects_json","certifications_json"):
        setattr(p,key,parsed[key])
def client():
    if not settings.telegram_api_id or not settings.telegram_api_hash: raise HTTPException(503,"Configure Telegram API credentials in .env")
    return TelegramClient(settings.telegram_session, settings.telegram_api_id, settings.telegram_api_hash)

TELEGRAM_LOCK = asyncio.Lock()
MONITOR_WAKE_EVENT: asyncio.Event | None = None
MONITOR_STATUS = {
    "state": "starting",
    "last_sync_at": None,
    "last_success_at": None,
    "last_error": None,
    "enabled_sources": 0,
    "messages_scanned": 0,
    "authorized": False,
    "account": None,
}

@asynccontextmanager
async def telegram_connection():
    """Share one connection and serialize access to Telethon's SQLite session."""
    global telegram_client
    async with TELEGRAM_LOCK:
        if telegram_client is None:
            telegram_client = client()
        if not telegram_client.is_connected():
            await telegram_client.connect()
        yield telegram_client
def job_out(j):
    return {"id":j.id,"title":j.title,"company":j.company,"description":j.description,"location":j.location,"employment_type":j.employment_type,"experience_required":j.experience_required,"education_required":j.education_required,"graduation_year":j.graduation_year,"work_mode":j.work_mode,"salary":j.salary,"application_deadline":j.application_deadline,"application_url":j.application_url,"contact_email":j.contact_email,"contact_information":j.contact_information,"source_title":j.source_title,"posted_at":j.posted_at.isoformat(),"score":j.score,"matched_skills":json.loads(j.matched_skills),"missing_skills":json.loads(j.missing_skills),"required_skills":json.loads(j.required_skills),"extraction_confidence":j.extraction_confidence,"eligibility":j.eligibility,"review_reasons":json.loads(j.review_reasons),"application_status":j.application_status}

async def bot_poll():
    offset=0
    while True:
        if not settings.bot_token:
            await asyncio.sleep(30); continue
        try:
            async with httpx.AsyncClient(timeout=40) as hc:
                response=await hc.get(f"https://api.telegram.org/bot{settings.bot_token}/getUpdates",params={"offset":offset,"timeout":30,"allowed_updates":"[\"message\"]"})
                response.raise_for_status()
                updates=response.json().get("result",[])
                for update in updates:
                    offset=max(offset,int(update.get("update_id",0))+1)
                    message=update.get("message") or {}; chat=message.get("chat",{})
                    if chat.get("type")!="private": continue
                    command=(message.get("text") or "").split()[0].split("@")[0].lower()
                    if not claim_bot_chat(str(chat.get("id")),command): continue
                    text=await bot_command(command)
                    if text:
                        await hc.post(f"https://api.telegram.org/bot{settings.bot_token}/sendMessage",json={"chat_id":chat.get("id"),"text":text,"disable_web_page_preview":True})
        except asyncio.CancelledError: raise
        except Exception: await asyncio.sleep(10)

def claim_bot_chat(chat_id:str,command:str)->bool:
    if settings.bot_chat_id and settings.bot_chat_id!=chat_id: return False
    session=SessionLocal()
    try:
        pref=session.get(NotificationPreference,1)
        if pref is None:
            pref=NotificationPreference(id=1,immediate_threshold=settings.match_threshold); session.add(pref); session.flush()
        if pref.chat_id and pref.chat_id!=chat_id: return False
        if not pref.chat_id:
            if command!="/start": return False
            pref.chat_id=chat_id; session.commit()
        return True
    finally: session.close()

async def bot_command(command:str)->str|None:
    if command in ("/start","/help"):
        return "Job Intelligence\n\n/jobs — recent opportunities\n/topjobs — best matches\n/today — added today\n/internships — internship roles\n/fulltime — full-time roles\n/applications — application pipeline\n/settings — connection and threshold\n/status — monitoring status"
    s=SessionLocal()
    try:
        q=select(Job)
        if command=="/topjobs": q=q.order_by(Job.score.desc()).limit(8)
        elif command=="/today": q=q.where(func.date(Job.created_at)==datetime.now(timezone.utc).date().isoformat()).order_by(Job.score.desc()).limit(10)
        elif command=="/internships": q=q.where(Job.employment_type.ilike("%intern%" )).order_by(Job.score.desc()).limit(10)
        elif command=="/fulltime": q=q.where(Job.employment_type.ilike("%full%" )).order_by(Job.score.desc()).limit(10)
        elif command=="/applications": q=q.where(Job.application_status!="New").order_by(Job.created_at.desc()).limit(15)
        elif command=="/settings": return f"Alert threshold: {settings.match_threshold}\nPush alerts: {'configured' if settings.bot_chat_id else 'not configured'}\nChange values in local .env and restart the backend."
        elif command=="/status":
            count=s.scalar(select(func.count()).select_from(Job)) or 0
            enabled=s.scalar(select(func.count()).select_from(Source).where(Source.enabled==True)) or 0
            return f"Job Intelligence is running.\n{count} opportunities · {enabled} Telegram sources enabled.\nBackground sync interval: 5 minutes."
        elif command=="/jobs": q=q.order_by(Job.created_at.desc()).limit(10)
        else: return "Unknown command. Send /help to see available commands."
        found=s.scalars(q).all()
        if not found: return "No matching opportunities yet. Connect sources in the dashboard and wait for a sync."
        lines=[]
        for j in found:
            line=f"{j.score}% · {j.title} — {j.company or 'Company not listed'}"
            if j.location: line+=f" · {j.location}"
            if j.application_url: line+=f"\n{j.application_url}"
            lines.append(line)
        return "\n\n".join(lines)[:3900]
    finally: s.close()

async def maybe_daily_digest(session):
    pref=session.get(NotificationPreference,1)
    chat_id=settings.bot_chat_id or (pref.chat_id if pref else None)
    if not pref or not pref.daily_digest or not settings.bot_token or not chat_id: return
    local_now=datetime.now(ZoneInfo("Asia/Kolkata")); digest_date=local_now.date().isoformat()
    if local_now.hour<9 or pref.last_digest_date==digest_date: return
    utc_date=datetime.now(timezone.utc).date().isoformat()
    jobs=session.scalars(select(Job).where(func.date(Job.created_at)==utc_date).order_by(Job.score.desc()).limit(10)).all()
    lines=[f"Daily Job Intelligence digest · {digest_date}"]
    lines.extend([f"{j.score}% · {j.title} — {j.company or 'Company not listed'}"+(f"\n{j.application_url}" if j.application_url else "") for j in jobs])
    if not jobs: lines.append("No new opportunities were collected today.")
    async with httpx.AsyncClient(timeout=15) as hc:
        response=await hc.post(f"https://api.telegram.org/bot{settings.bot_token}/sendMessage",json={"chat_id":chat_id,"text":"\n\n".join(lines)[:3900],"disable_web_page_preview":True})
        response.raise_for_status()
    pref.last_digest_date=digest_date
    session.commit()

async def sync_source_history(tg, session: Session, src: Source, *, batch_size: int = 100, max_messages: int | None = None) -> int:
    """Catch up from the durable checkpoint in bounded batches until current."""
    entity=await tg.get_entity(int(src.chat_id))
    scanned=0
    while max_messages is None or scanned<max_messages:
        limit=batch_size if max_messages is None else min(batch_size,max_messages-scanned)
        batch=[]
        async for message in tg.iter_messages(entity,limit=limit,min_id=src.last_message_id,reverse=True):
            batch.append(message)
        if not batch: break
        for message in batch:
            if message.message:
                posted=message.date or datetime.now(timezone.utc)
                await process_text(session,message.message,src.chat_id,message.id,posted,src.title)
                # A previous attempt may have saved the job before its checkpoint.
                job=session.scalar(select(Job).where(Job.source_chat_id==src.chat_id,Job.source_message_id==message.id))
                pref=session.get(NotificationPreference,1)
                threshold=pref.immediate_threshold if pref else settings.match_threshold
                notify_enabled=pref.enabled if pref else True
                chat_id=settings.bot_chat_id or (pref.chat_id if pref else None)
                if job and not job.notified and job.score>=threshold and notify_enabled and settings.bot_token and chat_id:
                    body=f"NEW JOB · {job.score}% match\n{job.title}\n{job.company or 'Company not listed'} · {job.location or 'Location not listed'}\nSource: {job.source_title}"
                    if job.application_url: body+=f"\n{job.application_url}"
                    try:
                        async with httpx.AsyncClient(timeout=15) as hc:
                            response=await hc.post(f"https://api.telegram.org/bot{settings.bot_token}/sendMessage",json={"chat_id":chat_id,"text":body,"disable_web_page_preview":True})
                            response.raise_for_status()
                        job.notified=True
                        session.add(Notification(job_id=job.id,channel="telegram",status="sent",sent_at=datetime.now(timezone.utc)))
                    except Exception as error:
                        logger.warning("Telegram alert delivery failed for job %s (%s)",job.id,type(error).__name__)
                        session.add(Notification(job_id=job.id,channel="telegram",status="failed",error_message=type(error).__name__))
            src.last_message_id=max(src.last_message_id,message.id)
        session.commit()
        scanned+=len(batch)
        await asyncio.sleep(0)
        if len(batch)<limit: break
    return scanned


async def wait_for_monitor(seconds: int):
    if MONITOR_WAKE_EVENT is None:
        await asyncio.sleep(seconds)
        return
    try:
        await asyncio.wait_for(MONITOR_WAKE_EVENT.wait(),timeout=seconds)
    except asyncio.TimeoutError:
        pass
    MONITOR_WAKE_EVENT.clear()


def wake_monitor():
    if MONITOR_WAKE_EVENT is not None:
        MONITOR_WAKE_EVENT.set()


async def background_monitor():
    await asyncio.sleep(5)
    retry_delay=10
    while True:
        session=None
        try:
            MONITOR_STATUS["state"]="syncing"
            MONITOR_STATUS["last_sync_at"]=datetime.now(timezone.utc).isoformat()
            MONITOR_STATUS["last_error"]=None
            scanned=0
            session=SessionLocal()
            if not (settings.telegram_api_id and settings.telegram_api_hash):
                MONITOR_STATUS["state"]="telegram_not_configured"
                await wait_for_monitor(300)
                continue
            async with telegram_connection() as tg:
                if not await tg.is_user_authorized():
                    MONITOR_STATUS["authorized"]=False
                    MONITOR_STATUS["state"]="telegram_login_required"
                else:
                    MONITOR_STATUS["authorized"]=True
                    me=await tg.get_me()
                    MONITOR_STATUS["account"]=getattr(me,"username",None) or getattr(me,"phone",None)
                    sources=session.scalars(select(Source).where(Source.enabled==True)).all()
                    MONITOR_STATUS["enabled_sources"]=len(sources)
                    for src in sources:
                        try:
                            scanned+=await sync_source_history(tg,session,src)
                        except asyncio.CancelledError:
                            raise
                        except Exception as error:
                            session.rollback()
                            logger.exception("Telegram catch-up failed for source %s",src.chat_id)
                            MONITOR_STATUS["last_error"]=type(error).__name__
                    await maybe_daily_digest(session)
                    if MONITOR_STATUS["last_error"] is None:
                        MONITOR_STATUS["state"]="connected"
                        MONITOR_STATUS["last_success_at"]=datetime.now(timezone.utc).isoformat()
                        retry_delay=10
                    else:
                        MONITOR_STATUS["state"]="retrying"
                        retry_delay=min(300,retry_delay*2)
            MONITOR_STATUS["messages_scanned"]=scanned
            await wait_for_monitor(300 if MONITOR_STATUS["last_error"] is None else retry_delay)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.exception("Telegram monitor cycle failed")
            MONITOR_STATUS["state"]="retrying"
            MONITOR_STATUS["last_error"]=type(error).__name__
            await wait_for_monitor(retry_delay)
            retry_delay=min(300,retry_delay*2)
        finally:
            if session: session.close()

@app.get("/api/health")
def health(): return {"status":"ok","database":"sqlite" if settings.database_url.startswith("sqlite") else "configured","telegram_configured":bool(settings.telegram_api_id and settings.telegram_api_hash),"monitor":dict(MONITOR_STATUS),"ai_configured":bool(settings.ai_base_url and settings.ai_model),"bot_configured":bool(settings.bot_token and settings.bot_chat_id)}
@app.get("/api/auth/status")
def auth_status(s:Session=Depends(db)):
    return {"account_configured":bool(s.scalar(select(func.count()).select_from(User)) or 0)}
@app.post("/api/auth/register")
def register(data:dict,s:Session=Depends(db)):
    email=str(data.get("email","")).strip().lower(); password=str(data.get("password", ""))
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",email): raise HTTPException(422,"Enter a valid email address")
    if len(password)<12: raise HTTPException(422,"Choose a password with at least 12 characters")
    if s.scalar(select(func.count()).select_from(User)): raise HTTPException(409,"The local account is already configured; sign in instead")
    user=User(email=email,password_hash=hash_password(password)); s.add(user); s.commit(); s.refresh(user)
    return {"access_token":create_token(user.id),"token_type":"bearer","email":user.email}
@app.post("/api/auth/login")
def login(data:dict,s:Session=Depends(db)):
    email=str(data.get("email","")).strip().lower(); password=str(data.get("password", ""))
    user=s.scalar(select(User).where(User.email==email))
    if not user or not verify_password(password,user.password_hash): raise HTTPException(401,"Email or password is incorrect")
    return {"access_token":create_token(user.id),"token_type":"bearer","email":user.email}
@app.get("/api/auth/me")
def auth_me(request:Request,s:Session=Depends(db)):
    user=s.get(User,request.state.user_id)
    if not user: raise HTTPException(401,"Local account no longer exists")
    return {"id":user.id,"email":user.email}
@app.post("/api/auth/logout")
def logout(): return {"ok":True}
@app.get("/api/profile")
def get_profile(s:Session=Depends(db)):
    p=profile(s); return {"name":p.name,"skills":json.loads(p.skills),"roles":json.loads(p.roles),"locations":json.loads(p.locations),"graduation_year":p.graduation_year,"education":p.education,"college":p.college,"degree":p.degree,"cgpa":p.cgpa,"experience":json.loads(p.experience_json),"projects":json.loads(p.projects_json),"certifications":json.loads(p.certifications_json),"resume_ready":bool(p.resume_text),"resume_preview":p.resume_text[:1200]}
@app.put("/api/profile")
def update_profile(data:dict,s:Session=Depends(db)):
    p=profile(s)
    for key in ("name","graduation_year","education","college","degree","cgpa"):
        if key in data: setattr(p,key,data[key])
    for key in ("skills","roles","locations"):
        if key in data: setattr(p,key,json.dumps(data[key]))
    for key,field in (("experience","experience_json"),("projects","projects_json"),("certifications","certifications_json")):
        if key in data: setattr(p,field,json.dumps(data[key]))
    s.commit(); return {"ok":True}
@app.get("/api/preferences")
def get_preferences(s:Session=Depends(db)):
    p=profile(s); return {"roles":json.loads(p.roles),"locations":json.loads(p.locations),"graduation_year":p.graduation_year}
@app.put("/api/preferences")
def update_preferences(data:dict,s:Session=Depends(db)):
    p=profile(s)
    for key in ("roles","locations"):
        if key in data: setattr(p,key,json.dumps(data[key]))
    if "graduation_year" in data: p.graduation_year=data["graduation_year"]
    s.commit(); return {"ok":True}
@app.post("/api/resume")
async def upload_resume(file:UploadFile=File(...),s:Session=Depends(db)):
    name=(file.filename or "").lower()
    if not name.endswith((".pdf",".docx",".txt")): raise HTTPException(400,"Upload a PDF, DOCX, or TXT resume")
    content=await file.read()
    if len(content)>8*1024*1024: raise HTTPException(413,"Resume must be under 8 MB")
    try:
        if name.endswith(".pdf"):
            import fitz
            doc=fitz.open(stream=content,filetype="pdf"); text="\n".join(page.get_text() for page in doc)
        elif name.endswith(".docx"):
            from docx import Document
            import io
            text="\n".join(p.text for p in Document(io.BytesIO(content)).paragraphs)
        else: text=content.decode("utf-8")
    except Exception as e: raise HTTPException(400,f"Could not read resume: {str(e)}")
    p=profile(s); apply_resume_text(p,text[:80000])
    found=json.loads(p.skills)
    version=(s.scalar(select(func.max(Resume.profile_version))) or 0)+1
    s.query(Resume).update({Resume.is_active:False})
    filename=file.filename or "resume"
    stored_path=Path("storage/resumes")/(uuid4().hex+Path(name).suffix)
    stored_path.parent.mkdir(parents=True,exist_ok=True)
    stored_path.write_bytes(content)
    resume=Resume(filename=filename,file_path=str(stored_path),extracted_text=text[:80000],profile_version=version,is_active=True)
    s.add(resume); s.commit()
    return {"ok":True,"resume_id":resume.id,"profile_version":version,"characters":len(text),"skills":found}
@app.get("/api/resume")
def list_resumes(s:Session=Depends(db)):
    items=s.scalars(select(Resume).order_by(Resume.profile_version.desc())).all()
    return [{"id":r.id,"filename":r.filename,"profile_version":r.profile_version,"is_active":r.is_active,"uploaded_at":r.uploaded_at.isoformat()} for r in items]
@app.put("/api/resume/{resume_id}/activate")
def activate_resume(resume_id:int,s:Session=Depends(db)):
    selected=s.get(Resume,resume_id)
    if not selected: raise HTTPException(404,"Resume not found")
    s.query(Resume).update({Resume.is_active:False}); selected.is_active=True
    p=profile(s); apply_resume_text(p,selected.extracted_text)
    s.commit(); return {"ok":True,"active_resume_id":selected.id}
@app.delete("/api/resume/{resume_id}")
def delete_resume(resume_id:int,s:Session=Depends(db)):
    selected=s.get(Resume,resume_id)
    if not selected: raise HTTPException(404,"Resume not found")
    was_active=selected.is_active; stored_path=Path(selected.file_path) if selected.file_path else None
    s.delete(selected); s.flush()
    if stored_path:
        stored_path.unlink(missing_ok=True)
    if was_active:
        replacement=s.scalar(select(Resume).order_by(Resume.profile_version.desc()).limit(1))
        p=profile(s); apply_resume_text(p,replacement.extracted_text if replacement else "")
        if replacement: replacement.is_active=True
    s.commit(); return {"ok":True}
@app.get("/api/telegram/status")
async def telegram_status():
    if not settings.telegram_api_id: return {"configured":False,"connected":False}
    if MONITOR_STATUS.get("authorized") and MONITOR_STATUS.get("state") in {"syncing","connected","retrying"}:
        return {"configured":True,"connected":True,"account":MONITOR_STATUS.get("account"),"monitor":dict(MONITOR_STATUS)}
    try:
        async with telegram_connection() as c:
            connected=await c.is_user_authorized(); me=await c.get_me() if connected else None
            MONITOR_STATUS["authorized"]=connected
            MONITOR_STATUS["account"]=getattr(me,"username",None) or getattr(me,"phone",None)
            return {"configured":True,"connected":connected,"account":getattr(me,"username",None) or getattr(me,"phone",None),"monitor":dict(MONITOR_STATUS)}
    except Exception as e: return {"configured":True,"connected":False,"error":type(e).__name__,"monitor":dict(MONITOR_STATUS)}
@app.post("/api/telegram/wake")
def wake_telegram_monitor():
    wake_monitor()
    return {"ok":True,"message":"Telegram catch-up requested."}
@app.post("/api/telegram/disconnect")
async def telegram_disconnect():
    async with telegram_connection() as c:
        if await c.is_user_authorized(): await c.log_out()
    MONITOR_STATUS["authorized"]=False
    MONITOR_STATUS["state"]="telegram_login_required"
    wake_monitor()
    return {"ok":True,"connected":False}
@app.post("/api/telegram/start")
async def telegram_start(data:dict):
    phone=data.get("phone")
    if not phone: raise HTTPException(400,"Phone number required")
    try:
        async with telegram_connection() as c:
            if await c.is_user_authorized():
                me=await c.get_me()
                MONITOR_STATUS["authorized"]=True
                MONITOR_STATUS["account"]=getattr(me,"username",None) or getattr(me,"phone",None)
                wake_monitor()
                return {"ok":True,"already_connected":True,"account":getattr(me,"username",None) or getattr(me,"phone",None)}
            try:
                sent=await c.send_code_request(phone)
            except (AuthRestartError, ConnectionError):
                # Telegram occasionally drops the authorization transport while
                # rotating its auth key. Reconnect once before surfacing an error.
                await c.disconnect()
                await asyncio.sleep(0.35)
                await c.connect()
                sent=await c.send_code_request(phone)
        return {"ok":True,"phone_code_hash":sent.phone_code_hash,"message":"Telegram sent a login code. Submit it to /api/telegram/verify."}
    except AuthRestartError:
        raise HTTPException(409,"Telegram asked to restart sign-in. Wait briefly, then request one new code.")
    except FloodWaitError as e:
        raise HTTPException(429,f"Telegram rate limit: wait {e.seconds} seconds before requesting another code.")
    except Exception as e:
        raise HTTPException(502,f"Telegram could not send a login code: {e}")
@app.post("/api/telegram/verify")
async def telegram_verify(data:dict):
    try:
        async with telegram_connection() as c:
            await c.sign_in(phone=data["phone"],code=data["code"],phone_code_hash=data["phone_code_hash"])
            me=await c.get_me()
        MONITOR_STATUS["authorized"]=True
        MONITOR_STATUS["account"]=getattr(me,"username",None) or getattr(me,"phone",None)
        wake_monitor()
        return {"ok":True,"connected":True}
    except SessionPasswordNeededError: raise HTTPException(428,"Two-step verification required. Submit your password to /api/telegram/password.")
    except HTTPException: raise
    except Exception as e: raise HTTPException(400,str(e))
@app.post("/api/telegram/password")
async def telegram_password(data:dict):
    try:
        async with telegram_connection() as c:
            await c.sign_in(password=data["password"])
            me=await c.get_me()
        MONITOR_STATUS["authorized"]=True
        MONITOR_STATUS["account"]=getattr(me,"username",None) or getattr(me,"phone",None)
        wake_monitor()
        return {"ok":True,"connected":True}
    except Exception as e: raise HTTPException(400,str(e))
@app.get("/api/telegram/sources")
async def telegram_sources(s:Session=Depends(db)):
    async with telegram_connection() as c:
        if not await c.is_user_authorized(): raise HTTPException(401,"Connect Telegram first")
        dialogs=await c.get_dialogs(limit=500)
        saved={x.chat_id:x for x in s.scalars(select(Source)).all()}
        out=[]
        for d in dialogs:
            if not (d.is_group or d.is_channel): continue
            cid=str(d.id); src=saved.get(cid)
            if not src: src=Source(chat_id=cid,title=d.name or cid); s.add(src); s.flush()
            out.append({"chat_id":cid,"title":d.name,"enabled":src.enabled,"type":"channel" if d.is_channel else "group"})
        s.commit(); return out
@app.put("/api/telegram/sources/{chat_id}")
def toggle_source(chat_id:str,data:dict,s:Session=Depends(db)):
    src=s.scalar(select(Source).where(Source.chat_id==chat_id))
    if not src: raise HTTPException(404,"Refresh source list first")
    src.enabled=bool(data.get("enabled")); s.commit(); wake_monitor(); return {"ok":True}
async def process_text(s, text, chat_id, message_id, posted, source_title):
    if not is_job(text): return False
    if s.scalar(select(Message).where(Message.chat_id==chat_id,Message.message_id==message_id)): return False
    existing=s.scalar(select(Job).where(Job.source_chat_id==chat_id,Job.source_message_id==message_id))
    if existing: return False
    obj=await extract(text)
    duplicate=None
    if obj.get("application_url"):
        normalized_url=obj["application_url"].strip().rstrip("/").lower()
        url_candidate=s.scalar(select(Job).where(func.lower(func.rtrim(Job.application_url,"/"))==normalized_url))
        if url_candidate and likely_duplicate(obj,{"title":url_candidate.title,"company":url_candidate.company,"location":url_candidate.location,"application_url":url_candidate.application_url,"description":url_candidate.description}):
            duplicate=url_candidate
    if duplicate is None and obj.get("company"):
        candidates=s.scalars(select(Job).where(func.lower(Job.title)==(obj.get("title") or "Job opportunity").lower(),func.lower(Job.company)==obj["company"].lower())).all()
        duplicate=next((candidate for candidate in candidates if likely_duplicate(obj,{"title":candidate.title,"company":candidate.company,"location":candidate.location,"application_url":candidate.application_url,"description":candidate.description})),None)
    if duplicate:
        if source_title not in duplicate.source_title: duplicate.source_title += " · "+source_title
        if not s.scalar(select(JobSource).where(JobSource.chat_id==chat_id,JobSource.message_id==message_id)):
            s.add(JobSource(job_id=duplicate.id,chat_id=chat_id,message_id=message_id,source_title=source_title,original_message=text,posted_at=posted))
        s.add(Message(chat_id=chat_id,message_id=message_id,text=text,posted_at=posted,processed=True)); s.commit(); return True
    p=profile(s); score,matched,missing=score_job(obj,p)
    eligibility,_=check_eligibility(obj,p)
    reasons=suspicious_reasons(text)
    j=Job(title=(obj.get("title") or "Job opportunity")[:300],company=obj.get("company"),description=obj.get("summary") or text,location=obj.get("location"),employment_type=obj.get("employment_type"),experience_required=obj.get("experience_required"),education_required=obj.get("education_required"),graduation_year=obj.get("graduation_year"),work_mode=obj.get("work_mode"),salary=obj.get("salary"),application_deadline=obj.get("application_deadline"),application_url=obj.get("application_url"),contact_email=obj.get("contact_email"),contact_information=obj.get("contact_information"),source_title=source_title,source_chat_id=chat_id,source_message_id=message_id,posted_at=posted,score=score,matched_skills=json.dumps(matched),missing_skills=json.dumps(missing),required_skills=json.dumps(obj.get("skills",[])),extraction_confidence=obj.get("confidence"),eligibility=eligibility,review_reasons=json.dumps(reasons))
    s.add(j); s.flush()
    s.add(JobSource(job_id=j.id,chat_id=chat_id,message_id=message_id,source_title=source_title,original_message=text,posted_at=posted))
    s.add(Message(chat_id=chat_id,message_id=message_id,text=text,posted_at=posted,processed=True)); s.commit(); return True
@app.post("/api/telegram/sync")
async def sync(s:Session=Depends(db),limit:int=Query(100,ge=1,le=500)):
    added=0
    async with telegram_connection() as c:
        if not await c.is_user_authorized(): raise HTTPException(401,"Connect Telegram first")
        for src in s.scalars(select(Source).where(Source.enabled==True)).all():
            start=s.scalar(select(func.count()).select_from(Job).where(Job.source_chat_id==src.chat_id)) or 0
            await sync_source_history(c,s,src,max_messages=limit)
            end=s.scalar(select(func.count()).select_from(Job).where(Job.source_chat_id==src.chat_id)) or 0
            added+=max(0,end-start)
    wake_monitor()
    return {"ok":True,"new_jobs":added,"message":"Sync completed. New postings will continue to appear automatically."}
@app.get("/api/jobs")
def list_jobs(search:str="",category:str="",sort:str="newest",s:Session=Depends(db)):
    q=select(Job)
    if search: q=q.where((Job.title.ilike(f"%{search}%"))|(Job.company.ilike(f"%{search}%"))|(Job.description.ilike(f"%{search}%")))
    if category=="excellent": q=q.where(Job.score>=85)
    elif category=="strong": q=q.where(Job.score.between(70,84))
    elif category=="moderate": q=q.where(Job.score.between(55,69))
    elif category=="internship": q=q.where(Job.employment_type.ilike("%intern%"))
    q=q.order_by(Job.score.desc() if sort=="match" else Job.posted_at.desc())
    return [job_out(j) for j in s.scalars(q.limit(500)).all()]
@app.get("/api/jobs/recommended")
def recommended_jobs(s:Session=Depends(db)):
    return [job_out(j) for j in s.scalars(select(Job).where(Job.score>=55).order_by(Job.score.desc(),Job.posted_at.desc()).limit(100)).all()]
@app.get("/api/jobs/recent")
def recent_jobs(s:Session=Depends(db)):
    return [job_out(j) for j in s.scalars(select(Job).order_by(Job.posted_at.desc()).limit(100)).all()]
@app.get("/api/jobs/categories")
def job_categories(s:Session=Depends(db)):
    jobs=s.scalars(select(Job)).all()
    return {"excellent":sum(j.score>=85 for j in jobs),"strong":sum(70<=j.score<85 for j in jobs),"moderate":sum(55<=j.score<70 for j in jobs),"low":sum(40<=j.score<55 for j in jobs),"poor":sum(j.score<40 for j in jobs),"internship":sum("intern" in (j.employment_type or "").lower() for j in jobs),"full_time":sum("full" in (j.employment_type or "").lower() for j in jobs)}
@app.get("/api/jobs/export")
def export_jobs(s:Session=Depends(db)):
    output=io.StringIO(newline="")
    writer=csv.writer(output)
    writer.writerow(["Title","Company","Location","Employment Type","Match Score","Eligibility","Application Status","Application URL","Source","Posted At","Description"])
    for j in s.scalars(select(Job).order_by(Job.posted_at.desc())).all():
        row=[j.title,j.company,j.location,j.employment_type,j.score,j.eligibility,j.application_status,j.application_url,j.source_title,j.posted_at.isoformat(),j.description]
        writer.writerow([("'"+str(value)) if isinstance(value,str) and value.startswith(("=","+","-","@")) else value for value in row])
    return Response(content=output.getvalue(),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=job-opportunities.csv"})
@app.get("/api/jobs/{job_id}")
def job_detail(job_id:int,s:Session=Depends(db)):
    j=s.get(Job,job_id)
    if not j: raise HTTPException(404,"Job not found")
    result=job_out(j)
    result["sources"]=[{"chat_id":source.chat_id,"message_id":source.message_id,"title":source.source_title,"original_message":source.original_message,"posted_at":source.posted_at.isoformat()} for source in s.scalars(select(JobSource).where(JobSource.job_id==job_id)).all()]
    p=profile(s); _,result["eligibility_reasons"]=check_eligibility({"application_deadline":j.application_deadline,"graduation_year":j.graduation_year,"education_required":j.education_required,"experience_required":j.experience_required},p)
    application=s.scalar(select(Application).where(Application.job_id==job_id))
    result["application_notes"]=application.notes if application else ""
    return result
@app.get("/api/applications")
def list_applications(s:Session=Depends(db)):
    rows=s.execute(select(Job,Application).outerjoin(Application,Application.job_id==Job.id).where(Job.application_status!="New").order_by(Job.created_at.desc())).all()
    return [{**job_out(job),"notes":application.notes if application else ""} for job,application in rows]
@app.get("/api/matches")
def list_matches(s:Session=Depends(db)):
    return [job_out(j) for j in s.scalars(select(Job).order_by(Job.score.desc()).limit(500)).all()]
@app.get("/api/matches/{job_id}")
def match_detail(job_id:int,s:Session=Depends(db)):
    return job_detail(job_id,s)
@app.get("/api/matches")
def list_matches(s:Session=Depends(db)):
    return [job_out(j) for j in s.scalars(select(Job).order_by(Job.score.desc()).limit(500)).all()]
@app.get("/api/matches/{job_id}")
def match_detail(job_id:int,s:Session=Depends(db)):
    return job_detail(job_id,s)
@app.put("/api/jobs/{job_id}/application")
def app_status(job_id:int,data:dict,s:Session=Depends(db)):
    j=s.get(Job,job_id)
    if not j: raise HTTPException(404,"Job not found")
    allowed={"New","Saved","Interested","Applied","Assessment","Interview","Offer","Rejected","Withdrawn"}; status=data.get("status")
    if status not in allowed: raise HTTPException(400,"Invalid application status")
    j.application_status=status
    application=s.scalar(select(Application).where(Application.job_id==job_id))
    if status=="New":
        if application: s.delete(application)
    else:
        if application is None: application=Application(job_id=job_id,status=status,notes=data.get("notes", "")); s.add(application)
        else:
            application.status=status
            if "notes" in data: application.notes=data["notes"]
    s.commit(); return {"ok":True}
@app.get("/api/dashboard")
def dashboard(s:Session=Depends(db)):
    jobs=s.scalars(select(Job)).all(); today=datetime.now(timezone.utc).date()
    return {"total":len(jobs),"new_today":sum(j.created_at.date()==today for j in jobs),"excellent":sum(j.score>=85 for j in jobs),"strong":sum(70<=j.score<85 for j in jobs),"applied":sum(j.application_status in ("Applied","Assessment","Interview","Offer") for j in jobs),"telegram_sources":s.scalar(select(func.count()).select_from(Source)) or 0}
@app.get("/api/dashboard/overview")
def dashboard_overview(s:Session=Depends(db)): return dashboard(s)
@app.get("/api/dashboard/statistics")
def dashboard_statistics(s:Session=Depends(db)): return dashboard(s)
@app.get("/api/notifications")
def list_notifications(s:Session=Depends(db)):
    rows=s.scalars(select(Notification).order_by(Notification.id.desc()).limit(100)).all()
    return [{"id":n.id,"job_id":n.job_id,"channel":n.channel,"status":n.status,"sent_at":n.sent_at.isoformat() if n.sent_at else None,"error_message":n.error_message} for n in rows]
@app.get("/api/notifications/settings")
def get_notification_settings(s:Session=Depends(db)):
    pref=s.get(NotificationPreference,1)
    if not pref: pref=NotificationPreference(id=1,immediate_threshold=settings.match_threshold); s.add(pref); s.commit(); s.refresh(pref)
    return {"enabled":pref.enabled,"immediate_threshold":pref.immediate_threshold,"daily_digest":pref.daily_digest,"bot_configured":bool(settings.bot_token and (settings.bot_chat_id or pref.chat_id))}
@app.put("/api/notifications/settings")
def update_notification_settings(data:dict,s:Session=Depends(db)):
    pref=s.get(NotificationPreference,1)
    if not pref: pref=NotificationPreference(id=1,immediate_threshold=settings.match_threshold); s.add(pref)
    if "enabled" in data: pref.enabled=bool(data["enabled"])
    if "daily_digest" in data: pref.daily_digest=bool(data["daily_digest"])
    if "immediate_threshold" in data:
        threshold=int(data["immediate_threshold"])
        if not 0<=threshold<=100: raise HTTPException(422,"Threshold must be between 0 and 100")
        pref.immediate_threshold=threshold
    s.commit(); return {"ok":True,"enabled":pref.enabled,"immediate_threshold":pref.immediate_threshold,"daily_digest":pref.daily_digest}
@app.post("/api/notifications/test")
async def test_notification(s:Session=Depends(db)):
    pref=s.get(NotificationPreference,1); chat_id=settings.bot_chat_id or (pref.chat_id if pref else None)
    if not settings.bot_token or not chat_id: raise HTTPException(503,"Configure BOT_TOKEN and send /start to your private bot first")
    async with httpx.AsyncClient(timeout=15) as hc:
        response=await hc.post(f"https://api.telegram.org/bot{settings.bot_token}/sendMessage",json={"chat_id":chat_id,"text":"Job Intelligence test notification. Your private alert connection works."})
        if response.is_error: raise HTTPException(502,"Telegram could not deliver the test notification")
    return {"ok":True}
@app.post("/api/matches/recalculate")
def recalculate(s:Session=Depends(db)):
    p=profile(s); jobs=s.scalars(select(Job)).all()
    for j in jobs:
        score,matched,missing=score_job({"title":j.title,"summary":j.description,"skills":json.loads(j.required_skills)},p); j.score=score; j.matched_skills=json.dumps(matched); j.missing_skills=json.dumps(missing)
    s.commit(); return {"updated":len(jobs)}
