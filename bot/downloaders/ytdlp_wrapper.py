import asyncio
import copy
import logging
import os
import subprocess
import uuid
from bot.config.settings import config
import yt_dlp

logger = logging.getLogger(__name__)

async def download_media(
    url: str,
    mode: str = 'video',
    max_height: int | None = None,
    audio_bitrate_kbps: int | None = None,
    status: dict | None = None,
) -> dict:
    # Run yt-dlp in executor to not block async loop
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _download_sync, url, mode, max_height, audio_bitrate_kbps, status)

async def probe_media(url: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _probe_sync, url)

def _find_downloaded_file(prefix: str) -> str | None:
    try:
        candidates = []
        for name in os.listdir(config.download_dir):
            if not name.startswith(prefix + "."):
                continue
            if name.endswith((".part", ".ytdl", ".tmp")):
                continue
            candidates.append(name)
        candidates.sort()
        if candidates:
            return os.path.join(config.download_dir, candidates[-1])
    except Exception:
        return None
    return None

def _shorten_stderr(text: str, max_lines: int = 25) -> str:
    lines = (text or "").splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines).strip()
    return "\n".join(lines[-max_lines:]).strip()

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

def _run_ffmpeg(cmd: list[str], timeout_s: int | None) -> None:
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True, timeout=timeout_s)

def _probe_video_height(path: str) -> int | None:
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=height",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15, check=True)
        out = (p.stdout or "").strip()
        if out.isdigit():
            return int(out)
    except Exception:
        return None
    return None

def _estimate_bytes(duration: int | float | None, tbr: int | float | None) -> int | None:
    try:
        if not duration or not tbr:
            return None
        bits = float(duration) * float(tbr) * 1000.0
        return int(bits / 8.0)
    except Exception:
        return None

