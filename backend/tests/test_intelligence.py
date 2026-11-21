import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.models import Profile
from backend.app.db import Base
from backend.app.security import create_token, hash_password, read_token, verify_password
from backend.app.services.intelligence import check_eligibility, extract, likely_duplicate, score_job, suspicious_reasons
from backend.app.services.resume_parser import parse_resume
from backend.app.config import settings
from backend.app import main


def test_matching_accepts_sqlalchemy_profile_object():
    profile=Profile(
        resume_text="Built Python APIs and SQL data tools",
        skills='["python", "sql"]',
        roles='["Backend Developer"]',
        locations='["Chennai"]',
    )
    score,matched,missing=score_job({
        "title":"Backend Developer", "summary":"Python APIs and SQL", "skills":["python","sql","java"],
        "location":"Chennai",
    },profile)
    assert 0<=score<=100
    assert matched==["python","sql"]
    assert missing==["java"]


def test_eligibility_checks_deadline_and_graduation_separately():
    profile=Profile(graduation_year=2025)
    status,reasons=check_eligibility({"graduation_year":"2024, 2025"},profile)
    assert status=="Possibly Eligible"
    assert any("Graduation year matches" in reason for reason in reasons)
    status,reasons=check_eligibility({"graduation_year":"2022"},profile)
    assert status=="Not Eligible"
    status,reasons=check_eligibility({"application_deadline":"2020-01-01"},profile)
    assert status=="Not Eligible"


def test_duplicate_detection_uses_url_and_content_safely():
    first={"title":"Java Developer","company":"Northwind","location":"Chennai","application_url":"https://jobs.example/app","summary":"Java Spring SQL backend role"}
    same={**first,"summary":"Java Spring SQL backend role"}
    different={**first,"title":"Data Analyst"}
    assert likely_duplicate(first,same)
    assert not likely_duplicate(first,different)
    assert not likely_duplicate({"title":"Developer"},{"title":"Developer"})


def test_resume_parser_extracts_structured_sections():
    parsed=parse_resume("""Ananya Rao
ananya@example.com
B.Tech Computer Science
Graduation Batch: 2025
CGPA: 8.4
Education
B.Tech, Example University
Experience
Backend Intern at Example Co
Projects
Job matching platform with Python
Certifications
AWS Cloud Practitioner
""")
    assert parsed["name"]=="Ananya Rao"
    assert parsed["degree"]
    assert parsed["graduation_year"]==2025
    assert parsed["cgpa"]=="8.4"
    assert "Backend Intern" in parsed["experience_json"]


def test_rule_extraction_falls_back_without_model(monkeypatch):
    monkeypatch.setattr(settings,"ai_base_url","")
    monkeypatch.setattr(settings,"ai_api_key","")
    monkeypatch.setattr(settings,"ai_model","")
    result=asyncio.run(extract("Hiring: Python Backend Developer\nLocation: Chennai\nRequired Python, SQL skills. Apply: https://jobs.example/app"))
    assert result["title"]=="Hiring: Python Backend Developer"
    assert result["location"]=="Chennai"
    assert result["application_url"]=="https://jobs.example/app"
    assert "python" in result["skills"]


def test_suspicious_post_flags_payment_credentials_and_short_links():
    reasons=suspicious_reasons("Hiring now! Pay registration fee to secure guaranteed placement. Send your OTP. Apply https://bit.ly/example")
    assert len(reasons)==4


def test_suspicious_post_does_not_flag_clear_no_fee_statement():
    assert suspicious_reasons("No fee is required to apply. Python developer role.")==[]


def test_ingestion_persists_suspicious_review_reasons(monkeypatch):
    engine=create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    async def fake_extract(_text):
        return {"title":"Python Developer","company":"Example","summary":"Python developer role","skills":["python"],"confidence":0.9}
    monkeypatch.setattr(main,"extract",fake_extract)
    source="Hiring Python Developer. Pay registration fee to apply for this position today."
    with Session(engine) as session:
        assert asyncio.run(main.process_text(session,source,"test-chat",1,datetime.now(timezone.utc),"Test source"))
        job=session.query(main.Job).one()
        assert json.loads(job.review_reasons)==["The post appears to request upfront payment."]


def test_single_user_profile_survives_database_reopen(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path / 'profile.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        main.update_profile({"name":"Manikandan","roles":["Backend Developer"],"locations":["Chennai"]},session)
    with Session(engine) as session:
        result=main.get_profile(session)
        assert result["name"]=="Manikandan"
        assert result["roles"]==["Backend Developer"]
        assert result["locations"]==["Chennai"]


def test_telegram_catchup_drains_multiple_batches_from_checkpoint(monkeypatch):
    engine=create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    async def skip_analysis(*_args):
        return False
    monkeypatch.setattr(main,"process_text",skip_analysis)
    messages=[type("TelegramMessage",(),{"id":i,"message":f"post {i}","date":datetime.now(timezone.utc)})() for i in range(1,238)]
    class FakeTelegram:
        async def get_entity(self,_chat_id):
            return object()
        async def iter_messages(self,_entity,*,limit,min_id,reverse):
            for message in [item for item in messages if item.id>min_id][:limit]:
                yield message
    with Session(engine) as session:
        source=main.Source(chat_id="123",title="jobs",last_message_id=0)
        session.add(source); session.commit()
        scanned=asyncio.run(main.sync_source_history(FakeTelegram(),session,source,batch_size=100))
        assert scanned==237
        assert source.last_message_id==237
        assert asyncio.run(main.sync_source_history(FakeTelegram(),session,source,batch_size=100))==0


def test_job_search_matches_skills_and_filters_latest_posts_first():
    engine=create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now=datetime.now(timezone.utc)
    with Session(engine) as session:
        session.add_all([
            main.Job(title="Python Engineer",company="Recent Labs",description="Backend role",required_skills='["python"]',posted_at=now-timedelta(hours=2)),
            main.Job(title="Engineer",company="This Week",description="Cloud role",required_skills='["python", "cloud"]',posted_at=now-timedelta(days=3)),
            main.Job(title="Engineer",company="Older Co",description="Old opening",required_skills='["python"]',posted_at=now-timedelta(days=40)),
        ])
        session.commit()
        newest=main.list_jobs(search="python",sort="newest",period="",s=session)
        assert [job["company"] for job in newest]==["Recent Labs","This Week","Older Co"]
        assert [job["company"] for job in main.list_jobs(search="cloud",sort="newest",period="5d",s=session)]==["This Week"]
        assert [job["company"] for job in main.list_jobs(search="python",sort="newest",period="1d",s=session)]==["Recent Labs"]
        assert [job["company"] for job in main.list_jobs(search="python",sort="newest",period="older",s=session)]==["Older Co"]


def test_password_hash_and_signed_token_round_trip():
    encoded=hash_password("local-safe-passphrase-2026")
    assert verify_password("local-safe-passphrase-2026",encoded)
    assert not verify_password("wrong passphrase",encoded)
    token=create_token(17)
    assert read_token(token)==17
    assert read_token(token+"x") is None
