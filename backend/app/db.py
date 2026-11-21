from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

if settings.database_url.startswith("sqlite"):
    Path("backend/data").mkdir(parents=True, exist_ok=True)
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
class Base(DeclarativeBase): pass

def upgrade_database():
    from alembic import command
    from alembic.config import Config
    command.upgrade(Config("alembic.ini"),"head")
