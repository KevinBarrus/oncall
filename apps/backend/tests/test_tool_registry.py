from __future__ import annotations

from typing import Any

import pytest

from super_ai.mcp_client import McpToolDefinition
from super_ai.tool_registry import ToolRegistry


class FakeMcpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def discover_tools(self) -> list[McpToolDefinition]:
        return [
            McpToolDefinition("search_log", "Search logs A", {}, "server_a"),
            McpToolDefinition("search_log", "Search logs B", {}, "server_b"),
        ]

    async def call_tool_on_server(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> object:
        self.calls.append((server_name, tool_name, arguments))
        return server_name


@pytest.mark.asyncio
async def test_registry_routes_same_mcp_tool_name_to_provider() -> None:
    client = FakeMcpClient()
    registry = ToolRegistry()

    await registry.register_mcp(client)  # type: ignore[arg-type]

    assert registry.names() == [
        "mcp__server_a__search_log",
        "mcp__server_b__search_log",
    ]
    assert await registry.execute("mcp__server_a__search_log", {}) == "server_a"
    assert await registry.execute("mcp__server_b__search_log", {}) == "server_b"
    tools = registry.langchain_tools()
    assert await tools[0].ainvoke({}) == "server_a"
    assert client.calls == [
        ("server_a", "search_log", {}),
        ("server_b", "search_log", {}),
        ("server_a", "search_log", {}),
    ]


def test_registry_rejects_duplicate_local_public_name() -> None:
    registry = ToolRegistry()

    async def handler(_arguments: dict[str, Any]) -> object:
        return None

    registry.register_local_handler(name="same", description="one", handler=handler)
    with pytest.raises(ValueError, match="Duplicate Agent tool name"):
        registry.register_local_handler(name="same", description="two", handler=handler)
