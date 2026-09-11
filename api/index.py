from __future__ import annotations

import sys
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Response

try:
    import psycopg
except ImportError:  # pragma: no cover - optional dependency error is handled below
    psycopg = None


REPO_ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_ROOT = REPO_ROOT / "authority"
if str(AUTHORITY_ROOT) not in sys.path:
    sys.path.insert(0, str(AUTHORITY_ROOT))

try:
    from loopos_authority.api import app as authority_app  # noqa: E402
except (OSError, RuntimeError, ValueError, sqlite3.Error) as error:
    # Keep serverless liveness available while readiness fails closed when an
    # external dependency is unavailable during module initialization.
    authority_app = None
    authority_failure_code = (
        "configuration_invalid"
        if isinstance(error, ValueError)
        else "persistence_unavailable"
        if isinstance(error, sqlite3.Error)
        else "authority_initialization_failed"
    )
except Exception as error:
    authority_app = None
    authority_failure_code = (
        "persistence_unavailable"
        if psycopg is not None and isinstance(error, psycopg.Error)
        else "authority_initialization_failed"
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if authority_app is None:
        yield
        return
    async with authority_app.router.lifespan_context(authority_app):
        yield


app = FastAPI(
    title="LoopOS",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)
if authority_app is None:
    def configuration_error() -> HTTPException:
        code = authority_failure_code
        detail = (
            "Authority configuration is invalid; configure the required production environment variables and redeploy."
            if code == "configuration_invalid"
            else "Authority persistence is unavailable; verify managed Postgres connectivity, migrations, and credentials."
            if code == "persistence_unavailable"
            else "Authority initialization failed; inspect the deployment logs and restore the missing runtime dependency or configuration."
        )
        return HTTPException(
            status_code=503,
            detail=detail,
            headers={
                "Cache-Control": "no-store",
                "X-LoopOS-Readiness-Code": code,
            },
        )

    @app.get("/api/health/live")
    async def configuration_liveness(response: Response) -> dict[str, str]:
        response.headers["cache-control"] = "no-store"
        return {"status": "live"}

    @app.get("/api/health/ready")
    async def configuration_readiness() -> None:
        raise configuration_error()

    @app.api_route("/api", methods=["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"])
    @app.api_route("/api/{path:path}", methods=["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"])
    async def configuration_unavailable() -> None:
        """Keep every API operation fail-closed when authority boot fails."""
        raise configuration_error()
else:
    app.mount("/api", authority_app)
    # Keep the mounted app as the runtime boundary, while exposing the
    # prefixed routes explicitly so Vercel maps nested /api requests to the
    # api/index.py function instead of only matching /api itself.
    app.include_router(authority_app.router, prefix="/api")
