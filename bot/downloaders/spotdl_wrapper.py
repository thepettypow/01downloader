import asyncio
import logging
import os
import uuid
import shutil
from bot.config.settings import config

logger = logging.getLogger(__name__)

async def download_spotify(url: str) -> dict:
    os.makedirs(config.download_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    unique_dir = os.path.join(config.download_dir, file_id)
    os.makedirs(unique_dir, exist_ok=True)
    
    try:
        spotdl_bin = "/opt/spotdl/bin/spotdl"
        if not os.path.exists(spotdl_bin):
            spotdl_bin = "spotdl"
        process = await asyncio.create_subprocess_exec(
            spotdl_bin, "download", url,
            "--output", f"{unique_dir}/{{title}} - {{artist}}.{{ext}}",
            "--format", "mp3",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
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
        logger.error("spotdl failed rc=%s url=%s stderr=%s", process.returncode, url, err.strip()[:2000])

        # Cleanup on failure
        shutil.rmtree(unique_dir, ignore_errors=True)
        msg = (err or out or 'Spotify download failed').strip()
        if "client id" in msg.lower() or "client secret" in msg.lower() or "spotipy" in msg.lower():
            msg = msg + "\n\nSet SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET in your environment."
        return {'success': False, 'error': msg}
    
    except Exception as e:
        logger.exception("spotdl exception url=%s", url)
        shutil.rmtree(unique_dir, ignore_errors=True)
        return {'success': False, 'error': str(e)}
