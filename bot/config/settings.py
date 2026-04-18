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
    ytdlp_proxy: Optional[str] = None
    ytdlp_user_agent: Optional[str] = None
    ytdlp_remote_components: str = "ejs:github"
    ytdlp_force_ipv4: bool = False
    ytdlp_socket_timeout: int = 20
    ytdlp_retries: int = 3
    ytdlp_skip_youtubetab_authcheck: bool = True
    ytdlp_playlist_end: int = 1

    class Config:
        env_file = ".env"

config = Settings()
