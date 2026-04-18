import json
import os
import subprocess

def probe_audio(path: str) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15, check=True)
    data = json.loads(p.stdout or "{}")
    tags = ((data.get("format") or {}).get("tags") or {})
    duration = None
    try:
        duration = float(((data.get("format") or {}).get("duration") or "0").strip())
    except Exception:
        duration = None
    title = tags.get("title") or tags.get("TITLE") or None
    artist = tags.get("artist") or tags.get("ARTIST") or tags.get("album_artist") or tags.get("ALBUM_ARTIST") or None
    album = tags.get("album") or tags.get("ALBUM") or None
    return {"title": title, "artist": artist, "album": album, "duration": duration}

def extract_audio_cover(audio_path: str, output_path: str) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
        "-y",
        "-i",
        audio_path,
        "-an",
        "-vcodec",
        "copy",
        output_path,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=20, check=True)
    return output_path

