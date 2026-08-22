from __future__ import annotations

import asyncio
import inspect
from dataclasses import is_dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

import pytest
from alembic import command
from alembic.config import Config

import super_ai.memory.repositories as repositories_module
from super_ai.memory.database import create_memory_engine, create_memory_session_factory
from super_ai.memory.repositories import (
    ChatMemoryRepository,
    ChatMessageRecord,
    ChatSessionRecord,
    DiagnosticReportRecord,
    DiagnosticTaskRecord,
    DocumentIndexTaskRecord,
    GraphCheckpointRecord,
    KnowledgeDocumentRecord,
    TimeRangeFilter,
    ToolCallAuditRecord,
)
from super_ai.memory.sqlite import (
    SQLiteChatMemoryRepository,
    SQLiteDiagnosticMemoryRepository,
    SQLiteKnowledgeDocumentRepository,
    SQLiteSopBeliefRepository,
    SQLiteUserChatPromptRepository,
    SQLiteUserChatSkillRepository,
    create_sqlite_memory_repositories,
)


@pytest.mark.asyncio
async def test_chat_repository_persists_and_queries_history(migrated_database_url: str) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        session_factory = create_memory_session_factory(engine)
        chat_repository = SQLiteChatMemoryRepository(session_factory)
        created_at = datetime(2026, 7, 8, 10, 0, tzinfo=timezone.utc)

        session = await chat_repository.create_session(
            owner_user_id="user-a",
            session_id="session-1",
            title="Production incident",
            created_at=created_at,
        )
        await chat_repository.append_message(
            owner_user_id="user-a",
            message_id="message-1",
            session_id=session.id,
            role="user",
            content="What happened?",
            metadata={"tokens": 3},
            created_at=created_at - timedelta(minutes=5),
        )
        expected_message = await chat_repository.append_message(
            owner_user_id="user-a",
            message_id="message-2",
            session_id=session.id,
            role="assistant",
            content="Investigating.",
            metadata={"sources": ["runbook"]},
            created_at=created_at + timedelta(minutes=1),
        )
        await chat_repository.append_message(
            owner_user_id="user-a",
            message_id="message-3",
            session_id=session.id,
            role="assistant",
            content="Resolved.",
            metadata={"sources": ["timeline"]},
            created_at=created_at + timedelta(minutes=30),
        )
        await chat_repository.create_session(
            owner_user_id="user-b",
            session_id="session-2",
            title="Another user's session",
            created_at=created_at,
        )
        await chat_repository.append_message(
            owner_user_id="user-b",
            message_id="message-4",
            session_id="session-2",
            role="user",
            content="Private to user B",
            created_at=created_at,
        )

        all_messages = await chat_repository.list_messages(
            owner_user_id="user-a",
            session_id=session.id,
        )
        ranged_messages = await chat_repository.list_messages(
            owner_user_id="user-a",
            session_id=session.id,
            time_range=TimeRangeFilter(
                start_at=created_at,
                end_at=created_at + timedelta(minutes=5),
            ),
        )
    finally:
        await engine.dispose()

    assert session.owner_user_id == "user-a"
    assert session.title == "Production incident"
    assert [message.id for message in all_messages] == ["message-1", "message-2", "message-3"]
    assert ranged_messages == [expected_message]
    assert all(message.owner_user_id == "user-a" for message in all_messages)
    assert ranged_messages[0].metadata == {"sources": ["runbook"]}


