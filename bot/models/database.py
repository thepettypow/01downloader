import aiosqlite
from bot.config.settings import config

async def init_db():
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                language TEXT DEFAULT 'en',
                quality_preference TEXT DEFAULT 'video',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                url TEXT,
                type TEXT,
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone()

async def upsert_user(user_id: int, username: str):
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute('''
            INSERT INTO users (user_id, username)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
        ''', (user_id, username))
        await db.commit()

async def set_user_language(user_id: int, language: str):
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute('UPDATE users SET language = ? WHERE user_id = ?', (language, user_id))
        await db.commit()

async def get_user_language(user_id: int) -> str:
    user = await get_user(user_id)
    if user and user[2]:
        return user[2]
    return 'en'

async def set_user_mode(user_id: int, mode: str):
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute('UPDATE users SET quality_preference = ? WHERE user_id = ?', (mode, user_id))
        await db.commit()

async def get_user_mode(user_id: int) -> str:
    user = await get_user(user_id)
    if user and user[3]:
        return user[3]
    return 'video'

async def check_rate_limit(user_id: int, limit: int) -> bool:
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute('''
            SELECT COUNT(*) FROM downloads 
            WHERE user_id = ? AND downloaded_at >= datetime('now', '-1 day')
        ''', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return (row[0] if row else 0) < limit

async def log_download(user_id: int, url: str, dl_type: str):
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute('INSERT INTO downloads (user_id, url, type) VALUES (?, ?, ?)', (user_id, url, dl_type))
        await db.commit()
