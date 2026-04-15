import os
import re
import shutil
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from bot.models.database import get_user_language, log_download, check_rate_limit, get_user_mode
from bot.utils.locales import get_text
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
        
    mode = await get_user_mode(user_id)
    
    for url in urls:
        if not await check_rate_limit(user_id, config.daily_limit):
            await message.reply(get_text(lang, 'rate_limit', limit=config.daily_limit))
            break
            
        position = await queue_manager.acquire()
        msg = await message.reply(get_text(lang, 'queued', position=position))
        
        await queue_manager.wait_and_acquire()
        
        try:
            await msg.edit_text(get_text(lang, 'downloading'))
            
            # Determine which downloader to use
            if 'spotify.com' in url:
                result = await download_spotify(url)
                download_type = 'audio'
            elif url.endswith('.mp3') or url.endswith('.mp4'):
                result = await download_direct_file(url)
                download_type = 'audio' if url.endswith('.mp3') else 'video'
            else:
                result = await download_media(url, mode)
                download_type = mode
            
            if not result['success']:
                # Fallback to direct HTTP download if yt-dlp fails and looks like a media link
                if not 'spotify.com' in url and not url.endswith(('.mp3', '.mp4')):
                    fallback_result = await download_direct_file(url)
                    if fallback_result['success']:
                        result = fallback_result
                        download_type = 'audio' if result['file_path'].endswith('.mp3') else 'video'
                
                if not result.get('success'):
                    await msg.edit_text(get_text(lang, 'error', error=result.get('error', 'Unknown Error')))
                    continue
                
            file_path = result['file_path']
            title = result.get('title', 'Media')
            dir_to_clean = result.get('dir_to_clean')
            
            try:
                if download_type == 'audio':
                    media = FSInputFile(file_path)
                    await message.reply_audio(media, caption=title)
                else:
                    media = FSInputFile(file_path)
                    await message.reply_video(media, caption=title)
                    
                await log_download(user_id, url, download_type)
                await msg.delete()
            except Exception as e:
                await msg.edit_text(get_text(lang, 'error', error=str(e)))
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)
                if dir_to_clean and os.path.exists(dir_to_clean):
                    shutil.rmtree(dir_to_clean, ignore_errors=True)
        finally:
            queue_manager.release()