@pytest.mark.asyncio
async def test_chat_repository_denies_cross_tenant_parent_writes(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        session_factory = create_memory_session_factory(engine)
        chat_repository = SQLiteChatMemoryRepository(session_factory)
        await chat_repository.create_session(
            owner_user_id="user-a",
            session_id="session-a",
            title="User A",
        )

        with pytest.raises(PermissionError):
            await chat_repository.append_message(
                owner_user_id="user-b",
                message_id="message-b",
                session_id="session-a",
                role="user",
                content="cross tenant write",
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_chat_repository_archives_compacted_history_without_losing_it(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        session_factory = create_memory_session_factory(engine)
        chat_repository = SQLiteChatMemoryRepository(session_factory)
        created_at = datetime(2026, 7, 11, 9, 0, tzinfo=timezone.utc)
        session = await chat_repository.create_session(
            owner_user_id="user-a",
            session_id="archive-session",
            title="Archived history",
            created_at=created_at,
        )
        for index, role in enumerate(("user", "assistant", "user"), start=1):
            await chat_repository.append_message(
                owner_user_id="user-a",
                message_id=f"archived-message-{index}",
                session_id=session.id,
                role=role,
                content=f"message {index}",
                metadata={"sequence": index},
                created_at=created_at + timedelta(minutes=index),
            )

        archived_session = await chat_repository.archive_compacted_messages(
            owner_user_id="user-a",
            session_id=session.id,
            message_ids=["archived-message-1", "archived-message-2"],
            memory_summary='{"summary":"first two messages"}',
            context_tokens=7,
            last_compacted_at=created_at + timedelta(minutes=4),
        )
        active_messages = await chat_repository.list_active_messages(
            owner_user_id="user-a", session_id=session.id
        )
        all_messages = await chat_repository.list_messages(
            owner_user_id="user-a", session_id=session.id
        )
        recent_messages = await chat_repository.list_recent_messages(
            owner_user_id="user-a", session_id=session.id, limit=2
        )
        other_owner_messages = await chat_repository.list_messages(
            owner_user_id="user-b", session_id=session.id
        )
        cleared_messages = await chat_repository.clear_messages(
            owner_user_id="user-a", session_id=session.id
        )
        remaining_messages = await chat_repository.list_messages(
            owner_user_id="user-a", session_id=session.id
        )
    finally:
        await engine.dispose()

    assert archived_session is not None
    assert archived_session.memory_summary == '{"summary":"first two messages"}'
    assert archived_session.compacted_message_count == 0
    assert [message.id for message in active_messages] == ["archived-message-3"]
    assert [message.id for message in all_messages] == [
        "archived-message-1",
        "archived-message-2",
        "archived-message-3",
    ]
    assert all_messages[0].metadata == {"sequence": 1}
    assert [message.id for message in recent_messages] == [
        "archived-message-2",
        "archived-message-3",
    ]
    assert other_owner_messages == []
    assert cleared_messages == 3
    assert remaining_messages == []


@pytest.mark.asyncio
async def test_archive_rejects_stale_message_set_when_new_messages_appended(
    migrated_database_url: str,
) -> None:
    """回归（问题2）：摘要覆盖期间有新消息追加时，CAS 归档必须放弃且不误删。"""
    engine = create_memory_engine(migrated_database_url)
    try:
        chat_repository = SQLiteChatMemoryRepository(create_memory_session_factory(engine))
        session = await chat_repository.create_session(
            owner_user_id="user-a", session_id="archive-cas"
        )
        for index in range(2):
            await chat_repository.append_message(
                owner_user_id="user-a",
                message_id=f"cas-message-{index}",
                session_id=session.id,
                role="user",
                content=f"message {index}",
            )
        # 模拟并发：内联压缩先归档了 cas-message-0/1，随后新消息追加补齐行数
        await chat_repository.archive_compacted_messages(
            owner_user_id="user-a",
            session_id=session.id,
            message_ids=["cas-message-0", "cas-message-1"],
            memory_summary='{"summary":"inline"}',
            context_tokens=3,
            last_compacted_at=datetime.now(timezone.utc),
        )
        for index in range(2, 4):
            await chat_repository.append_message(
                owner_user_id="user-a",
                message_id=f"cas-message-{index}",
                session_id=session.id,
                role="user",
                content=f"message {index}",
            )
        # 后台任务用旧快照的 ID 集归档：这些 ID 已不在 active 表 → 必须放弃
        with pytest.raises(RuntimeError):
            await chat_repository.archive_compacted_messages(
                owner_user_id="user-a",
                session_id=session.id,
                message_ids=["cas-message-0", "cas-message-1"],
                memory_summary='{"summary":"stale"}',
                context_tokens=3,
                last_compacted_at=datetime.now(timezone.utc),
            )
        active = await chat_repository.list_active_messages(
            owner_user_id="user-a", session_id=session.id
        )
        session_after = await chat_repository.get_session(
            owner_user_id="user-a", session_id=session.id
        )
        # 新消息未被误归档，旧摘要也未覆盖新摘要
        assert [message.id for message in active] == ["cas-message-2", "cas-message-3"]
        assert session_after is not None and session_after.memory_summary == '{"summary":"inline"}'
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_clear_messages_removes_evidence_and_audits_and_dedupes_evidence(
    migrated_database_url: str,
) -> None:
    """回归（问题8）：clear_messages 清理压缩证据与审计；同 (会话, source_hash) 证据去重。"""
    engine = create_memory_engine(migrated_database_url)
    try:
        repositories = create_sqlite_memory_repositories(create_memory_session_factory(engine))
        session = await repositories.chat.create_session(
            owner_user_id="user-a", session_id="clear-evidence"
        )
        evidence_repo = cast(Any, repositories.compressed_tool_evidence)
        evidence = await evidence_repo.create(
            owner_user_id="user-a",
            chat_session_id=session.id,
            tool_name="SearchLog",
            content="full raw output",
            source_hash="hash-1",
        )
        audits_repo = cast(Any, repositories.tool_call_audits)
        await audits_repo.create_for_chat_session(
            owner_user_id="user-a",
            audit_id="audit-1",
            chat_session_id=session.id,
            tool_name="SearchLog",
            arguments={},
        )
        # 去重：同 (会话, source_hash) 返回同一行，不重复写原文
        duplicate = await evidence_repo.create(
            owner_user_id="user-a",
            chat_session_id=session.id,
            tool_name="SearchLog",
            content="full raw output",
            source_hash="hash-1",
        )
        assert duplicate.id == evidence.id
        # 清空会话消息：证据与审计一并清理
        await repositories.chat.clear_messages(owner_user_id="user-a", session_id=session.id)
        assert (
            await evidence_repo.get(
                owner_user_id="user-a",
                chat_session_id=session.id,
                evidence_id=evidence.id,
            )
            is None
        )
        assert (
            await audits_repo.list_for_chat_session(
                owner_user_id="user-a", chat_session_id=session.id
            )
            == []
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_chat_execution_lease_is_exclusive_and_token_scoped(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        session_factory = create_memory_session_factory(engine)
        first_repository = SQLiteChatMemoryRepository(session_factory)
        second_repository = SQLiteChatMemoryRepository(session_factory)
        await first_repository.create_session(
            owner_user_id="user-a",
            session_id="session-a",
            title="Lease test",
        )
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=1)

        acquired = await asyncio.gather(
            first_repository.acquire_execution_lease(
                owner_user_id="user-a",
                session_id="session-a",
                token="first-token",
                expires_at=expires_at,
            ),
            second_repository.acquire_execution_lease(
                owner_user_id="user-a",
                session_id="session-a",
                token="second-token",
                expires_at=expires_at,
            ),
        )
        wrong_token_released = await first_repository.release_execution_lease(
            owner_user_id="user-a",
            session_id="session-a",
            token="wrong-token",
        )
        first_token_released = await first_repository.release_execution_lease(
            owner_user_id="user-a",
            session_id="session-a",
            token="first-token",
        )
        second_token_released = await second_repository.release_execution_lease(
            owner_user_id="user-a",
            session_id="session-a",
            token="second-token",
        )
    finally:
        await engine.dispose()

    assert acquired.count(True) == 1
    assert wrong_token_released is False
    assert first_token_released != second_token_released


@pytest.mark.asyncio
async def test_chat_repository_updates_clears_and_deletes_sessions_by_owner(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        session_factory = create_memory_session_factory(engine)
        chat_repository = SQLiteChatMemoryRepository(session_factory)
        created_at = datetime(2026, 7, 9, 9, 0, tzinfo=timezone.utc)
        session = await chat_repository.create_session(
            owner_user_id="user-a",
            session_id="session-a",
            title=None,
            created_at=created_at,
        )
        await chat_repository.create_session(
            owner_user_id="user-b",
            session_id="session-b",
            title="Other user",
            created_at=created_at + timedelta(minutes=1),
        )
        await chat_repository.append_message(
            owner_user_id="user-a",
            message_id="message-a-1",
            session_id=session.id,
            role="user",
            content="How do I restart the API service?",
            metadata={
                "citations": [
                    {
                        "chunkId": "chunk_1",
                        "documentId": "doc_1",
                        "knowledgeBaseId": "kb_user_a",
                    }
                ],
                "toolCallIds": ["tool_call_1"],
            },
            created_at=created_at + timedelta(minutes=2),
        )
        await chat_repository.append_message(
            owner_user_id="user-a",
            message_id="message-a-2",
            session_id=session.id,
            role="assistant",
            content="Use the runbook.",
            created_at=created_at + timedelta(minutes=3),
        )

        updated = await chat_repository.update_session_title(
            owner_user_id="user-a",
            session_id=session.id,
            title="Restart API",
            updated_at=created_at + timedelta(minutes=4),
        )
        cross_tenant_update = await chat_repository.update_session_title(
            owner_user_id="user-b",
            session_id=session.id,
            title="Should not change",
            updated_at=created_at + timedelta(minutes=5),
        )
        messages_before_clear = await chat_repository.list_messages(
            owner_user_id="user-a",
            session_id=session.id,
        )
        deleted_messages = await chat_repository.clear_messages(
            owner_user_id="user-a",
            session_id=session.id,
            updated_at=created_at + timedelta(minutes=6),
        )
        messages_after_clear = await chat_repository.list_messages(
            owner_user_id="user-a",
            session_id=session.id,
        )
        cross_tenant_deleted = await chat_repository.delete_session(
            owner_user_id="user-b",
            session_id=session.id,
        )
        deleted = await chat_repository.delete_session(
            owner_user_id="user-a",
            session_id=session.id,
        )
        session_after_delete = await chat_repository.get_session(
            owner_user_id="user-a",
            session_id=session.id,
        )
    finally:
        await engine.dispose()

    assert updated is not None
    assert updated.title == "Restart API"
    assert cross_tenant_update is None
    assert messages_before_clear[0].metadata["toolCallIds"] == ["tool_call_1"]
    assert deleted_messages == 2
    assert messages_after_clear == []
    assert cross_tenant_deleted is False
    assert deleted is True
    assert session_after_delete is None


@pytest.mark.asyncio
async def test_diagnostic_repository_persists_artifacts_and_filters_tasks(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        session_factory = create_memory_session_factory(engine)
        diagnostic_repository = SQLiteDiagnosticMemoryRepository(session_factory)
        created_at = datetime(2026, 7, 8, 11, 0, tzinfo=timezone.utc)

        await diagnostic_repository.create_task(
            owner_user_id="user-a",
            task_id="task-old",
            status="completed",
            query="old incident",
            input_payload={"service": "api"},
            result_payload={"summary": "old"},
            created_at=created_at - timedelta(days=1),
        )
        await diagnostic_repository.create_task(
            owner_user_id="user-b",
            task_id="task-other-user",
            status="running",
            query="other incident",
            created_at=created_at,
        )
        task = await diagnostic_repository.create_task(
            owner_user_id="user-a",
            task_id="task-1",
            status="running",
            query="latency spike",
            input_payload={"service": "checkout"},
            result_payload={"stage": "collecting"},
            created_at=created_at,
        )
        report = await diagnostic_repository.add_report(
            owner_user_id="user-a",
            report_id="report-1",
            task_id=task.id,
            title="Latency report",
            content="p95 increased",
            payload={"p95_ms": 1200},
            created_at=created_at + timedelta(minutes=2),
        )
        audit = await diagnostic_repository.add_tool_call_audit(
            owner_user_id="user-a",
            audit_id="audit-1",
            task_id=task.id,
            tool_name="kubectl",
            status="success",
            arguments={"namespace": "prod"},
            result_payload={"pods": 3},
            error_message=None,
            started_at=created_at + timedelta(minutes=1),
            completed_at=created_at + timedelta(minutes=2),
        )
        checkpoint = await diagnostic_repository.save_checkpoint(
            owner_user_id="user-a",
            checkpoint_record_id="checkpoint-row-1",
            task_id=task.id,
            thread_id="thread-1",
            checkpoint_ns="diagnosis",
            checkpoint_id="checkpoint-1",
            checkpoint_payload={"node": "summarize"},
            metadata={"graph": "aiops"},
            created_at=created_at + timedelta(minutes=3),
        )

        ranged_tasks = await diagnostic_repository.list_tasks(
            owner_user_id="user-a",
            time_range=TimeRangeFilter(
                start_at=created_at - timedelta(minutes=1),
                end_at=created_at + timedelta(minutes=1),
            ),
        )
        reports = await diagnostic_repository.list_reports(owner_user_id="user-a", task_id=task.id)
        audits = await diagnostic_repository.list_tool_call_audits(
            owner_user_id="user-a",
            task_id=task.id,
        )
        checkpoints = await diagnostic_repository.list_checkpoints(
            owner_user_id="user-a",
            task_id=task.id,
        )
    finally:
        await engine.dispose()

    assert ranged_tasks == [task]
    assert reports == [report]
    assert audits == [audit]
    assert checkpoints == [checkpoint]
    assert task.owner_user_id == "user-a"
    assert report.owner_user_id == "user-a"
    assert audit.arguments == {"namespace": "prod"}
    assert checkpoint.checkpoint_payload == {"node": "summarize"}


@pytest.mark.asyncio
async def test_diagnostic_repository_denies_cross_tenant_artifact_writes(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        session_factory = create_memory_session_factory(engine)
        diagnostic_repository = SQLiteDiagnosticMemoryRepository(session_factory)
        await diagnostic_repository.create_task(
            owner_user_id="user-a",
            task_id="task-a",
            status="running",
            query="latency",
        )

        with pytest.raises(PermissionError):
            await diagnostic_repository.add_report(
                owner_user_id="user-b",
                report_id="report-b",
                task_id="task-a",
                title="Cross tenant",
                content="nope",
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_diagnosis_case_repository_is_owner_scoped_and_idempotent(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        repositories = create_sqlite_memory_repositories(create_memory_session_factory(engine))
        created_at = datetime(2026, 7, 10, 14, 0, tzinfo=timezone.utc)
        task = await repositories.diagnostics.create_task(
            owner_user_id="user-a",
            task_id="diagnostic-case-a",
            status="succeeded",
            query="Investigate checkout timeout",
        )
        report = await repositories.diagnostics.add_report(
            owner_user_id="user-a",
            report_id="report-case-a",
            task_id=task.id,
            title="Checkout report",
            content="Evidence-backed conclusion.",
        )
        document = await repositories.documents.create_document(
            owner_user_id="user-a",
            document_id="document-case-a",
            knowledge_base_id="kb_user-a",
            filename="checkout-case.md",
            size_bytes=24,
            mime_type="text/markdown",
            content_hash="sha256:diagnosis-case-a",
            metadata={"knowledgeType": "diagnostic-case"},
            uploaded_at=created_at,
        )
        index_task = await repositories.document_index_tasks.create_task(
            owner_user_id="user-a",
            task_id="index-case-a",
            knowledge_base_id=document.knowledge_base_id,
            document_id=document.id,
            created_at=created_at,
        )
        case = await repositories.diagnostics.create_case(
            owner_user_id="user-a",
            case_id="case-a",
            task_id=task.id,
            report_id=report.id,
            document_id=document.id,
            index_task_id=index_task.id,
            alert_name="CheckoutTimeout",
            service="checkout",
            keywords=["checkout", "timeout"],
            root_cause="database connection pool exhausted",
            remediation="increase the pool and retry failed requests",
            summary="Evidence-backed conclusion.",
            evidence_ids=["evidence-a"],
        )
        duplicate = await repositories.diagnostics.create_case(
            owner_user_id="user-a",
            case_id="case-a-second-attempt",
            task_id=task.id,
            report_id=report.id,
            document_id=document.id,
            index_task_id=index_task.id,
            alert_name="Different alert must not replace the original",
            service="other",
            keywords=[],
            root_cause="",
            remediation="",
            summary="",
            evidence_ids=[],
        )
        owner_case = await repositories.diagnostics.get_case(
            owner_user_id="user-a",
            case_id=case.id,
        )
        other_case = await repositories.diagnostics.get_case(
            owner_user_id="user-b",
            case_id=case.id,
        )
        owner_cases = await repositories.diagnostics.list_cases(owner_user_id="user-a")
    finally:
        await engine.dispose()

    assert duplicate == case
    assert owner_case == case
    assert other_case is None
    assert owner_cases == [case]


@pytest.mark.asyncio
async def test_document_repository_persists_queries_duplicates_and_marks_deleted(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        session_factory = create_memory_session_factory(engine)
        document_repository = SQLiteKnowledgeDocumentRepository(session_factory)
        uploaded_at = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)

        document = await document_repository.create_document(
            owner_user_id="user-a",
            document_id="doc-1",
            knowledge_base_id="kb-user-a",
            filename="runbook.md",
            size_bytes=42,
            mime_type="text/markdown",
            content_hash="sha256:abc",
            status="ready",
            index_status="pending",
            metadata={"source": "upload"},
            uploaded_at=uploaded_at,
        )
        await document_repository.create_document(
            owner_user_id="user-b",
            document_id="doc-2",
            knowledge_base_id="kb-user-b",
            filename="private.md",
            size_bytes=13,
            mime_type="text/markdown",
            content_hash="sha256:abc",
        )

        duplicate = await document_repository.find_active_by_hash(
            owner_user_id="user-a",
            knowledge_base_id="kb-user-a",
            content_hash="sha256:abc",
        )
        ranged_documents = await document_repository.list_documents(
            owner_user_id="user-a",
            knowledge_base_id="kb-user-a",
            time_range=TimeRangeFilter(
                start_at=uploaded_at - timedelta(minutes=1),
                end_at=uploaded_at + timedelta(minutes=1),
            ),
        )
        deleted = await document_repository.mark_document_deleted(
            owner_user_id="user-a",
            knowledge_base_id="kb-user-a",
            document_id=document.id,
        )
        after_delete = await document_repository.list_documents(
            owner_user_id="user-a",
            knowledge_base_id="kb-user-a",
        )
    finally:
        await engine.dispose()

    assert document.owner_user_id == "user-a"
    assert document.filename == "runbook.md"
    assert document.metadata == {"source": "upload"}
    assert duplicate == document
    assert ranged_documents == [document]
    assert deleted is not None
    assert deleted.status == "deleted"
    assert after_delete == []


@pytest.mark.asyncio
async def test_document_index_task_repository_tracks_status_failure_and_retry(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        session_factory = create_memory_session_factory(engine)
        repositories = create_sqlite_memory_repositories(session_factory)
        created_at = datetime(2026, 7, 9, 14, 0, tzinfo=timezone.utc)

        await repositories.documents.create_document(
            owner_user_id="user-a",
            document_id="doc-1",
            knowledge_base_id="kb-user-a",
            filename="runbook.md",
            size_bytes=42,
            mime_type="text/markdown",
            content_hash="sha256:index",
            metadata={"indexableText": "alpha beta"},
            uploaded_at=created_at,
        )
        task = await repositories.document_index_tasks.create_task(
            owner_user_id="user-a",
            task_id="index-task-1",
            knowledge_base_id="kb-user-a",
            document_id="doc-1",
            status="pending",
            created_at=created_at,
        )
        running = await repositories.document_index_tasks.mark_running(
            owner_user_id="user-a",
            task_id=task.id,
            started_at=created_at + timedelta(seconds=1),
        )
        failed = await repositories.document_index_tasks.mark_failed(
            owner_user_id="user-a",
            task_id=task.id,
            failure_reason="embedding unavailable",
            completed_at=created_at + timedelta(seconds=2),
        )
        retry = await repositories.document_index_tasks.create_retry(
            owner_user_id="user-a",
            task_id="index-task-2",
            retry_of_task_id=task.id,
            created_at=created_at + timedelta(seconds=3),
        )
        by_document = await repositories.document_index_tasks.list_tasks_for_document(
            owner_user_id="user-a",
            knowledge_base_id="kb-user-a",
            document_id="doc-1",
        )
        cross_tenant = await repositories.document_index_tasks.get_task(
            owner_user_id="user-b",
            task_id=task.id,
        )
    finally:
        await engine.dispose()

    assert task.status == "pending"
    assert running is not None
    assert running.status == "running"
    assert failed is not None
    assert failed.status == "failed"
    assert failed.failure_reason == "embedding unavailable"
    assert retry.retry_of_task_id == task.id
    assert retry.knowledge_base_id == "kb-user-a"
    assert retry.document_id == "doc-1"
    assert [item.id for item in by_document] == ["index-task-1", "index-task-2"]
    assert cross_tenant is None


@pytest.mark.asyncio
async def test_sop_belief_repository_scopes_versions_and_records_evidence(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        repository = SQLiteSopBeliefRepository(create_memory_session_factory(engine))
        first = await repository.record(
            owner_user_id="user-a",
            tenant_id="user-a",
            task_id="task-1",
            document_id="doc-1",
            document_version="hash-v1",
            context="critical:checkout",
            outcome="success",
            source="auto",
            failure_mode="",
            total_tokens=120,
            turns=2,
            elapsed_seconds=1.5,
        )
        updated = await repository.record(
            owner_user_id="user-a",
            tenant_id="user-a",
            task_id="task-1",
            document_id="doc-1",
            document_version="hash-v1",
            context="critical:checkout",
            outcome="failure",
            source="manual",
            failure_mode="timeout",
            total_tokens=60,
            turns=1,
            elapsed_seconds=0.5,
            metadata={"rating": "not_helpful"},
        )
        other_version = await repository.record(
            owner_user_id="user-a",
            tenant_id="user-a",
            task_id="task-2",
            document_id="doc-1",
            document_version="hash-v2",
            context="warning:checkout",
            outcome="failure",
            source="auto",
            failure_mode="stale_sop",
            total_tokens=10,
            turns=1,
            elapsed_seconds=0.1,
        )
        evidence = await repository.list_evidence_for_task(
            owner_user_id="user-a", tenant_id="user-a", task_id="task-1"
        )
        cross_owner = await repository.list_states(
            owner_user_id="user-b", tenant_id="user-b", document_versions={"doc-1": "hash-v1"}
        )
        cross_tenant = await repository.list_states(
            owner_user_id="user-a", tenant_id="tenant-b", document_versions={"doc-1": "hash-v1"}
        )
    finally:
        await engine.dispose()

    assert first.observations == 1
    assert updated.alpha == 2.0
    assert updated.beta == 4.0
    assert updated.observations == 2
    assert updated.failure_modes == {"timeout": 1}
    assert updated.contexts == {"critical:checkout": 2}
    assert [item.source for item in evidence] == ["auto", "manual"]
    assert [item.attribution_stage for item in evidence] == ["legacy", "legacy"]
    assert [item.evidence_strength for item in evidence] == ["unknown", "unknown"]
    assert evidence[1].metadata == {"rating": "not_helpful"}
    assert other_version.observations == 1
    assert cross_owner == []
    assert cross_tenant == []


@pytest.mark.asyncio
async def test_sop_belief_exposure_is_scoped_and_does_not_create_state(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        repository = SQLiteSopBeliefRepository(create_memory_session_factory(engine))
        exposure = await repository.record_exposure(
            owner_user_id="user-a",
            tenant_id="user-a",
            task_id="task-1",
            document_id="doc-1",
            document_version="hash-v1",
            attribution_stage="retrieval",
            evidence_strength="candidate",
            metadata={"rank": 1},
        )
        visible = await repository.list_exposures_for_task(
            owner_user_id="user-a", tenant_id="user-a", task_id="task-1"
        )
        hidden = await repository.list_exposures_for_task(
            owner_user_id="user-b", tenant_id="user-b", task_id="task-1"
        )
        states = await repository.list_states(
            owner_user_id="user-a", tenant_id="user-a", document_versions={"doc-1": "hash-v1"}
        )
    finally:
        await engine.dispose()

    assert exposure.attribution_stage == "retrieval"
    assert exposure.evidence_strength == "candidate"
    assert [item.id for item in visible] == [exposure.id]
    assert hidden == []
    assert states == []


@pytest.mark.asyncio
async def test_sop_belief_feedback_submission_applies_one_rating_once(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        repository = SQLiteSopBeliefRepository(create_memory_session_factory(engine))
        await repository.record(
            owner_user_id="user-a",
            tenant_id="user-a",
            task_id="task-1",
            document_id="doc-1",
            document_version="hash-v1",
            context="critical:checkout",
            outcome="success",
            source="auto",
            failure_mode="",
            total_tokens=120,
            turns=2,
            elapsed_seconds=1.5,
        )
        first = await repository.record_feedback_once(
            owner_user_id="user-a",
            tenant_id="user-a",
            task_id="task-1",
            rating="helpful",
            context="critical:checkout",
            outcome="success",
            failure_mode="",
        )
        replay = await repository.record_feedback_once(
            owner_user_id="user-a",
            tenant_id="user-a",
            task_id="task-1",
            rating="helpful",
            context="critical:checkout",
            outcome="success",
            failure_mode="",
        )
        evidence = await repository.list_evidence_for_task(
            owner_user_id="user-a", tenant_id="user-a", task_id="task-1"
        )
    finally:
        await engine.dispose()

    assert first.applied is True
    assert replay.applied is False
    assert [(item.alpha, item.beta, item.observations) for item in first.states] == [
        (5.0, 1.0, 2)
    ]
    assert [(item.alpha, item.beta, item.observations) for item in replay.states] == [
        (5.0, 1.0, 2)
    ]
    assert [(item.source, item.attribution_stage, item.evidence_strength) for item in evidence] == [
        ("auto", "legacy", "unknown"),
        ("manual", "feedback", "manual"),
    ]


@pytest.mark.asyncio
async def test_sop_belief_feedback_submission_is_concurrent_and_owner_scoped(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        repository = SQLiteSopBeliefRepository(create_memory_session_factory(engine))
        await repository.record(
            owner_user_id="user-a",
            tenant_id="user-a",
            task_id="task-1",
            document_id="doc-1",
            document_version="hash-v1",
            context="critical:checkout",
            outcome="success",
            source="auto",
            failure_mode="",
            total_tokens=120,
            turns=2,
            elapsed_seconds=1.5,
        )
        first, second = await asyncio.gather(
            *[
                repository.record_feedback_once(
                    owner_user_id="user-a",
                    tenant_id="user-a",
                    task_id="task-1",
                    rating="helpful",
                    context="critical:checkout",
                    outcome="success",
                    failure_mode="",
                )
                for _ in range(2)
            ]
        )
        evidence = await repository.list_evidence_for_task(
            owner_user_id="user-a", tenant_id="user-a", task_id="task-1"
        )
        other_owner = await repository.list_evidence_for_task(
            owner_user_id="user-b", tenant_id="user-b", task_id="task-1"
        )
    finally:
        await engine.dispose()

    assert sum(result.applied for result in (first, second)) == 1
    assert [item.observations for item in first.states] == [2]
    assert [item.observations for item in second.states] == [2]
    assert [item.source for item in evidence] == ["auto", "manual"]
    assert other_owner == []


def test_repository_boundary_exposes_protocols_and_records_only() -> None:
    assert inspect.isclass(ChatMemoryRepository)
    assert all(
        is_dataclass(record_type)
        for record_type in [
            ChatSessionRecord,
            ChatMessageRecord,
            KnowledgeDocumentRecord,
            DocumentIndexTaskRecord,
            DiagnosticTaskRecord,
            DiagnosticReportRecord,
            ToolCallAuditRecord,
            GraphCheckpointRecord,
        ]
    )
    assert all(
        not hasattr(record_type, "__table__")
        for record_type in [
            ChatSessionRecord,
            ChatMessageRecord,
            KnowledgeDocumentRecord,
            DocumentIndexTaskRecord,
            DiagnosticTaskRecord,
            DiagnosticReportRecord,
            ToolCallAuditRecord,
            GraphCheckpointRecord,
        ]
    )

    repository_source = inspect.getsource(repositories_module)
    assert "sqlalchemy" not in repository_source.lower()


@pytest.mark.asyncio
async def test_sqlite_repository_bundle_can_be_injected(migrated_database_url: str) -> None:
    engine = create_memory_engine(migrated_database_url)
    try:
        repositories = create_sqlite_memory_repositories(create_memory_session_factory(engine))
    finally:
        await engine.dispose()

    assert isinstance(repositories.chat, SQLiteChatMemoryRepository)
    assert isinstance(repositories.documents, SQLiteKnowledgeDocumentRepository)
    assert repositories.document_index_tasks is not None
    assert isinstance(repositories.diagnostics, SQLiteDiagnosticMemoryRepository)
    assert isinstance(repositories.chat_prompts, SQLiteUserChatPromptRepository)
    assert isinstance(repositories.chat_skills, SQLiteUserChatSkillRepository)
    assert isinstance(repositories.sop_beliefs, SQLiteSopBeliefRepository)


@pytest.fixture
def migrated_database_url(tmp_path: Path) -> str:
    database_path = tmp_path / "memory.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(config, "head")
    return f"sqlite+aiosqlite:///{database_path}"
