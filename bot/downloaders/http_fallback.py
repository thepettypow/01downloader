import asyncio
import aiohttp
import aiofiles
import os
import subprocess
import uuid
from bot.config.settings import config

def _ffmpeg_fix_mp4(input_path: str, output_path: str) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
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
        "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        output_path,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True)

async def download_direct_file(url: str) -> dict:
    os.makedirs(config.download_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=True) as response:
                if response.status != 200:
                    return {'success': False, 'error': f'HTTP Error {response.status}'}
                
                content_type = response.headers.get('Content-Type', '')
                if 'audio' not in content_type and 'video' not in content_type:
                    return {'success': False, 'error': 'Link does not point to direct audio/video media'}
                
                ext = 'mp3' if 'audio' in content_type else 'mp4'
                file_path = os.path.join(config.download_dir, f'{file_id}.{ext}')
                
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        await f.write(chunk)

                if ext == "mp4":
                    fixed_path = os.path.join(config.download_dir, f'{file_id}.fixed.mp4')
                    loop = asyncio.get_event_loop()
                    try:
                        await loop.run_in_executor(None, _ffmpeg_fix_mp4, file_path, fixed_path)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        file_path = os.path.join(config.download_dir, f'{file_id}.mp4')
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        os.rename(fixed_path, file_path)
                    except subprocess.CalledProcessError as e:
                        if os.path.exists(fixed_path):
                            os.remove(fixed_path)
                        return {'success': False, 'error': (e.stderr or str(e)).strip() or str(e)}
                        
                return {
                    'success': True, 
                    'file_path': file_path, 
                    'title': f'Direct Media.{ext}'
                }
    except Exception as e:
        return {'success': False, 'error': str(e)}
