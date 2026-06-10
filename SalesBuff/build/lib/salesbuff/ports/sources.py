"""Abstract ports for external data sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class WebSource(ABC):
    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "basic",
        topic: str = "general",
        time_range: str | None = None,
        days: int | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        include_raw_content: bool = False,
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    async def extract(
        self,
        urls: list[str],
        *,
        extract_depth: str = "basic",
        output_format: str = "markdown",
        query: str = "",
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    async def research(
        self,
        input: str,
        *,
        model: str | None = None,
        output_schema: dict[str, Any] | None = None,
        output_length: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Submit a deep-research task; returns a dict with ``request_id``."""
        ...

    @abstractmethod
    async def get_research(self, request_id: str) -> dict[str, Any]:
        """Poll a deep-research task; returns ``status`` and ``content``."""
        ...

    @abstractmethod
    async def aclose(self) -> None:
        ...


class LegalSource(ABC):
    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        search_type: str = "d",
        semantic: bool = False,
        order_by: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    async def follow(self, url: str) -> dict[str, Any]:
        ...

    @abstractmethod
    async def get_docket_entries(self, docket_id: int | str) -> dict[str, Any]:
        ...

    @abstractmethod
    async def aclose(self) -> None:
        ...