def _probe_sync(url: str) -> dict:
    ydl_opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "age_limit": 18,
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

    proxy = (config.ytdlp_proxy or "").strip()
    if proxy:
        ydl_opts["proxy"] = proxy
    user_agent = (config.ytdlp_user_agent or "").strip()
    if user_agent:
        ydl_opts["user_agent"] = user_agent

    if "pornhub.com" in (url or ""):
        ydl_opts["geo_bypass"] = True
        headers = dict(ydl_opts.get("http_headers") or {})
        headers.update({
            "Referer": "https://www.pornhub.com/",
            "Origin": "https://www.pornhub.com",
        })
        if user_agent:
            headers.setdefault("User-Agent", user_agent)
        ydl_opts["http_headers"] = headers
        ydl_opts["retries"] = max(int(ydl_opts.get("retries") or 0), 5)
        ydl_opts["fragment_retries"] = max(int(ydl_opts.get("fragment_retries") or 0), 5)
        ydl_opts.setdefault("sleep_interval", 1)
        ydl_opts.setdefault("max_sleep_interval", 5)
        ydl_opts.setdefault("concurrent_fragment_downloads", 4)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        duration = info.get("duration") or 0
        formats = info.get("formats") or []
        by_height: dict[int, dict] = {}
        for f in formats:
            if f.get("vcodec") in (None, "none"):
                continue
            h = f.get("height")
            if not h:
                continue
            try:
                h_int = int(h)
            except Exception:
                continue
            cur = by_height.get(h_int)
            tbr = f.get("tbr") or 0
            if not cur or float(tbr or 0) > float(cur.get("tbr") or 0):
                by_height[h_int] = f

        video_options = []
        for h, f in sorted(by_height.items(), key=lambda x: x[0], reverse=True):
            size = f.get("filesize") or f.get("filesize_approx") or _estimate_bytes(duration, f.get("tbr"))
            video_options.append({
                "height": h,
                "width": f.get("width") or 0,
                "size_bytes": int(size) if size else 0,
            })

        return {
            "success": True,
            "title": info.get("title") or "Media",
            "duration": duration,
            "video_options": video_options,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def _ffmpeg_transcode_telegram_mp4(input_path: str, output_path: str, max_height: int | None) -> None:
    if max_height:
        h0 = _probe_video_height(input_path)
        if h0 and int(h0) <= int(max_height):
            max_height = None

    base = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
        "-y",
        "-i",
        input_path,
    ]
    timeout_s = int(getattr(config, "ytdlp_overall_timeout", 1800) or 1800)
    if not max_height:
        try:
            cmd = [
                *base,
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                output_path,
            ]
            _run_ffmpeg(cmd, timeout_s=timeout_s)
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if os.path.exists(output_path):
                os.remove(output_path)

        try:
            cmd = [
                *base,
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                output_path,
            ]
            _run_ffmpeg(cmd, timeout_s=timeout_s)
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if os.path.exists(output_path):
                os.remove(output_path)

    vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p"
    if max_height:
        h = int(max_height)
        vf = f"scale=-2:trunc(min({h}\\,ih)/2)*2,format=yuv420p"
    cmd = [
        *base,
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
    _run_ffmpeg(cmd, timeout_s=timeout_s)

def _download_sync(url: str, mode: str, max_height: int | None, audio_bitrate_kbps: int | None, status: dict | None) -> dict:
    os.makedirs(config.download_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    logger.info("download start mode=%s max_height=%s audio_kbps=%s url=%s", mode, max_height, audio_bitrate_kbps, url)
    if status is not None:
        status["phase"] = "init"
        status["detail"] = ""
        status["progress"] = ""
    
    ydl_opts = {
        'outtmpl': os.path.join(config.download_dir, f'{file_id}.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'age_limit': 18,
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

    if "pornhub.com" in (url or ""):
        ydl_opts["geo_bypass"] = True
        headers = dict(ydl_opts.get("http_headers") or {})
        headers.update({
            "Referer": "https://www.pornhub.com/",
            "Origin": "https://www.pornhub.com",
        })
        if user_agent:
            headers.setdefault("User-Agent", user_agent)
        ydl_opts["http_headers"] = headers
        ydl_opts["retries"] = max(int(ydl_opts.get("retries") or 0), 5)
        ydl_opts["fragment_retries"] = max(int(ydl_opts.get("fragment_retries") or 0), 5)
        ydl_opts.setdefault("sleep_interval", 1)
        ydl_opts.setdefault("max_sleep_interval", 5)
        ydl_opts.setdefault("concurrent_fragment_downloads", 4)
    
    if mode == 'audio':
        bitrate = int(audio_bitrate_kbps or 192)
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': str(bitrate),
            }],
        })
    else:
        if max_height:
            h = int(max_height)
            video_format = f"bestvideo[height<={h}][ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[height<={h}][ext=mp4]/best[height<={h}]/best"
        else:
            video_format = 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        ydl_opts.update({
            'format': video_format,
        })
        
    try:
        def progress_hook(d: dict) -> None:
            if status is None:
                return
            st = d.get("status")
            if st == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                if total:
                    pct = int(downloaded * 100 / total)
                    status["progress"] = f"{pct}%"
                else:
                    status["progress"] = ""
                status["phase"] = "downloading"
            elif st == "finished":
                status["phase"] = "processing"
                status["progress"] = ""

        ydl_opts["progress_hooks"] = [progress_hook]

        def run_download(opts: dict) -> tuple[dict, str]:
            if status is not None:
                status["phase"] = "extracting"
                status["detail"] = "yt-dlp"
                status["progress"] = ""
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if mode == 'audio':
                    file_path = os.path.join(config.download_dir, f'{file_id}.mp3')
                else:
                    input_path = _find_downloaded_file(file_id) or ydl.prepare_filename(info)
                    temp_out = os.path.join(config.download_dir, f'{file_id}.tg.mp4')
                    file_path = os.path.join(config.download_dir, f'{file_id}.mp4')
                    if os.path.exists(temp_out):
                        os.remove(temp_out)
                    if status is not None:
                        status["phase"] = "processing"
                        status["detail"] = "ffmpeg"
                        status["progress"] = ""
                    _ffmpeg_transcode_telegram_mp4(input_path, temp_out, max_height)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    os.rename(temp_out, file_path)
                    if input_path not in (file_path, temp_out) and os.path.exists(input_path):
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
            msg = _shorten_stderr(e.stderr or msg) or msg
        if isinstance(e, subprocess.TimeoutExpired):
            msg = "Processing timed out. Try a lower quality."
        if _is_youtubetab_authcheck_error(msg):
            msg = (
                "YouTube blocked playlist extraction (authentication/webpage check). "
                "If this playlist is private/age-restricted, the bot needs valid YouTube cookies."
            )
        logger.exception("download failed")
        return {
            'success': False,
            'error': msg
        }
