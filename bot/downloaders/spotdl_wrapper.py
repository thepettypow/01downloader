import asyncio
import logging
import os
import uuid
import shutil
from bot.config.settings import config

logger = logging.getLogger(__name__)

def _find_cookie_file() -> str | None:
    cookie_file = (getattr(config, "ytdlp_cookie_file", None) or "").strip()
    candidates = []
    if cookie_file:
        candidates.append(cookie_file)
        candidates.append(os.path.join("/app/data", os.path.basename(cookie_file)))
    candidates.append("/app/data/cookies.txt")
    candidates.append("data/cookies.txt")
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None

async def download_spotify(url: str) -> dict:
    os.makedirs(config.download_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    unique_dir = os.path.join(config.download_dir, file_id)
    os.makedirs(unique_dir, exist_ok=True)
    
    try:
        spotdl_bin = "/opt/spotdl/bin/spotdl"
        if not os.path.exists(spotdl_bin):
            spotdl_bin = "spotdl"
        args = [
            spotdl_bin,
            "download",
            url,
            "--output", f"{unique_dir}/{{title}} - {{artist}}.{{ext}}",
            "--format", "mp3",
            "--print-errors",
            "--log-level",
            "ERROR",
        ]
        client_id = (getattr(config, "spotdl_client_id", None) or "").strip()
        client_secret = (getattr(config, "spotdl_client_secret", None) or "").strip()
        if client_id and client_secret:
            args += ["--client-id", client_id, "--client-secret", client_secret]
        cookie_path = _find_cookie_file()
        if cookie_path:
            args += ["--cookie-file", cookie_path]
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=int(getattr(config, "spotdl_timeout", 900)))
        except asyncio.TimeoutError:
            try:
                process.kill()
            except Exception:
                pass
            await process.wait()
            shutil.rmtree(unique_dir, ignore_errors=True)
            return {'success': False, 'error': 'Spotify download timed out. If this is YouTube blocking, add valid cookies.txt for music.youtube.com.'}
        
        if process.returncode == 0:
            files = sorted([f for f in os.listdir(unique_dir) if f.lower().endswith(".mp3")])
            if files:
                file_paths = [os.path.join(unique_dir, f) for f in files]
                return {
                    'success': True, 
                    'file_paths': file_paths,
                    'title': os.path.splitext(files[0])[0], 
                    'dir_to_clean': unique_dir
                }
        
        err = (stderr.decode('utf-8', errors='ignore') if stderr else '') or ''
        out = (stdout.decode('utf-8', errors='ignore') if stdout else '') or ''
        logger.error("spotdl failed rc=%s url=%s stderr=%s stdout=%s", process.returncode, url, err.strip()[:1200], out.strip()[:1200])

        # Cleanup on failure
        shutil.rmtree(unique_dir, ignore_errors=True)
        msg = (err or out or '').strip()
        if not msg:
            msg = "Spotify download failed with no error output."
            if not (client_id and client_secret):
                msg += "\n\nSet SPOTDL_CLIENT_ID and SPOTDL_CLIENT_SECRET (Spotify API app creds)."
        if "client id" in msg.lower() or "client secret" in msg.lower() or "spotipy" in msg.lower():
            msg = msg + "\n\nSet SPOTDL_CLIENT_ID and SPOTDL_CLIENT_SECRET (Spotify API app creds)."
        if "active premium subscription required for the owner of the app" in msg.lower():
            msg = (
                "Spotify API rejected the request: Premium subscription is required for the Spotify account that owns the Developer App.\n\n"
                "Fix:\n"
                "1) Upgrade the app owner account to Spotify Premium\n"
                "2) Wait a few hours for Spotify to propagate the subscription change\n"
                "3) If it still fails, rotate the app Client Secret and update SPOTDL_CLIENT_SECRET"
            )
        if "sign in to confirm you're not a bot" in msg.lower() or "sign in to confirm you’re not a bot" in msg.lower():
            msg = msg + "\n\nYouTube is blocking downloads. Add cookies.txt for music.youtube.com (spotdl --cookie-file)."
        return {'success': False, 'error': msg}
    
    except Exception as e:
        logger.exception("spotdl exception url=%s", url)
        shutil.rmtree(unique_dir, ignore_errors=True)
        return {'success': False, 'error': str(e)}
