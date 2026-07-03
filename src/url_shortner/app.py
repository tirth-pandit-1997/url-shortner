"""FastAPI application exposing the core URL-shortening service.

Two surfaces:

* ``POST /shorten`` — accept a long URL, generate a unique short code, persist
  the code->URL mapping, and return the code plus a full short URL.
* ``GET /{code}`` — redirect (302) to the stored original URL, or 404 if the
  code is unknown.
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .store import URLStore

_ALLOWED_SCHEMES = {"http", "https"}


class ShortenRequest(BaseModel):
    url: str


class ShortenResponse(BaseModel):
    code: str
    short_url: str


def _is_valid_http_url(url: str) -> bool:
    """Return True only for non-empty absolute http(s) URLs."""
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in _ALLOWED_SCHEMES and bool(parsed.netloc)


def create_app(store: URLStore | None = None) -> FastAPI:
    """Build the FastAPI app. A store may be injected (tests use a fresh one)."""
    app = FastAPI(title="url-shortner")
    # Production wiring: when no store is injected, use a real in-memory store.
    app.state.store = store if store is not None else URLStore()

    @app.post("/shorten", response_model=ShortenResponse, status_code=201)
    def shorten(payload: ShortenRequest, request: Request) -> ShortenResponse:
        url = payload.url.strip()
        if not _is_valid_http_url(url):
            # Reject empty / non-http(s) input WITHOUT storing anything.
            raise HTTPException(
                status_code=400,
                detail="url must be a non-empty absolute http:// or https:// URL",
            )
        current_store: URLStore = request.app.state.store
        code = current_store.add(url)
        base = str(request.base_url).rstrip("/")
        return ShortenResponse(code=code, short_url=f"{base}/{code}")

    @app.get("/{code}")
    def resolve(code: str, request: Request) -> RedirectResponse:
        current_store: URLStore = request.app.state.store
        original = current_store.get(code)
        if original is None:
            raise HTTPException(status_code=404, detail="unknown short code")
        return RedirectResponse(url=original, status_code=302)

    return app


# Module-level app for ``uvicorn url_shortner.app:app`` in production.
app = create_app()
