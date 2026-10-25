from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from finsight.api.main import _is_loopback_host, create_app, run
from finsight.api.security import InMemoryRateLimiter
from finsight.config import Settings
from tests.factories import research_response


def _runner(*_args: object, **_kwargs: object):
    return research_response()


def test_api_health_auth_research_and_request_lookup() -> None:
    settings = Settings(
        api_key=SecretStr("local-test-secret"),
        rate_limit_requests=10,
    )
    client = TestClient(create_app(settings, researcher=_runner))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.headers["x-request-id"]

    unauthorized = client.post("/research", json={"ticker": "AAPL"})
    assert unauthorized.status_code == 401

    headers = {"Authorization": "Bearer local-test-secret"}
    created = client.post("/research", json={"ticker": "AAPL"}, headers=headers)
    assert created.status_code == 200
    assert created.json()["ticker"] == "AAPL"

    retrieved = client.get("/research/test-request", headers=headers)
    assert retrieved.status_code == 200
    assert retrieved.json()["request_id"] == "test-request"


def test_api_rejects_duplicate_or_subject_peer_tickers() -> None:
    client = TestClient(create_app(Settings(), researcher=_runner))
    response = client.post(
        "/research",
        json={"ticker": "AAPL", "peer_tickers": ["MSFT", "msft"]},
    )

    assert response.status_code == 422


def test_api_rate_limit_returns_retry_after() -> None:
    settings = Settings(rate_limit_requests=1, rate_limit_window_seconds=60)
    client = TestClient(create_app(settings, researcher=_runner))

    first = client.post("/research", json={"ticker": "AAPL"})
    second = client.post("/research", json={"ticker": "AAPL"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers["retry-after"]) >= 1


def test_api_request_logs_are_structured_and_omit_credentials(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = TestClient(
        create_app(Settings(api_key=SecretStr("do-not-log-this")), researcher=_runner)
    )
    caplog.set_level(logging.INFO, logger="finsight.api")

    response = client.post(
        "/research",
        json={"ticker": "AAPL"},
        headers={"Authorization": "Bearer do-not-log-this"},
    )

    event = next(
        json.loads(record.message)
        for record in caplog.records
        if record.name == "finsight.api" and '"event":"http_request"' in record.message
    )
    assert response.status_code == 200
    assert event["route"] == "/research"
    assert event["status_code"] == 200
    assert event["duration_ms"] >= 0
    assert "do-not-log-this" not in caplog.text


def test_rate_limiter_window_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [100.0]
    monkeypatch.setattr("finsight.api.security.monotonic", lambda: now[0])
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=10)

    assert limiter.retry_after("client-a") is None
    assert limiter.retry_after("client-a") == 10
    now[0] = 110.0
    assert limiter.retry_after("client-a") is None


def test_non_loopback_api_bind_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "finsight.api.main.get_settings",
        lambda: Settings(api_host="0.0.0.0", api_key=SecretStr("")),
    )

    with pytest.raises(RuntimeError, match="API_KEY"):
        run()


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1"])
def test_loopback_host_detection(host: str) -> None:
    assert _is_loopback_host(host)


def test_non_loopback_host_detection() -> None:
    assert not _is_loopback_host("0.0.0.0")
