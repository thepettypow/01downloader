import asyncio
import os
import uuid
from bot.config.settings import config
import yt_dlp

async def download_media(url: str, mode: str = 'video') -> dict:
    # Run yt-dlp in executor to not block async loop
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _download_sync, url, mode)

def _find_downloaded_file(prefix: str) -> str | None:
    try:
        for name in os.listdir(config.download_dir):
            if name.startswith(prefix + "."):
                return os.path.join(config.download_dir, name)
    except Exception:
        return None
    return None

def _download_sync(url: str, mode: str) -> dict:
    os.makedirs(config.download_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    
    ydl_opts = {
        'outtmpl': os.path.join(config.download_dir, f'{file_id}.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 2000000000, # 2GB
    }
    cookie_file = (config.ytdlp_cookie_file or "").strip()
    cookie_candidates = []
    if cookie_file:
        cookie_candidates.append(cookie_file)
        cookie_candidates.append(os.path.join("/app/data", os.path.basename(cookie_file)))
    cookie_candidates.append("/app/data/cookies.txt")
    cookie_candidates.append("data/cookies.txt")
    for candidate in cookie_candidates:
        if candidate and os.path.exists(candidate):
            ydl_opts['cookiefile'] = candidate
            break
    proxy = (config.ytdlp_proxy or "").strip()
    if proxy:
        ydl_opts['proxy'] = proxy
    user_agent = (config.ytdlp_user_agent or "").strip()
    if user_agent:
        ydl_opts['user_agent'] = user_agent
    
    if mode == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        ydl_opts.update({
            'format': 'bv*+ba/best',
            'merge_output_format': 'mp4',
        })
        
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if mode == 'audio':
                file_path = os.path.join(config.download_dir, f'{file_id}.mp3')
            else:
                file_path = _find_downloaded_file(file_id) or ydl.prepare_filename(info)
            
            return {
                'success': True,
                'file_path': file_path,
                'title': info.get('title', 'Unknown Title'),
                'duration': info.get('duration', 0)
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
