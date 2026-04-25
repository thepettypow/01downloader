import aiohttp
import aiofiles
import os
import re
import uuid
from urllib.parse import quote_plus

from bot.config.settings import config


def _guess_ext(content_type: str, url: str) -> str:
    ct = (content_type or "").lower()
    if "png" in ct:
        return "png"
    if "webp" in ct:
        return "webp"
    if "jpeg" in ct or "jpg" in ct:
        return "jpg"
    u = (url or "").lower()
    for ext in ("jpg", "jpeg", "png", "webp"):
        if f".{ext}" in u:
            return "jpg" if ext == "jpeg" else ext
    return "jpg"

def _extract_meta_image(html: str) -> str:
    s = html or ""
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, s, flags=re.IGNORECASE)
        if m and m.group(1):
            return m.group(1).strip()
    return ""

def _image_url_candidates(url: str) -> list[str]:
    u = (url or "").strip()
    if not u:
        return []
    candidates = [u]
    for size in ("originals", "736x", "564x"):
        candidates.append(re.sub(r"/\d+x/", f"/{size}/", u))
    out = []
    seen = set()
    for c in candidates:
        s = (c or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out

async def download_pinterest_images(url: str) -> dict:
    os.makedirs(config.download_dir, exist_ok=True)
    oembed = f"https://www.pinterest.com/oembed.json?url={quote_plus(url)}"
    try:
        user_agent = (getattr(config, "ytdlp_user_agent", None) or "").strip() or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        headers = {
            "User-Agent": user_agent,
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        unique_dir = os.path.join(config.download_dir, uuid.uuid4().hex)
        os.makedirs(unique_dir, exist_ok=True)
        async with aiohttp.ClientSession(headers=headers) as session:
            img = ""
            title = ""
            async with session.get(oembed, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    img = (data or {}).get("thumbnail_url") or ""
                    title = (data or {}).get("title") or ""
                else:
                    title = ""
            if not img:
                async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=30)) as resp2:
                    if resp2.status != 200:
                        return {"success": False, "error": f"Pinterest HTML HTTP {resp2.status}"}
                    html = await resp2.text(errors="ignore")
                img = _extract_meta_image(html)
                if not img:
                    return {"success": False, "error": "Pinterest HTML: no og:image"}
            last_status = None
            last_url = None
            for img_url in _image_url_candidates(img):
                last_url = img_url
                async with session.get(img_url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=90)) as r2:
                    last_status = r2.status
                    if r2.status != 200:
                        continue
                    ext = _guess_ext(r2.headers.get("Content-Type", ""), img_url)
                    fp = os.path.join(unique_dir, f"{uuid.uuid4().hex}.{ext}")
                    async with aiofiles.open(fp, "wb") as f:
                        async for chunk in r2.content.iter_chunked(1024 * 256):
                            await f.write(chunk)
                    return {"success": True, "file_paths": [fp], "caption": title, "dir_to_clean": unique_dir}
            return {"success": False, "error": f"Pinterest image HTTP {last_status} ({last_url})"}
    except Exception as e:
        return {"success": False, "error": str(e)}
