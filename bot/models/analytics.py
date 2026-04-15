import aiosqlite
from bot.config.settings import config
from datetime import datetime, timedelta

async def get_total_users() -> int:
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute('SELECT COUNT(*) FROM users') as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_total_downloads() -> int:
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute('SELECT COUNT(*) FROM downloads') as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_recent_downloads(limit: int = 10) -> list:
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute('''
            SELECT d.user_id, u.username, d.url, d.type, d.downloaded_at 
            FROM downloads d
            LEFT JOIN users u ON d.user_id = u.user_id
            ORDER BY d.downloaded_at DESC LIMIT ?
        ''', (limit,)) as cursor:
            return await cursor.fetchall()

async def get_active_users(days: int = 1) -> int:
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute('''
            SELECT COUNT(DISTINCT user_id) FROM downloads 
            WHERE downloaded_at >= datetime('now', ?)
        ''', (f'-{days} day',)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0
