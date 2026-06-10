"""Evidence-dossier output models for the FACTS tab.

The LLM returns a flat list of findings (each tagged with a category key from the
YAML domain logic); FactsBuilder groups them into ordered sections.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from salesbuff.models.brief import BriefSubject, Citation


class FactFinding(BaseModel):
    category: str = ""
    headline: str
    detail: str = ""
    why_it_matters: str = ""
    citations: list[Citation] = Field(default_factory=list)


class FactFindingList(BaseModel):
    """Raw LLM output before grouping into sections."""

    findings: list[FactFinding] = Field(default_factory=list)


class FactSection(BaseModel):
    category: str
    display: str
    findings: list[FactFinding] = Field(default_factory=list)


class FactsReport(BaseModel):
    subject: BriefSubject
    sections: list[FactSection] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def finding_count(self) -> int:
        return sum(len(s.findings) for s in self.sections)
