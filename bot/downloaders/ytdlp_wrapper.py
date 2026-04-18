import asyncio
import copy
import os
import subprocess
import uuid
from bot.config.settings import config
import yt_dlp

async def download_media(url: str, mode: str = 'video', max_height: int | None = None) -> dict:
    # Run yt-dlp in executor to not block async loop
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _download_sync, url, mode, max_height)

def _find_downloaded_file(prefix: str) -> str | None:
    try:
        for name in os.listdir(config.download_dir):
            if name.startswith(prefix + "."):
                return os.path.join(config.download_dir, name)
    except Exception:
        return None
    return None

def _merge_extractor_args(opts: dict, extra: dict) -> None:
    existing = opts.get("extractor_args") or {}
    for extractor, extractor_args in (extra or {}).items():
        if extractor not in existing or not isinstance(existing.get(extractor), dict):
            existing[extractor] = copy.deepcopy(extractor_args)
            continue
        for key, values in (extractor_args or {}).items():
            if key not in existing[extractor] or not isinstance(existing[extractor].get(key), list):
                existing[extractor][key] = list(values)
                continue
            for v in values:
                if v not in existing[extractor][key]:
                    existing[extractor][key].append(v)
    opts["extractor_args"] = existing

def _is_youtubetab_authcheck_error(msg: str) -> bool:
    m = (msg or "").lower()
    return "playlists that require authentication" in m or "youtubetab:skip=authcheck" in m

def _ffmpeg_transcode_telegram_mp4(input_path: str, output_path: str, max_height: int | None) -> None:
    vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p"
    if max_height:
        h = int(max_height)
        vf = f"scale=-2:trunc(min({h},ih)/2)*2,format=yuv420p"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-vf",
        vf,
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        output_path,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True)

def _download_sync(url: str, mode: str, max_height: int | None) -> dict:
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
    playlist_end = int(getattr(config, "ytdlp_playlist_end", 1) or 0)
    if playlist_end > 0:
        ydl_opts["playlistend"] = playlist_end
    if getattr(config, "ytdlp_skip_youtubetab_authcheck", True):
        _merge_extractor_args(ydl_opts, {"youtubetab": {"skip": ["authcheck"]}})
    if getattr(config, "ytdlp_force_ipv4", False):
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
        if max_height:
            h = int(max_height)
            video_format = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
        else:
            video_format = 'bv*+ba/best'
        ydl_opts.update({
            'format': video_format,
        })
        
    try:
        def run_download(opts: dict) -> tuple[dict, str]:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if mode == 'audio':
                    file_path = os.path.join(config.download_dir, f'{file_id}.mp3')
                else:
                    input_path = _find_downloaded_file(file_id) or ydl.prepare_filename(info)
                    file_path = os.path.join(config.download_dir, f'{file_id}.mp4')
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    _ffmpeg_transcode_telegram_mp4(input_path, file_path, max_height)
                    if input_path != file_path and os.path.exists(input_path):
                        os.remove(input_path)
                return info, file_path

        def download_with_format_fallback(opts: dict) -> tuple[dict, str]:
            try:
                return run_download(opts)
            except yt_dlp.utils.DownloadError as e:
                msg = str(e)
                if 'Requested format is not available' not in msg:
                    raise
                fallback_opts = copy.deepcopy(opts)
                fallback_opts['format'] = 'best'
                return run_download(fallback_opts)

        try:
            info, file_path = download_with_format_fallback(ydl_opts)
        except yt_dlp.utils.DownloadError as e:
            msg = str(e)
            if _is_youtubetab_authcheck_error(msg):
                retry_opts = copy.deepcopy(ydl_opts)
                _merge_extractor_args(retry_opts, {"youtubetab": {"skip": ["authcheck"]}})
                retry_opts.pop("source_address", None)
                info, file_path = download_with_format_fallback(retry_opts)
            else:
                m = msg.lower()
                if "source_address" in ydl_opts and (
                    "unable to download webpage" in m
                    or "timed out" in m
                    or "network is unreachable" in m
                    or "connection refused" in m
                    or "name resolution" in m
                ):
                    retry_opts = copy.deepcopy(ydl_opts)
                    retry_opts.pop("source_address", None)
                    info, file_path = download_with_format_fallback(retry_opts)
                else:
                    raise

        return {
            'success': True,
            'file_path': file_path,
            'title': info.get('title', 'Unknown Title'),
            'duration': info.get('duration', 0)
        }
    except Exception as e:
        msg = str(e)
        if isinstance(e, subprocess.CalledProcessError):
            msg = (e.stderr or msg).strip() or msg
        if _is_youtubetab_authcheck_error(msg):
            msg = (
                "YouTube blocked playlist extraction (authentication/webpage check). "
                "If this playlist is private/age-restricted, the bot needs valid YouTube cookies."
            )
        return {
            'success': False,
            'error': msg
        }
