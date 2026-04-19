import asyncio
import logging
import os
import random
import re
import shutil
import uuid
from urllib.parse import urlparse
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
from bot.downloaders.spotify_fallback import download_spotify_fallback, iter_spotify_fallback
from bot.downloaders.quick_ytdlp import quick_download
from bot.downloaders.http_fallback import download_direct_file
from bot.utils.telegram_compress import compress_video_to_size, compress_audio_to_size
from bot.utils.video_tools import probe_video, extract_thumbnail
from bot.utils.audio_tools import probe_audio, extract_audio_cover

router = Router()
logger = logging.getLogger(__name__)

URL_REGEX = re.compile(r'https?://[^\s]+')

def _is_spotify_url(u: str) -> bool:
    s = (u or "").lower()
    return "spotify.com" in s or "open.spotify.com" in s or "spotify.link" in s

def _is_x_url(u: str) -> bool:
    s = (u or "").lower()
    return "x.com/" in s or "twitter.com/" in s or "t.co/" in s

def _is_long_video_site(u: str) -> bool:
    try:
        host = (urlparse(u).netloc or "").lower()
    except Exception:
        host = ""
    return any(
        h in host
        for h in (
            "youtube.com",
            "youtu.be",
            "pornhub.com",
            "vk.com",
        )
    )

async def _send_quick_files(message: Message, caption_top: str | None, result: dict):
    files = list(result.get("file_paths") or [])
    caption = (caption_top or "").strip()
    if caption:
        await message.answer(caption)

    loop = asyncio.get_event_loop()
    for fp in files:
        ext = os.path.splitext(fp)[1].lower()
        if ext in (".jpg", ".jpeg", ".png", ".webp"):
            await message.answer_photo(FSInputFile(fp))
            continue
        if ext in (".mp4", ".m4v", ".mov"):
            try:
                size = os.path.getsize(fp)
            except Exception:
                size = 0
            max_upload = int(getattr(config, "telegram_max_upload_bytes", 50 * 1024 * 1024))
            if size and size > max_upload and bool(getattr(config, "telegram_enable_compression", True)):
                target = max_upload
                outp = os.path.join(config.download_dir, f"tg_{uuid.uuid4().hex}.mp4")
                try:
                    await loop.run_in_executor(
                        None,
                        compress_video_to_size,
                        fp,
                        outp,
                        target,
                        None,
                        720,
                        int(getattr(config, "telegram_compress_timeout", 120)),
                    )
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
                    fp = outp
                except Exception:
                    try:
                        if os.path.exists(outp):
                            os.remove(outp)
                    except Exception:
                        pass

            meta = {}
            try:
                meta = await loop.run_in_executor(None, probe_video, fp)
            except Exception:
                meta = {}
            d = meta.get("duration")
            duration_s = int(d) if d else None
            thumb_path = None
            try:
                thumb_path = os.path.join(config.download_dir, f"thumb_{uuid.uuid4().hex}.jpg")
                await loop.run_in_executor(None, extract_thumbnail, fp, thumb_path)
            except Exception:
                thumb_path = None
            try:
                kwargs = {"supports_streaming": True}
                if duration_s:
                    kwargs["duration"] = duration_s
                if meta.get("width"):
                    kwargs["width"] = int(meta["width"])
                if meta.get("height"):
                    kwargs["height"] = int(meta["height"])
                if thumb_path and os.path.exists(thumb_path):
                    kwargs["thumbnail"] = FSInputFile(thumb_path)
                await message.answer_video(FSInputFile(fp), **kwargs)
            finally:
                if thumb_path and os.path.exists(thumb_path):
                    try:
                        os.remove(thumb_path)
                    except Exception:
                        pass
            continue
        await message.answer_document(FSInputFile(fp))

async def _handle_x_message(message: Message, user_id: int, lang: str, url: str):
    if not await check_rate_limit(user_id, config.daily_limit):
        await message.answer(get_text(lang, 'rate_limit', limit=config.daily_limit))
        return

    position = await queue_manager.acquire()
    status_msg = await message.answer(get_text(lang, 'queued', position=position))
    await queue_manager.wait_and_acquire()
    try:
        await status_msg.edit_text(get_text(lang, 'downloading'))
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, quick_download, url)
        if not result.get("success"):
            await status_msg.edit_text(get_text(lang, 'error', error=result.get("error", "Download failed")))
            return
        try:
            await status_msg.delete()
        except Exception:
            pass
        await _send_quick_files(message, result.get("caption"), result)
        await log_download(user_id, url, "video")
    finally:
        dir_to_clean = result.get("dir_to_clean") if isinstance(locals().get("result"), dict) else None
        if dir_to_clean and os.path.exists(dir_to_clean):
            shutil.rmtree(dir_to_clean, ignore_errors=True)
        queue_manager.release()

