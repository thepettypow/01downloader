import os
from aiogram import Router, F
from aiogram.types import Message, FSInputFile, CallbackQuery
from aiogram.filters import Command, CommandStart
from bot.config.settings import config
from bot.models.analytics import get_total_users, get_total_downloads, get_recent_downloads, get_active_users
from bot.models.database import list_users, get_user_downloads, set_user_premium, get_user_premium, ensure_user, get_user_language
from bot.utils.keyboards import users_list_menu, user_downloads_menu, admin_reply_menu
from bot.utils.locales import get_text
from bot.utils.formatting import format_bytes

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in config.admin_ids

@router.message(CommandStart())
async def cmd_admin_start(message: Message):
    if not is_admin(message.from_user.id):
        return
    lang = await get_user_language(message.from_user.id)
    await message.answer(get_text(lang, "admin_panel_title"), reply_markup=admin_reply_menu(lang))

@router.message(Command("admin"))
async def cmd_admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    lang = await get_user_language(message.from_user.id)

    total_users = await get_total_users()
    total_dl = await get_total_downloads()
    active_24h = await get_active_users(1)
    
    stats_text = (
        f"{get_text(lang, 'admin_panel_title')}\n\n"
        f"👥 users: `{total_users}`\n"
        f"🔥 active(24h): `{active_24h}`\n"
        f"📥 downloads: `{total_dl}`\n\n"
        "/logs\n"
        "/db\n"
        "/users\n"
        "/setpremium <user_id>\n"
        "/unsetpremium <user_id>"
    )
    
    await message.answer(stats_text, parse_mode="Markdown")

@router.message()
async def admin_text_shortcuts(message: Message):
    if not is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if not text:
        return
    lang = await get_user_language(message.from_user.id)
    if text == get_text(lang, "admin_kb_panel"):
        await cmd_admin_panel(message)
        return
    if text == get_text(lang, "admin_kb_users"):
        await cmd_admin_users(message)
        return
    if text == get_text(lang, "admin_kb_logs"):
        await cmd_admin_logs(message)
        return
    if text == get_text(lang, "admin_kb_db"):
        await cmd_admin_db(message)
        return

@router.message(Command("logs"))
async def cmd_admin_logs(message: Message):
    if not is_admin(message.from_user.id):
        return
    lang = await get_user_language(message.from_user.id)

    recent = await get_recent_downloads(10)
    if not recent:
        await message.answer(get_text(lang, "admin_no_recent"))
        return
        
    logs_text = f"{get_text(lang, 'admin_logs_title')}\n\n"
    for user_id, username, url, dl_type, time in recent:
        user_display = f"@{username}" if username else f"ID:{user_id}"
        domain = url.split('/')[2] if '//' in url else url[:15]
        logs_text += f"👤 {user_display} | 📥 {dl_type}\n🔗 `{domain}`\n🕒 {time}\n\n"
        
    await message.answer(logs_text, parse_mode="Markdown", disable_web_page_preview=True)

@router.message(Command("db"))
async def cmd_admin_db(message: Message):
    if not is_admin(message.from_user.id):
        return
    lang = await get_user_language(message.from_user.id)

    if os.path.exists(config.db_path):
        db_file = FSInputFile(config.db_path, filename="backup_bot.db")
        await message.answer_document(db_file, caption=get_text(lang, "admin_db_caption"))
    else:
        await message.answer(get_text(lang, "admin_db_missing"))

@router.message(Command("users"))
async def cmd_admin_users(message: Message):
    if not is_admin(message.from_user.id):
        return
    lang = await get_user_language(message.from_user.id)
    await _send_users_page(message, lang, page=0)

async def _send_users_page(message: Message, lang: str, page: int):
    page_size = 10
    offset = max(0, int(page)) * page_size
    rows = await list_users(limit=page_size + 1, offset=offset)
    has_next = len(rows) > page_size
    rows = rows[:page_size]
    text = get_text(lang, "admin_users_title")
    await message.answer(text, reply_markup=users_list_menu(lang, rows, page=page, has_next=has_next))

