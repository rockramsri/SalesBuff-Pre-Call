"""Composition root for the pre-call feature.

Extends the shared CoreContainer (config + llm + web_source) with the legal
adapter and the full pre-call pipeline. On-fly uses CoreContainer directly and
never imports this module.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from salesbuff.adapters.courtlistener import CourtListenerAdapter
from salesbuff.config import Config
from salesbuff.core import CoreContainer
from salesbuff.domain.sales_logic import SalesLogic
from salesbuff.pipeline import Pipeline
from salesbuff.precall.brief import BriefBuilder
from salesbuff.precall.deep import DeepResearcher
from salesbuff.precall.facts import FactsBuilder
from salesbuff.precall.legal import LegalEnricher, LegalResearcher
from salesbuff.precall.resolve import EntityResolver
from salesbuff.precall.web import WebResearcher


@dataclass
class Container(CoreContainer):
    legal_source: CourtListenerAdapter
    pipeline: Pipeline

    @classmethod
    def from_config(cls, config: Config | None = None) -> Container:
        cfg = config or Config.from_env()
        core = CoreContainer.from_config(cfg)
        llm = core.llm
        web_source = core.web_source
        legal_source = CourtListenerAdapter(token=cfg.courtlistener_token)

        deep = DeepResearcher(
            web_source,
            model=cfg.research_model,
            concurrency=cfg.research_concurrency,
            poll_interval=cfg.research_poll_interval,
            max_polls=cfg.research_max_polls,
            output_length=cfg.research_output_length,
        )

        sales_logic = SalesLogic.load()

        pipeline = Pipeline(
            resolver=EntityResolver(llm, web_source),
            web_researcher=WebResearcher(deep),
            legal_researcher=LegalResearcher(legal_source),
            legal_enricher=LegalEnricher(deep, batch_size=cfg.legal_batch_size),
            brief_builder=BriefBuilder(llm, sales_logic),
            facts_builder=FactsBuilder(llm, sales_logic),
            max_cases_per_entity=cfg.max_cases_per_entity,
        )
        return cls(
            config=cfg,
            llm=llm,
            web_source=web_source,
            legal_source=legal_source,
            pipeline=pipeline,
        )

    @classmethod
    def from_keys(
        cls,
        base: Config,
        *,
        openai: str | None = None,
        tavily: str | None = None,
        courtlistener: str | None = None,
    ) -> Container:
        """Per-request container using a user's own keys (falls back to base)."""
        cfg = replace(
            base,
            openai_api_key=openai or base.openai_api_key,
            tavily_api_key=tavily or base.tavily_api_key,
            courtlistener_token=courtlistener or base.courtlistener_token,
        )
        return cls.from_config(cfg)

    async def aclose(self) -> None:
        await super().aclose()
        await self.legal_source.aclose()
