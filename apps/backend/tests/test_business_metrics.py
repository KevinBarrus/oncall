"""Business metrics registry and /metrics endpoint integration tests."""

from __future__ import annotations

import pytest

from super_ai.observability import (
    record_business_metric,
    reset_business_metrics,
    snapshot_business_metrics,
)


@pytest.fixture(autouse=True)
def _isolate_business_metrics() -> None:  # pyright: ignore[reportUnusedFunction]
    reset_business_metrics()


def test_business_metrics_accumulate_total_and_samples() -> None:
    record_business_metric("chat_streams")
    record_business_metric("chat_streams")
    record_business_metric("chat_context_tokens", 4000.0)

    snapshot = snapshot_business_metrics()
    assert snapshot["chat_streams"] == {"count": 2, "total": 2.0, "average": 1.0}
    assert snapshot["chat_context_tokens"]["count"] == 1
    assert snapshot["chat_context_tokens"]["total"] == 4000.0
    assert snapshot["chat_context_tokens"]["average"] == 4000.0


def test_business_metrics_snapshot_is_sorted_and_empty_initial() -> None:
    assert snapshot_business_metrics() == {}
    record_business_metric("z_last")
    record_business_metric("a_first")
    assert list(snapshot_business_metrics().keys()) == ["a_first", "z_last"]


@pytest.mark.asyncio
async def test_metrics_endpoint_includes_business_metrics() -> None:
    import httpx

    from super_ai.api.app import create_app

    app = create_app(database_url="sqlite+aiosqlite:///:memory:")
    transport = httpx.ASGITransport(app=app)
    record_business_metric("chat_streams")
    record_business_metric("mcp_tool_latency_ms", 120.0)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")
        body = response.json()
    assert response.status_code == 200
    business = body["data"]["business"]
    assert business["chat_streams"]["count"] == 1
    assert business["mcp_tool_latency_ms"]["average"] == 120.0
