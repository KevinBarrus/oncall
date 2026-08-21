"""Memory database engine tests: file permission hardening and URL handling."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from super_ai.memory.database import (
    _sqlite_database_path,  # pyright: ignore[reportPrivateUsage]
    create_memory_engine,
)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission semantics only")
@pytest.mark.asyncio
async def test_memory_engine_restricts_database_file_permissions(tmp_path: Path) -> None:
    database_path = tmp_path / "memory.sqlite3"
    engine = create_memory_engine(f"sqlite+aiosqlite:///{database_path}")
    try:
        assert database_path.exists()
        assert (database_path.stat().st_mode & 0o777) == 0o600
    finally:
        await engine.dispose()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission semantics only")
@pytest.mark.asyncio
async def test_memory_engine_reapplies_permissions_to_existing_file(tmp_path: Path) -> None:
    database_path = tmp_path / "existing.sqlite3"
    database_path.touch(mode=0o644)
    engine = create_memory_engine(f"sqlite+aiosqlite:///{database_path}")
    try:
        assert (database_path.stat().st_mode & 0o777) == 0o600
    finally:
        await engine.dispose()


def test_memory_engine_skips_in_memory_database() -> None:
    engine = create_memory_engine("sqlite+aiosqlite:///:memory:")
    assert engine is not None


def test_sqlite_database_path_resolves_relative_and_absolute_urls(tmp_path: Path) -> None:
    relative = _sqlite_database_path("sqlite+aiosqlite:///./var/memory.sqlite3")
    assert relative is not None
    assert relative.is_absolute()
    assert relative.name == "memory.sqlite3"

    absolute = _sqlite_database_path(f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}")
    assert absolute is not None
    assert absolute == tmp_path / "db.sqlite3"

    assert _sqlite_database_path("sqlite+aiosqlite:///:memory:") is None
