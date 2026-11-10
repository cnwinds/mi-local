import re


def byte_range(header: str, size: int) -> tuple[int, int] | None:
    """(start, end) inclusive for a single "bytes=" Range header; None to send everything.

    Raises ValueError when the range lies outside the body (HTTP 416).
    """
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
    if not match or not (match[1] or match[2]):
        return None
    start = int(match[1]) if match[1] else max(0, size - int(match[2]))
    end = min(int(match[2]), size - 1) if match[1] and match[2] else size - 1
    if start > end:
        raise ValueError(header)
    return start, end
