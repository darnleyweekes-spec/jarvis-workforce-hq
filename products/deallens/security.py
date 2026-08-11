from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 2_000_000

SUSPICIOUS_PATTERNS = [
    r"ignore (all|any|the) previous instructions",
    r"system prompt",
    r"developer message",
    r"reveal .*secret",
    r"exfiltrat",
    r"send .*data .*to",
    r"execute .*command",
    r"run .*shell",
    r"override .*instruction",
]


@dataclass
class FileAssessment:
    sha256: str
    size_bytes: int
    allowed: bool
    reason: str


def assess_file(raw: bytes) -> FileAssessment:
    digest = hashlib.sha256(raw).hexdigest()
    size = len(raw)
    if size == 0:
        return FileAssessment(digest, size, False, "empty file")
    if size > MAX_FILE_BYTES:
        return FileAssessment(digest, size, False, f"file exceeds {MAX_FILE_BYTES // (1024 * 1024)} MB limit")
    return FileAssessment(digest, size, True, "accepted")


def sanitize_text(text: str) -> str:
    text = text.replace("\x00", "")
    return text[:MAX_TEXT_CHARS]


def prompt_injection_hits(text: str):
    compact = re.sub(r"\s+", " ", text).lower()
    return [pattern for pattern in SUSPICIOUS_PATTERNS if re.search(pattern, compact, re.IGNORECASE)]
