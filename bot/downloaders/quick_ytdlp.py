import copy
import os
import uuid
import yt_dlp

from bot.config.settings import config
from bot.downloaders.ytdlp_wrapper import _merge_extractor_args, _cookiefile_has_youtube_cookies

def _list_media_files(dir_path: str) -> list[str]:
    files = []
    for name in os.listdir(dir_path):
        if name.endswith((".part", ".ytdl", ".tmp", ".info.json")):
            continue
        files.append(os.path.join(dir_path, name))
    files.sort()
    return files

def quick_download(url: str) -> dict:
    os.makedirs(config.download_dir, exist_ok=True)
    dl_id = uuid.uuid4().hex
    unique_dir = os.path.join(config.download_dir, dl_id)
    os.makedirs(unique_dir, exist_ok=True)

    ydl_opts: dict = {
        "outtmpl": os.path.join(unique_dir, "%(title).150B_%(id)s.%(ext)s"),
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
            ydl_opts["cookiefile"] = candidate
            break

    cookies_from_browser = (getattr(config, "ytdlp_cookies_from_browser", "") or "").strip()
    if cookies_from_browser:
        parts = [p.strip() for p in cookies_from_browser.split(":", 1)]
        browser = parts[0]
        profile = parts[1] if len(parts) > 1 and parts[1] else None
        ydl_opts["cookiesfrombrowser"] = (browser, profile) if profile else (browser,)

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

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        files = _list_media_files(unique_dir)
        caption = (info.get("description") or info.get("title") or "").strip()
        return {"success": True, "file_paths": files, "caption": caption, "dir_to_clean": unique_dir}
    except Exception as e:
        msg = str(e)
        m = msg.lower()
        if "sign in to confirm you’re not a bot" in m or "sign in to confirm you're not a bot" in m:
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
        try:
            for f in _list_media_files(unique_dir):
                try:
                    os.remove(f)
                except Exception:
                    pass
            try:
                os.rmdir(unique_dir)
            except Exception:
                pass
        except Exception:
            pass
        return {"success": False, "error": msg}
