"""Shared helpers — ids and URL normalization."""

from __future__ import annotations

import uuid
from urllib.parse import urlparse, urlunparse


def make_id(prefix: str = "card") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def normalize_url(url: str) -> str:
    """Strip fragments and trailing slashes for citation matching."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/") or ""
    return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, ""))


def strip_trailing_punctuation(url: str) -> str:
    return url.rstrip(".,);]")
