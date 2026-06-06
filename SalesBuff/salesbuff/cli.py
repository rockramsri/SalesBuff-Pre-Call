"""Console entrypoint: `salesbuff-serve` hosts the FastAPI service.

Requires the API extra:  pip install "salesbuff[api]"
"""

from __future__ import annotations

import argparse
import os


def serve() -> None:
    parser = argparse.ArgumentParser(
        prog="salesbuff-serve",
        description="Host the SalesBuff FastAPI service.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8000")),
        help="Bind port (default: $PORT or 8000)",
    )
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes (dev)")
    args = parser.parse_args()

    try:
        import uvicorn
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise SystemExit(
            'The API server needs the "api" extra. Install it with:\n'
            '    pip install "salesbuff[api]"'
        ) from exc

    uvicorn.run("salesbuff.api:app", host=args.host, port=args.port, reload=args.reload)
