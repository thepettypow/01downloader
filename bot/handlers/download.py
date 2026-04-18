import asyncio
import logging
import os
import random
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
from bot.utils.keyboards import download_choice_menu, download_quality_menu
from bot.utils.queue_manager import queue_manager
from bot.config.settings import config
from bot.downloaders.ytdlp_wrapper import download_media, probe_media
from bot.downloaders.spotdl_wrapper import download_spotify
from bot.downloaders.http_fallback import download_direct_file
from bot.utils.telegram_compress import compress_video_to_size, compress_audio_to_size
from bot.utils.file_chunker import split_file

router = Router()
logger = logging.getLogger(__name__)

URL_REGEX = re.compile(r'https?://[^\s]+')

def _sanitize_url(url: str) -> str:
    u = (url or "").strip()
    u = u.replace("`", "")
    u = u.strip("'\"<>[]()")
    u = u.lstrip("'\"<>[]()")
    while u and u[-1] in ("`", "'", "\"", ">", "]", ")", ".", ",", ";", ":"):
        u = u[:-1]
    return u

@router.message(F.text.regexp(r'https?://[^\s]+'))
async def process_url(message: Message):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    
    urls = URL_REGEX.findall(message.text)
    if not urls:
        return
    
    for url in urls:
        clean_url = _sanitize_url(url)
        if not clean_url:
            continue
        pending_id = await create_pending_download(user_id, clean_url)
        kb = None
        try:
            info = await asyncio.wait_for(probe_media(clean_url), timeout=12)
            if info.get("success"):
                kb = download_quality_menu(lang, pending_id, info.get("video_options"), info.get("duration"))
        except Exception:
            kb = None
        await message.reply(
            get_text(lang, 'choose_format'),
            reply_markup=kb or download_choice_menu(lang, pending_id)
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
    url = _sanitize_url(url)

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

        max_height = None
        audio_bitrate_kbps = None
        requested_mode = 'video'
        if action == 'video':
            requested_mode = 'video'
        elif action == 'audio':
            requested_mode = 'audio'
            audio_bitrate_kbps = 192
        if action.startswith('video_'):
            requested_mode = 'video'
            suffix = action.split('_', 1)[1]
            if suffix.isdigit():
                max_height = int(suffix)
        elif action.startswith('audio_'):
            requested_mode = 'audio'
            suffix = action.split('_', 1)[1]
            if suffix.isdigit():
                audio_bitrate_kbps = int(suffix)
            else:
                audio_bitrate_kbps = 320

        if 'spotify.com' in url:
            result = await download_spotify(url)
            download_type = 'audio'
        elif url.endswith('.mp3') or url.endswith('.mp4'):
            result = await download_direct_file(url)
            download_type = 'audio' if url.endswith('.mp3') else 'video'
        else:
            try:
                status = {}
                download_task = asyncio.create_task(
                    download_media(
                        url,
                        requested_mode,
                        max_height=max_height,
                        audio_bitrate_kbps=audio_bitrate_kbps,
                        status=status,
                    )
                )
                started = asyncio.get_event_loop().time()

                async def ticker():
                    while not download_task.done():
                        await asyncio.sleep(20)
                        if download_task.done():
                            break
                        elapsed = int(asyncio.get_event_loop().time() - started)
                        phase = (status or {}).get("phase") or ""
                        progress = (status or {}).get("progress") or ""
                        detail = (status or {}).get("detail") or ""
                        extra = " ".join([x for x in (detail, phase, progress) if x]).strip()
                        try:
                            text = f"{get_text(lang, 'downloading')}\n\n{elapsed}s"
                            if extra:
                                text = f"{get_text(lang, 'downloading')}\n\n{extra}\n{elapsed}s"
                            await callback.message.edit_text(text)
                        except Exception:
                            pass

                ticker_task = asyncio.create_task(ticker())
                try:
                    result = await asyncio.wait_for(
                        download_task,
                        timeout=int(getattr(config, "ytdlp_overall_timeout", 1800)),
                    )
                finally:
                    ticker_task.cancel()
            except asyncio.TimeoutError:
                await callback.message.edit_text(get_text(lang, 'error', error="Download timed out. Try a lower quality."))
                return
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
        duration = result.get('duration')
        try:
            size = os.path.getsize(file_path)
            logger.info("sending file=%s bytes=%s", file_path, size)
        except Exception:
            pass

        try:
            hard_limit = int(getattr(config, "telegram_hard_limit_bytes", 2000 * 1024 * 1024))
            max_upload = int(getattr(config, "telegram_max_upload_bytes", 50 * 1024 * 1024))
            fallback_upload = int(getattr(config, "telegram_fallback_upload_bytes", 50 * 1024 * 1024))
            enable_compress = bool(getattr(config, "telegram_enable_compression", True))
            delivery_mode = (getattr(config, "telegram_delivery_mode", "chunk") or "chunk").strip().lower()

            def is_transient_upload_error(err: Exception) -> bool:
                s = (str(err) or "").lower()
                needles = (
                    "cannot write to closing transport",
                    "connection reset",
                    "connection aborted",
                    "broken pipe",
                    "timeout",
                    "timed out",
                    "bad gateway",
                    "gateway timeout",
                    "service unavailable",
                    "temporary failure",
                    "server disconnected",
                )
                return any(n in s for n in needles)

            async def backoff_sleep(attempt: int) -> None:
                base = min(20, 2 ** attempt)
                await asyncio.sleep(base + random.uniform(0, 1.5))
            try:
                current_size = os.path.getsize(file_path)
            except Exception:
                current_size = 0
            if current_size and current_size > hard_limit:
                await callback.message.edit_text(get_text(lang, 'error', error="File is larger than 2GB and cannot be uploaded by the bot."))
                return

            async def send_once():
                async def do_send():
                    media = FSInputFile(file_path)
                    if download_type == 'audio':
                        return await callback.message.answer_audio(media, caption=title)
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext in ('.mp4', '.m4v', '.mov'):
                        return await callback.message.answer_video(media, caption=title, supports_streaming=True)
                    return await callback.message.answer_document(media, caption=title)

                return await asyncio.wait_for(
                    do_send(),
                    timeout=int(getattr(config, "telegram_send_timeout", 120)),
                )

            async def send_as_parts():
                loop = asyncio.get_event_loop()
                part_size = max(1, min(fallback_upload, hard_limit))
                part_paths = await loop.run_in_executor(None, split_file, file_path, part_size, config.download_dir)
                total = len(part_paths)
                try:
                    for i, part_path in enumerate(part_paths, start=1):
                        try:
                            await callback.message.edit_text(get_text(lang, 'downloading') + f"\n\nuploading part {i}/{total}")
                        except Exception:
                            pass
                        cap = f"{title} (part {i}/{total})"
                        await callback.message.answer_document(FSInputFile(part_path), caption=cap)
                finally:
                    for p in part_paths:
                        try:
                            if os.path.exists(p):
                                os.remove(p)
                        except Exception:
                            pass

            try:
                current_size = os.path.getsize(file_path)
            except Exception:
                current_size = 0
            if current_size and current_size > max_upload:
                if delivery_mode == "chunk":
                    await send_as_parts()
                else:
                    raise RuntimeError("File exceeds upload limit")
            else:
                last_err = None
                max_attempts = 3
                for attempt in range(max_attempts):
                    try:
                        await send_once()
                        last_err = None
                        break
                    except Exception as e:
                        last_err = e
                        if isinstance(e, asyncio.TimeoutError):
                            if delivery_mode == "chunk":
                                await send_as_parts()
                                last_err = None
                                break
                            raise RuntimeError("Telegram upload timed out")
                        if attempt == 0 and is_transient_upload_error(e) and enable_compress:
                            loop = asyncio.get_event_loop()
                            compressed_path = os.path.join(config.download_dir, f"tg_retry_{os.path.basename(file_path)}")
                            try:
                                await callback.message.edit_text(get_text(lang, 'downloading') + "\n\ncompressing…")
                            except Exception:
                                pass
                            if download_type == "audio":
                                await loop.run_in_executor(
                                    None,
                                    compress_audio_to_size,
                                    file_path,
                                    compressed_path,
                                    fallback_upload,
                                    duration,
                                    int(getattr(config, "telegram_compress_timeout", 180)),
                                )
                            else:
                                await loop.run_in_executor(
                                    None,
                                    compress_video_to_size,
                                    file_path,
                                    compressed_path,
                                    fallback_upload,
                                    duration,
                                    max_height,
                                    int(getattr(config, "telegram_compress_timeout", 180)),
                                )
                            if os.path.exists(file_path):
                                os.remove(file_path)
                            file_path = compressed_path
                        if attempt < (max_attempts - 1) and is_transient_upload_error(e):
                            await backoff_sleep(attempt)
                            continue
                        if delivery_mode == "chunk":
                            await send_as_parts()
                            last_err = None
                            break
                        raise
                if last_err is not None:
                    raise last_err

            await log_download(user_id, url, download_type)
            try:
                await callback.message.delete()
            except Exception:
                pass
        except Exception as e:
            logger.exception("send failed")
            await callback.message.edit_text(get_text(lang, 'error', error=str(e)))
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
            if dir_to_clean and os.path.exists(dir_to_clean):
                shutil.rmtree(dir_to_clean, ignore_errors=True)
    finally:
        queue_manager.release()
