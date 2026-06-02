"""Source quality tiers — how much to trust a citation's domain.

Tier 1 = official / authoritative, Tier 4 = anecdotal. The brief and facts
prompts use this so a single App Store review can't become a primary proof.
"""

from __future__ import annotations

from urllib.parse import urlparse

# Tier 4: anecdotal / self-published — prep-only unless corroborated.
_TIER4 = (
    "apps.apple.com", "play.google.com", "glassdoor.", "g2.com", "trustpilot.",
    "reddit.com", "linkedin.com", "twitter.com", "x.com", "facebook.com",
    "instagram.com", "medium.com", "quora.com",
)
# Tier 3: interviews / talks / personal.
_TIER3 = ("youtube.com", "youtu.be", "podcasts.apple.com", "spotify.com", "substack.com")
# Tier 1: official orgs, government, courts.
_TIER1_SUFFIXES = (".gov", ".edu", ".mil")
_TIER1_HOSTS = ("courtlistener.com", "sec.gov", "fda.gov", "cms.gov")


def source_tier(url: str) -> int:
    """Return 1 (most trusted) .. 4 (weakest) for a URL's domain."""
    if not url:
        return 4
    host = urlparse(url).netloc.lower().replace("www.", "")
    if not host:
        return 4
    if host.endswith(_TIER1_SUFFIXES) or any(h in host for h in _TIER1_HOSTS):
        return 1
    if any(frag in host for frag in _TIER4):
        return 4
    if any(frag in host for frag in _TIER3):
        return 3
    # Everything else (company sites, trade press, news) defaults to Tier 2.
    return 2
