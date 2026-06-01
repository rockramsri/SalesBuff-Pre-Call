"""Shared helpers — ids, text truncation, URL normalization."""

from __future__ import annotations

import re
import uuid
from urllib.parse import urlparse, urlunparse


def make_id(prefix: str = "card") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def truncate(text: str, max_len: int) -> str:
    if not text or max_len <= 0:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def normalize_url(url: str) -> str:
    """Strip fragments and trailing slashes for citation matching."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/") or ""
    return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, ""))


def strip_trailing_punctuation(url: str) -> str:
    return url.rstrip(".,);]")
