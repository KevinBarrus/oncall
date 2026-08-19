from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast

import pytest

import super_ai.mcp_client as mcp_client_module
import super_ai.mcp_connections as mcp_connections_module
from super_ai.mcp_client import LocalMcpClient, McpClientError, McpServerConnection
from super_ai.mcp_connections import McpConnectionService
from super_ai.memory.repositories import McpConnectionRecord, MemoryRepositories


class _Streams(AbstractAsyncContextManager[tuple[object, object]]):
    def __init__(self) -> None:
        self.opens = 0
        self.closes = 0

    async def __aenter__(self) -> tuple[object, object]:
        self.opens += 1
        return object(), object()

    async def __aexit__(self, *args: object) -> None:
        self.closes += 1


class _Session(AbstractAsyncContextManager["_Session"]):
    def __init__(self) -> None:
        self.initializations = 0
        self.calls = 0

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def initialize(self) -> None:
        self.initializations += 1

    async def list_tools(self) -> object:
        return SimpleNamespace(tools=[])

    async def call_tool(self, _name: str, _arguments: dict[str, Any], **_kwargs: object) -> object:
        self.calls += 1
        return SimpleNamespace(
            isError=False,
            content=[SimpleNamespace(type="text", text="result")],
        )


@pytest.mark.asyncio
async def test_local_mcp_client_reuses_server_session_and_tool_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    streams = _Streams()
    session = _Session()

    def fake_sse(*_args: object, **_kwargs: object) -> _Streams:
        return streams

    def fake_session(*_args: object) -> _Session:
        return session

    monkeypatch.setattr(mcp_client_module, "sse_client", fake_sse)
    monkeypatch.setattr(mcp_client_module, "ClientSession", fake_session)
    client = LocalMcpClient("http://mcp.test/sse", retries=0)

    assert await client.call_tool("search_log", {}) == [{"type": "text", "text": "result"}]
    assert await client.call_tool("search_log", {}) == [{"type": "text", "text": "result"}]

    assert streams.opens == 1
    assert session.initializations == 1
    assert session.calls == 2
    await client.aclose()
    assert streams.closes == 1


class _ConnectionRepository:
    def __init__(self, records: list[McpConnectionRecord]) -> None:
        self.records = records

    async def list(self, *, owner_user_id: str) -> list[McpConnectionRecord]:
        assert owner_user_id == "user_1"
        return self.records


class _FakeClient:
    def __init__(self, *, connections: tuple[object, ...]) -> None:
        self.connections = connections
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


def _record(url: str) -> McpConnectionRecord:
    now = datetime.now(timezone.utc)
    return McpConnectionRecord(
        id="mcp_1",
        owner_user_id="user_1",
        name="CLS",
        transport="sse",
        url=url,
        enabled=True,
        timeout_seconds=15,
        retries=1,
        last_check_ok=None,
        last_tool_count=None,
        last_tools=[],
        last_error=None,
        last_checked_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_mcp_connection_service_replaces_client_when_configuration_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _ConnectionRepository([_record("http://mcp.test/sse")])
    monkeypatch.setattr(mcp_connections_module, "LocalMcpClient", _FakeClient)
    service = McpConnectionService(
        cast(MemoryRepositories, SimpleNamespace(mcp_connections=repository)),
        default_url="http://default.test/sse",
        default_timeout_seconds=15,
        default_retries=1,
    )

    first = await service.client_for_user(owner_user_id="user_1")
    assert await service.client_for_user(owner_user_id="user_1") is first
    repository.records = [_record("http://mcp.changed/sse")]
    second = await service.client_for_user(owner_user_id="user_1")

    assert second is not first
    assert cast(_FakeClient, first).closed
    await service.aclose()
    assert cast(_FakeClient, second).closed


@pytest.mark.asyncio
async def test_mcp_discovery_keeps_healthy_server_tools_when_another_server_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = LocalMcpClient(
        connections=[
            McpServerConnection("healthy", "http://healthy.test/sse", retries=0),
            McpServerConnection("broken", "http://broken.test/sse", retries=0),
        ]
    )

    async def discover_on_connection(
        connection: McpServerConnection, _operation: object
    ) -> object:
        if connection.name == "broken":
            raise McpClientError("broken")
        return SimpleNamespace(
            tools=[SimpleNamespace(name="search_log", description="Search logs", inputSchema={})]
        )

    monkeypatch.setattr(client, "_run_connection", discover_on_connection)

    assert [tool.name for tool in await client.discover_tools()] == ["search_log"]
    assert await client.readiness() == {
        "ok": True,
        "endpoint": "http://healthy.test/sse",
        "toolCount": 1,
        "error": None,
        "servers": [
            {
                "name": "healthy",
                "endpoint": "http://healthy.test/sse",
                "ok": True,
                "toolCount": 1,
                "error": None,
            },
            {
                "name": "broken",
                "endpoint": "http://broken.test/sse",
                "ok": False,
                "toolCount": 0,
                "error": "MCP server is unavailable.",
            },
        ],
    }


@pytest.mark.asyncio
async def test_mcp_discovery_returns_no_tools_when_all_servers_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = LocalMcpClient(
        connections=[McpServerConnection("broken", "http://broken.test/sse", retries=0)]
    )

    async def fail_discovery(_connection: McpServerConnection, _operation: object) -> object:
        raise McpClientError("broken")

    monkeypatch.setattr(client, "_run_connection", fail_discovery)

    assert await client.discover_tools() == []
    assert (await client.readiness())["ok"] is False
