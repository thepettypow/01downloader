import asyncio
import copy
import logging
import os
import subprocess
import uuid
from urllib.parse import urlparse
from bot.config.settings import config
from bot.utils.round_robin import rotate as _round_robin_rotate
import yt_dlp

logger = logging.getLogger(__name__)

def _split_list(value: str | None) -> list[str]:
    items = []
    for raw in (value or "").split(","):
        s = (raw or "").strip()
        if s:
            items.append(s)
    return items

def _is_youtube_url(u: str) -> bool:
    try:
        host = (urlparse(u).netloc or "").lower()
    except Exception:
        host = ""
    return ("youtube.com" in host) or ("youtu.be" in host)

def _is_youtube_login_block(msg: str) -> bool:
    m = (msg or "").lower()
    return (
        "sign in to confirm you" in m
        or "confirm you’re not a bot" in m
        or "confirm you're not a bot" in m
        or "login_required" in m
    )

def _youtube_player_clients_from_config() -> list[str]:
    raw = (getattr(config, "ytdlp_youtube_player_clients", "") or "").strip()
    out = []
    for p in (raw or "").split(","):
        s = (p or "").strip()
        if s:
            out.append(s)
    return out or ["mweb", "web_safari", "android", "ios", "web"]

def _apply_youtube_hardening(ydl_opts: dict, url: str) -> None:
    if not _is_youtube_url(url):
        return
    _merge_extractor_args(ydl_opts, {"youtube": {"player_client": _youtube_player_clients_from_config()}})
    pot_base = (getattr(config, "ytdlp_youtube_pot_base_url", None) or "").strip()
    if pot_base:
        _merge_extractor_args(ydl_opts, {"youtubepot-bgutilhttp": {"base_url": [pot_base]}})
    ydl_opts.setdefault("sleep_interval", 1)
    ydl_opts.setdefault("max_sleep_interval", 3)
    ydl_opts.setdefault("sleep_interval_requests", 1)
    ydl_opts.setdefault("concurrent_fragment_downloads", 1)
    ydl_opts.setdefault("http_chunk_size", 10 * 1024 * 1024)
    if not (ydl_opts.get("user_agent") or "").strip():
        ydl_opts["user_agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    headers = dict(ydl_opts.get("http_headers") or {})
    headers.setdefault("Accept-Language", "en-US,en;q=0.9")
    if (ydl_opts.get("user_agent") or "").strip():
        headers.setdefault("User-Agent", str(ydl_opts["user_agent"]))
    ydl_opts["http_headers"] = headers

def _cookiefile_candidates() -> list[str]:
    candidates = []
    cookie_file = (config.ytdlp_cookie_file or "").strip()
    if cookie_file:
        candidates.append(cookie_file)
        candidates.append(os.path.join("/app/data", os.path.basename(cookie_file)))
    candidates.append("/app/data/cookies.txt")
    candidates.append("data/cookies.txt")

    cookie_dir = (getattr(config, "ytdlp_cookie_dir", "") or "").strip()
    if cookie_dir and os.path.isdir(cookie_dir):
        try:
            for name in sorted(os.listdir(cookie_dir)):
                if not name.lower().endswith(".txt"):
                    continue
                candidates.append(os.path.join(cookie_dir, name))
        except Exception:
            pass

    out = []
    seen = set()
    for c in candidates:
        if not c or c in seen:
            continue
        seen.add(c)
        if os.path.exists(c):
            out.append(c)
    return out

def _cookiefile_candidates_rotated() -> list[str]:
    return _round_robin_rotate(_cookiefile_candidates())

def _proxy_candidates_for_url(url: str) -> list[str]:
    proxies = []
    if _is_youtube_url(url):
        yt_proxy = (getattr(config, "ytdlp_youtube_proxy", "") or "").strip()
        if yt_proxy:
            proxies.append(yt_proxy)
        proxies.extend(_split_list(getattr(config, "ytdlp_youtube_proxy_list", None)))

    proxies.extend(_split_list(getattr(config, "ytdlp_proxy_list", None)))
    base_proxy = (config.ytdlp_proxy or "").strip()
    if base_proxy:
        proxies.append(base_proxy)

    out = []
    seen = set()
    for p in proxies:
        s = (p or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out

def _cookiefile_has_youtube_cookies(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                s = (line or "").lower()
                if not s or s.startswith("#"):
                    continue
                if "\tyoutube.com\t" in s or "\t.google.com\t" in s or "\taccounts.google.com\t" in s:
                    return True
                if s.startswith("youtube.com\t") or s.startswith(".youtube.com\t"):
                    return True
                if s.startswith("google.com\t") or s.startswith(".google.com\t"):
                    return True
                if s.startswith("accounts.google.com\t") or s.startswith(".accounts.google.com\t"):
                    return True
    except Exception:
        return False
    return False

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

    proxies = _proxy_candidates_for_url(url)
    if proxies:
        ydl_opts["proxy"] = proxies[0]
    user_agent = (config.ytdlp_user_agent or "").strip()
    if user_agent:
        ydl_opts["user_agent"] = user_agent
    _apply_youtube_hardening(ydl_opts, url)

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
    cookies_from_browser = (getattr(config, "ytdlp_cookies_from_browser", "") or "").strip()
    if cookies_from_browser:
        parts = [p.strip() for p in cookies_from_browser.split(":", 1)]
        browser = parts[0]
        profile = parts[1] if len(parts) > 1 and parts[1] else None
        ydl_opts["cookiesfrombrowser"] = (browser, profile) if profile else (browser,)
    user_agent = (config.ytdlp_user_agent or "").strip()
    if user_agent:
        ydl_opts['user_agent'] = user_agent
    _apply_youtube_hardening(ydl_opts, url)

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

        def attempt_download(base_opts: dict, cookiefile: str | None, proxy: str | None) -> tuple[dict, str]:
            opts = copy.deepcopy(base_opts)
            if cookiefile:
                opts["cookiefile"] = cookiefile
            else:
                opts.pop("cookiefile", None)
            if proxy:
                opts["proxy"] = proxy
            else:
                opts.pop("proxy", None)
            return download_with_format_fallback(opts)

        try:
            info, file_path = attempt_download(ydl_opts, None, (_proxy_candidates_for_url(url) or [None])[0])
        except yt_dlp.utils.DownloadError as e:
            msg = str(e)
            if _is_youtubetab_authcheck_error(msg):
                retry_opts = copy.deepcopy(ydl_opts)
                _merge_extractor_args(retry_opts, {"youtubetab": {"skip": ["authcheck"]}})
                retry_opts.pop("source_address", None)
                info, file_path = attempt_download(retry_opts, None, (_proxy_candidates_for_url(url) or [None])[0])
            else:
                m = msg.lower()
                if _is_youtube_login_block(msg) and _is_youtube_url(url):
                    cookiefiles = _cookiefile_candidates_rotated()
                    proxies = _proxy_candidates_for_url(url)
                    max_tries = int(getattr(config, "ytdlp_youtube_login_retries", 3) or 0)
                    max_tries = max(1, max_tries)
                    tried = 0
                    last_e = e
                    for proxy in (proxies or [None]):
                        for cookiefile in (cookiefiles or [None]):
                            tried += 1
                            try:
                                info, file_path = attempt_download(ydl_opts, cookiefile, proxy)
                                last_e = None
                                break
                            except yt_dlp.utils.DownloadError as e2:
                                last_e = e2
                                if not _is_youtube_login_block(str(e2)):
                                    raise
                            if tried >= max_tries and max_tries > 0:
                                break
                        if last_e is None:
                            break
                        if tried >= max_tries and max_tries > 0:
                            break
                    if last_e is not None:
                        raise last_e
                elif "source_address" in ydl_opts and (
                    "unable to download webpage" in m
                    or "timed out" in m
                    or "network is unreachable" in m
                    or "connection refused" in m
                    or "name resolution" in m
                ):
                    retry_opts = copy.deepcopy(ydl_opts)
                    retry_opts.pop("source_address", None)
                    info, file_path = attempt_download(retry_opts, None, (_proxy_candidates_for_url(url) or [None])[0])
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
        if "sign in to confirm you’re not a bot" in msg.lower() or "sign in to confirm you're not a bot" in msg.lower():
            cookiefile = (ydl_opts or {}).get("cookiefile")
            cookie_hint = ""
            try:
                if cookiefile and os.path.exists(str(cookiefile)) and not _cookiefile_has_youtube_cookies(str(cookiefile)):
                    cookie_hint = " Current cookies.txt does not include youtube.com/google.com cookies."
            except Exception:
                cookie_hint = ""
            msg = (
                "YouTube requires verification (anti-bot). "
                "Add a valid cookies.txt (YTDLP_COOKIE_FILE) or set YTDLP_COOKIES_FROM_BROWSER."
                + cookie_hint
            )
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
