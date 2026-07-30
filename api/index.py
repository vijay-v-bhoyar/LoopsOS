from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI


REPO_ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_ROOT = REPO_ROOT / "authority"
if str(AUTHORITY_ROOT) not in sys.path:
    sys.path.insert(0, str(AUTHORITY_ROOT))

from loopos_authority.api import app as authority_app  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with authority_app.router.lifespan_context(authority_app):
        yield


app = FastAPI(
    title="LoopOS",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)
app.mount("/api", authority_app)
