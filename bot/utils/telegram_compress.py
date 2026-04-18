import os
import subprocess

def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True)

def _target_video_bitrate_kbps(max_bytes: int, duration_s: int | None, audio_kbps: int) -> int | None:
    if not duration_s or duration_s <= 0:
        return None
    total_kbps = int((max_bytes * 8) / 1000 / duration_s)
    v_kbps = max(200, total_kbps - audio_kbps)
    return v_kbps

def compress_video_to_size(
    input_path: str,
    output_path: str,
    max_bytes: int,
    duration_s: int | None = None,
    prefer_height: int | None = None,
) -> str:
    heights = [h for h in [prefer_height, 720, 480, 360, 240] if h]
    audio_kbps_steps = [128, 96, 64]
    for height in heights:
        for audio_kbps in audio_kbps_steps:
            v_kbps = _target_video_bitrate_kbps(max_bytes, duration_s, audio_kbps)
            vf = f"scale=-2:{int(height)}:force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p"
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
                "-pix_fmt",
                "yuv420p",
                "-vf",
                vf,
                "-c:a",
                "aac",
                "-b:a",
                f"{audio_kbps}k",
                "-movflags",
                "+faststart",
            ]
            if v_kbps is None:
                cmd += ["-crf", "30"]
            else:
                cmd += ["-b:v", f"{v_kbps}k", "-maxrate", f"{v_kbps}k", "-bufsize", f"{v_kbps*2}k"]
            cmd.append(output_path)
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
                _run(cmd)
            except subprocess.CalledProcessError:
                if os.path.exists(output_path):
                    os.remove(output_path)
                continue
            try:
                if os.path.getsize(output_path) <= max_bytes:
                    return output_path
            except Exception:
                pass
    raise RuntimeError("Unable to compress video under the configured upload limit")

def compress_audio_to_size(
    input_path: str,
    output_path: str,
    max_bytes: int,
    duration_s: int | None = None,
) -> str:
    bitrate_steps = [192, 160, 128, 96, 64]
    for kbps in bitrate_steps:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostats",
            "-y",
            "-i",
            input_path,
            "-vn",
            "-c:a",
            "libmp3lame",
            "-b:a",
            f"{kbps}k",
            output_path,
        ]
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
            _run(cmd)
        except subprocess.CalledProcessError:
            if os.path.exists(output_path):
                os.remove(output_path)
            continue
        try:
            if os.path.getsize(output_path) <= max_bytes:
                return output_path
        except Exception:
            pass
    raise RuntimeError("Unable to compress audio under the configured upload limit")

