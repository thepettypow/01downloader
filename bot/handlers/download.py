import os
import re
import shutil
from aiogram import Router, F
from aiogram.types import Message, FSInputFile, CallbackQuery
from bot.models.database import (
    get_user_language,
    log_download,
    check_rate_limit,
    create_pending_download,
    get_pending_download,
    delete_pending_download,
)
from bot.utils.locales import get_text
from bot.utils.keyboards import download_choice_menu
from bot.utils.queue_manager import queue_manager
from bot.config.settings import config
from bot.downloaders.ytdlp_wrapper import download_media
from bot.downloaders.spotdl_wrapper import download_spotify
from bot.downloaders.http_fallback import download_direct_file

router = Router()

URL_REGEX = re.compile(r'https?://[^\s]+')

@router.message(F.text.regexp(r'https?://[^\s]+'))
async def process_url(message: Message):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    
    urls = URL_REGEX.findall(message.text)
    if not urls:
        return
    
    for url in urls:
        pending_id = await create_pending_download(user_id, url)
        await message.reply(
            get_text(lang, 'choose_format'),
            reply_markup=download_choice_menu(lang, pending_id)
        )

@router.callback_query(F.data.startswith('dl:'))
async def process_download_choice(callback: CallbackQuery):
    parts = (callback.data or "").split(':', 2)
    if len(parts) != 3:
        await callback.answer()
        return

    try:
        pending_id = int(parts[1])
    except ValueError:
        await callback.answer()
        return

    action = parts[2]
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    row = await get_pending_download(pending_id)
    if not row:
        await callback.answer(get_text(lang, 'invalid_request'), show_alert=True)
        return

    owner_user_id, url = row
    if owner_user_id != user_id:
        await callback.answer(get_text(lang, 'invalid_request'), show_alert=True)
        return

    await delete_pending_download(pending_id)

    if action == 'cancel':
        try:
            await callback.message.edit_text(get_text(lang, 'cancelled'))
        except Exception:
            pass
        await callback.answer()
        return

    if not await check_rate_limit(user_id, config.daily_limit):
        await callback.answer(get_text(lang, 'rate_limit', limit=config.daily_limit), show_alert=True)
        return

    position = await queue_manager.acquire()
    await callback.answer()
    await callback.message.edit_text(get_text(lang, 'queued', position=position))

    await queue_manager.wait_and_acquire()
    try:
        await callback.message.edit_text(get_text(lang, 'downloading'))

        force_document = action == 'document'
        max_height = None
        requested_mode = 'audio' if action == 'audio' else 'video'
        if action.startswith('video_'):
            requested_mode = 'video'
            suffix = action.split('_', 1)[1]
            if suffix.isdigit():
                max_height = int(suffix)

        if 'spotify.com' in url:
            result = await download_spotify(url)
            download_type = 'audio'
        elif url.endswith('.mp3') or url.endswith('.mp4'):
            result = await download_direct_file(url)
            download_type = 'audio' if url.endswith('.mp3') else 'video'
        else:
            result = await download_media(url, requested_mode, max_height=max_height)
            download_type = requested_mode

        if not result['success']:
            if not 'spotify.com' in url and not url.endswith(('.mp3', '.mp4')):
                fallback_result = await download_direct_file(url)
                if fallback_result['success']:
                    result = fallback_result
                    download_type = 'audio' if result['file_path'].endswith('.mp3') else 'video'

            if not result.get('success'):
                await callback.message.edit_text(get_text(lang, 'error', error=result.get('error', 'Unknown Error')))
                return

        file_path = result['file_path']
        title = result.get('title', 'Media')
        dir_to_clean = result.get('dir_to_clean')

        try:
            media = FSInputFile(file_path)
            if force_document:
                await callback.message.answer_document(media, caption=title)
            elif download_type == 'audio':
                await callback.message.answer_audio(media, caption=title)
            else:
                ext = os.path.splitext(file_path)[1].lower()
                if ext in ('.mp4', '.m4v', '.mov'):
                    await callback.message.answer_video(media, caption=title, supports_streaming=True)
                else:
                    await callback.message.answer_document(media, caption=title)

            await log_download(user_id, url, download_type if not force_document else 'document')
            try:
                await callback.message.delete()
            except Exception:
                pass
        except Exception as e:
            await callback.message.edit_text(get_text(lang, 'error', error=str(e)))
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
            if dir_to_clean and os.path.exists(dir_to_clean):
                shutil.rmtree(dir_to_clean, ignore_errors=True)
    finally:
        queue_manager.release()
