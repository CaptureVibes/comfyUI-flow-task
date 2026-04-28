from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./task_manager.db"
    admin_username: str = "admin"
    admin_password: str  # 必须通过环境变量 ADMIN_PASSWORD 设置，无默认值
    auth_secret: str  # 必须通过环境变量 AUTH_SECRET 设置，无默认值
    auth_token_expire_minutes: int = 1440
    upload_api_base_url: str = "http://api.test-hot-product.echooo.link"
    log_level: str = "INFO"
    log_dir: str = "logs"

    max_image_size_mb: int = 10
    max_images_per_subtask: int = 10

    cors_origins: str = "http://localhost:5173,http://localhost:5173/comfyui-flow"
    auto_create_tables: bool = True

    video_image_upload_api_url: str = "http://api.hot-products.echooo.link/api/v1/video/upload-image"
    splitting_api_base_url: str = "http://34.21.127.95:8080"

    gcs_project_id: str = "ai-agent-461123"
    gcs_bucket_name: str = "audio_test_112"

    # Open API 配置
    open_api_base_url: str = "http://192.168.199.28:8080"
    open_api_client_id: str = "default_client"
    open_api_client_secret: str = ""
    open_api_callback_url: str | None = None  # 回调地址，由外部注入

    # Google Gemini 官方 API（设置后优先使用，替代 REST API fallback）
    google_api_key: str = ""

    # TikTok 第三方 API 配置
    tikwm_api_key: str = ""       # tikwm.com API key（可选，不传也可访问）
    rapidapi_key: str = ""        # RapidAPI key，用于 tiktok-api23 fallback
    apify_token: str = ""         # Apify API token，用于 clockworks/tiktok-scraper
    tiktok_search_use_rapidapi: bool = True  # False 则跳过 RapidAPI，直接用 Apify 搜索

    # Lark 通知
    lark_webhook_url: str = ""    # Lark 机器人 Webhook 地址（为空则不发通知）

    # 外部发布 API（独立维护的第三方频道发布服务）
    ext_pub_api_base_url: str = "http://34.21.25.209:8000"
    ext_pub_api_key: str = ""     # X-API-Key 认证
    account_channel_api_key: str = ""  # 外部团队领取/确认/绑定 AI 博主频道用
    account_channel_owner_id: str = ""  # 默认 owner_id，请求方不传时使用
    open_api_channel_usage_types: str = ""  # 逗号分隔，如 "short_video,live"；为空则不传
    promotion_code_pool_size: int = 10000  # 启动时预生成的 8 位数字口令数量
    product_search_api_url: str = "https://api.alvinclub.com/ai-service/api/v1/style-outfits/search/image-internal"
    product_search_internal_score_threshold: float = 0.9
    product_search_top_n: int = 3
    product_search_timeout_seconds: float = 45.0

    @property
    def open_api_channel_usage_types_list(self) -> list[str]:
        return [t.strip() for t in self.open_api_channel_usage_types.split(",") if t.strip()]

    @property
    def max_image_size_bytes(self) -> int:
        return self.max_image_size_mb * 1024 * 1024

    @property
    def upload_api_url(self) -> str:
        return f"{self.upload_api_base_url.rstrip('/')}/api/v1/video/upload-image"

    @property
    def video_upload_api_url(self) -> str:
        return f"{self.upload_api_base_url.rstrip('/')}/api/v1/video/upload-video"

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def video_image_upload_url(self) -> str:
        return self.video_image_upload_api_url


settings = Settings()
