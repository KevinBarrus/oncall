"""Request-scoped registry for local and MCP Agent tools."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast

from langchain_core.tools import StructuredTool

from super_ai.mcp_client import LocalMcpClient, McpToolDefinition

ToolHandler = Callable[[dict[str, Any]], Awaitable[object]]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """The Agent-facing definition and provider routing identity."""

    tool_id: str
    name: str
    native_name: str
    description: str
    input_schema: dict[str, Any]
    provider_type: str
    provider_id: str


class ToolExecutor(Protocol):
    async def execute(self, definition: ToolDefinition, arguments: dict[str, Any]) -> object:
        ...


class LocalToolExecutor:
    def __init__(self, handler: ToolHandler) -> None:
        self._handler = handler

    async def execute(self, definition: ToolDefinition, arguments: dict[str, Any]) -> object:
        return await self._handler(arguments)


class McpToolExecutor:
    def __init__(self, client: LocalMcpClient) -> None:
        self._client = client

    async def execute(self, definition: ToolDefinition, arguments: dict[str, Any]) -> object:
        call_on_server = getattr(self._client, "call_tool_on_server", None)
        if callable(call_on_server):
            invoke = cast(Callable[..., Awaitable[object]], call_on_server)
            return await invoke(definition.provider_id, definition.native_name, arguments)
        return await self._client.call_tool(definition.native_name, arguments)


@dataclass(frozen=True, slots=True)
class _ToolEntry:
    definition: ToolDefinition
    executor: ToolExecutor
    langchain_tool: StructuredTool | None = None


class ToolRegistry:
    """Small request-scoped registry; it never contains another user's tools."""

    def __init__(self) -> None:
        self._entries: dict[str, _ToolEntry] = {}

    def register_local_tool(self, tool: StructuredTool) -> None:
        async def invoke(arguments: dict[str, Any]) -> object:
            return await cast(Any, tool).ainvoke(arguments)

        definition = ToolDefinition(
            tool_id=f"local:{tool.name}",
            name=tool.name,
            native_name=tool.name,
            description=tool.description,
            input_schema=_tool_schema(tool),
            provider_type="local",
            provider_id="local",
        )
        self._register(definition, LocalToolExecutor(invoke), tool)

    def register_local_handler(
        self,
        *,
        name: str,
        description: str,
        handler: ToolHandler,
        input_schema: dict[str, Any] | None = None,
    ) -> None:
        definition = ToolDefinition(
            tool_id=f"local:{name}",
            name=name,
            native_name=name,
            description=description,
            input_schema=input_schema or {"type": "object"},
            provider_type="local",
            provider_id="local",
        )
        self._register(definition, LocalToolExecutor(handler))

    async def register_mcp(
        self, client: LocalMcpClient, *, with_langchain_tools: bool = True
    ) -> None:
        definitions = await client.discover_tools()
        counts: dict[str, int] = {}
        for definition in definitions:
            counts[definition.name] = counts.get(definition.name, 0) + 1

        for definition in definitions:
            qualified = counts[definition.name] > 1 or definition.name in self._entries
            public_name = (
                _qualified_name(definition.server_name, definition.name)
                if qualified
                else definition.name
            )
            description = (
                _qualified_mcp_description(definition.description, definition, public_name)
                if qualified
                else definition.description
            )
            wrapped = self._mcp_langchain_tool(
                public_name, description, definition.input_schema
            ) if with_langchain_tools else None
            self._register(
                ToolDefinition(
                    tool_id=f"mcp:{definition.server_name}:{definition.name}",
                    name=public_name,
                    native_name=definition.name,
                    description=description,
                    input_schema=definition.input_schema,
                    provider_type="mcp",
                    provider_id=definition.server_name,
                ),
                McpToolExecutor(client),
                wrapped,
            )

    def definitions(self) -> list[ToolDefinition]:
        return [entry.definition for entry in self._entries.values()]

    def names(self) -> list[str]:
        return list(self._entries)

    async def execute(self, name: str, arguments: Mapping[str, Any]) -> object:
        entry = self._entries.get(name)
        if entry is None:
            raise KeyError(f"Unknown Agent tool: {name}")
        return await entry.executor.execute(entry.definition, dict(arguments))

    def langchain_tools(self) -> list[StructuredTool]:
        return [
            entry.langchain_tool
            for entry in self._entries.values()
            if entry.langchain_tool is not None
        ]

    def _register(
        self,
        definition: ToolDefinition,
        executor: ToolExecutor,
        langchain_tool: StructuredTool | None = None,
    ) -> None:
        if definition.name in self._entries:
            raise ValueError(f"Duplicate Agent tool name: {definition.name}")
        self._entries[definition.name] = _ToolEntry(definition, executor, langchain_tool)

    def _mcp_langchain_tool(
        self, public_name: str, description: str, input_schema: dict[str, Any]
    ) -> StructuredTool:
        async def invoke(**arguments: object) -> object:
            return await self.execute(public_name, arguments)

        return StructuredTool.from_function(
            coroutine=invoke,
            name=public_name,
            description=description,
            args_schema=input_schema,
        )


def _qualified_name(provider_id: str, native_name: str) -> str:
    return f"mcp__{_safe_name(provider_id)}__{_safe_name(native_name)}"


def _qualified_mcp_description(
    description: str, definition: McpToolDefinition, public_name: str
) -> str:
    return (
        f"{description}\n\n"
        f"MCP provider: {definition.server_name}\n"
        f"Original MCP tool name: {definition.name}\n"
        f"Qualified Agent tool name: {public_name}"
    )


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char == "_" else "_" for char in value)


def _tool_schema(tool: StructuredTool) -> dict[str, Any]:
    schema = getattr(tool.args_schema, "model_json_schema", None)
    if callable(schema):
        return cast(dict[str, Any], schema())
    return {"type": "object"}
