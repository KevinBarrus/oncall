from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import pytest
from alembic import command
from alembic.config import Config

from super_ai.chat.memory import (
    ChatContextLimitReached,
    ChatMemoryService,
    ChatRuntimeContextBudget,
    ChatRuntimeContextLimitReached,
    _memory_instruction,  # pyright: ignore[reportPrivateUsage]
    _select_messages_for_compaction,  # pyright: ignore[reportPrivateUsage]
    _validated_memory_document,  # pyright: ignore[reportPrivateUsage]
    count_tokens,
    maybe_compress_structured_tool_output,
    maybe_compress_tool_output,
)
from super_ai.llm import LlmProvider
from super_ai.memory.database import create_memory_engine, create_memory_session_factory
from super_ai.memory.repositories import ChatMessageRecord
from super_ai.memory.sqlite import create_sqlite_memory_repositories


@dataclass
class FakeMessage:
    content: str


class FakeChatModel:
    def __init__(self) -> None:
        self.inputs: list[object] = []

    async def ainvoke(self, input: object) -> object:
        self.inputs.append(input)
        match = re.search(r"\[message_id=([^\]]+)\]", str(input))
        source_id = match.group(1) if match else "unknown"
        return FakeMessage(
            json.dumps(
                {
                    "version": 1,
                    "summary": "用户正在排查 API，需保留工具结果和后续任务。",
                    "items": [
                        {
                            "category": "goal",
                            "content": "继续排查 API",
                            "sourceMessageIds": [source_id],
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )


class FakeProvider:
    def __init__(self) -> None:
        self.model = FakeChatModel()

    def create_chat_model(self) -> FakeChatModel:
        return self.model


class CountingProvider(FakeProvider):
    def __init__(self, token_count: int) -> None:
        super().__init__()
        self.token_count = token_count
        self.counted_texts: list[str] = []

    def count_tokens(self, text: str) -> int:
        self.counted_texts.append(text)
        return self.token_count


class FailingProvider:
    class Model:
        async def ainvoke(self, input: object) -> object:
            raise RuntimeError("summary unavailable")

    def create_chat_model(self) -> Model:
        return self.Model()


def test_memory_compaction_selects_bounded_old_prefix() -> None:
    messages = [
        ChatMessageRecord(
            id=f"message-{index}",
            owner_user_id="user-a",
            session_id="session-a",
            role="user",
            content=f"历史消息 {index} " * 40,
            metadata={},
            created_at=datetime.now(timezone.utc),
        )
        for index in range(20)
    ]

    selected = _select_messages_for_compaction(
        messages=messages,
        system_prompt="你是助手。",
        memory_summary=None,
        context_window_tokens=4_000,
    )

    assert 0 < len(selected) < len(messages)
    assert [message.id for message in selected] == [
        message.id for message in messages[: len(selected)]
    ]


def test_structured_memory_requires_known_source_ids() -> None:
    payload = json.dumps(
        {
            "version": 1,
            "summary": "已确认 API 需要继续排查。",
            "items": [
                {
                    "category": "fact",
                    "content": "API 返回超时",
                    "sourceMessageIds": ["message-1"],
                }
            ],
        }
    )

    assert _validated_memory_document(payload, allowed_source_ids={"message-1"}) is not None
    assert _validated_memory_document(payload, allowed_source_ids={"message-2"}) is None
    assert "message-1" in _memory_instruction(payload)


def test_runtime_context_budget_reserves_output_and_rejects_overflow() -> None:
    budget = ChatRuntimeContextBudget.create(
        system_prompt="你是助手。",
        memory_summary=None,
        messages=[],
        context_window_tokens=1_000,
    )

    with pytest.raises(ChatRuntimeContextLimitReached):
        budget.add("工具输出 " * 5_000, role="tool")


def test_token_count_prefers_provider_and_conservatively_counts_chinese() -> None:
    provider = CountingProvider(7)

    assert count_tokens("中文日志", llm_provider=cast(LlmProvider, provider)) == 7
    assert provider.counted_texts == ["中文日志"]
    assert count_tokens("中文日志", llm_provider=None) >= len("中文日志")


def test_runtime_context_budget_uses_provider_token_count() -> None:
    provider = CountingProvider(3)
    budget = ChatRuntimeContextBudget.create(
        system_prompt="系统提示",
        memory_summary=None,
        messages=[],
        context_window_tokens=5_000,
        llm_provider=cast(LlmProvider, provider),
    )

    budget.add("工具输出", role="tool")

    assert provider.counted_texts == ["系统提示", "工具输出"]


@pytest.mark.asyncio
async def test_tool_compression_uses_provider_token_count() -> None:
    provider = CountingProvider(2_001)

    compressed = await maybe_compress_tool_output(
        "中文日志",
        tool_name="SearchLog",
        llm_provider=cast(LlmProvider, provider),
    )

    assert compressed.startswith("[compressed]")
    assert provider.counted_texts == ["中文日志"]


@pytest.mark.asyncio
async def test_tool_compression_scans_tail_and_signal_regions() -> None:
    provider = FakeProvider()
    text = "\n".join([f"INFO request={index}" for index in range(2_000)])
    text += "\nFATAL database corrupted request_id=abc123"

    compressed = await maybe_compress_tool_output(
        text,
        tool_name="SearchLog",
        llm_provider=cast(LlmProvider, provider),
    )

    assert compressed.startswith("[compressed]")
    prompt = str(provider.model.inputs[0])
    assert "FATAL database corrupted" in prompt
    assert "[1] INFO request=0" in prompt


@pytest.mark.asyncio
async def test_tool_compression_fallback_keeps_selected_regions() -> None:
    text = "\n".join([f"INFO request={index}" for index in range(2_000)])
    text += "\nFATAL database corrupted request_id=abc123"

    compressed = await maybe_compress_tool_output(
        text,
        tool_name="SearchLog",
        llm_provider=cast(LlmProvider, FailingProvider()),
    )

    assert len(compressed) <= 4_100
    assert "FATAL database corrupted" in compressed


@pytest.mark.asyncio
async def test_structured_tool_compression_keeps_machine_readable_metadata() -> None:
    result = await maybe_compress_structured_tool_output(
        {
            "status": "ok",
            "citations": [{"id": "citation-1"}],
            "records": [{"message": "timeout"}] * 2_000,
        },
        tool_name="knowledge_retrieval",
        llm_provider=cast(LlmProvider, FakeProvider()),
    )

    assert isinstance(result, dict)
    assert result["preserved"] == {
        "status": "ok",
        "citations": [{"id": "citation-1"}],
    }
    compression = result["_compression"]
    assert isinstance(compression, dict)
    assert compression["sourceHash"]


@pytest.fixture
def migrated_database_url(tmp_path: Path) -> str:
    database_path = tmp_path / "memory.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(config, "head")
    return f"sqlite+aiosqlite:///{database_path}"


@pytest.mark.asyncio
async def test_thirty_turn_mode_defers_compaction_without_deleting_history(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        repositories = create_sqlite_memory_repositories(create_memory_session_factory(engine))
        session = await repositories.chat.create_session(
            owner_user_id="user-a", session_id="chat-thirty"
        )
        for index in range(30):
            for role in ("user", "assistant"):
                await repositories.chat.append_message(
                    owner_user_id="user-a",
                    message_id=f"message-{index}-{role}",
                    session_id=session.id,
                    role=role,
                    content=f"turn {index} {role}",
                )
        history = await repositories.chat.list_messages(
            owner_user_id="user-a", session_id=session.id
        )
        provider = FakeProvider()
        scheduled: list[tuple[str, str]] = []

        async def schedule(owner_user_id: str, session_id: str) -> None:
            scheduled.append((owner_user_id, session_id))

        service = ChatMemoryService(
            repositories=repositories,
            llm_provider=cast(LlmProvider, provider),
            context_window_tokens=131072,
            schedule_compaction=schedule,
        )

        prepared = await service.prepare_message(
            owner_user_id="user-a",
            session=session,
            history=history,
            system_prompt="你是助手。",
            content="继续",
        )
        persisted = await repositories.chat.list_messages(
            owner_user_id="user-a", session_id=session.id
        )
    finally:
        await engine.dispose()

    assert provider.model.inputs == []
    assert scheduled == [("user-a", session.id)]
    assert prepared.session.compacted_message_count == 0
    assert prepared.session.memory_summary is None
    assert len(prepared.messages) == 61
    assert len(persisted) == 60


@pytest.mark.asyncio
async def test_context_threshold_and_manual_mode_are_session_scoped(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        repositories = create_sqlite_memory_repositories(create_memory_session_factory(engine))
        threshold_session = await repositories.chat.create_session(
            owner_user_id="user-a", session_id="chat-threshold"
        )
        manual_session = await repositories.chat.create_session(
            owner_user_id="user-a", session_id="chat-manual"
        )
        for session in (threshold_session, manual_session):
            await repositories.chat.append_message(
                owner_user_id="user-a",
                message_id=f"message-{session.id}",
                session_id=session.id,
                role="user",
                content="需要保留的历史内容 " * 30,
            )
        await repositories.chat.update_memory_state(
            owner_user_id="user-a",
            session_id=threshold_session.id,
            memory_mode="context_70_percent",
        )
        provider = FakeProvider()
        service = ChatMemoryService(
            repositories=repositories,
            llm_provider=cast(LlmProvider, provider),
            context_window_tokens=120,
        )
        threshold_record = await repositories.chat.get_session(
            owner_user_id="user-a", session_id="chat-threshold"
        )
        manual_record = await repositories.chat.get_session(
            owner_user_id="user-a", session_id="chat-manual"
        )
        assert threshold_record is not None and manual_record is not None
        threshold_history = await repositories.chat.list_messages(
            owner_user_id="user-a", session_id=threshold_record.id
        )
        manual_history = await repositories.chat.list_messages(
            owner_user_id="user-a", session_id=manual_record.id
        )

        threshold_result = await service.prepare_message(
            owner_user_id="user-a",
            session=threshold_record,
            history=threshold_history,
            system_prompt="你是助手。",
            content="继续",
        )
        manual_result = await service.set_mode(
            owner_user_id="user-a",
            session=manual_record,
            mode="manual",
            history=manual_history,
            system_prompt="你是助手。",
        )
    finally:
        await engine.dispose()

    assert threshold_result.session.memory_mode == "context_70_percent"
    assert threshold_result.session.compacted_message_count == 1
    assert manual_result.memory_mode == "manual"
    assert manual_result.compacted_message_count == 1
    assert len(provider.model.inputs) == 2


@pytest.mark.asyncio
async def test_failed_background_compaction_preserves_existing_memory(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        repositories = create_sqlite_memory_repositories(create_memory_session_factory(engine))
        session = await repositories.chat.create_session(
            owner_user_id="user-a", session_id="chat-summary-failure"
        )
        await repositories.chat.append_message(
            owner_user_id="user-a",
            message_id="message-1",
            session_id=session.id,
            role="user",
            content="需要压缩的历史消息",
        )
        history = await repositories.chat.list_messages(
            owner_user_id="user-a", session_id=session.id
        )
        service = ChatMemoryService(
            repositories=repositories,
            llm_provider=cast(LlmProvider, FailingProvider()),
            context_window_tokens=1_000,
        )

        with pytest.raises(RuntimeError, match="summary unavailable"):
            await service.compact_once(
                owner_user_id="user-a",
                session=session,
                history=history,
                system_prompt="你是助手。",
            )
        persisted = await repositories.chat.get_session(
            owner_user_id="user-a", session_id=session.id
        )
    finally:
        await engine.dispose()

    assert persisted is not None
    assert persisted.memory_summary is None
    assert persisted.compacted_message_count == 0


@pytest.mark.asyncio
async def test_hard_limit_rejects_candidate_without_persisting_it(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        repositories = create_sqlite_memory_repositories(create_memory_session_factory(engine))
        session = await repositories.chat.create_session(
            owner_user_id="user-a", session_id="chat-limit"
        )
        service = ChatMemoryService(
            repositories=repositories,
            llm_provider=cast(LlmProvider, FakeProvider()),
            context_window_tokens=20,
        )

        with pytest.raises(ChatContextLimitReached):
            await service.prepare_message(
                owner_user_id="user-a",
                session=session,
                history=[],
                system_prompt="system prompt with enough context",
                content="a candidate message that must not be saved",
            )
        history = await repositories.chat.list_messages(
            owner_user_id="user-a", session_id=session.id
        )
    finally:
        await engine.dispose()

    assert history == []
