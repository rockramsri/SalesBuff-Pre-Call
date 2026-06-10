"""Abstract port for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LlmClient(ABC):
    @abstractmethod
    async def json(self, system: str, user: str) -> dict:
        ...

    @abstractmethod
    async def text(self, system: str, user: str) -> str:
        ...

    @abstractmethod
    async def aclose(self) -> None:
        ...
