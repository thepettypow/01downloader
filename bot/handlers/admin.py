import os
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from bot.config.settings import config
from bot.models.analytics import get_total_users, get_total_downloads, get_recent_downloads, get_active_users

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in config.admin_ids

@router.message(Command("admin"))
async def cmd_admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return

    total_users = await get_total_users()
    total_dl = await get_total_downloads()
    active_24h = await get_active_users(1)
    
    stats_text = (
        "👑 **Admin Analytics Panel** 👑\n\n"
        f"👥 **Total Users:** `{total_users}`\n"
        f"🔥 **Active (24h):** `{active_24h}`\n"
        f"📥 **Total Downloads:** `{total_dl}`\n\n"
        "Commands:\n"
        "/logs - View recent downloads\n"
        "/db - Download database backup\n"
        "/broadcast <message> - Send to all users (Soon)"
    )
    
    await message.answer(stats_text, parse_mode="Markdown")

@router.message(Command("logs"))
async def cmd_admin_logs(message: Message):
    if not is_admin(message.from_user.id):
        return

    recent = await get_recent_downloads(10)
    if not recent:
        await message.answer("No recent downloads found.")
        return
        
    logs_text = "📜 **Last 10 Downloads:**\n\n"
    for user_id, username, url, dl_type, time in recent:
        user_display = f"@{username}" if username else f"ID:{user_id}"
        domain = url.split('/')[2] if '//' in url else url[:15]
        logs_text += f"👤 {user_display} | 📥 {dl_type}\n🔗 `{domain}`\n🕒 {time}\n\n"
        
    await message.answer(logs_text, parse_mode="Markdown", disable_web_page_preview=True)

@router.message(Command("db"))
async def cmd_admin_db(message: Message):
    if not is_admin(message.from_user.id):
        return

    if os.path.exists(config.db_path):
        db_file = FSInputFile(config.db_path, filename="backup_bot.db")
        await message.answer_document(db_file, caption="📦 Database Backup")
    else:
        await message.answer("Database file not found!")
