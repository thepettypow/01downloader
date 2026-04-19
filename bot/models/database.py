import aiosqlite
from bot.config.settings import config
from datetime import datetime
from zoneinfo import ZoneInfo

def get_tehran_ymd() -> str:
    tz = ZoneInfo((getattr(config, "quota_timezone", None) or "Asia/Tehran").strip() or "Asia/Tehran")
    return datetime.now(tz).strftime("%Y-%m-%d")

def _gb_to_bytes(gb: int) -> int:
    return int(gb) * 1024 * 1024 * 1024

async def init_db():
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                language TEXT DEFAULT 'en',
                quality_preference TEXT DEFAULT 'video',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                language_selected INTEGER DEFAULT 0,
                is_premium INTEGER DEFAULT 0,
                referral_bonus_gb INTEGER DEFAULT 0,
                referred_by INTEGER
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                url TEXT,
                type TEXT,
                bytes INTEGER DEFAULT 0,
                title TEXT DEFAULT '',
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS pending_downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS daily_usage (
                user_id INTEGER,
                ymd TEXT,
                bytes_used INTEGER,
                PRIMARY KEY(user_id, ymd)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                referrer_id INTEGER,
                referred_id INTEGER UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        async with db.execute("PRAGMA table_info(users)") as cursor:
            rows = await cursor.fetchall()
        cols = {r[1] for r in (rows or []) if r and len(r) > 1}
        if "language_selected" not in cols:
            await db.execute("ALTER TABLE users ADD COLUMN language_selected INTEGER DEFAULT 0")
            await db.execute("UPDATE users SET language_selected = 1 WHERE language IS NOT NULL AND TRIM(language) != ''")
        if "is_premium" not in cols:
            await db.execute("ALTER TABLE users ADD COLUMN is_premium INTEGER DEFAULT 0")
        if "referral_bonus_gb" not in cols:
            await db.execute("ALTER TABLE users ADD COLUMN referral_bonus_gb INTEGER DEFAULT 0")
        if "referred_by" not in cols:
            await db.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")

        async with db.execute("PRAGMA table_info(downloads)") as cursor:
            drows = await cursor.fetchall()
        dcols = {r[1] for r in (drows or []) if r and len(r) > 1}
        if "bytes" not in dcols:
            await db.execute("ALTER TABLE downloads ADD COLUMN bytes INTEGER DEFAULT 0")
        if "title" not in dcols:
            await db.execute("ALTER TABLE downloads ADD COLUMN title TEXT DEFAULT ''")
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

async def is_language_selected(user_id: int) -> bool:
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute("SELECT language_selected FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row and int(row[0] or 0))

async def set_user_language(user_id: int, language: str):
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute('UPDATE users SET language = ?, language_selected = 1 WHERE user_id = ?', (language, user_id))
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
    if int(limit or 0) <= 0:
        return True
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute('''
            SELECT COUNT(*) FROM downloads 
            WHERE user_id = ? AND downloaded_at >= datetime('now', '-1 day')
        ''', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return (row[0] if row else 0) < limit

async def log_download(user_id: int, url: str, dl_type: str, bytes_used: int = 0, title: str = ""):
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute(
            'INSERT INTO downloads (user_id, url, type, bytes, title) VALUES (?, ?, ?, ?, ?)',
            (user_id, url, dl_type, int(bytes_used or 0), (title or "")),
        )
        await db.commit()

async def get_user_premium(user_id: int) -> bool:
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute("SELECT is_premium FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row and int(row[0] or 0))

async def set_user_premium(user_id: int, is_premium: bool) -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute("UPDATE users SET is_premium = ? WHERE user_id = ?", (1 if is_premium else 0, user_id))
        await db.commit()

async def get_referral_bonus_gb(user_id: int) -> int:
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute("SELECT referral_bonus_gb FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return int(row[0] or 0) if row else 0

async def get_referral_count(user_id: int) -> int:
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return int(row[0] or 0) if row else 0

async def apply_referral_if_new_user(new_user_id: int, referrer_id: int) -> bool:
    if not referrer_id or int(referrer_id) == int(new_user_id):
        return False
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (int(referrer_id),)) as cursor:
            exists = await cursor.fetchone()
        if not exists:
            return False
        await db.execute(
            "INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
            (int(referrer_id), int(new_user_id)),
        )
        async with db.execute("SELECT changes()") as cursor:
            row = await cursor.fetchone()
        changed = bool(row and int(row[0] or 0) > 0)
        if not changed:
            await db.commit()
            return False
        await db.execute(
            "UPDATE users SET referred_by = ? WHERE user_id = ? AND (referred_by IS NULL OR referred_by = 0)",
            (int(referrer_id), int(new_user_id)),
        )
        bonus = int(getattr(config, "referral_bonus_gb", 1) or 1)
        await db.execute(
            "UPDATE users SET referral_bonus_gb = COALESCE(referral_bonus_gb, 0) + ? WHERE user_id = ?",
            (bonus, int(referrer_id)),
        )
        await db.commit()
        return True

async def get_user_daily_quota_bytes(user_id: int) -> int:
    premium = bool(int(user_id) in set(getattr(config, "premium_ids", []) or [])) or await get_user_premium(user_id)
    base_gb = int(getattr(config, "premium_daily_quota_gb", 50) if premium else getattr(config, "free_daily_quota_gb", 10))
    bonus_gb = await get_referral_bonus_gb(user_id)
    return _gb_to_bytes(base_gb + bonus_gb)

async def get_user_used_bytes_today(user_id: int) -> int:
    ymd = get_tehran_ymd()
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute(
            "SELECT bytes_used FROM daily_usage WHERE user_id = ? AND ymd = ?",
            (user_id, ymd),
        ) as cursor:
            row = await cursor.fetchone()
            return int(row[0] or 0) if row else 0

async def can_consume(user_id: int, bytes_needed: int) -> tuple[bool, int, int]:
    limit = await get_user_daily_quota_bytes(user_id)
    used = await get_user_used_bytes_today(user_id)
    need = max(0, int(bytes_needed or 0))
    return (used + need) <= limit, used, limit

async def consume_bytes(user_id: int, bytes_used: int) -> None:
    ymd = get_tehran_ymd()
    inc = max(0, int(bytes_used or 0))
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO daily_usage (user_id, ymd, bytes_used) VALUES (?, ?, 0)",
            (user_id, ymd),
        )
        await db.execute(
            "UPDATE daily_usage SET bytes_used = COALESCE(bytes_used, 0) + ? WHERE user_id = ? AND ymd = ?",
            (inc, user_id, ymd),
        )
        await db.commit()

async def list_users(limit: int = 10, offset: int = 0) -> list[tuple]:
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute(
            "SELECT user_id, username, joined_at, is_premium, referral_bonus_gb FROM users ORDER BY joined_at DESC LIMIT ? OFFSET ?",
            (int(limit), int(offset)),
        ) as cursor:
            return await cursor.fetchall()

async def get_user_downloads(user_id: int, limit: int = 10, offset: int = 0) -> list[tuple]:
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute(
            "SELECT url, type, downloaded_at, bytes, title FROM downloads WHERE user_id = ? ORDER BY downloaded_at DESC LIMIT ? OFFSET ?",
            (user_id, int(limit), int(offset)),
        ) as cursor:
            return await cursor.fetchall()

async def search_user_downloads(user_id: int, query: str, limit: int = 20) -> list[tuple]:
    q = (query or "").strip()
    like = f"%{q}%"
    async with aiosqlite.connect(config.db_path) as db:
        if q:
            async with db.execute(
                "SELECT url, type, downloaded_at, bytes, title FROM downloads WHERE user_id = ? AND url LIKE ? ORDER BY downloaded_at DESC LIMIT ?",
                (user_id, like, int(limit)),
            ) as cursor:
                return await cursor.fetchall()
        async with db.execute(
            "SELECT url, type, downloaded_at, bytes, title FROM downloads WHERE user_id = ? ORDER BY downloaded_at DESC LIMIT ?",
            (user_id, int(limit)),
        ) as cursor:
            return await cursor.fetchall()

async def get_user_download_count(user_id: int) -> int:
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute("SELECT COUNT(*) FROM downloads WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return int(row[0] or 0) if row else 0

async def ensure_user(user_id: int, username: str | None = None) -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (int(user_id), (username or "")),
        )
        await db.commit()

async def create_pending_download(user_id: int, url: str) -> int:
    async with aiosqlite.connect(config.db_path) as db:
        cursor = await db.execute('INSERT INTO pending_downloads (user_id, url) VALUES (?, ?)', (user_id, url))
        await db.commit()
        return cursor.lastrowid

async def get_pending_download(pending_id: int):
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute('SELECT user_id, url FROM pending_downloads WHERE id = ?', (pending_id,)) as cursor:
            return await cursor.fetchone()

async def delete_pending_download(pending_id: int):
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute('DELETE FROM pending_downloads WHERE id = ?', (pending_id,))
        await db.commit()
