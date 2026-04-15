from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    bot_token: str
    admin_ids: List[int] = []
    db_path: str = "data/bot.db"
    download_dir: str = "downloads"
    max_concurrent_downloads: int = 4
    daily_limit: int = 50

    class Config:
        env_file = ".env"

config = Settings()
