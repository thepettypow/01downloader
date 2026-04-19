from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from bot.models.database import upsert_user, set_user_language, get_user_language, set_user_mode, get_user
from bot.utils.locales import get_text
from bot.utils.keyboards import main_menu_inline, settings_menu, language_menu
import aiosqlite
from bot.config.settings import config

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    await upsert_user(user_id, username)

    user = await get_user(user_id)
    selected = True
    if user and len(user) >= 6:
        selected = bool(user[5])
    if not selected:
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
    
    text = "✅ Video mode selected." if lang == 'en' else "✅ حالت ویدیو انتخاب شد."
    if mode == 'audio':
        text = "✅ Audio mode selected." if lang == 'en' else "✅ حالت صدا انتخاب شد."
        
    await callback.answer(text, show_alert=True)

@router.callback_query(F.data.startswith('menu_'))
async def process_menu_callbacks(callback: CallbackQuery):
    action = callback.data.split('_')[1]
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    if action == 'stats':
        async with aiosqlite.connect(config.db_path) as db:
            async with db.execute('SELECT COUNT(*) FROM downloads WHERE user_id = ?', (user_id,)) as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0
        await callback.answer(get_text(lang, 'stats', count=count), show_alert=True)
    elif action == 'settings':
        await callback.message.edit_text(
            "⚙️ Settings / تنظیمات", 
            reply_markup=settings_menu(lang)
        )
    elif action == 'back':
        await callback.message.edit_text(
            get_text(lang, 'welcome', user_id=user_id),
            reply_markup=main_menu_inline(lang)
        )
    else:
        await callback.answer(get_text(lang, 'coming_soon'), show_alert=True)

@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = await get_user_language(message.from_user.id)
    await message.answer(get_text(lang, 'help'))

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute('SELECT COUNT(*) FROM downloads WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            count = row[0] if row else 0
            
    await message.answer(get_text(lang, 'stats', count=count))
