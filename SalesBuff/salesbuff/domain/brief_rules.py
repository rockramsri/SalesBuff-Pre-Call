"""Citation grounding and brief validation — pure functions."""

from __future__ import annotations

from salesbuff.models.brief import CITATION_OPTIONAL, BriefCard, SalesBrief
from salesbuff.models.findings import AllWebFindings, LitigationFindings
from salesbuff.utils import normalize_url, strip_trailing_punctuation

def collect_allowed_sources(
    web: AllWebFindings,
    incumbent_legal: LitigationFindings | None,
    prospect_legal: LitigationFindings | None,
) -> set[str]:
    urls: set[str] = set()
    for findings in (web.prospect, web.contact, web.incumbent):
        if findings:
            for result in findings.all_results():
                if result.url:
                    urls.add(result.url)
                    urls.add(normalize_url(result.url))
    for legal in (incumbent_legal, prospect_legal):
        if legal:
            for case in legal.cases:
                if case.url:
                    urls.add(case.url)
                    urls.add(normalize_url(case.url))
                for source in case.web_sources:
                    if source:
                        urls.add(source)
                        urls.add(normalize_url(source))
    return urls


def url_in_sources(url: str, allowed: set[str]) -> bool:
    """True if a citation URL matches one of the gathered research sources."""
    if not url:
        return False
    candidates = {url, normalize_url(url), strip_trailing_punctuation(url)}
    return any(candidate in allowed for candidate in candidates)


# Generic, non-actionable titles the model sometimes falls back to. A card whose
# title is one of these (or whose preview is empty) isn't useful at scan speed.
_VAGUE_TITLES = {
    "company signal",
    "person insight",
    "potential concern",
    "interesting development",
    "open question",
    "watch out",
    "note",
}


def _is_low_quality(card: BriefCard) -> bool:
    title = card.title.strip().lower()
    return not card.preview.strip() or not title or title in _VAGUE_TITLES


def ground_brief(brief: SalesBrief, allowed: set[str]) -> tuple[SalesBrief, list[str]]:
    """Drop cards that are uncited (when required) or too vague to act on."""
    dropped_titles: list[str] = []
    kept: list[BriefCard] = []

    for card in brief.cards:
        if _is_low_quality(card):
            dropped_titles.append(card.title or "(untitled)")
            continue
        valid_citations = [
            citation
            for citation in card.citations
            if url_in_sources(citation.url, allowed)
        ]
        if card.category in CITATION_OPTIONAL:
            kept.append(card.model_copy(update={"citations": valid_citations}))
            continue
        if not valid_citations:
            dropped_titles.append(card.title)
            continue
        kept.append(card.model_copy(update={"citations": valid_citations}))

    return brief.model_copy(update={"cards": kept}), dropped_titles
