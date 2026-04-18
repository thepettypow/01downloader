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
    remote_components = (getattr(config, "ytdlp_remote_components", "") or "").strip()
    if remote_components:
        ydl_opts["remote_components"] = {c.strip() for c in remote_components.split(",") if c.strip()}

    ydl_opts["js_runtimes"] = {"deno": {}}
    ydl_opts["socket_timeout"] = getattr(config, "ytdlp_socket_timeout", 20)
    ydl_opts["retries"] = getattr(config, "ytdlp_retries", 3)
    ydl_opts["fragment_retries"] = getattr(config, "ytdlp_retries", 3)
    if getattr(config, "ytdlp_skip_youtubetab_authcheck", True):
        ydl_opts["extractor_args"] = {"youtubetab": {"skip": ["authcheck"]}}
    if getattr(config, "ytdlp_force_ipv4", True):
        ydl_opts["source_address"] = "0.0.0.0"
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
        })
        
    try:
        def run_download(opts: dict) -> tuple[dict, str]:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if mode == 'audio':
                    file_path = os.path.join(config.download_dir, f'{file_id}.mp3')
                else:
                    file_path = _find_downloaded_file(file_id) or ydl.prepare_filename(info)
                return info, file_path

        try:
            info, file_path = run_download(ydl_opts)
        except yt_dlp.utils.DownloadError as e:
            msg = str(e)
            if 'Requested format is not available' not in msg:
                raise
            fallback_opts = dict(ydl_opts)
            fallback_opts['format'] = 'best'
            info, file_path = run_download(fallback_opts)

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