async def _handle_quick_message(message: Message, user_id: int, lang: str, url: str):
    if not await check_rate_limit(user_id, config.daily_limit):
        await message.answer(get_text(lang, 'rate_limit', limit=config.daily_limit))
        return

    position = await queue_manager.acquire()
    status_msg = await message.answer(get_text(lang, 'queued', position=position))
    await queue_manager.wait_and_acquire()
    try:
        await status_msg.edit_text(get_text(lang, 'downloading'))
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, quick_download, url)
        if not result.get("success"):
            await status_msg.edit_text(get_text(lang, 'error', error=result.get("error", "Download failed")))
            return
        try:
            await status_msg.delete()
        except Exception:
            pass
        await _send_quick_files(message, None, result)
        await log_download(user_id, url, "video")
    finally:
        dir_to_clean = result.get("dir_to_clean") if isinstance(locals().get("result"), dict) else None
        if dir_to_clean and os.path.exists(dir_to_clean):
            shutil.rmtree(dir_to_clean, ignore_errors=True)
        queue_manager.release()

async def _send_spotify_result(message: Message, lang: str, user_id: int, url: str, result: dict):
    spotify_files = result.get('file_paths') or []
    title = result.get('title', 'Media')
    dir_to_clean = result.get('dir_to_clean')
    cover_path = result.get("cover_path")
    tracks = result.get("tracks") or []
    try:
        if not spotify_files:
            await message.answer(get_text(lang, 'error', error="Spotify download returned no files"))
            return

        loop = asyncio.get_event_loop()
        if not cover_path:
            try:
                cover_path = os.path.join(config.download_dir, f"cover_{uuid.uuid4().hex}.jpg")
                await loop.run_in_executor(None, extract_audio_cover, spotify_files[0], cover_path)
            except Exception:
                cover_path = None
        if cover_path and os.path.exists(cover_path):
            await message.answer_photo(FSInputFile(cover_path), caption=title)

        for idx, fp in enumerate(spotify_files):
            meta = {}
            try:
                meta = await loop.run_in_executor(None, probe_audio, fp)
            except Exception:
                meta = {}
            performer = meta.get("artist")
            track_title = meta.get("title") or os.path.splitext(os.path.basename(fp))[0]
            if idx < len(tracks):
                performer = tracks[idx].get("artist") or performer
                track_title = tracks[idx].get("title") or track_title
            d = meta.get("duration")
            duration_s = int(d) if d else None
            thumb_path = cover_path if cover_path and os.path.exists(cover_path) else None
            kwargs = {"performer": performer, "title": track_title}
            if duration_s:
                kwargs["duration"] = duration_s
            if thumb_path:
                kwargs["thumbnail"] = FSInputFile(thumb_path)
            await message.answer_audio(FSInputFile(fp), **{k: v for k, v in kwargs.items() if v})

        await log_download(user_id, url, "audio")
    finally:
        if cover_path and os.path.exists(cover_path):
            try:
                os.remove(cover_path)
            except Exception:
                pass
        for fp in spotify_files:
            try:
                if fp and os.path.exists(fp):
                    os.remove(fp)
            except Exception:
                pass
        if dir_to_clean and os.path.exists(dir_to_clean):
            shutil.rmtree(dir_to_clean, ignore_errors=True)

