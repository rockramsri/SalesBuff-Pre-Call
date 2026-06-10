"""Shared core wiring reused by every feature (pre-call, on-fly).

CoreContainer holds only the building blocks that have no feature dependency:
configuration plus the LLM and web-search clients. On-fly depends on this and
never imports pre-call. The pre-call ``Container`` extends CoreContainer.
"""

from __future__ import annotations

from dataclasses import dataclass

from salesbuff.adapters.openai_llm import OpenAiLlmClient
from salesbuff.adapters.tavily import TavilyAdapter
from salesbuff.config import Config


@dataclass
class CoreContainer:
    """Shared clients every feature reuses. No knowledge of any feature."""

    config: Config
    llm: OpenAiLlmClient
    web_source: TavilyAdapter

    @classmethod
    def from_config(cls, config: Config | None = None) -> CoreContainer:
        cfg = config or Config.from_env()
        return cls(
            config=cfg,
            llm=OpenAiLlmClient(api_key=cfg.openai_api_key, model=cfg.openai_model),
            web_source=TavilyAdapter(api_key=cfg.tavily_api_key),
        )

    async def aclose(self) -> None:
        await self.llm.aclose()
        await self.web_source.aclose()
