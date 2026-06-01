"""Brief builder — one LLM call to SalesBrief, then ground citations."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pydantic import ValidationError

from salesbuff.domain.brief_rules import collect_allowed_sources, ground_brief
from salesbuff.domain.framing import get_sales_frame
from salesbuff.domain.prompts import prompt_card_brief
from salesbuff.models.brief import SalesBrief
from salesbuff.models.findings import AllWebFindings, LitigationFindings, WebFindings
from salesbuff.ports.llm import LlmClient

if TYPE_CHECKING:
    from salesbuff.models.entities import SalesContext


class BriefBuilder:
    def __init__(self, llm: LlmClient) -> None:
        self.llm = llm

    async def build(
        self,
        ctx: SalesContext,
        web: AllWebFindings,
        incumbent_legal: LitigationFindings | None,
        prospect_legal: LitigationFindings | None,
    ) -> tuple[SalesBrief | None, list[str]]:
        facts = self._build_fact_pack(web, incumbent_legal, prospect_legal)
        user = f"Facts (JSON):\n{json.dumps(facts, default=str)}"

        brief: SalesBrief | None = None
        for attempt in range(2):
            try:
                raw = await self.llm.json(prompt_card_brief(ctx), user)
                brief = SalesBrief.model_validate(raw)
                break
            except (ValidationError, ValueError):
                if attempt == 1:
                    return None, []

        if brief is None:
            return None, []

        allowed = collect_allowed_sources(web, incumbent_legal, prospect_legal)
        return ground_brief(brief, allowed)

    def _build_fact_pack(
        self,
        web: AllWebFindings,
        incumbent_legal: LitigationFindings | None,
        prospect_legal: LitigationFindings | None,
    ) -> dict:
        return build_fact_pack(web, incumbent_legal, prospect_legal)


def build_fact_pack(
    web: AllWebFindings,
    incumbent_legal: LitigationFindings | None,
    prospect_legal: LitigationFindings | None,
) -> dict:
    """Shared verified-fact bundle consumed by both the Actions and Facts lanes."""
    return {
        "prospect_company": _web_facts(web.prospect),
        "prospect_legal": _legal_facts(prospect_legal),
        "contact_person": _web_facts(web.contact),
        "incumbent_vendor": _web_facts(web.incumbent),
        "incumbent_legal": _legal_facts(incumbent_legal),
    }


def _legal_facts(findings: LitigationFindings | None) -> list[dict]:
    if not findings:
        return []
    return [
        {
            "case": case.case_name,
            "type": case.risk_type,
            "sales_frame": get_sales_frame(case.risk_type)["implication"],
            "filed": case.date_filed,
            "status": case.status,
            "details": case.details,
            "url": case.url,
        }
        for case in findings.cases
    ]


def _web_facts(findings: WebFindings | None) -> list[dict]:
    if not findings:
        return []
    return [
        {
            "category": cat,
            "title": result.title,
            "snippet": result.content,
            "url": result.url,
        }
        for cat, results in findings.categories.items()
        for result in results
    ]
