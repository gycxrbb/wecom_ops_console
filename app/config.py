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
    # ── CRM 数据库（按环境隔离） ─────────────────────────────────────────
    # crm_env: '' 表示跟随 app_env（production → prod，其他 → test）；显式 'test'/'production' 可覆盖
    # 这样可以在开发机用 production CRM 库做一次性排查，或在生产机临时切回测试库
    crm_env: str = ''
    # 测试 CRM 库（本地开发 + 旧服务器 gezelling.com 默认走这里）
    crm_test_db_host: str = ''
    crm_test_db_port: int = 3306
    crm_test_db_user: str = ''
    crm_test_db_password: str = ''
    crm_test_db_name: str = 'mfgcrmdb'
    crm_test_db_ssl_path: str = ''
    # 生产 CRM 库（新服务器走这里）
    crm_prod_db_host: str = ''
    crm_prod_db_port: int = 3306
    crm_prod_db_user: str = ''
    crm_prod_db_password: str = ''
    crm_prod_db_name: str = 'habitilitydb'
    crm_prod_db_ssl_path: str = ''
    # 旧字段：单套 CRM 配置。保留是为了向后兼容，crm_test/prod 都为空时会回退到这里
    crm_admin_db_host: str = ''
    crm_admin_db_port: int = 3306
    crm_admin_db_user: str = ''
    crm_admin_db_password: str = ''
    crm_admin_db_name: str = 'mfgcrmdb'
    crm_admin_db_ssl_path: str = ''
    crm_admin_table_name: str = 'admins'
    crm_jwt_secret_key: str = ''                                # CRM 后端 APP_PUBLIC_KEY，用于验证 CRM 签发的 JWT
    crm_token_strict_redis_check: bool = False                  # 生产环境建议开启 Redis token 比对
    database_url: str = 'sqlite:///./data/app.db'
    # 业务库 SSL CA 证书路径（相对项目根或绝对路径；目录则自动取 rds-ca.pem 或首个 *.pem）。
    # 本地/旧机走 127.0.0.1 直连可留空；新机连阿里云 RDS habitilitydb 必须配。
    database_ssl_path: str = ''
    redis_url: str = 'redis://127.0.0.1:6379/0'
    # Redis 业务 key 前缀（用于隔离多个应用复用同一 Redis 实例的场景）。
    # 留空 = 不加前缀，本地/旧机维持现状；新机连阿里云 Redis 时建议设 'wecom'。
    # 注意：Celery broker/backend 不受此前缀影响，它有自己的命名空间。
    redis_key_prefix: str = ''
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
    ai_available_models: str = 'deepseek-v4-pro,gpt-5.5,gpt-5.4,gpt-4o-mini,deepseek-v4-flash,deepseek-v3.2-fast,claude-opus-4-7,kimi-k2.6,glm-5.1,gemini-3.1-pro-preview,xiaomi-mimo-v2.5,doubao-seed-2-0-pro'
    ai_http2_enabled: bool = True
    deepseek_api_key: str = ''
    deepseek_base_url: str = 'https://api.deepseek.com'
    deepseek_model: str = 'deepseek-v4-pro'
    ai_thinking_provider: str = 'aihubmix'           # fast provider for thinking stream
    ai_thinking_model: str = ''                      # empty=follow ai_model (gpt-4o-mini)
    crm_profile_cache_fresh_ttl_seconds: int = 1800
    crm_profile_cache_stale_ttl_seconds: int = 7200
    crm_profile_cache_preload_wait_ms: int = 15000
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
    # Vision analysis (GPT-4o-mini on aihubmix)
    vision_model: str = 'gemini-2.0-flash'
    vision_fallback_model: str = 'gpt-4o'
    vision_fallback_model_2: str = 'claude-sonnet-4-6'
    vision_max_image_size_mb: int = 10
    vision_max_pdf_size_mb: int = 20
    vision_max_pdf_pages: int = 10

    # AI Visual Agent
    ai_visual_enabled: bool = False
    ai_visual_provider: str = "aihubmix"
    ai_visual_model: str = "doubao/doubao-seedream-4-5-251128"
    ai_visual_generation_strategy: str = "direct_image"
    ai_visual_auto_generate_confidence: float = 0.80
    ai_visual_manual_confirm_confidence: float = 0.45
    ai_visual_max_jobs_per_session: int = 2
    # aihubmix 官方说明 gpt-image-2 单次生成可能 >5 分钟，建议客户端超时 ≥10 分钟
    ai_visual_generation_timeout_seconds: int = 1500
    ai_visual_generation_max_retries: int = 2
    ai_visual_generation_retry_delay_seconds: float = 1.5
    # 仅当真正长 hang（接近读超时）后断开才判 api_timeout 不再重试，避免短暂抖动直接放弃
    ai_visual_generation_gateway_timeout_hint_seconds: int = 540
    # 生图链路是否启用 HTTP/2。默认关闭：httpx HTTP/2 长 hang 历史不稳，OpenAI SDK 也走 HTTP/1.1
    ai_visual_http2_enabled: bool = False
    ai_visual_seedream_size: str = "2K"
    ai_visual_seedream_watermark: bool = True
    ai_visual_auto_sendable: bool = False
    ai_visual_llm_judge_enabled: bool = False
    ai_visual_llm_judge_model: str = "gpt-4.1-mini"
    ai_visual_llm_judge_timeout_seconds: int = 8

    # RAG
    rag_enabled: bool = False
    qdrant_mode: str = "local"  # "local" = 本地文件, "remote" = 远程服务器
    qdrant_host: str = "127.0.0.1"
    qdrant_port: int = 6333
    qdrant_local_path: str = "data/qdrant"
    qdrant_collection: str = "wecom_health_rag"
    rag_embedding_base_url: str = "https://aihubmix.com/v1"
    rag_embedding_api_key: str = ""
    rag_embedding_model: str = "text-embedding-3-large"
    rag_embedding_dimension: int = 1024
    rag_rerank_enabled: bool = False
    rag_rerank_model: str = "jina-reranker-v3"
    rag_top_k: int = 30
    rag_rerank_top_n: int = 6
    rag_chunk_size: int = 600
    rag_chunk_overlap: int = 80
    rag_min_score: float = 0.42
    rag_relative_score_ratio: float = 0.65
    rag_max_visible_sources: int = 5
    rag_max_source_chars: int = 800
    rag_points_operation_scenes: str = "top_leader,top_six,top_ten,surge,daily_remind,group_pk,lurker_remind"

settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