async def _handle_spotify_message(message: Message, user_id: int, lang: str, url: str):
    if not await check_rate_limit(user_id, config.daily_limit):
        await message.answer(get_text(lang, 'rate_limit', limit=config.daily_limit))
        return

    position = await queue_manager.acquire()
    status_msg = await message.answer(get_text(lang, 'queued', position=position))
    await queue_manager.wait_and_acquire()
    try:
        try:
            await status_msg.edit_text(get_text(lang, 'downloading'))
        except Exception:
            pass

        started = asyncio.get_event_loop().time()
        result = None
        if bool(getattr(config, "spotify_use_spotdl", False)):
            task = asyncio.create_task(download_spotify(url))

            async def ticker():
                while not task.done():
                    await asyncio.sleep(15)
                    if task.done():
                        break
                    elapsed = int(asyncio.get_event_loop().time() - started)
                    try:
                        await status_msg.edit_text(get_text(lang, 'downloading') + f"\n\n{elapsed}s")
                    except Exception:
                        pass

            ticker_task = asyncio.create_task(ticker())
            try:
                result = await task
            finally:
                ticker_task.cancel()

        if not (result or {}).get("success"):
            try:
                await status_msg.edit_text(get_text(lang, 'downloading') + "\n\nYouTube fallback…")
            except Exception:
                pass

            cover_path = None
            title = "Spotify"
            tracks = []
            sent_any = False

            try:
                i = 0
                async for ev in iter_spotify_fallback(url, max_tracks=50):
                    if ev.get("type") == "error":
                        raise RuntimeError(ev.get("error") or "Spotify fallback failed")
                    if ev.get("type") == "cover":
                        title = ev.get("title") or title
                        cover_path = ev.get("cover_path")
                        tracks = ev.get("tracks") or []
                        try:
                            await status_msg.delete()
                        except Exception:
                            pass
                        if cover_path and os.path.exists(cover_path):
                            await message.answer_photo(FSInputFile(cover_path), caption=title)
                        continue
                    if ev.get("type") == "track":
                        i += 1
                        fp = ev.get("file_path")
                        track = ev.get("track") or {}
                        if not fp:
                            continue
                        try:
                            meta = {}
                            try:
                                meta = await asyncio.get_event_loop().run_in_executor(None, probe_audio, fp)
                            except Exception:
                                meta = {}
                            performer = (track.get("artist") or meta.get("artist"))
                            track_title = (track.get("title") or meta.get("title") or os.path.splitext(os.path.basename(fp))[0])
                            d = meta.get("duration")
                            duration_s = int(d) if d else None
                            kwargs = {"performer": performer, "title": track_title}
                            if duration_s:
                                kwargs["duration"] = duration_s
                            if cover_path and os.path.exists(cover_path):
                                kwargs["thumbnail"] = FSInputFile(cover_path)
                            await message.answer_audio(FSInputFile(fp), **{k: v for k, v in kwargs.items() if v})
                            sent_any = True
                        finally:
                            try:
                                if os.path.exists(fp):
                                    os.remove(fp)
                            except Exception:
                                pass

                if not sent_any:
                    raise RuntimeError("No matches found on YouTube")
                await log_download(user_id, url, "audio")
                return
            finally:
                if cover_path and os.path.exists(cover_path):
                    try:
                        os.remove(cover_path)
                    except Exception:
                        pass

        try:
            await status_msg.delete()
        except Exception:
            pass
        await _send_spotify_result(message, lang, user_id, url, result)
    finally:
        queue_manager.release()

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
        if _is_spotify_url(clean_url):
            await _handle_spotify_message(message, user_id, lang, clean_url)
            continue
        if _is_x_url(clean_url):
            await _handle_x_message(message, user_id, lang, clean_url)
            continue
        if not _is_long_video_site(clean_url):
            await _handle_quick_message(message, user_id, lang, clean_url)
            continue
        pending_id = await create_pending_download(user_id, clean_url)
        kb = None
        try:
            if _is_long_video_site(clean_url):
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

        spotify_files = result.get('file_paths')
        file_path = result.get('file_path')
        title = result.get('title', 'Media')
        dir_to_clean = result.get('dir_to_clean')
        duration = result.get('duration')
        try:
            size = os.path.getsize(file_path)
            logger.info("sending file=%s bytes=%s", file_path, size)
        except Exception:
            pass

        try:
            if 'spotify.com' in url and spotify_files:
                loop = asyncio.get_event_loop()
                cover_path = None
                try:
                    cover_path = os.path.join(config.download_dir, f"cover_{uuid.uuid4().hex}.jpg")
                    await loop.run_in_executor(None, extract_audio_cover, spotify_files[0], cover_path)
                    await callback.message.answer_photo(FSInputFile(cover_path), caption=title)
                except Exception:
                    cover_path = None
                finally:
                    if cover_path and os.path.exists(cover_path):
                        try:
                            os.remove(cover_path)
                        except Exception:
                            pass

                for fp in spotify_files:
                    meta = {}
                    try:
                        meta = await loop.run_in_executor(None, probe_audio, fp)
                    except Exception:
                        meta = {}
                    performer = meta.get("artist")
                    track_title = meta.get("title") or os.path.splitext(os.path.basename(fp))[0]
                    d = meta.get("duration")
                    duration_s = int(d) if d else None

                    thumb_path = None
                    try:
                        thumb_path = os.path.join(config.download_dir, f"thumb_{uuid.uuid4().hex}.jpg")
                        await loop.run_in_executor(None, extract_audio_cover, fp, thumb_path)
                    except Exception:
                        thumb_path = None

                    try:
                        kwargs = {"performer": performer, "title": track_title}
                        if duration_s:
                            kwargs["duration"] = duration_s
                        if thumb_path and os.path.exists(thumb_path):
                            kwargs["thumbnail"] = FSInputFile(thumb_path)
                        await callback.message.answer_audio(FSInputFile(fp), **{k: v for k, v in kwargs.items() if v})
                    finally:
                        if thumb_path and os.path.exists(thumb_path):
                            try:
                                os.remove(thumb_path)
                            except Exception:
                                pass

                await log_download(user_id, url, "audio")
                try:
                    await callback.message.delete()
                except Exception:
                    pass
                return

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
                        loop = asyncio.get_event_loop()
                        meta = await loop.run_in_executor(None, probe_video, file_path)
                        d = meta.get("duration")
                        if not d:
                            d = duration
                        duration_s = int(d) if d else None
                        thumb_path = None
                        try:
                            thumb_path = os.path.join(config.download_dir, f"thumb_{uuid.uuid4().hex}.jpg")
                            await loop.run_in_executor(None, extract_thumbnail, file_path, thumb_path)
                        except Exception:
                            thumb_path = None

                        try:
                            kwargs = {"supports_streaming": True}
                            if duration_s:
                                kwargs["duration"] = duration_s
                            if meta.get("width"):
                                kwargs["width"] = int(meta["width"])
                            if meta.get("height"):
                                kwargs["height"] = int(meta["height"])
                            if thumb_path and os.path.exists(thumb_path):
                                kwargs["thumbnail"] = FSInputFile(thumb_path)
                            return await callback.message.answer_video(media, caption=title, **kwargs)
                        finally:
                            if thumb_path and os.path.exists(thumb_path):
                                try:
                                    os.remove(thumb_path)
                                except Exception:
                                    pass
                    return await callback.message.answer_document(media, caption=title)

                return await asyncio.wait_for(
                    do_send(),
                    timeout=int(getattr(config, "telegram_send_timeout", 120)),
                )

            async def compress_to_limit(target_bytes: int):
                if not enable_compress:
                    return
                loop = asyncio.get_event_loop()
                try:
                    current_size_local = os.path.getsize(file_path)
                except Exception:
                    current_size_local = 0
                if not current_size_local or current_size_local <= target_bytes:
                    return
                started_c = asyncio.get_event_loop().time()
                await callback.message.edit_text(get_text(lang, 'downloading') + "\n\ncompressing…")
                compressed_path = os.path.join(config.download_dir, f"tg_{os.path.basename(file_path)}")
                timeout_s = int(getattr(config, "telegram_compress_timeout", 180))
                if download_type == "audio":
                    fut = loop.run_in_executor(
                        None,
                        compress_audio_to_size,
                        file_path,
                        compressed_path,
                        target_bytes,
                        duration,
                        timeout_s,
                    )
                else:
                    fut = loop.run_in_executor(
                        None,
                        compress_video_to_size,
                        file_path,
                        compressed_path,
                        target_bytes,
                        duration,
                        max_height,
                        timeout_s,
                    )
                while True:
                    try:
                        await asyncio.wait_for(asyncio.shield(fut), timeout=10)
                        break
                    except asyncio.TimeoutError:
                        elapsed = int(asyncio.get_event_loop().time() - started_c)
                        try:
                            await callback.message.edit_text(get_text(lang, 'downloading') + f"\n\ncompressing… {elapsed}s")
                        except Exception:
                            pass
                if os.path.exists(file_path):
                    os.remove(file_path)
                return compressed_path

            try:
                current_size = os.path.getsize(file_path)
            except Exception:
                current_size = 0
            if current_size and current_size > max_upload:
                new_path = await compress_to_limit(max_upload)
                if new_path:
                    file_path = new_path

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
                        raise RuntimeError("Telegram upload timed out")
                    if "request entity too large" in str(e).lower():
                        new_path = await compress_to_limit(fallback_upload)
                        if new_path:
                            file_path = new_path
                            await backoff_sleep(attempt)
                            continue
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
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            if dir_to_clean and os.path.exists(dir_to_clean):
                shutil.rmtree(dir_to_clean, ignore_errors=True)
    finally:
        queue_manager.release()
