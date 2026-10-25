from __future__ import annotations

import re
from dataclasses import dataclass

_NIK = re.compile(r"(?<!\d)\d{16}(?!\d)")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(
    r"(?<![\w])(?:\+?62|0)8[1-9](?:[\s.-]?\d){6,11}(?!\d)",
    re.IGNORECASE,
)

_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("nik", _NIK, "[NIK]"),
    ("email", _EMAIL, "[EMAIL]"),
    ("telepon", _PHONE, "[TELEPON]"),
)


@dataclass(frozen=True, slots=True)
class RedactionResult:
    text: str
    categories: tuple[str, ...]

    @property
    def changed(self) -> bool:
        return bool(self.categories)


def redact_pii(text: str) -> RedactionResult:
    """Menyamarkan pola PII umum sebelum retrieval atau pemanggilan provider."""
    redacted = text
    found: list[str] = []
    for name, pattern, replacement in _PATTERNS:
        redacted, count = pattern.subn(replacement, redacted)
        if count:
            found.append(name)
    return RedactionResult(text=redacted, categories=tuple(found))
