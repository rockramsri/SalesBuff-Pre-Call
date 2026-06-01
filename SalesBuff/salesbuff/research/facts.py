"""Facts builder — turns the shared research into a grounded evidence dossier.

Reuses the same verified fact pack as the Actions brief, but organizes it into
citation-backed findings grouped by the YAML domain-logic categories.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pydantic import ValidationError

from salesbuff.domain.brief_rules import collect_allowed_sources, url_in_sources
from salesbuff.domain.prompts import prompt_fact_brief
from salesbuff.domain.sales_logic import SalesLogic
from salesbuff.models.brief import BriefSubject
from salesbuff.models.facts import FactFinding, FactFindingList, FactsReport, FactSection
from salesbuff.models.findings import AllWebFindings, LitigationFindings
from salesbuff.research.brief import build_fact_pack
from salesbuff.ports.llm import LlmClient

if TYPE_CHECKING:
    from salesbuff.models.entities import SalesContext


class FactsBuilder:
    def __init__(self, llm: LlmClient, sales_logic: SalesLogic) -> None:
        self.llm = llm
        self.logic = sales_logic

    async def build(
        self,
        ctx: SalesContext,
        web: AllWebFindings,
        incumbent_legal: LitigationFindings | None,
        prospect_legal: LitigationFindings | None,
    ) -> tuple[FactsReport | None, list[str]]:
        facts = build_fact_pack(web, incumbent_legal, prospect_legal)
        system = prompt_fact_brief(
            ctx,
            category_block=self._category_block(),
            question_block=self._question_block(ctx),
            guardrails=self.logic.compliance_overlay(ctx.prospect.industry),
        )
        user = f"Facts (JSON):\n{json.dumps(facts, default=str)}"

        raw: FactFindingList | None = None
        for attempt in range(2):
            try:
                data = await self.llm.json(system, user)
                raw = FactFindingList.model_validate(data)
                break
            except (ValidationError, ValueError):
                if attempt == 1:
                    return None, []

        if raw is None:
            return None, []

        allowed = collect_allowed_sources(web, incumbent_legal, prospect_legal)
        return self._assemble(ctx, raw.findings, allowed)

    def _assemble(
        self, ctx: SalesContext, findings: list[FactFinding], allowed: set[str]
    ) -> tuple[FactsReport, list[str]]:
        by_key = {c.key: c for c in self.logic.categories}
        buckets: dict[str, list[FactFinding]] = {c.key: [] for c in self.logic.categories}
        dropped: list[str] = []

        for finding in findings:
            cat = by_key.get(finding.category)
            if cat is None:  # unknown category from the model
                dropped.append(finding.headline or "(unknown category)")
                continue
            valid = [c for c in finding.citations if url_in_sources(c.url, allowed)]
            if cat.citation_required and not valid:
                dropped.append(finding.headline or "(uncited)")
                continue
            buckets[cat.key].append(finding.model_copy(update={"citations": valid}))

        sections = [
            FactSection(category=cat.key, display=cat.display, findings=buckets[cat.key])
            for cat in self.logic.categories
            if buckets[cat.key]
        ]
        report = FactsReport(subject=_subject(ctx), sections=sections)
        return report, dropped

    def _category_block(self) -> str:
        return "\n".join(
            f"- {c.key} ({c.display}): {c.description}" for c in self.logic.categories
        )

    def _question_block(self, ctx: SalesContext) -> str:
        roles = [("Prospect company", "prospect_company")]
        if ctx.contact.full_name and ctx.contact.full_name != ctx.prospect.name:
            roles.append(("Contact person", "contact_person"))
        if ctx.incumbent:
            roles.append(("Incumbent vendor", "incumbent_vendor"))
        roles.append(("Cross-entity", "cross_entity"))

        lines: list[str] = []
        for label, role in roles:
            questions = self.logic.questions_for(role)
            if not questions:
                continue
            lines.append(f"{label}:")
            lines.extend(f"- {q}" for q in questions)
        return "\n".join(lines)


def _subject(ctx: SalesContext) -> BriefSubject:
    return BriefSubject(
        prospect=ctx.prospect.name,
        contact=ctx.contact.full_name,
        incumbent=ctx.incumbent.name if ctx.incumbent else None,
    )
