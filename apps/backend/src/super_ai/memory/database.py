"""Database configuration and session helpers for memory persistence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from super_ai.project_config import (
    ProjectConfigurationError,
    project_config_section,
    required_str,
)

DEFAULT_MEMORY_DATABASE_URL = "sqlite+aiosqlite:///./var/memory.sqlite3"
SQLITE_BUSY_TIMEOUT_SECONDS = 5


@dataclass(frozen=True, slots=True)
class MemoryDatabaseSettings:
    """Runtime database settings for memory persistence."""

    database_url: str = DEFAULT_MEMORY_DATABASE_URL


def load_memory_database_settings(config_path: Path | str | None = None) -> MemoryDatabaseSettings:
    """Load memory database settings from the repository project config."""
    try:
        backend_config = project_config_section("backend", config_path=config_path)
        database_url = required_str(backend_config, "memoryDatabaseUrl")
    except ProjectConfigurationError as exc:
        raise RuntimeError(str(exc)) from exc
    return MemoryDatabaseSettings(database_url=database_url)


def create_memory_engine(
    database_url: str | None = None,
    *,
    echo: bool = False,
    config_path: Path | str | None = None,
) -> AsyncEngine:
    """Create an async SQLAlchemy engine for memory persistence."""
    settings = load_memory_database_settings(config_path) if database_url is None else None
    resolved_url = settings.database_url if settings is not None else database_url
    if resolved_url is None:
        resolved_url = DEFAULT_MEMORY_DATABASE_URL
    if not resolved_url.startswith("sqlite"):
        return create_async_engine(resolved_url, echo=echo)
    engine = create_async_engine(
        resolved_url,
        echo=echo,
        connect_args={"timeout": SQLITE_BUSY_TIMEOUT_SECONDS},
    )
    event.listen(engine.sync_engine, "connect", _configure_sqlite_connection)
    return engine


def create_memory_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory for repository implementations."""
    return async_sessionmaker(engine, expire_on_commit=False)


def _configure_sqlite_connection(dbapi_connection: object, _connection_record: object) -> None:
    connection = cast(Any, dbapi_connection)
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_SECONDS * 1000}")
        cursor.execute("PRAGMA journal_mode=WAL")
    finally:
        cursor.close()
