import json
import os
import subprocess

def probe_video(path: str) -> dict:
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
    duration = None
    try:
        duration = float(((data.get("format") or {}).get("duration") or "0").strip())
    except Exception:
        duration = None
    width = None
    height = None
    for s in data.get("streams") or []:
        if s.get("codec_type") == "video":
            width = int(s.get("width") or 0) or None
            height = int(s.get("height") or 0) or None
            break
    return {"duration": duration, "width": width, "height": height}

def extract_thumbnail(video_path: str, output_path: str) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
        "-y",
        "-ss",
        "00:00:01",
        "-i",
        video_path,
        "-vframes",
        "1",
        "-vf",
        "scale=320:-2",
        "-q:v",
        "6",
        output_path,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=20, check=True)
    return output_path

