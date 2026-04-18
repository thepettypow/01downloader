import os
import uuid

def split_file(input_path: str, max_part_bytes: int, out_dir: str) -> list[str]:
    max_part_bytes = int(max_part_bytes)
    if max_part_bytes <= 0:
        raise ValueError("max_part_bytes must be > 0")
    if not os.path.exists(input_path):
        raise FileNotFoundError(input_path)
    os.makedirs(out_dir, exist_ok=True)

    part_paths: list[str] = []
    base = os.path.basename(input_path)
    token = uuid.uuid4().hex[:8]
    idx = 1

    with open(input_path, "rb") as src:
        while True:
            chunk = src.read(max_part_bytes)
            if not chunk:
                break
            part_path = os.path.join(out_dir, f"{base}.{token}.part{idx:03d}")
            with open(part_path, "wb") as dst:
                dst.write(chunk)
            part_paths.append(part_path)
            idx += 1

    if not part_paths:
        part_path = os.path.join(out_dir, f"{base}.{token}.part001")
        with open(part_path, "wb") as dst:
            dst.write(b"")
        part_paths.append(part_path)

    return part_paths

