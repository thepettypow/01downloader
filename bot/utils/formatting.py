def format_bytes(n: int) -> str:
    n = int(n or 0)
    if n < 0:
        n = 0
    units = ["B", "KB", "MB", "GB", "TB"]
    v = float(n)
    i = 0
    while v >= 1024.0 and i < len(units) - 1:
        v /= 1024.0
        i += 1
    if i == 0:
        return f"{int(v)}{units[i]}"
    return f"{v:.2f}{units[i]}"

