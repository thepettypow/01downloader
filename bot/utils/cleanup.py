import os
import time
import shutil

def cleanup_downloads(download_dir: str, max_age_seconds: int) -> int:
    now = time.time()
    deleted = 0
    if not download_dir or not os.path.exists(download_dir):
        return 0

    for name in os.listdir(download_dir):
        path = os.path.join(download_dir, name)
        try:
            mtime = os.path.getmtime(path)
        except Exception:
            continue
        if now - mtime < max_age_seconds:
            continue
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                os.remove(path)
            deleted += 1
        except Exception:
            continue
    return deleted

