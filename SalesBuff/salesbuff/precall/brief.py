"""Brief builder — one LLM call to SalesBrief, then ground + validate coverage."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pydantic import ValidationError

from salesbuff.domain.brief_rules import collect_allowed_sources, ground_brief
from salesbuff.domain.framing import get_sales_frame
from salesbuff.domain.prompts import prompt_card_brief
from salesbuff.domain.sales_logic import SalesLogic
from salesbuff.domain.sources import source_tier
from salesbuff.models.brief import BriefCard, BriefCategory, CardActionType, SalesBrief, UseWhen
from salesbuff.models.findings import AllWebFindings, LitigationFindings, WebFindings
from salesbuff.ports.llm import LlmClient
from salesbuff.utils import make_id

if TYPE_CHECKING:
    from salesbuff.models.entities import SalesContext

logger = logging.getLogger(__name__)

# A brief should cover these moves; each entry is a set of acceptable categories.
_REQUIRED_COVERAGE: list[set[BriefCategory]] = [
    {BriefCategory.OPENING_MOVE},
    {BriefCategory.PAIN_HYPOTHESIS, BriefCategory.PRIORITY_SIGNAL},
    {BriefCategory.PROOF_POINT, BriefCategory.DIFFERENTIATION_ANGLE},
    {BriefCategory.NEXT_STEP},
]


class BriefBuilder:
    def __init__(self, llm: LlmClient, sales_logic: SalesLogic | None = None) -> None:
        self.llm = llm
        self.logic = sales_logic

    async def build(
        self,
        ctx: SalesContext,
        web: AllWebFindings,
        incumbent_legal: LitigationFindings | None,
        prospect_legal: LitigationFindings | None,
    ) -> tuple[SalesBrief | None, list[str]]:
        facts = build_fact_pack(web, incumbent_legal, prospect_legal)
        user = f"Facts (JSON):\n{json.dumps(facts, default=str)}"
        guardrails = (
            self.logic.compliance_overlay(ctx.prospect.industry) if self.logic else ""
        )

        brief: SalesBrief | None = None
        for attempt in range(2):
            try:
                raw = await self.llm.json(prompt_card_brief(ctx, guardrails), user)
                brief = SalesBrief.model_validate(raw)
                break
            except (ValidationError, ValueError):
                if attempt == 1:
                    return None, []

        if brief is None:
            return None, []

        allowed = collect_allowed_sources(web, incumbent_legal, prospect_legal)
        grounded, dropped = ground_brief(brief, allowed)
        grounded = self._fill_coverage_gaps(grounded, allowed)
        grounded = _assign_server_metadata(grounded)
        return grounded, dropped

    def _fill_coverage_gaps(self, brief: SalesBrief, allowed: set[str]) -> SalesBrief:
        """Log missing required moves; synthesize a next_step card if it was dropped."""
        present = {card.category for card in brief.cards}
        missing = [grp for grp in _REQUIRED_COVERAGE if not (grp & present)]
        if missing:
            logger.warning(
                "Brief coverage gaps after grounding: %s",
                [sorted(c.value for c in grp) for grp in missing],
            )

        has_next_step = BriefCategory.NEXT_STEP in present
        if not has_next_step and brief.next_step_line.strip():
            fallback = _fallback_next_step(brief)
            if fallback is not None:
                logger.info("Synthesized deterministic next_step card from a cited move.")
                return brief.model_copy(update={"cards": [*brief.cards, fallback]})
        return brief


def _fallback_next_step(brief: SalesBrief) -> BriefCard | None:
    """Build a next_step card from next_step_line, borrowing a surviving citation."""
    donor = next((c for c in brief.cards if c.citations), None)
    if donor is None:
        return None
    return BriefCard(
        category=BriefCategory.NEXT_STEP,
        action_type=CardActionType.ASK,
        use_when=UseWhen.CLOSE,
        title="Lock the next step",
        preview=brief.next_step_line,
        talk_track=brief.next_step_line,
        detail="Concrete commitment to advance the deal, grounded in the brief's strongest signal.",
        priority="high",
        confidence="medium",
        citations=list(donor.citations[:1]),
    )


def _assign_server_metadata(brief: SalesBrief) -> SalesBrief:
    """Server owns timestamps and card ids — never trust the model for these."""
    now = datetime.now(timezone.utc).isoformat()
    cards = [
        card.model_copy(update={"card_id": make_id("card")}) for card in brief.cards
    ]
    return brief.model_copy(update={"cards": cards, "generated_at": now})


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
    out: list[dict] = []
    for case in findings.cases:
        # Prefer the docket URL; fall back to a verified web source. Drop cases
        # with no usable link — a legal fact you can't cite only misleads.
        url = case.url or (case.web_sources[0] if case.web_sources else "")
        if not url:
            continue
        out.append(
            {
                "case": case.case_name,
                "type": case.risk_type,
                "sales_frame": get_sales_frame(case.risk_type)["implication"],
                "filed": case.date_filed,
                "status": case.status,
                "details": case.details,
                "url": url,
                "tier": 1,  # court records / verified legal sources
            }
        )
    return out


def _web_facts(findings: WebFindings | None) -> list[dict]:
    if not findings:
        return []
    return [
        {
            "category": cat,
            "title": result.title,
            "snippet": result.content,
            "url": result.url,
            "tier": source_tier(result.url),
        }
        for cat, results in findings.categories.items()
        for result in results
    ]
