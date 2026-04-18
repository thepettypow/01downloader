from typing import List, Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    bot_token: str
    admin_ids: List[int] = []
    db_path: str = "data/bot.db"
    download_dir: str = "downloads"
    max_concurrent_downloads: int = 4
    daily_limit: int = 50
    ytdlp_cookie_file: Optional[str] = None
    ytdlp_cookies_from_browser: Optional[str] = None
    ytdlp_proxy: Optional[str] = None
    ytdlp_user_agent: Optional[str] = None
    ytdlp_remote_components: str = "ejs:github"
    ytdlp_force_ipv4: bool = False
    ytdlp_socket_timeout: int = 20
    ytdlp_retries: int = 3
    ytdlp_skip_youtubetab_authcheck: bool = True
    ytdlp_playlist_end: int = 1
    ytdlp_overall_timeout: int = 1800
    spotdl_timeout: int = 900
    telegram_request_timeout: int = 7200
    telegram_send_timeout: int = 120
    telegram_compress_timeout: int = 120
    telegram_max_upload_bytes: int = 45 * 1024 * 1024
    telegram_fallback_upload_bytes: int = 40 * 1024 * 1024
    telegram_hard_limit_bytes: int = 2000 * 1024 * 1024
    telegram_enable_compression: bool = True
    telegram_delivery_mode: str = "chunk"
    download_retention_hours: int = 12
    cleanup_interval_seconds: int = 3600

    class Config:
        env_file = ".env"

config = Settings()
