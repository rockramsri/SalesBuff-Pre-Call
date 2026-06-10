"""SalesBuff — sales intelligence SDK.

`pip install salesbuff` for the shared core; add feature extras:
    salesbuff[precall]  pre-call due diligence (SDK: SalesBuff, research_once)
    salesbuff[onfly]    live on-the-fly coaching
    salesbuff[api]      FastAPI host (salesbuff.api:app, `salesbuff-serve`)

The pre-call SDK symbols are imported lazily so that installing a single feature
(e.g. ``salesbuff[onfly]``) never forces pre-call-only dependencies to load.
"""

from typing import TYPE_CHECKING

__version__ = "0.2.0"
__all__ = ["SalesBuff", "ResearchResult", "research_once", "__version__"]

if TYPE_CHECKING:
    from salesbuff.client import ResearchResult, SalesBuff, research_once


def __getattr__(name: str):
    if name in ("SalesBuff", "ResearchResult", "research_once"):
        from salesbuff import client

        return getattr(client, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
