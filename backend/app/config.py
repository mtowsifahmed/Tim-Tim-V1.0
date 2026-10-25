from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
# Provider API keys are read with os.getenv(), which only sees the real environment, so .env must be loaded into it.
load_dotenv(ENV_FILE, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), extra="ignore")

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_db_url: str = ""
    supabase_jwt_secret: str = ""          # only needed for legacy projects that still sign tokens with HS256
    key_encryption_secret: str = ""
    free_daily_cap: int = 30
    pro_rotation_daily_cap: int = 100


settings = Settings()
