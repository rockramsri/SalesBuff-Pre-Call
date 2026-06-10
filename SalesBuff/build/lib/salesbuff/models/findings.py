"""Web and legal research findings."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class WebResult(BaseModel):
    title: str = ""
    url: str = ""
    content: str = ""
    score: float | None = None
    published_date: str | None = None
    source_domain: str = ""
    raw_content: str | None = None

    @classmethod
    def from_tavily(cls, item: dict[str, Any]) -> WebResult:
        url = item.get("url", "") or ""
        return cls(
            title=item.get("title", "") or "",
            url=url,
            content=item.get("content", "") or "",
            score=item.get("score"),
            published_date=item.get("published_date"),
            source_domain=urlparse(url).netloc if url else "",
            raw_content=item.get("raw_content"),
        )


class WebFindings(BaseModel):
    subject: str
    subject_type: str
    entity_role: str = ""
    categories: dict[str, list[WebResult]] = Field(default_factory=dict)

    def all_results(self) -> list[WebResult]:
        seen: set[str] = set()
        out: list[WebResult] = []
        for results in self.categories.values():
            for result in results:
                key = result.url or result.title
                if key and key not in seen:
                    seen.add(key)
                    out.append(result)
        return out

    @property
    def total(self) -> int:
        return len(self.all_results())


class AllWebFindings(BaseModel):
    prospect: WebFindings | None = None
    contact: WebFindings | None = None
    incumbent: WebFindings | None = None

    @property
    def has_incumbent(self) -> bool:
        return self.incumbent is not None and self.incumbent.total > 0


_SITE_ROOT = "https://www.courtlistener.com"


class LegalCase(BaseModel):
    case_name: str = ""
    docket_number: str = ""
    docket_id: int | None = None
    date_filed: str | None = None
    date_terminated: str | None = None
    court: str = ""
    nature_of_suit: str | None = None
    cause: str | None = None
    status: str | None = None
    url: str = ""
    parties: list[str] = Field(default_factory=list)
    snippet: str = ""
    risk_type: str = "other"
    key_filings: list[str] = Field(default_factory=list)
    web_sources: list[str] = Field(default_factory=list)
    details: str = ""

    @classmethod
    def from_result(cls, item: dict[str, Any]) -> LegalCase:
        rel = item.get("absolute_url", "") or ""
        url = f"{_SITE_ROOT}{rel}" if rel.startswith("/") else rel
        opinions = item.get("opinions") or []
        first = opinions[0] if isinstance(opinions, list) and opinions else None
        snippet = (first.get("snippet") or "").strip() if isinstance(first, dict) else ""
        return cls(
            case_name=item.get("caseName", "") or "",
            docket_number=item.get("docketNumber", "") or "",
            docket_id=item.get("docket_id"),
            date_filed=item.get("dateFiled"),
            date_terminated=item.get("dateTerminated"),
            court=item.get("court", "") or "",
            nature_of_suit=item.get("suitNature") or item.get("nature_of_suit"),
            cause=item.get("cause"),
            status=item.get("status"),
            url=url,
            parties=item.get("party", []) or [],
            snippet=snippet,
            risk_type=_classify_risk(item),
        )


class LitigationFindings(BaseModel):
    subject: str
    subject_type: str
    total_count: int = 0
    searched_variants: list[str] = Field(default_factory=list)
    cases: list[LegalCase] = Field(default_factory=list)

    @property
    def no_cases(self) -> bool:
        return len(self.cases) == 0


# --- Tavily Deep Research structured outputs (output_schema targets) ---


class WebFinding(BaseModel):
    """One sales-relevant fact discovered for an entity."""

    category: str = Field(
        default="general",
        description="Bucket: news, financial, leadership, hiring, reputation, pain, legal, social, podcast, or general",
    )
    headline: str = Field(default="", description="Short fast-scan headline for the finding")
    detail: str = Field(default="", description="1-3 sentences explaining the fact and why it matters for a sales conversation")
    url: str = Field(default="", description="Exact source URL backing this finding")


class EntityWebProfile(BaseModel):
    """Structured deep-research profile for a single entity."""

    summary: str = Field(default="", description="2-3 sentence overview of the entity grounded in the sources")
    findings: list[WebFinding] = Field(
        default_factory=list, description="Distinct sales-relevant findings, each with a source URL"
    )


class CaseEnrichment(BaseModel):
    """Per-case verdict + enrichment from deep research over a batch of dockets."""

    id: int = Field(description="The id of the case from the input list, echoed back exactly")
    involved: bool = Field(
        default=False,
        description="True only if the target company is genuinely a named party in real commercial/corporate litigation",
    )
    sales_relevant: bool = Field(
        default=False, description="True if the case is useful for the rep's sales conversation"
    )
    risk_type: str = Field(
        default="other",
        description="One of: fraud, product_liability, breach_of_contract, employment, antitrust, other",
    )
    status: str = Field(default="", description="Case status/outcome if known, else empty")
    summary: str = Field(default="", description="One to two sentence sales-facing summary of the case")
    sources: list[str] = Field(
        default_factory=list, description="URLs used to verify and summarize the case"
    )


class LegalEnrichmentBatch(BaseModel):
    cases: list[CaseEnrichment] = Field(
        default_factory=list, description="One entry per input case, echoing its id"
    )


def _classify_risk(item: dict[str, Any]) -> str:
    blob = " ".join(
        str(item.get(key, "")).lower()
        for key in ("suitNature", "nature_of_suit", "cause", "caseName")
    )
    if "fraud" in blob or "securit" in blob:
        return "fraud"
    if "product" in blob or "liabilit" in blob or "injury" in blob:
        return "product_liability"
    if "contract" in blob or "breach" in blob:
        return "breach_of_contract"
    if "employ" in blob or "discriminat" in blob or "wrongful" in blob or "labor" in blob:
        return "employment"
    if "antitrust" in blob:
        return "antitrust"
    return "other"
