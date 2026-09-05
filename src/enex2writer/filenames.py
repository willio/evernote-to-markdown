"""Cross-platform filename helpers."""

from __future__ import annotations

import re
import unicodedata


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
_WHITESPACE = re.compile(r"\s+")
_WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


def safe_component(value: str | None, fallback: str, *, max_length: int = 160) -> str:
    """Return a readable filename component with traversal characters removed."""

    text = unicodedata.normalize("NFKC", value or "")
    text = text.replace("/", "-").replace("\\", "-")
    text = _INVALID_FILENAME_CHARS.sub("-", text)
    text = _WHITESPACE.sub(" ", text).strip().rstrip(". ")
    if not text or text in {".", ".."}:
        text = fallback

    # Keep names portable to Windows even when the conversion runs on macOS
    # or Linux. The extension is deliberately included in this check.
    if text.casefold().split(".", 1)[0] in _WINDOWS_RESERVED:
        text = f"{text}-"

    return text[:max_length].rstrip(". ") or fallback


def with_numeric_suffix(filename: str, number: int) -> str:
    """Insert ``-number`` before a filename extension."""

    dot = filename.rfind(".")
    if dot <= 0:
        return f"{filename}-{number}"
    return f"{filename[:dot]}-{number}{filename[dot:]}"


def unique_filename(candidate: str, used: set[str]) -> str:
    """Choose a case-insensitive unique filename within one conversion."""

    result = candidate
    number = 2
    while result.casefold() in used:
        result = with_numeric_suffix(candidate, number)
        number += 1
    used.add(result.casefold())
    return result
