from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from llm_replay_proxy.config import ReplayMode, Settings
from llm_replay_proxy.fingerprint import RequestFingerprint, fingerprint_request
from llm_replay_proxy.models import Cassette, StoredResponse
from llm_replay_proxy.store import CassetteStore, CassetteStoreError

_HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
_STORED_RESPONSE_HEADERS = {"content-type", "retry-after"}


@dataclass(slots=True)
class ProxyStats:
    hits: int = 0
    misses: int = 0
    forwarded: int = 0
    recorded: int = 0


def _reject_non_finite_number(value: str) -> object:
    raise ValueError(f"non-finite number {value!r} is not valid JSON")


def _forward_headers(request: Request, auth_env: str | None) -> dict[str, str]:
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in _HOP_BY_HOP_HEADERS
    }
    if auth_env:
        token = os.environ.get(auth_env)
        if not token:
            raise RuntimeError(f"environment variable {auth_env!r} is not set")
        headers["authorization"] = f"Bearer {token}"
    return headers


def _stored_headers(response: httpx.Response) -> dict[str, str]:
    return {
        key.lower(): value
        for key, value in response.headers.items()
        if key.lower() in _STORED_RESPONSE_HEADERS
    }


def _replayed_response(cassette: Cassette) -> Response:
    headers = dict(cassette.response.headers)
    headers["x-llm-replay"] = "hit"
    return Response(
        content=cassette.response.body.encode("utf-8"),
        status_code=cassette.response.status_code,
        headers=headers,
    )


def _recorded_response(response: httpx.Response) -> Response:
    headers = _stored_headers(response)
    headers["x-llm-replay"] = "recorded"
    return Response(content=response.content, status_code=response.status_code, headers=headers)


def _build_upstream_url(settings: Settings, fingerprint: RequestFingerprint) -> str:
    if settings.upstream_base_url is None:
        raise RuntimeError("upstream URL is unavailable in replay-only mode")
    url = f"{settings.upstream_base_url.rstrip('/')}{fingerprint.path}"
    if fingerprint.query:
        query = httpx.QueryParams(list(fingerprint.query))
        url = f"{url}?{query}"
    return url


def create_app(
    settings: Settings,
    *,
    upstream_client: httpx.AsyncClient | None = None,
) -> FastAPI:
    store = CassetteStore(settings.cassette_dir)
    stats = ProxyStats()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if app.state.upstream_client is None and settings.upstream_base_url is not None:
            app.state.upstream_client = httpx.AsyncClient(timeout=settings.timeout_seconds)
            app.state.owns_upstream_client = True
        yield
        if app.state.owns_upstream_client:
            await app.state.upstream_client.aclose()

    app = FastAPI(
        title="llm-replay-proxy",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.upstream_client = upstream_client
    app.state.owns_upstream_client = False

    @app.get("/_replay/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "mode": settings.mode.value,
            "cassettes": len(store),
            "upstream": settings.upstream_base_url,
        }

    @app.get("/_replay/stats")
    async def replay_stats() -> dict[str, int]:
        return asdict(stats)

    @app.api_route("/{path:path}", methods=["POST"])
    async def proxy_request(path: str, request: Request) -> Response:
        try:
            request_body = json.loads(
                await request.body(),
                parse_constant=_reject_non_finite_number,
            )
        except (json.JSONDecodeError, ValueError):
            return JSONResponse(
                status_code=400,
                content={"detail": "request body must be valid JSON"},
            )

        if isinstance(request_body, dict) and request_body.get("stream") is True:
            return JSONResponse(
                status_code=422,
                content={"detail": "streaming responses are not supported"},
            )

        fingerprint = fingerprint_request(
            method=request.method,
            path=path,
            query=request.url.query,
            body=request_body,
        )
        try:
            cassette = store.load(fingerprint.key)
        except CassetteStoreError as exc:
            return JSONResponse(status_code=500, content={"detail": str(exc)})

        if cassette is not None and settings.mode is not ReplayMode.RECORD:
            stats.hits += 1
            return _replayed_response(cassette)

        stats.misses += 1
        if settings.mode is ReplayMode.REPLAY:
            return JSONResponse(
                status_code=404,
                content={
                    "detail": "no cassette matches this request",
                    "request_key": fingerprint.key,
                },
                headers={"x-llm-replay": "miss"},
            )

        client = app.state.upstream_client
        if client is None:
            return JSONResponse(
                status_code=503,
                content={"detail": "upstream client is unavailable"},
            )

        try:
            headers = _forward_headers(request, settings.auth_env)
            response = await client.request(
                method=request.method,
                url=_build_upstream_url(settings, fingerprint),
                headers=headers,
                content=await request.body(),
            )
        except RuntimeError as exc:
            return JSONResponse(status_code=500, content={"detail": str(exc)})
        except httpx.RequestError as exc:
            return JSONResponse(
                status_code=502,
                content={"detail": f"upstream request failed: {exc}"},
            )

        stats.forwarded += 1
        cassette = Cassette.create(
            key=fingerprint.key,
            method=fingerprint.method,
            path=fingerprint.path,
            query=fingerprint.query,
            request_body=fingerprint.body,
            response=StoredResponse(
                status_code=response.status_code,
                headers=_stored_headers(response),
                body=response.text,
            ),
        )
        try:
            store.save(cassette)
        except CassetteStoreError as exc:
            return JSONResponse(status_code=500, content={"detail": str(exc)})
        stats.recorded += 1
        return _recorded_response(response)

    return app