@router.callback_query(F.data.startswith("admin_users:"))
async def cb_admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts = (callback.data or "").split(":", 1)
    if len(parts) != 2:
        await callback.answer()
        return
    try:
        page = int(parts[1])
    except ValueError:
        await callback.answer()
        return
    lang = await get_user_language(callback.from_user.id)
    page_size = 10
    offset = max(0, page) * page_size
    rows = await list_users(limit=page_size + 1, offset=offset)
    has_next = len(rows) > page_size
    rows = rows[:page_size]
    await callback.answer()
    await callback.message.edit_text(get_text(lang, "admin_users_title"), reply_markup=users_list_menu(lang, rows, page=page, has_next=has_next))

@router.callback_query(F.data.startswith("admin_user:"))
async def cb_admin_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    try:
        user_id = int(parts[1])
        page = int(parts[2])
    except ValueError:
        await callback.answer()
        return
    lang = await get_user_language(callback.from_user.id)
    page_size = 10
    offset = max(0, page) * page_size
    rows = await get_user_downloads(user_id, limit=page_size + 1, offset=offset)
    has_next = len(rows) > page_size
    rows = rows[:page_size]
    lines = [get_text(lang, "admin_user_downloads_title", user=str(user_id))]
    if not rows:
        lines.append("—")
    for url, dl_type, downloaded_at, bytes_used, title in rows:
        label = (title or "").strip() or url
        lines.append(f"- {label} | {dl_type} | {format_bytes(int(bytes_used or 0))}\n{url}")
    is_p = bool(await get_user_premium(user_id))
    await callback.answer()
    await callback.message.edit_text(
        "\n\n".join(lines),
        disable_web_page_preview=True,
        reply_markup=user_downloads_menu(lang, user_id, page, has_next, is_premium=is_p),
    )

@router.callback_query(F.data.startswith("admin_premium:"))
async def cb_admin_premium(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    try:
        user_id = int(parts[1])
        page = int(parts[2])
    except ValueError:
        await callback.answer()
        return
    await ensure_user(user_id)
    is_p = bool(await get_user_premium(user_id))
    await set_user_premium(user_id, not is_p)
    lang = await get_user_language(callback.from_user.id)
    rows = await get_user_downloads(user_id, limit=11, offset=max(0, page) * 10)
    has_next = len(rows) > 10
    rows = rows[:10]
    lines = [get_text(lang, "admin_user_downloads_title", user=str(user_id))]
    if not rows:
        lines.append("—")
    for url, dl_type, downloaded_at, bytes_used, title in rows:
        label = (title or "").strip() or url
        lines.append(f"- {label} | {dl_type} | {format_bytes(int(bytes_used or 0))}\n{url}")
    await callback.answer(get_text(lang, "admin_premium_updated"))
    is_p2 = bool(await get_user_premium(user_id))
    await callback.message.edit_text(
        "\n\n".join(lines),
        disable_web_page_preview=True,
        reply_markup=user_downloads_menu(lang, user_id, page, has_next, is_premium=is_p2),
    )

@router.message(Command("setpremium"))
async def cmd_setpremium(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        return
    uid = int(parts[1].strip())
    await ensure_user(uid)
    await set_user_premium(uid, True)
    lang = await get_user_language(message.from_user.id)
    await message.answer(get_text(lang, "premium_set_ok"))

@router.message(Command("unsetpremium"))
async def cmd_unsetpremium(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        return
    uid = int(parts[1].strip())
    await ensure_user(uid)
    await set_user_premium(uid, False)
    lang = await get_user_language(message.from_user.id)
    await message.answer(get_text(lang, "premium_unset_ok"))

@router.message(Command("premium"))
async def cmd_premium_status(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        return
    uid = int(parts[1].strip())
    is_p = await get_user_premium(uid)
    await message.answer(f"{uid}: {'premium' if is_p else 'free'}")
