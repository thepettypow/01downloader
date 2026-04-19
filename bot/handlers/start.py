from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.filters import CommandStart, Command
from bot.models.database import (
    upsert_user,
    set_user_language,
    get_user_language,
    set_user_mode,
    get_user,
    is_language_selected,
    apply_referral_if_new_user,
    get_referral_bonus_gb,
    get_referral_count,
    get_user_downloads,
    get_user_download_count,
    get_user_daily_quota_bytes,
    get_user_used_bytes_today,
)
from bot.utils.locales import get_text
from bot.utils.keyboards import main_menu_inline, settings_menu, language_menu, pager_menu
from bot.utils.formatting import format_bytes
from bot.config.settings import config

router = Router()

def _parse_start_referrer_id(text: str | None) -> int | None:
    parts = (text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    arg = (parts[1] or "").strip()
    if arg.startswith("ref_"):
        arg = arg[4:]
    if arg.isdigit():
        return int(arg)
    return None

def _back_kb(lang: str):
    return pager_menu(lang, None, None, back_cb="menu_back")

def _domain(url: str) -> str:
    try:
        if "://" in url:
            return url.split("/")[2]
    except Exception:
        pass
    return (url or "")[:32]

@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    existing = await get_user(user_id)
    await upsert_user(user_id, username)

    if not await is_language_selected(user_id):
        if not existing:
            referrer_id = _parse_start_referrer_id(message.text)
            if referrer_id:
                await apply_referral_if_new_user(user_id, referrer_id)
        await message.answer(get_text("en", "choose_language"), reply_markup=language_menu())
        return

    lang = await get_user_language(user_id)
    await message.answer(get_text(lang, 'welcome', user_id=user_id), reply_markup=main_menu_inline(lang))

@router.callback_query(F.data.startswith('lang_'))
async def process_language(callback: CallbackQuery):
    lang = callback.data.split('_')[1]
    user_id = callback.from_user.id
    await set_user_language(user_id, lang)
    
    await callback.answer(get_text(lang, 'language_set'), show_alert=True)
    await callback.message.edit_text(
        get_text(lang, 'welcome', user_id=user_id),
        reply_markup=main_menu_inline(lang)
    )

@router.callback_query(F.data.startswith('set_mode_'))
async def process_set_mode(callback: CallbackQuery):
    mode = callback.data.split('_')[2]
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    
    await set_user_mode(user_id, mode)
    
    text = get_text(lang, "mode_video_set")
    if mode == 'audio':
        text = get_text(lang, "mode_audio_set")
        
    await callback.answer(text, show_alert=True)

@router.callback_query(F.data.startswith('menu_'))
async def process_menu_callbacks(callback: CallbackQuery):
    action = callback.data.split('_')[1]
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    if action == 'stats':
        count = await get_user_download_count(user_id)
        used = await get_user_used_bytes_today(user_id)
        limit = await get_user_daily_quota_bytes(user_id)
        text = get_text(lang, 'stats', count=count) + "\n" + get_text(lang, "quota_status", used=format_bytes(used), limit=format_bytes(limit))
        await callback.answer(text, show_alert=True)
    elif action == 'files':
        await _show_files(callback, user_id, lang, page=0)
    elif action == 'settings':
        await callback.message.edit_text(
            get_text(lang, "settings_title"),
            reply_markup=settings_menu(lang)
        )
    elif action == 'contact':
        await callback.message.edit_text(get_text(lang, "contact_text", channel=getattr(config, "support_channel", "https://t.me/sefroyeki")), reply_markup=_back_kb(lang))
    elif action == 'rules':
        quota = f"{int(getattr(config, 'free_daily_quota_gb', 10))}GB Free / {int(getattr(config, 'premium_daily_quota_gb', 50))}GB Premium"
        if (lang or "").lower().startswith("fa"):
            quota = f"{int(getattr(config, 'free_daily_quota_gb', 10))}GB رایگان / {int(getattr(config, 'premium_daily_quota_gb', 50))}GB پرمیوم"
        await callback.message.edit_text(get_text(lang, "rules_text", quota=quota), reply_markup=_back_kb(lang))
    elif action == 'services':
        await callback.message.edit_text(get_text(lang, "services_text"), reply_markup=_back_kb(lang))
    elif action == 'referral':
        await _show_referral(callback, user_id, lang)
    elif action == 'premium':
        quota = f"{int(getattr(config, 'premium_daily_quota_gb', 50))}GB"
        await callback.message.edit_text(get_text(lang, "premium_text", quota=quota, channel=getattr(config, "support_channel", "https://t.me/sefroyeki")), reply_markup=_back_kb(lang))
    elif action == 'news':
        news = "Updates are live." if lang == "en" else "آپدیت‌ها فعال شد."
        await callback.message.edit_text(get_text(lang, "news_text", news=news), reply_markup=_back_kb(lang))
    elif action == 'back':
        await callback.message.edit_text(
            get_text(lang, 'welcome', user_id=user_id),
            reply_markup=main_menu_inline(lang)
        )
    else:
        await callback.answer(get_text(lang, 'coming_soon'), show_alert=True)

async def _show_files(callback: CallbackQuery, user_id: int, lang: str, page: int):
    page_size = 10
    offset = max(0, int(page)) * page_size
    rows = await get_user_downloads(user_id, limit=page_size + 1, offset=offset)
    has_next = len(rows) > page_size
    rows = rows[:page_size]
    lines = [get_text(lang, "files_title")]
    if not rows:
        lines.append("—")
    for url, dl_type, downloaded_at, bytes_used, title in rows:
        label = (title or "").strip() or _domain(url)
        lines.append(f"- {label} | {dl_type} | {format_bytes(int(bytes_used or 0))}\n{url}")
    prev_cb = f"files:{page - 1}" if page > 0 else None
    next_cb = f"files:{page + 1}" if has_next else None
    await callback.message.edit_text("\n\n".join(lines), disable_web_page_preview=True, reply_markup=pager_menu(lang, prev_cb, next_cb, back_cb="menu_back"))

@router.callback_query(F.data.startswith("files:"))
async def process_files_pager(callback: CallbackQuery):
    parts = (callback.data or "").split(":", 1)
    if len(parts) != 2:
        await callback.answer()
        return
    try:
        page = int(parts[1])
    except ValueError:
        await callback.answer()
        return
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    await callback.answer()
    await _show_files(callback, user_id, lang, page=page)

async def _show_referral(callback: CallbackQuery, user_id: int, lang: str):
    me = await callback.bot.get_me()
    uname = (getattr(me, "username", None) or "").strip().lstrip("@")
    link = f"https://t.me/{uname}?start={user_id}" if uname else f"/start {user_id}"
    count = await get_referral_count(user_id)
    bonus = await get_referral_bonus_gb(user_id)
    await callback.message.edit_text(get_text(lang, "referral_text", link=link, count=count, bonus=bonus), disable_web_page_preview=True, reply_markup=_back_kb(lang))

@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = await get_user_language(message.from_user.id)
    await message.answer(get_text(lang, 'help'))

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    count = await get_user_download_count(user_id)
    used = await get_user_used_bytes_today(user_id)
    limit = await get_user_daily_quota_bytes(user_id)
    await message.answer(get_text(lang, 'stats', count=count) + "\n" + get_text(lang, "quota_status", used=format_bytes(used), limit=format_bytes(limit)))

@router.inline_query()
async def inline_search(query: InlineQuery):
    from bot.models.database import search_user_downloads

    user_id = query.from_user.id
    q = (query.query or "").strip()
    rows = await search_user_downloads(user_id, q, limit=20)
    results = []
    for i, (url, dl_type, downloaded_at, bytes_used, title) in enumerate(rows):
        label = (title or "").strip() or _domain(url)
        desc = f"{dl_type} • {format_bytes(int(bytes_used or 0))}"
        results.append(
            InlineQueryResultArticle(
                id=str(i),
                title=label[:128],
                description=desc[:256],
                input_message_content=InputTextMessageContent(message_text=url),
            )
        )
    await query.answer(results, cache_time=1, is_personal=True)
