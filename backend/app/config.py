from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    telegram_session: str = "./storage/telegram"
    database_url: str = "sqlite:///./backend/data/job_intelligence.db"
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    bot_token: str = ""
    bot_chat_id: str = ""
    match_threshold: int = 65
    cors_origins: str = ""

settings = Settings()
