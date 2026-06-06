"""SalesBuff — pre-call due-diligence intelligence (SDK).

`pip install salesbuff` for the SDK; `pip install "salesbuff[api]"` to also get
the FastAPI service (`salesbuff.api:app`).
"""

from salesbuff.client import ResearchResult, SalesBuff, research_once

__version__ = "0.1.0"
__all__ = ["SalesBuff", "ResearchResult", "research_once", "__version__"]
