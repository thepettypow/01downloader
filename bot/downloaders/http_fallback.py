import aiohttp
import aiofiles
import os
import uuid
from bot.config.settings import config

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
                        
                return {
                    'success': True, 
                    'file_path': file_path, 
                    'title': f'Direct Media.{ext}'
                }
    except Exception as e:
        return {'success': False, 'error': str(e)}
