from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from llm_replay_proxy.config import ReplayMode, Settings
from llm_replay_proxy.proxy import create_app


def settings_for(
    tmp_path: Path,
    *,
    mode: ReplayMode = ReplayMode.AUTO,
    auth_env: str | None = None,
) -> Settings:
    return Settings(
        cassette_dir=tmp_path,
        mode=mode,
        upstream_base_url=None if mode is ReplayMode.REPLAY else "https://upstream.test",
        auth_env=auth_env,
    )


@pytest.mark.asyncio
async def test_auto_mode_records_then_replays_semantic_match(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={"id": "recorded", "choices": [{"message": {"content": "hello"}}]},
            headers={"content-type": "application/json", "x-secret-header": "discard-me"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        app = create_app(settings_for(tmp_path), upstream_client=upstream)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://proxy") as client:
            first = await client.post(
                "/v1/chat/completions?region=eu&version=1",
                json={"model": "demo", "messages": [{"role": "user", "content": "hello"}]},
            )
            second = await client.post(
                "/v1/chat/completions?version=1&region=eu",
                json={"messages": [{"content": "hello", "role": "user"}], "model": "demo"},
            )
            stats = await client.get("/_replay/stats")
            health = await client.get("/_replay/health")

    assert len(calls) == 1
    assert first.headers["x-llm-replay"] == "recorded"
    assert second.headers["x-llm-replay"] == "hit"
    assert second.json() == first.json()
    assert "x-secret-header" not in second.headers
    assert stats.json() == {"hits": 1, "misses": 1, "forwarded": 1, "recorded": 1}
    assert health.json()["cassettes"] == 1


@pytest.mark.asyncio
async def test_replay_mode_miss_never_calls_upstream(tmp_path: Path) -> None:
    app = create_app(settings_for(tmp_path, mode=ReplayMode.REPLAY))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://proxy") as client:
        response = await client.post("/v1/responses", json={"model": "demo", "input": "hello"})

    assert response.status_code == 404
    assert response.headers["x-llm-replay"] == "miss"
    assert len(response.json()["request_key"]) == 64


@pytest.mark.asyncio
async def test_record_mode_refreshes_existing_cassette(tmp_path: Path) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={"attempt": call_count})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        record_app = create_app(
            settings_for(tmp_path, mode=ReplayMode.RECORD),
            upstream_client=upstream,
        )
        record_transport = httpx.ASGITransport(app=record_app)
        async with httpx.AsyncClient(
            transport=record_transport,
            base_url="http://proxy",
        ) as client:
            await client.post("/v1/responses", json={"model": "demo", "input": "same"})
            second = await client.post(
                "/v1/responses",
                json={"model": "demo", "input": "same"},
            )

    replay_app = create_app(settings_for(tmp_path, mode=ReplayMode.REPLAY))
    replay_transport = httpx.ASGITransport(app=replay_app)
    async with httpx.AsyncClient(transport=replay_transport, base_url="http://proxy") as client:
        replayed = await client.post(
            "/v1/responses",
            json={"model": "demo", "input": "same"},
        )

    assert call_count == 2
    assert second.json() == {"attempt": 2}
    assert replayed.json() == {"attempt": 2}


@pytest.mark.asyncio
async def test_streaming_requests_are_rejected_before_forwarding(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"unexpected": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        app = create_app(settings_for(tmp_path), upstream_client=upstream)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://proxy") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={"model": "demo", "stream": True},
            )

    assert response.status_code == 422
    assert calls == 0


@pytest.mark.asyncio
async def test_invalid_json_is_rejected(tmp_path: Path) -> None:
    app = create_app(settings_for(tmp_path, mode=ReplayMode.REPLAY))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://proxy") as client:
        response = await client.post(
            "/v1/responses",
            content="{broken",
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_non_finite_json_number_is_rejected(tmp_path: Path) -> None:
    app = create_app(settings_for(tmp_path, mode=ReplayMode.REPLAY))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://proxy") as client:
        response = await client.post(
            "/v1/responses",
            content='{"temperature":NaN}',
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_auth_env_is_forwarded_but_never_recorded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_authorization = ""
    monkeypatch.setenv("TEST_LLM_TOKEN", "top-secret-token")

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_authorization
        seen_authorization = request.headers["authorization"]
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        app = create_app(
            settings_for(tmp_path, auth_env="TEST_LLM_TOKEN"),
            upstream_client=upstream,
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://proxy") as client:
            response = await client.post(
                "/v1/responses",
                json={"model": "demo", "input": "hello"},
                headers={"authorization": "Bearer caller-token"},
            )

    cassette_text = next(tmp_path.glob("*.json")).read_text(encoding="utf-8")
    assert response.status_code == 200
    assert seen_authorization == "Bearer top-secret-token"
    assert "top-secret-token" not in cassette_text
    assert "caller-token" not in cassette_text


@pytest.mark.asyncio
async def test_missing_auth_env_returns_clear_error(tmp_path: Path) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200))
    async with httpx.AsyncClient(transport=transport) as upstream:
        app = create_app(
            settings_for(tmp_path, auth_env="MISSING_LLM_TOKEN"),
            upstream_client=upstream,
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://proxy") as client:
            response = await client.post("/v1/responses", json={"model": "demo"})

    assert response.status_code == 500
    assert "MISSING_LLM_TOKEN" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upstream_network_error_becomes_bad_gateway(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        app = create_app(settings_for(tmp_path), upstream_client=upstream)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://proxy") as client:
            response = await client.post("/v1/responses", json={"model": "demo"})

    assert response.status_code == 502
    assert "connection refused" in response.json()["detail"]


@pytest.mark.asyncio
async def test_corrupt_matching_cassette_returns_server_error(tmp_path: Path) -> None:
    body = {"model": "demo"}
    from llm_replay_proxy.fingerprint import fingerprint_request

    key = fingerprint_request("POST", "/v1/responses", "", body).key
    (tmp_path / f"{key}.json").write_text(json.dumps({"key": "bad"}), encoding="utf-8")
    app = create_app(settings_for(tmp_path, mode=ReplayMode.REPLAY))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://proxy") as client:
        response = await client.post("/v1/responses", json=body)

    assert response.status_code == 500
    assert "cannot read cassette" in response.json()["detail"]
