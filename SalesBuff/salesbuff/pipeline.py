"""End-to-end due-diligence pipeline.

Flow:
1. Entity resolution (3-shot LLM + Tavily search) -> SalesContext.
2. Parallel lanes: web deep-research per entity; legal search + batched
   deep-research enrichment for prospect and incumbent companies.
3. Brief: compile findings into a citation-grounded SalesBrief.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable

from salesbuff.domain.framing import sales_context_blurb
from salesbuff.domain.queries import build_incumbent_legal_params, build_prospect_legal_params
from salesbuff.metrics import get_metrics
from salesbuff.models.brief import SalesBrief
from salesbuff.models.entities import SalesContext
from salesbuff.models.findings import AllWebFindings, LitigationFindings
from salesbuff.models.facts import FactsReport
from salesbuff.research.brief import BriefBuilder
from salesbuff.research.facts import FactsBuilder
from salesbuff.research.legal import LegalEnricher, LegalResearcher
from salesbuff.research.resolve import EntityResolver
from salesbuff.research.web import WebResearcher

logger = logging.getLogger(__name__)

# Called with a stage name as the pipeline advances (resolving -> researching
# -> briefing -> done). Used to drive user-facing progress.
ProgressFn = Callable[[str], None]


@dataclass
class PipelineResult:
    context: SalesContext
    web: AllWebFindings
    incumbent_legal: LitigationFindings | None
    prospect_legal: LitigationFindings | None
    brief: SalesBrief | None
    dropped_cards: list[str]
    facts: FactsReport | None = None


class Pipeline:
    def __init__(
        self,
        *,
        resolver: EntityResolver,
        web_researcher: WebResearcher,
        legal_researcher: LegalResearcher,
        legal_enricher: LegalEnricher,
        brief_builder: BriefBuilder,
        facts_builder: FactsBuilder,
        max_cases_per_entity: int,
    ) -> None:
        self.resolver = resolver
        self.web_researcher = web_researcher
        self.legal_researcher = legal_researcher
        self.legal_enricher = legal_enricher
        self.brief_builder = brief_builder
        self.facts_builder = facts_builder
        self.max_cases_per_entity = max_cases_per_entity

    async def _legal_lane(
        self, params: dict, blurb: str, variants: list[str]
    ) -> LitigationFindings | None:
        if not params:
            return None
        findings = await self.legal_researcher.research_company(
            params["name"],
            years_back=params["years_back"],
            match_field=params["match_field"],
            max_results=self.max_cases_per_entity,
            variants=variants,
        )
        return await self.legal_enricher.enrich(findings, blurb)

    async def run_all_research(
        self, ctx: SalesContext
    ) -> tuple[AllWebFindings, LitigationFindings | None, LitigationFindings | None]:
        blurb = sales_context_blurb(ctx)

        web_task = self.web_researcher.research_all(ctx)
        prospect_task = self._legal_lane(
            build_prospect_legal_params(ctx), blurb, ctx.prospect.aliases
        )
        incumbent_task = (
            self._legal_lane(
                build_incumbent_legal_params(ctx), blurb, ctx.incumbent.aliases
            )
            if ctx.incumbent
            else None
        )

        tasks = [web_task, prospect_task]
        if incumbent_task is not None:
            tasks.append(incumbent_task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        web = results[0] if not isinstance(results[0], Exception) else AllWebFindings()
        prospect_legal = results[1] if not isinstance(results[1], Exception) else None
        incumbent_legal = (
            results[2]
            if len(results) > 2 and not isinstance(results[2], Exception)
            else None
        )
        return web, incumbent_legal, prospect_legal

    async def run(
        self, rep_prompt: str, *, on_stage: ProgressFn | None = None
    ) -> PipelineResult:
        metrics = get_metrics()

        def stage(name: str) -> None:
            if on_stage:
                on_stage(name)

        stage("resolving")
        ctx = await self.resolver.resolve(rep_prompt)
        if metrics:
            metrics.snapshot("resolving")

        stage("researching")
        web, incumbent_legal, prospect_legal = await self.run_all_research(ctx)
        if metrics:
            metrics.snapshot("researching")

        stage("briefing")
        # Actions (move-coach) and Facts (dossier) share the research above and
        # run concurrently — each is one independent LLM call.
        brief_task = self.brief_builder.build(ctx, web, incumbent_legal, prospect_legal)
        facts_task = self.facts_builder.build(ctx, web, incumbent_legal, prospect_legal)
        brief_res, facts_res = await asyncio.gather(
            brief_task, facts_task, return_exceptions=True
        )

        brief, dropped_cards = _unpack(brief_res, "Brief", default=(None, []))
        facts, _dropped_facts = _unpack(facts_res, "Facts", default=(None, []))
        if metrics:
            metrics.snapshot("briefing")

        stage("done")

        return PipelineResult(
            context=ctx,
            web=web,
            incumbent_legal=incumbent_legal,
            prospect_legal=prospect_legal,
            brief=brief,
            dropped_cards=dropped_cards,
            facts=facts,
        )


def _unpack(result: object, label: str, default: tuple):
    """Return a gathered lane result, or the default if that lane raised."""
    if isinstance(result, Exception):
        logger.warning("%s generation failed: %s", label, result)
        return default
    return result


async def run_scenario(rep_prompt: str, pipeline: Pipeline) -> PipelineResult:
    return await pipeline.run(rep_prompt)
