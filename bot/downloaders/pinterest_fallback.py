import aiohttp
import aiofiles
import os
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
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(oembed, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return {"success": False, "error": f"Pinterest oEmbed HTTP {resp.status}"}
                data = await resp.json(content_type=None)
            img = (data or {}).get("thumbnail_url") or ""
            title = (data or {}).get("title") or ""
            if not img:
                return {"success": False, "error": "Pinterest oEmbed: no thumbnail_url"}
            async with session.get(img, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=90)) as r2:
                if r2.status != 200:
                    return {"success": False, "error": f"Pinterest image HTTP {r2.status}"}
                ext = _guess_ext(r2.headers.get("Content-Type", ""), img)
                fp = os.path.join(config.download_dir, f"{uuid.uuid4().hex}.{ext}")
                async with aiofiles.open(fp, "wb") as f:
                    async for chunk in r2.content.iter_chunked(1024 * 256):
                        await f.write(chunk)
            return {"success": True, "file_paths": [fp], "caption": title}
    except Exception as e:
        return {"success": False, "error": str(e)}
