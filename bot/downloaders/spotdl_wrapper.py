import asyncio
import os
import uuid
import shutil
from bot.config.settings import config

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
        
        # Cleanup on failure
        shutil.rmtree(unique_dir, ignore_errors=True)
        return {'success': False, 'error': stderr.decode('utf-8') or 'Spotify download failed'}
    
    except Exception as e:
        shutil.rmtree(unique_dir, ignore_errors=True)
        return {'success': False, 'error': str(e)}
