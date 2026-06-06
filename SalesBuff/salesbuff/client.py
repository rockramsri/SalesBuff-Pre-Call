"""Public SDK surface for SalesBuff.

Use this to run a due-diligence pass from your own code with your own keys:

    from salesbuff import SalesBuff

    async with SalesBuff(openai_api_key="sk-...", tavily_api_key="tvly-...") as sb:
        result = await sb.research("Meeting the VP of Ops at Acme Health next week...")
        print(result.brief, result.facts)

Or a one-shot synchronous call:

    from salesbuff import research_once
    result = research_once("...", openai_api_key="sk-...", tavily_api_key="tvly-...")
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from salesbuff.config import Config
from salesbuff.container import Container
from salesbuff.models.brief import SalesBrief
from salesbuff.models.facts import FactsReport

ProgressFn = Callable[[str], None]


@dataclass
class ResearchResult:
    """The two products of a run, plus any non-fatal warnings."""

    brief: SalesBrief | None
    facts: FactsReport | None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "brief": self.brief.model_dump(mode="json") if self.brief else None,
            "facts": self.facts.model_dump(mode="json") if self.facts else None,
            "warnings": self.warnings,
        }


class SalesBuff:
    """SalesBuff SDK client. Create with your keys, then call ``research``.

    Async-first. Use as an async context manager (recommended) so HTTP clients
    are closed cleanly, or call ``aclose()`` yourself when done.
    """

    def __init__(
        self,
        *,
        openai_api_key: str,
        tavily_api_key: str,
        courtlistener_token: str | None = None,
        openai_model: str = "gpt-4o-mini",
        **options: object,
    ) -> None:
        cfg = Config.create(
            openai_api_key=openai_api_key,
            tavily_api_key=tavily_api_key,
            courtlistener_token=courtlistener_token,
            openai_model=openai_model,
            **options,
        )
        self._container = Container.from_config(cfg)

    async def research(
        self, prompt: str, *, on_stage: ProgressFn | None = None
    ) -> ResearchResult:
        """Run the full pipeline and return the Actions brief + Facts dossier."""
        result = await self._container.pipeline.run(prompt, on_stage=on_stage)
        warnings: list[str] = []
        if result.brief is None:
            warnings.append("Brief could not be generated from the available findings.")
        if result.dropped_cards:
            warnings.append(f"{len(result.dropped_cards)} card(s) dropped for lacking citations.")
        return ResearchResult(brief=result.brief, facts=result.facts, warnings=warnings)

    async def validate_keys(self) -> None:
        """Raise if the configured OpenAI or Tavily key is unauthorized."""
        await self._container.llm.validate()
        await self._container.web_source.validate()

    async def aclose(self) -> None:
        await self._container.aclose()

    async def __aenter__(self) -> SalesBuff:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()


def research_once(
    prompt: str,
    *,
    openai_api_key: str,
    tavily_api_key: str,
    courtlistener_token: str | None = None,
    openai_model: str = "gpt-4o-mini",
    **options: object,
) -> ResearchResult:
    """Synchronous one-shot: builds a client, runs once, and closes it.

    Convenience for scripts/notebooks. For repeated calls or inside an async
    app, use ``SalesBuff`` with ``await client.research(...)`` instead.
    """

    async def _go() -> ResearchResult:
        async with SalesBuff(
            openai_api_key=openai_api_key,
            tavily_api_key=tavily_api_key,
            courtlistener_token=courtlistener_token,
            openai_model=openai_model,
            **options,
        ) as sb:
            return await sb.research(prompt)

    return asyncio.run(_go())
