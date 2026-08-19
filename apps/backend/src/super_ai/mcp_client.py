"""Client boundary for the local official MCP SSE server."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client

from super_ai.observability import elapsed_ms, emit_event

logger = logging.getLogger(__name__)
_TOOL_DISCOVERY_TTL_SECONDS = 60


@dataclass(frozen=True, slots=True)
class McpToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str = "default"


@dataclass(frozen=True, slots=True)
class McpServerConnection:
    name: str
    url: str
    transport: str = "sse"
    timeout_seconds: float = 15
    retries: int = 1


class McpClientError(RuntimeError):
    pass


@dataclass(slots=True)
class _McpSession:
    lock: asyncio.Lock
    stack: AsyncExitStack | None = None
    session: ClientSession | None = None


@dataclass(frozen=True, slots=True)
class _McpServerReadiness:
    name: str
    endpoint: str
    ok: bool
    tool_count: int
    error: str | None = None


def create_current_time_tool() -> Any:
    """Create the explicit time tool used before time-range MCP queries."""
    from langchain_core.tools import StructuredTool

    def get_current_time() -> dict[str, object]:
        now = datetime.now(timezone.utc)
        return {"iso8601": now.isoformat(), "unixMilliseconds": int(now.timestamp() * 1000)}

    return StructuredTool.from_function(
        func=get_current_time,
        name="get_current_time",
        description="Return the current UTC time and Unix timestamp in milliseconds.",
    )


class LocalMcpClient:
    def __init__(
        self,
        endpoint: str | None = None,
        *,
        timeout_seconds: float = 15,
        retries: int = 1,
        connections: Sequence[McpServerConnection] | None = None,
    ) -> None:
        configured = list(connections or [])
        if not configured and endpoint is not None:
            configured = [
                McpServerConnection(
                    name="cls",
                    url=endpoint,
                    transport="sse",
                    timeout_seconds=timeout_seconds,
                    retries=retries,
                )
            ]
        self._connections = tuple(configured)
        self._sessions = {connection.name: _McpSession(asyncio.Lock()) for connection in configured}
        self._discovered_tools: tuple[McpToolDefinition, ...] | None = None
        self._discovered_at = 0.0
        self._server_readiness: tuple[_McpServerReadiness, ...] = ()

    async def discover_tools(self) -> list[McpToolDefinition]:
        if (
            self._discovered_tools is not None
            and monotonic() - self._discovered_at < _TOOL_DISCOVERY_TTL_SECONDS
        ):
            return list(self._discovered_tools)
        definitions: list[McpToolDefinition] = []
        readiness: list[_McpServerReadiness] = []
        for connection in self._connections:
            try:
                result = await self._run_connection(
                    connection,
                    lambda session: session.list_tools(),
                )
            except McpClientError:
                readiness.append(
                    _McpServerReadiness(
                        connection.name,
                        connection.url,
                        False,
                        0,
                        "MCP server is unavailable.",
                    )
                )
                continue
            readiness.append(
                _McpServerReadiness(connection.name, connection.url, True, len(result.tools))
            )
            for tool in result.tools:
                definitions.append(
                    McpToolDefinition(
                        tool.name,
                        tool.description or "MCP tool",
                        tool.inputSchema,
                        connection.name,
                    )
                )
        self._discovered_tools = tuple(definitions)
        self._discovered_at = monotonic()
        self._server_readiness = tuple(readiness)
        return definitions

    async def aclose(self) -> None:
        for entry in self._sessions.values():
            async with entry.lock:
                await self._close_session(entry)

    async def readiness(self) -> dict[str, object]:
        tools = await self.discover_tools()
        servers = [
            {
                "name": item.name,
                "endpoint": item.endpoint,
                "ok": item.ok,
                "toolCount": item.tool_count,
                "error": item.error,
            }
            for item in self._server_readiness
        ]
        is_ready = any(item.ok for item in self._server_readiness)
        return {
            "ok": is_ready,
            "endpoint": self._connections[0].url if self._connections else None,
            "toolCount": len(tools),
            "error": None if is_ready else "MCP server is unavailable.",
            "servers": servers,
        }

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return await self._call_tool(name, arguments)

    async def call_tool_on_server(
        self,
        server_name: str,
        name: str,
        arguments: dict[str, Any],
    ) -> Any:
        connection = next(
            (item for item in self._connections if item.name == server_name),
            None,
        )
        if connection is None:
            raise McpClientError(f"MCP server is unavailable: {server_name}")
        return await self._call_tool(name, arguments, connection=connection)

    async def _call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        connection: McpServerConnection | None = None,
    ) -> Any:
        started_at = monotonic()
        emit_event(logger, "mcp.tool.started", toolName=name, argumentKeys=sorted(arguments))
        try:
            if connection is not None:
                result = await self._run_connection(
                    connection,
                    lambda session: session.call_tool(
                        name,
                        arguments,
                        read_timeout_seconds=timedelta(
                            seconds=connection.timeout_seconds
                        ),
                    ),
                )
            elif len(self._connections) == 1:
                connection = self._connections[0]
                result = await self._run(
                    lambda session: session.call_tool(
                        name,
                        arguments,
                        read_timeout_seconds=timedelta(
                            seconds=connection.timeout_seconds
                        ),
                    )
                )
            else:
                matching = [tool for tool in await self.discover_tools() if tool.name == name]
                if len(matching) != 1:
                    raise McpClientError(f"MCP tool is unavailable or ambiguous: {name}")
                connection = next(
                    item for item in self._connections if item.name == matching[0].server_name
                )
                result = await self._run_connection(
                    connection,
                    lambda session: session.call_tool(
                        name,
                        arguments,
                        read_timeout_seconds=timedelta(
                            seconds=connection.timeout_seconds
                        ),
                    ),
                )
        except Exception as exc:
            emit_event(
                logger,
                "mcp.tool.failed",
                toolName=name,
                errorCategory=exc.__class__.__name__,
                durationMs=elapsed_ms(started_at),
            )
            raise
        if result.isError:
            emit_event(
                logger,
                "mcp.tool.failed",
                toolName=name,
                errorCategory="McpToolError",
                durationMs=elapsed_ms(started_at),
            )
            raise McpClientError(f"MCP tool {name} returned an error")
        payload = [
            {"type": item.type, "text": getattr(item, "text", None)} for item in result.content
        ]
        emit_event(
            logger,
            "mcp.tool.completed",
            toolName=name,
            resultItemCount=len(payload),
            durationMs=elapsed_ms(started_at),
        )
        return payload

    async def _run(self, operation: Callable[[Any], Awaitable[Any]]) -> Any:
        if len(self._connections) != 1:
            raise McpClientError("A single MCP connection is required for this operation.")
        return await self._run_connection(self._connections[0], operation)

    async def _run_connection(
        self,
        connection: McpServerConnection,
        operation: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        entry = self._sessions[connection.name]
        async with entry.lock:
            error: Exception | None = None
            for attempt in range(connection.retries + 1):
                try:
                    session = await self._get_session(connection, entry)
                    return await asyncio.wait_for(
                        operation(session), timeout=connection.timeout_seconds
                    )
                except Exception as exc:
                    error = exc
                    self._discovered_tools = None
                    await self._close_session(entry)
                    if attempt < connection.retries:
                        await asyncio.sleep(0.2 * (attempt + 1))
        raise McpClientError(f"MCP server unavailable at {connection.url}") from error

    async def _get_session(
        self,
        connection: McpServerConnection,
        entry: _McpSession,
    ) -> ClientSession:
        if entry.session is not None:
            return entry.session
        stack = AsyncExitStack()
        try:
            if connection.transport == "streamable_http":
                http_client = await stack.enter_async_context(
                    httpx.AsyncClient(timeout=connection.timeout_seconds)
                )
                streams = await stack.enter_async_context(
                    streamable_http_client(connection.url, http_client=http_client)
                )
            else:
                streams = await stack.enter_async_context(
                    sse_client(
                        connection.url,
                        timeout=connection.timeout_seconds,
                        sse_read_timeout=connection.timeout_seconds,
                    )
                )
            session = await stack.enter_async_context(ClientSession(streams[0], streams[1]))
            await asyncio.wait_for(session.initialize(), timeout=connection.timeout_seconds)
        except Exception:
            await stack.aclose()
            raise
        entry.stack = stack
        entry.session = session
        return session

    async def _close_session(self, entry: _McpSession) -> None:
        stack = entry.stack
        entry.stack = None
        entry.session = None
        if stack is not None:
            await stack.aclose()
