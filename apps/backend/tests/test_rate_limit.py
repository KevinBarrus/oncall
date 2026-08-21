"""Per-user rate limiting: limiter unit tests and API 429 integration."""

from __future__ import annotations

from pathlib import Path
from time import monotonic

import httpx
import pytest
from alembic import command
from alembic.config import Config

from super_ai.api.app import create_app
from super_ai.api.rate_limit import SlidingWindowLimiter


@pytest.fixture
def migrated_database_url(tmp_path: Path) -> str:
    database_path = tmp_path / "rate-limit.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(config, "head")
    return f"sqlite+aiosqlite:///{database_path}"


def test_sliding_window_allows_within_limit_and_rejects_overflow() -> None:
    limiter = SlidingWindowLimiter(limit=3, window_seconds=60)
    assert limiter.allow("user_a") is True
    assert limiter.allow("user_a") is True
    assert limiter.allow("user_a") is True
    assert limiter.allow("user_a") is False
    assert limiter.allow("user_b") is True


def test_sliding_window_expires_after_window() -> None:
    limiter = SlidingWindowLimiter(limit=2, window_seconds=0.1)
    assert limiter.allow("user_a") is True
    assert limiter.allow("user_a") is True
    assert limiter.allow("user_a") is False

    start = monotonic()
    while monotonic() - start < 0.2:
        pass
    assert limiter.allow("user_a") is True


@pytest.mark.asyncio
async def test_aiops_diagnosis_endpoint_returns_429_when_rate_limited(
    migrated_database_url: str,
) -> None:
    app = create_app(database_url=migrated_database_url)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        user = await _register(client)
        headers = {"Authorization": f"Bearer {user['accessToken']}"}

        for index in range(11):
            response = await client.post(
                "/aiops/diagnostics",
                headers=headers,
                json={"query": "排查 API 延迟告警"},
            )
            if index < 10:
                assert response.status_code == 202, response.text
            else:
                assert response.status_code == 429
                assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


async def _register(client: httpx.AsyncClient) -> dict[str, object]:
    response = await client.post(
        "/auth/register",
        json={
            "email": "rate-limit-owner@example.com",
            "password": "RateLimit123456",
            "displayName": "Rate Limit Owner",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]
