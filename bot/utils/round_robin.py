_cursor = 0


def reset_cursor() -> None:
    global _cursor
    _cursor = 0


def rotate(items: list[str]) -> list[str]:
    global _cursor
    if not items:
        return []
    start = _cursor % len(items)
    _cursor += 1
    return items[start:] + items[:start]

