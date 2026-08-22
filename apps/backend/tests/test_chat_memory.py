from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import pytest
from alembic import command
from alembic.config import Config
from langchain_core.tools import StructuredTool

from super_ai.chat import streaming as streaming_module
from super_ai.chat.configuration import SelectedChatSkill
from super_ai.chat.memory import (
    ChatContextLimitReached,
    ChatMemoryService,
    ChatRuntimeContextBudget,
    ChatRuntimeContextLimitReached,
    MemoryFidelityError,
    _memory_instruction,  # pyright: ignore[reportPrivateUsage]
    _select_messages_for_compaction,  # pyright: ignore[reportPrivateUsage]
    _validate_memory_fidelity,  # pyright: ignore[reportPrivateUsage]
    _validated_memory_document,  # pyright: ignore[reportPrivateUsage]
    count_tokens,
    maybe_compress_structured_tool_output,
    maybe_compress_tool_output,
)
from super_ai.chat.streaming import (
    ChatAgentRequest,
    ChatAgentRunner,
    ChatAgentToolCall,
    ChatStreamingService,
    _wrap_tool_output_compression,  # pyright: ignore[reportPrivateUsage]
    create_load_skill_tool,
    create_read_tool_output_evidence_tool,
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


class FabricatedMemoryProvider:
    """返回含原文无法支撑数字的摘要，模拟模型编造。"""

    class Model:
        async def ainvoke(self, input: object) -> object:
            return FakeMessage(
                json.dumps(
                    {
                        "version": 1,
                        "summary": "服务超时 503，重试 2 次。",
                        "items": [
                            {
                                "category": "fact",
                                "content": "请求返回 503",
                                "sourceMessageIds": ["message-1"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            )

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


def test_memory_fidelity_rejects_untraceable_numbers() -> None:
    memory: dict[str, object] = {
        "version": 1,
        "summary": "服务超时 503，重试 3 次。",
        "items": [],
    }
    source_text = "[message_id=message-1] user: 服务返回 502，重试 2 次。"
    assert _validate_memory_fidelity(memory, source_text=source_text) is False


def test_memory_fidelity_accepts_traceable_numbers() -> None:
    memory: dict[str, object] = {
        "version": 1,
        "summary": "服务超时 503，重试 2 次。",
        "items": [],
    }
    source_text = "[message_id=message-1] user: 服务返回 503，重试 2 次。"
    assert _validate_memory_fidelity(memory, source_text=source_text) is True


def test_memory_fidelity_rejects_unfounded_decision() -> None:
    memory: dict[str, object] = {
        "version": 1,
        "summary": "继续排查。",
        "items": [
            {
                "category": "decision",
                "content": "加大内存",
                "sourceMessageIds": ["message-1"],
            }
        ],
    }
    source_text = "[message_id=message-1] user: 先看日志定位超时。"
    assert _validate_memory_fidelity(memory, source_text=source_text) is False


def test_memory_fidelity_accepts_decision_with_literal_evidence() -> None:
    memory: dict[str, object] = {
        "version": 1,
        "summary": "继续排查。",
        "items": [
            {
                "category": "decision",
                "content": "重启服务",
                "sourceMessageIds": ["message-1"],
            }
        ],
    }
    source_text = "[message_id=message-1] user: 先重启服务再观察。"
    assert _validate_memory_fidelity(memory, source_text=source_text) is True


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
async def test_tool_compression_fallback_keeps_selected_regions(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logging.getLogger("super_ai.chat.memory").disabled = False
    caplog.set_level(logging.INFO, logger="super_ai.chat.memory")
    text = "\n".join([f"INFO request={index}" for index in range(2_000)])
    text += "\nFATAL database corrupted request_id=abc123 secret-log-content"

    compressed = await maybe_compress_tool_output(
        text,
        tool_name="SearchLog",
        llm_provider=cast(LlmProvider, FailingProvider()),
    )

    assert len(compressed) <= 4_100
    assert "FATAL database corrupted" in compressed
    events = [
        json.loads(record.message) for record in caplog.records if record.message.startswith("{")
    ]
    assert events == [
        {
            "event": "chat.tool_compression.fallback",
            "toolName": "SearchLog",
            "compressionMode": "sampled_fallback",
            "failureCategory": "RuntimeError",
        }
    ]
    assert "secret-log-content" not in "\n".join(record.message for record in caplog.records)


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


@pytest.mark.asyncio
async def test_structured_tool_compression_fallback_marks_failure() -> None:
    """回归（问题4）：结构化路径 sampled_fallback 必须带 compressionFailed 标记。"""
    result = await maybe_compress_structured_tool_output(
        {"records": [{"message": "timeout"}] * 2_000},
        tool_name="knowledge_retrieval",
        llm_provider=cast(LlmProvider, FailingProvider()),
    )
    assert isinstance(result, dict)
    compression = result["_compression"]
    assert isinstance(compression, dict)
    assert compression["mode"] == "sampled_fallback"
    assert compression["compressionFailed"] is True
    assert compression["sourceHash"]
    # llm_summary 成功路径不标记失败
    ok = await maybe_compress_structured_tool_output(
        {"records": [{"message": "timeout"}] * 2_000},
        tool_name="knowledge_retrieval",
        llm_provider=cast(LlmProvider, FakeProvider()),
    )
    assert isinstance(ok, dict)
    ok_compression = ok["_compression"]
    assert isinstance(ok_compression, dict)
    assert ok_compression["mode"] == "llm_summary"
    assert "compressionFailed" not in ok_compression


@pytest.mark.asyncio
async def test_read_evidence_tool_skips_compression_and_returns_original(
    migrated_database_url: str,
) -> None:
    """回归：read_tool_output_evidence 不得被压缩包装击穿（问题1）。"""
    engine = create_memory_engine(migrated_database_url)
    try:
        repositories = create_sqlite_memory_repositories(create_memory_session_factory(engine))
        session = await repositories.chat.create_session(
            owner_user_id="user-a", session_id="chat-evidence-unwrap"
        )
        evidence_repo = cast(Any, repositories.compressed_tool_evidence)
        original = "x" * 12_000  # 远超 2000 token 压缩阈值
        evidence = await evidence_repo.create(
            owner_user_id="user-a",
            chat_session_id=session.id,
            tool_name="SearchLog",
            content=original,
            source_hash="hash-unwrap",
        )
        request = ChatAgentRequest(
            owner_user_id="user-a",
            session_id=session.id,
            system_prompt="system",
            messages=[],
            accessible_knowledge_base_ids=(),
        )
        tool = create_read_tool_output_evidence_tool(request, evidence_repo)
        wrapped = _wrap_tool_output_compression(
            tool,
            cast(LlmProvider, CountingProvider(token_count=10_000)),
            request,
            evidence_repo,
        )
        # 修复前：被替换为压缩 coroutine，返回摘要而非原文
        assert wrapped is tool
        coroutine = wrapped.coroutine
        assert coroutine is not None
        assert await coroutine(evidence_id=evidence.id) == original
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_load_skill_tool_skips_compression_wrapper() -> None:
    """回归：load_skill 返回指令原文，不得被压缩包装（问题1 覆盖范围）。"""
    skill = SelectedChatSkill(
        name="runbook",
        description="故障处理手册",
        content="Step 1: 检查告警\nStep 2: 按 SOP 处理\n" + "x" * 10_000,
    )
    tool = create_load_skill_tool((skill,))
    wrapped = _wrap_tool_output_compression(
        tool,
        cast(LlmProvider, CountingProvider(token_count=10_000)),
        ChatAgentRequest(
            owner_user_id="user-a",
            session_id="chat-skill-unwrap",
            system_prompt="system",
            messages=[],
            accessible_knowledge_base_ids=(),
        ),
        None,
    )
    assert wrapped is tool
    coroutine = wrapped.coroutine
    assert coroutine is not None
    loaded = await coroutine(skill_name="runbook")
    assert "Step 1: 检查告警" in str(loaded)


@pytest.mark.asyncio
async def test_large_async_tool_still_gets_compression_wrapper() -> None:
    """防止豁免名单误伤：普通大输出 async 工具仍应被压缩包装。"""

    async def big_output() -> str:
        return "y" * 12_000

    tool = StructuredTool.from_function(coroutine=big_output, name="big_output", description="")
    wrapped = _wrap_tool_output_compression(
        tool,
        cast(LlmProvider, FailingProvider()),
        ChatAgentRequest(
            owner_user_id="user-a",
            session_id="chat-big-output",
            system_prompt="system",
            messages=[],
            accessible_knowledge_base_ids=(),
        ),
        None,
    )
    assert wrapped is not tool
    coroutine = wrapped.coroutine
    assert coroutine is not None
    result = await coroutine()
    assert "[... 输出已按信号" in str(result)


@pytest.mark.asyncio
async def test_evidence_persist_failure_keeps_compressed_tool_result(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """回归（问题12）：evidence 落库失败不得把成功的工具调用转为失败。"""
    engine = create_memory_engine(migrated_database_url)
    try:
        repositories = create_sqlite_memory_repositories(create_memory_session_factory(engine))
        session = await repositories.chat.create_session(
            owner_user_id="user-a", session_id="evidence-persist-fail"
        )
        evidence_repo = cast(Any, repositories.compressed_tool_evidence)

        async def failing_create(**kwargs: object) -> Any:
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(evidence_repo, "create", failing_create)

        async def big_output() -> str:
            return "y" * 12_000

        tool = StructuredTool.from_function(coroutine=big_output, name="big_output", description="")
        request = ChatAgentRequest(
            owner_user_id="user-a",
            session_id=session.id,
            system_prompt="system",
            messages=[],
            accessible_knowledge_base_ids=(),
        )
        wrapped = _wrap_tool_output_compression(
            tool,
            cast(LlmProvider, FailingProvider()),
            request,
            evidence_repo,
        )
        coroutine = wrapped.coroutine
        assert coroutine is not None
        result = await coroutine()
        # 压缩摘要仍返回，且无 evidenceId（落库失败不影响工具调用）
        assert isinstance(result, dict)
        assert "content" in result
        compression = cast(dict[str, object], result["_compression"])
        assert compression.get("evidenceId") is None
    finally:
        await engine.dispose()


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
        active_threshold_history = await repositories.chat.list_active_messages(
            owner_user_id="user-a", session_id=threshold_session.id
        )
        complete_threshold_history = await repositories.chat.list_messages(
            owner_user_id="user-a", session_id=threshold_session.id
        )
    finally:
        await engine.dispose()

    assert threshold_result.session.memory_mode == "context_70_percent"
    assert manual_result.memory_mode == "manual"
    assert active_threshold_history == []
    assert [message.id for message in complete_threshold_history] == ["message-chat-threshold"]
    assert len(provider.model.inputs) == 1


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


@pytest.mark.asyncio
async def test_fabricated_memory_rejected_without_overwriting_existing(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        repositories = create_sqlite_memory_repositories(create_memory_session_factory(engine))
        session = await repositories.chat.create_session(
            owner_user_id="user-a", session_id="chat-fabricated"
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
            llm_provider=cast(LlmProvider, FabricatedMemoryProvider()),
            context_window_tokens=1_000,
        )

        with pytest.raises(MemoryFidelityError):
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


async def test_hard_limit_compaction_failure_records_error(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        repositories = create_sqlite_memory_repositories(create_memory_session_factory(engine))
        session = await repositories.chat.create_session(
            owner_user_id="user-a", session_id="chat-compaction-error"
        )
        await repositories.chat.append_message(
            owner_user_id="user-a",
            message_id="message-history",
            session_id=session.id,
            role="user",
            content="需要保留的历史内容 " * 30,
        )
        service = ChatMemoryService(
            repositories=repositories,
            llm_provider=cast(LlmProvider, FailingProvider()),
            context_window_tokens=20,
        )
        history = await repositories.chat.list_messages(
            owner_user_id="user-a", session_id=session.id
        )
        with pytest.raises(ChatContextLimitReached):
            await service.prepare_message(
                owner_user_id="user-a",
                session=session,
                history=history,
                system_prompt="system prompt with enough context",
                content="a candidate message that must not be saved",
            )
        updated = await repositories.chat.get_session(
            owner_user_id="user-a", session_id=session.id
        )
    finally:
        await engine.dispose()

    assert updated is not None
    assert updated.last_compaction_error == "RuntimeError"
    assert updated.last_compaction_failed_at is not None


async def test_successful_compaction_clears_previous_error(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        repositories = create_sqlite_memory_repositories(create_memory_session_factory(engine))
        session = await repositories.chat.create_session(
            owner_user_id="user-a", session_id="chat-compaction-clear"
        )
        await repositories.chat.append_message(
            owner_user_id="user-a",
            message_id="message-history",
            session_id=session.id,
            role="user",
            content="需要保留的历史内容 " * 30,
        )
        await repositories.chat.update_memory_state(
            owner_user_id="user-a",
            session_id=session.id,
            last_compaction_error="TimeoutError",
            last_compaction_failed_at=datetime.now(timezone.utc),
        )
        service = ChatMemoryService(
            repositories=repositories,
            llm_provider=cast(LlmProvider, FakeProvider()),
            context_window_tokens=120,
        )
        session = await repositories.chat.get_session(
            owner_user_id="user-a", session_id=session.id
        )
        assert session is not None
        history = await repositories.chat.list_messages(
            owner_user_id="user-a", session_id=session.id
        )
        assert history
        await service.compact_once(
            owner_user_id="user-a",
            session=session,
            history=history,
            system_prompt="你是助手。",
        )
        updated = await repositories.chat.get_session(
            owner_user_id="user-a", session_id=session.id
        )
    finally:
        await engine.dispose()

    assert updated is not None
    assert updated.last_compaction_error is None
    assert updated.last_compaction_failed_at is None


async def test_audit_failure_increments_session_counter(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        repositories = create_sqlite_memory_repositories(create_memory_session_factory(engine))
        session = await repositories.chat.create_session(
            owner_user_id="user-a", session_id="chat-audit-failure"
        )

        async def _boom(**kwargs: object) -> None:
            raise RuntimeError("audit write failed")

        monkeypatch.setattr(repositories.tool_call_audits, "create_for_chat_session", _boom)
        service = ChatStreamingService(
            repositories=repositories,
            agent_runner=cast(ChatAgentRunner, object()),
        )
        await service._persist_tool_call_audit(  # pyright: ignore[reportPrivateUsage]
            owner_user_id="user-a",
            session_id=session.id,
            event=ChatAgentToolCall(
                id="tool-audit-1",
                name="SearchLog",
                status="started",
                input={},
            ),
        )
        updated = await repositories.chat.get_session(
            owner_user_id="user-a", session_id=session.id
        )
    finally:
        await engine.dispose()

    assert updated is not None
    assert updated.audit_failure_count == 1


async def test_cross_turn_evidence_dedupes_and_drops_whole_lines(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(streaming_module, "_CROSS_TURN_CONTEXT_LIMIT", 200)
    engine = create_memory_engine(migrated_database_url)
    try:
        repositories = create_sqlite_memory_repositories(create_memory_session_factory(engine))
        session = await repositories.chat.create_session(
            owner_user_id="user-a", session_id="chat-cross-turn"
        )
        audits = cast(Any, repositories.tool_call_audits)
        for index in range(3):
            audit = await audits.create_for_chat_session(
                owner_user_id="user-a",
                audit_id=f"audit-{index}",
                chat_session_id=session.id,
                tool_name="SearchLog",
                arguments={},
            )
            await audits.finalize(
                owner_user_id="user-a",
                audit_id=audit.id,
                status="completed",
                result_summary="重复证据片段",
            )
        long_audit = await audits.create_for_chat_session(
            owner_user_id="user-a",
            audit_id="audit-3",
            chat_session_id=session.id,
            tool_name="SearchLog",
            arguments={},
        )
        await audits.finalize(
            owner_user_id="user-a",
            audit_id=long_audit.id,
            status="completed",
            result_summary="x" * 3000,
        )
        for index in range(2):
            await repositories.chat.append_message(
                owner_user_id="user-a",
                message_id=f"message-{index}",
                session_id=session.id,
                role="assistant",
                content=f"回答 {index}",
                metadata={
                    "citations": [
                        {"id": "cite-1", "title": "SOP A", "sourceType": "knowledge-base"}
                    ]
                },
            )
        service = ChatStreamingService(
            repositories=repositories,
            agent_runner=cast(ChatAgentRunner, object()),
        )
        context = await service._cross_turn_evidence_context(  # pyright: ignore[reportPrivateUsage]
            owner_user_id="user-a", session_id=session.id
        )
    finally:
        await engine.dispose()

    assert context.count("重复证据片段") == 1
    assert "audit-1" not in context
    assert "audit-2" not in context
    assert "audit-3" not in context
    assert context.count("cite-1") == 1
