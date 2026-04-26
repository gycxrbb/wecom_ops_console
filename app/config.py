from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
UPLOAD_DIR = DATA_DIR / 'uploads'
TEMPLATE_DIR = BASE_DIR / 'app' / 'templates'
STATIC_DIR = BASE_DIR / 'app' / 'static'
FRONTEND_DIR = BASE_DIR / 'frontend' / 'dist'

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / '.env'), env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'WeCom Ops Console'
    app_env: str = 'development'
    app_secret_key: str = 'change-me'
    jwt_secret_key: str = 'your-256-bit-secret-key-change-me'
    jwt_algorithm: str = 'HS256'
    jwt_access_token_expire_minutes: int = 1440 # 24小时
    admin_username: str = 'admin'
    admin_password: str = 'Admin123456'
    coach_username: str = 'coach'
    coach_password: str = 'Coach123456'
    crm_admin_auth_enabled: bool = False
    crm_admin_db_host: str = ''
    crm_admin_db_port: int = 3306
    crm_admin_db_user: str = ''
    crm_admin_db_password: str = ''
    crm_admin_db_name: str = 'mfgcrmdb'
    crm_admin_table_name: str = 'admins'
    database_url: str = 'sqlite:///./data/app.db'
    redis_url: str = 'redis://127.0.0.1:6379/0'
    asset_storage_provider: str = 'local'
    asset_storage_fallback_provider: str = 'local'
    qiniu_enabled: bool = False
    qiniu_access_key: str = ''
    qiniu_secret_key: str = ''
    qiniu_bucket: str = ''
    qiniu_region: str = 'z2'
    qiniu_public_domain: str = ''
    qiniu_use_https: bool = True
    qiniu_prefix: str = 'materials/'
    qiniu_private_bucket: bool = False
    qiniu_signed_url_expire_seconds: int = 3600
    default_timezone: str = 'Asia/Shanghai'
    ai_api_key: str = ''
    ai_base_url: str = 'https://aihubmix.com/v1'
    ai_model: str = 'gpt-4o-mini'
    ai_provider: str = 'aihubmix'                  # 'aihubmix' | 'deepseek'
    ai_http2_enabled: bool = True
    deepseek_api_key: str = ''
    deepseek_base_url: str = 'https://api.deepseek.com'
    deepseek_model: str = 'deepseek-v4-pro'
    send_timeout_seconds: int = 30
    file_upload_timeout_seconds: int = 120
    send_max_retries: int = 3
    send_retry_delay_seconds: float = 1.0
    file_send_max_retries: int = 3
    file_send_retry_delay_seconds: float = 3.0
    ffmpeg_binary: str = 'ffmpeg'
    host: str = '0.0.0.0'
    port: int = 8000
    cors_allowed_origins: str = ''  # 逗号分隔，留空则只允许同源
    crm_profile_enabled: bool = False
    ai_coach_enabled: bool = False

settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
