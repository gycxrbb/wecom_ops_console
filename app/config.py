from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
UPLOAD_DIR = DATA_DIR / 'uploads'
TEMPLATE_DIR = BASE_DIR / 'app' / 'templates'
STATIC_DIR = BASE_DIR / 'app' / 'static'

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / '.env'), env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'WeCom Ops Console'
    app_env: str = 'development'
    app_secret_key: str = 'change-me'
    jwt_secret_key: str = 'your-256-bit-secret-key-change-me'
    jwt_algorithm: str = 'HS256'
    jwt_access_token_expire_minutes: int = 1440
    admin_username: str = 'admin'
    admin_password: str = 'Admin123456'
    coach_username: str = 'coach'
    coach_password: str = 'Coach123456'
    database_url: str = 'sqlite:///./data/app.db'
    redis_url: str = 'redis://127.0.0.1:6379/0'
    default_timezone: str = 'Asia/Shanghai'
    host: str = '0.0.0.0'
    port: int = 8000

settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
