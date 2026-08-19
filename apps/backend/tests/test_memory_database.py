from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from super_ai.memory.database import create_memory_engine, create_memory_session_factory
from super_ai.memory.models import ChatMessageModel


@pytest.fixture
def migrated_database_url(tmp_path: Path) -> str:
    database_path = tmp_path / "memory.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(config, "head")
    return f"sqlite+aiosqlite:///{database_path}"


@pytest.mark.asyncio
async def test_file_sqlite_engine_enables_concurrency_and_foreign_key_pragmas(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        async with engine.connect() as connection:
            journal_mode = (await connection.execute(text("PRAGMA journal_mode"))).scalar_one()
            foreign_keys = (await connection.execute(text("PRAGMA foreign_keys"))).scalar_one()
            busy_timeout = (await connection.execute(text("PRAGMA busy_timeout"))).scalar_one()

        session_factory = create_memory_session_factory(engine)
        async with session_factory() as session:
            session.add(
                ChatMessageModel(
                    id="orphan-message",
                    owner_user_id="user-a",
                    session_id="missing-session",
                    role="user",
                    content="must fail",
                    metadata_json={},
                    created_at=datetime.now(timezone.utc),
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()

    assert journal_mode == "wal"
    assert foreign_keys == 1
    assert busy_timeout >= 5_000
