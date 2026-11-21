import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

_SECRET_PATH=Path("backend/data/jwt.secret")
def secret_key()->bytes:
    _SECRET_PATH.parent.mkdir(parents=True,exist_ok=True)
    if not _SECRET_PATH.exists():
        _SECRET_PATH.write_bytes(secrets.token_bytes(32))
        try: os.chmod(_SECRET_PATH,0o600)
        except OSError: pass
    return _SECRET_PATH.read_bytes()

def hash_password(password:str)->str:
    salt=secrets.token_bytes(16)
    derived=hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1,dklen=32)
    return "scrypt$"+salt.hex()+"$"+derived.hex()

def verify_password(password:str,stored:str)->bool:
    try:
        algorithm,salt_hex,digest_hex=stored.split("$",2)
        if algorithm!="scrypt": return False
        expected=bytes.fromhex(digest_hex)
        actual=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt_hex),n=2**14,r=8,p=1,dklen=len(expected))
        return hmac.compare_digest(actual,expected)
    except (ValueError,TypeError): return False

def _b64(value:bytes)->str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

def create_token(user_id:int)->str:
    header=_b64(b'{"alg":"HS256","typ":"JWT"}')
    payload=_b64(json.dumps({"sub":str(user_id),"exp":int(time.time())+43200}).encode())
    signing=f"{header}.{payload}".encode()
    signature=_b64(hmac.new(secret_key(),signing,hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"

def read_token(token:str)->int|None:
    try:
        header,payload,signature=token.split(".",2)
        signing=f"{header}.{payload}".encode()
        expected=_b64(hmac.new(secret_key(),signing,hashlib.sha256).digest())
        if not hmac.compare_digest(signature,expected): return None
        data=json.loads(base64.urlsafe_b64decode(payload+"="*((4-len(payload)%4)%4)))
        if int(data["exp"])<int(time.time()): return None
        return int(data["sub"])
    except (ValueError,KeyError,TypeError,json.JSONDecodeError): return None
