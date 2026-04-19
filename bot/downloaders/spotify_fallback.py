import asyncio
import json
import os
import re
import uuid
import html as _html
import aiohttp

from bot.config.settings import config
from bot.downloaders.ytdlp_wrapper import download_media

_NEXT_DATA_RE = re.compile(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_META_OG_RE = re.compile(r'<meta[^>]+property="og:(title|image)"[^>]+content="([^"]+)"', re.IGNORECASE)
_TRACK_ANCHOR_RE = re.compile(r'href="/track/([A-Za-z0-9]+)[^"]*"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_ARTIST_ANCHOR_RE = re.compile(r'href="/artist/([A-Za-z0-9]+)[^"]*"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")

def _dedupe_tracks(tracks: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for t in tracks:
        name = (t.get("title") or "").strip()
        artist = (t.get("artist") or "").strip()
        key = (name.lower(), artist.lower())
        if not name:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out

def _strip_tags(s: str) -> str:
    s = _TAG_RE.sub("", s or "")
    s = _html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _clean_og_title(t: str) -> str:
    t = (t or "").strip()
    if " | Spotify" in t:
        t = t.split(" | Spotify", 1)[0].strip()
    return t

def _parse_html_tracklist(html: str) -> dict:
    og = {k.lower(): v for (k, v) in _META_OG_RE.findall(html or "")}
    title = _clean_og_title(og.get("title") or "")
    cover_url = og.get("image")

    tracks: list[dict] = []
    for m in _TRACK_ANCHOR_RE.finditer(html or ""):
        track_title = _strip_tags(m.group(2))
        if not track_title:
            continue
        tail = (html or "")[m.end() : m.end() + 1200]
        am = _ARTIST_ANCHOR_RE.search(tail)
        artist = _strip_tags(am.group(2)) if am else None
        if artist:
            artist = re.sub(r"^\s*E\s*", "", artist).strip()
        tracks.append({"title": track_title, "artist": artist, "album": title or None})

    tracks = _dedupe_tracks(tracks)
    return {"success": True, "title": title or None, "cover_url": cover_url, "tracks": tracks}

def _collect_tracks(obj, out: list[dict], album_name: str | None):
    if isinstance(obj, dict):
        t = obj.get("type") or obj.get("__typename")
        if (t == "track" or t == "Track") and obj.get("name"):
            artists = obj.get("artists") or obj.get("artist") or []
            names = []
            if isinstance(artists, list):
                for a in artists:
                    if isinstance(a, dict) and a.get("name"):
                        names.append(a["name"])
            elif isinstance(artists, dict) and artists.get("name"):
                names.append(artists["name"])
            out.append({
                "title": obj.get("name"),
                "artist": ", ".join(names) if names else None,
                "album": album_name,
            })
        if "track" in obj and isinstance(obj["track"], dict):
            _collect_tracks(obj["track"], out, album_name)
        for v in obj.values():
            _collect_tracks(v, out, album_name)
    elif isinstance(obj, list):
        for v in obj:
            _collect_tracks(v, out, album_name)

def _find_album_name(obj) -> str | None:
    if isinstance(obj, dict):
        t = obj.get("type") or obj.get("__typename")
        if t in ("album", "Album") and obj.get("name"):
            return obj.get("name")
        for v in obj.values():
            r = _find_album_name(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_album_name(v)
            if r:
                return r
    return None

def _find_best_image(obj) -> str | None:
    best = None
    best_w = -1
    def walk(x):
        nonlocal best, best_w
        if isinstance(x, dict):
            if "images" in x and isinstance(x["images"], list):
                for im in x["images"]:
                    if not isinstance(im, dict):
                        continue
                    url = im.get("url")
                    w = im.get("width") or 0
                    if url and int(w or 0) >= best_w:
                        best_w = int(w or 0)
                        best = url
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(obj)
    return best

async def _http_get_json(url: str) -> dict | None:
    timeout = aiohttp.ClientTimeout(total=20)
    headers = {
        "User-Agent": (config.ytdlp_user_agent or "Mozilla/5.0").strip() or "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(url, allow_redirects=True) as resp:
            if resp.status != 200:
                return None
            return await resp.json()

async def _http_get_text(url: str) -> str | None:
    timeout = aiohttp.ClientTimeout(total=25)
    headers = {
        "User-Agent": (config.ytdlp_user_agent or "Mozilla/5.0").strip() or "Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(url, allow_redirects=True) as resp:
            if resp.status != 200:
                return None
            return await resp.text()

async def resolve_spotify_url(url: str) -> str:
    timeout = aiohttp.ClientTimeout(total=20)
    headers = {
        "User-Agent": (config.ytdlp_user_agent or "Mozilla/5.0").strip() or "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(url, allow_redirects=True) as resp:
            return str(resp.url)

async def fetch_spotify_oembed(url: str) -> dict | None:
    oembed_url = "https://open.spotify.com/oembed?url=" + aiohttp.helpers.quote(url, safe="")
    return await _http_get_json(oembed_url)

async def scrape_tracklist(url: str) -> dict:
    html = await _http_get_text(url)
    if not html:
        return {"success": False, "error": "Unable to load Spotify page"}
    m = _NEXT_DATA_RE.search(html)
    if not m:
        parsed = _parse_html_tracklist(html)
        if parsed.get("tracks"):
            return parsed
        return {"success": False, "error": "Unable to parse Spotify page"}
    try:
        data = json.loads(m.group(1))
    except Exception:
        parsed = _parse_html_tracklist(html)
        if parsed.get("tracks"):
            return parsed
        return {"success": False, "error": "Unable to decode Spotify page data"}

    album_name = _find_album_name(data)
    tracks: list[dict] = []
    _collect_tracks(data, tracks, album_name)
    tracks = _dedupe_tracks(tracks)
    cover_url = _find_best_image(data)
    if not tracks:
        parsed = _parse_html_tracklist(html)
        if parsed.get("tracks"):
            return parsed
    return {"success": True, "title": album_name, "cover_url": cover_url, "tracks": tracks}

async def _download_cover(cover_url: str) -> str | None:
    if not cover_url:
        return None
    os.makedirs(config.download_dir, exist_ok=True)
    out_path = os.path.join(config.download_dir, f"cover_{uuid.uuid4().hex}.jpg")
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {"User-Agent": (config.ytdlp_user_agent or "Mozilla/5.0").strip() or "Mozilla/5.0"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(cover_url, allow_redirects=True) as resp:
            if resp.status != 200:
                return None
            with open(out_path, "wb") as f:
                while True:
                    chunk = await resp.content.read(1024 * 64)
                    if not chunk:
                        break
                    f.write(chunk)
    return out_path if os.path.exists(out_path) else None

async def download_spotify_fallback(url: str, max_tracks: int = 50) -> dict:
    url = await resolve_spotify_url(url)
    oembed = await fetch_spotify_oembed(url)
    cover_url = (oembed or {}).get("thumbnail_url")
    title = (oembed or {}).get("title") or "Spotify"

    tracks: list[dict] = []
    if "/track/" in url:
        tracks = [{"title": title, "artist": (oembed or {}).get("author_name"), "album": None}]
    else:
        scraped = await scrape_tracklist(url)
        if scraped.get("success") and scraped.get("tracks"):
            tracks = scraped["tracks"]
            title = scraped.get("title") or title
            cover_url = scraped.get("cover_url") or cover_url
        else:
            return {"success": False, "error": scraped.get("error") or "Unable to extract Spotify track list"}

    tracks = tracks[:max_tracks]
    if not tracks:
        return {"success": False, "error": "No tracks found"}

    cover_path = await _download_cover(cover_url) if cover_url else None

    file_paths: list[str] = []
    for t in tracks:
        q_artist = (t.get("artist") or "").strip()
        q_title = (t.get("title") or "").strip()
        query = f"{q_artist} - {q_title}".strip(" -")
        y = await download_media(f"ytsearch1:{query}", mode="audio", audio_bitrate_kbps=192)
        if not y.get("success"):
            continue
        file_paths.append(y["file_path"])

    if not file_paths:
        if cover_path and os.path.exists(cover_path):
            os.remove(cover_path)
        return {"success": False, "error": "No matches found on YouTube"}

    return {
        "success": True,
        "file_paths": file_paths,
        "title": title,
        "cover_path": cover_path,
        "tracks": tracks,
    }
