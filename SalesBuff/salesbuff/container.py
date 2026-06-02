"""Composition root — wires concrete adapters to the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, replace

from salesbuff.adapters.courtlistener import CourtListenerAdapter
from salesbuff.adapters.openai_llm import OpenAiLlmClient
from salesbuff.adapters.tavily import TavilyAdapter
from salesbuff.config import Config
from salesbuff.domain.sales_logic import SalesLogic
from salesbuff.pipeline import Pipeline
from salesbuff.research.brief import BriefBuilder
from salesbuff.research.deep import DeepResearcher
from salesbuff.research.facts import FactsBuilder
from salesbuff.research.legal import LegalEnricher, LegalResearcher
from salesbuff.research.resolve import EntityResolver
from salesbuff.research.web import WebResearcher


@dataclass
class Container:
    config: Config
    llm: OpenAiLlmClient
    web_source: TavilyAdapter
    legal_source: CourtListenerAdapter
    pipeline: Pipeline

    @classmethod
    def from_config(cls, config: Config | None = None) -> Container:
        cfg = config or Config.from_env()
        llm = OpenAiLlmClient(api_key=cfg.openai_api_key, model=cfg.openai_model)
        web_source = TavilyAdapter(api_key=cfg.tavily_api_key)
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
        await self.llm.aclose()
        await self.web_source.aclose()
        await self.legal_source.aclose()
