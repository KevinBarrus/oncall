from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config

from super_ai.api.app import create_app
from super_ai.jobs import BackgroundJobRuntime
from super_ai.mcp_client import LocalMcpClient, McpToolDefinition
from super_ai.memory.database import create_memory_engine, create_memory_session_factory
from super_ai.memory.extended_sqlite import SQLiteBackgroundJobRepository
from super_ai.vector_store import MilvusHealthCheckResult


class FakeVectorStore:
    def health_check(self) -> MilvusHealthCheckResult:
        return MilvusHealthCheckResult(True, "http://milvus.test", "chunks", 1.0)


def _fast_worker_backoff(_failures: int) -> float:
    """测试用：把 worker 退避缩短，避免拖慢用例。"""
    return 0.01


@pytest.mark.asyncio
async def test_background_runtime_recovers_leases_persists_events_and_retries(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    repository = SQLiteBackgroundJobRepository(create_memory_session_factory(engine))
    handled: list[str] = []

    async def handler(context: Any) -> None:
        handled.append(context.job.id)
        await context.append_event({"type": "task.status", "message": "done"})

    runtime = BackgroundJobRuntime(repository, concurrency=1, poll_seconds=0.01)
    runtime.register("test", handler)
    try:
        job = await repository.enqueue(
            owner_user_id="user-a",
            job_id="job-1",
            kind="test",
            resource_type="test-resource",
            resource_id="resource-1",
        )
        await runtime.start()
        completed = await _wait_for_job(repository, "user-a", job.id, "succeeded")
        events = await repository.list_events(owner_user_id="user-a", job_id=job.id)
        await runtime.stop()

        recoverable = await repository.enqueue(
            owner_user_id="user-a",
            job_id="job-2",
            kind="test",
            resource_type="test-resource",
            resource_id="resource-2",
        )
        now = datetime.now(timezone.utc)
        first_claim = await repository.claim_next(
            worker_id="dead-worker",
            lease_expires_at=now - timedelta(seconds=1),
            now=now,
        )
        second_claim = await repository.claim_next(
            worker_id="replacement-worker",
            lease_expires_at=now + timedelta(seconds=31),
            now=now + timedelta(seconds=1),
        )

        cancelled = await repository.enqueue(
            owner_user_id="user-a",
            job_id="job-3",
            kind="test",
            resource_type="test-resource",
            resource_id="resource-3",
        )
        cancelled = await repository.request_cancel(owner_user_id="user-a", job_id=cancelled.id)
        retried = await repository.retry(
            owner_user_id="user-a",
            source_job_id="job-3",
            new_job_id="job-4",
        )
    finally:
        await runtime.stop()
        await engine.dispose()

    assert completed is not None and completed.attempt == 1
    assert handled == ["job-1"]
    assert [event.sequence for event in events] == [1]
    assert events[0].payload["message"] == "done"
    assert recoverable.status == "queued"
    assert first_claim is not None and first_claim.attempt == 1
    assert second_claim is not None and second_claim.id == "job-2"
    assert second_claim.attempt == 2
    assert cancelled is not None and cancelled.status == "cancelled"
    assert retried is not None and retried.retry_of_job_id == "job-3"
    assert await repository.get(owner_user_id="user-b", job_id="job-1") is None


@pytest.mark.asyncio
async def test_background_runtime_enforces_per_kind_concurrency_limit(
    migrated_database_url: str,
) -> None:
    engine = create_memory_engine(migrated_database_url)
    repository = SQLiteBackgroundJobRepository(create_memory_session_factory(engine))
    active: dict[str, int] = {}
    peak: dict[str, int] = {}

    async def slow_handler(context: Any) -> None:
        kind = context.job.kind
        active[kind] = active.get(kind, 0) + 1
        peak[kind] = max(peak.get(kind, 0), active[kind])
        await asyncio.sleep(0.2)
        active[kind] -= 1

    runtime = BackgroundJobRuntime(
        repository,
        concurrency=2,
        poll_seconds=0.01,
        max_concurrent_per_kind={"slow": 1},
    )
    runtime.register("slow", slow_handler)
    runtime.register("fast", slow_handler)
    try:
        for index in range(3):
            await repository.enqueue(
                owner_user_id="user-a",
                job_id=f"slow-{index}",
                kind="slow",
                resource_type="test-resource",
                resource_id=f"resource-{index}",
                max_attempts=1,
            )
        await repository.enqueue(
            owner_user_id="user-a",
            job_id="fast-1",
            kind="fast",
            resource_type="test-resource",
            resource_id="resource-fast",
            max_attempts=1,
        )
        await runtime.start()
        await _wait_for_job(repository, "user-a", "slow-0", "succeeded")
        await _wait_for_job(repository, "user-a", "slow-1", "succeeded")
        await _wait_for_job(repository, "user-a", "slow-2", "succeeded")
        await _wait_for_job(repository, "user-a", "fast-1", "succeeded")
        await runtime.stop()
    finally:
        await runtime.stop()
        await engine.dispose()

    assert peak["slow"] == 1
    assert peak["fast"] == 1


@pytest.mark.asyncio
async def test_background_worker_survives_claim_error_and_keeps_working(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """回归（问题3）：claim_next 抛瞬时 DB 错误不得终止 worker 循环。"""
    monkeypatch.setattr("super_ai.jobs.runtime._worker_backoff", _fast_worker_backoff)
    engine = create_memory_engine(migrated_database_url)
    repository = SQLiteBackgroundJobRepository(create_memory_session_factory(engine))
    handled: list[str] = []

    async def handler(context: Any) -> None:
        handled.append(context.job.id)

    runtime = BackgroundJobRuntime(repository, concurrency=1, poll_seconds=0.01)
    runtime.register("test", handler)

    real_claim_next = repository.claim_next
    calls = {"n": 0}

    async def flaky_claim_next(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            raise sqlite3.OperationalError("database is locked")
        return await real_claim_next(*args, **kwargs)

    monkeypatch.setattr(repository, "claim_next", flaky_claim_next)
    try:
        job = await repository.enqueue(
            owner_user_id="user-a",
            job_id="job-1",
            kind="test",
            resource_type="test-resource",
            resource_id="resource-1",
        )
        await runtime.start()
        await _wait_for_job(repository, "user-a", job.id, "succeeded")
        assert calls["n"] >= 2
        assert handled == ["job-1"]
        # worker 存活：第二个 job 仍能被处理
        job2 = await repository.enqueue(
            owner_user_id="user-a",
            job_id="job-2",
            kind="test",
            resource_type="test-resource",
            resource_id="resource-2",
        )
        await _wait_for_job(repository, "user-a", job2.id, "succeeded")
        assert handled == ["job-1", "job-2"]
    finally:
        await runtime.stop()
        await engine.dispose()


@pytest.mark.asyncio
async def test_background_worker_survives_mark_succeeded_error(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """回归（问题3）：mark_succeeded 抛错不得冒泡终止 worker。"""
    monkeypatch.setattr("super_ai.jobs.runtime._worker_backoff", _fast_worker_backoff)
    engine = create_memory_engine(migrated_database_url)
    repository = SQLiteBackgroundJobRepository(create_memory_session_factory(engine))
    handled: list[str] = []

    async def handler(context: Any) -> None:
        handled.append(context.job.id)

    runtime = BackgroundJobRuntime(repository, concurrency=1, poll_seconds=0.01)
    runtime.register("test", handler)

    real_mark_succeeded = repository.mark_succeeded
    failed_jobs: set[str] = set()

    async def flaky_mark_succeeded(**kwargs: Any) -> Any:
        job_id = str(kwargs["job_id"])
        if job_id == "job-1":
            failed_jobs.add(job_id)
            raise sqlite3.OperationalError("database is locked")
        return await real_mark_succeeded(**kwargs)

    monkeypatch.setattr(repository, "mark_succeeded", flaky_mark_succeeded)
    try:
        job = await repository.enqueue(
            owner_user_id="user-a",
            job_id="job-1",
            kind="test",
            resource_type="test-resource",
            resource_id="resource-1",
            max_attempts=1,
        )
        await runtime.start()
        # job-1 完成但 mark 失败：等 job 因租约过期被重新领取（max_attempts=1 走失败）
        for _ in range(200):
            current = await repository.get(owner_user_id="user-a", job_id=job.id)
            if current is not None and current.status == "failed":
                break
            await asyncio.sleep(0.01)
        assert "job-1" in failed_jobs
        # worker 存活：第二个 job 正常完成
        job2 = await repository.enqueue(
            owner_user_id="user-a",
            job_id="job-2",
            kind="test",
            resource_type="test-resource",
            resource_id="resource-2",
            max_attempts=1,
        )
        await _wait_for_job(repository, "user-a", job2.id, "succeeded")
        assert handled == ["job-1", "job-2"]
    finally:
        await runtime.stop()
        await engine.dispose()


@pytest.mark.asyncio
async def test_background_worker_survives_handle_failure_error(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """回归（问题3）：handler 异常 + handle_failure 抛错不得冒泡终止 worker。"""
    monkeypatch.setattr("super_ai.jobs.runtime._worker_backoff", _fast_worker_backoff)
    engine = create_memory_engine(migrated_database_url)
    repository = SQLiteBackgroundJobRepository(create_memory_session_factory(engine))
    handled: list[str] = []

    async def failing_handler(context: Any) -> None:
        handled.append(context.job.id)
        raise RuntimeError("handler boom")

    async def ok_handler(context: Any) -> None:
        handled.append(context.job.id)

    runtime = BackgroundJobRuntime(repository, concurrency=1, poll_seconds=0.01)
    runtime.register("boom", failing_handler)
    runtime.register("ok", ok_handler)

    real_handle_failure = repository.handle_failure
    failed_jobs: set[str] = set()

    async def flaky_handle_failure(**kwargs: Any) -> Any:
        job_id = str(kwargs["job_id"])
        if job_id == "job-boom":
            failed_jobs.add(job_id)
            raise sqlite3.OperationalError("database is locked")
        return await real_handle_failure(**kwargs)

    monkeypatch.setattr(repository, "handle_failure", flaky_handle_failure)
    try:
        await repository.enqueue(
            owner_user_id="user-a",
            job_id="job-boom",
            kind="boom",
            resource_type="test-resource",
            resource_id="resource-boom",
            max_attempts=1,
        )
        await runtime.start()
        # handler 抛错 + handle_failure 抛错：worker 不应死亡
        for _ in range(200):
            if "job-boom" in failed_jobs:
                break
            await asyncio.sleep(0.01)
        assert "job-boom" in failed_jobs
        job2 = await repository.enqueue(
            owner_user_id="user-a",
            job_id="job-ok",
            kind="ok",
            resource_type="test-resource",
            resource_id="resource-ok",
            max_attempts=1,
        )
        await _wait_for_job(repository, "user-a", job2.id, "succeeded")
        assert handled == ["job-boom", "job-ok"]
    finally:
        await runtime.stop()
        await engine.dispose()


@pytest.mark.asyncio
async def test_feedback_api_updates_targets_and_enforces_owner_scope(
    migrated_database_url: str,
) -> None:
    app = create_app(database_url=migrated_database_url, vector_store=FakeVectorStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        user_a = await _register(client, "feedback-a@example.com")
        user_b = await _register(client, "feedback-b@example.com")
        repositories = app.state.memory_repositories
        session = await repositories.chat.create_session(
            owner_user_id=user_a["user"]["id"],
            session_id="chat-feedback",
            title="Feedback",
        )
        await repositories.chat.append_message(
            owner_user_id=user_a["user"]["id"],
            message_id="message-feedback",
            session_id=session.id,
            role="assistant",
            content="Use the runbook.",
            metadata={"citations": [{"id": "citation-1", "title": "runbook"}]},
        )

        first = await client.post(
            "/feedback",
            headers=_headers(user_a),
            json={
                "targetType": "chat_message",
                "targetId": "message-feedback",
                "rating": "positive",
            },
        )
        updated = await client.post(
            "/feedback",
            headers=_headers(user_a),
            json={
                "targetType": "chat_message",
                "targetId": "message-feedback",
                "rating": "negative",
                "reason": "incomplete",
                "comment": "Missing rollback steps",
            },
        )
        citation = await client.post(
            "/feedback",
            headers=_headers(user_a),
            json={
                "targetType": "citation",
                "targetId": "message-feedback",
                "subjectId": "citation-1",
                "rating": "positive",
            },
        )
        forbidden = await client.post(
            "/feedback",
            headers=_headers(user_b),
            json={
                "targetType": "chat_message",
                "targetId": "message-feedback",
                "rating": "positive",
            },
        )
        listed = await client.get(
            "/feedback?targetType=chat_message&targetId=message-feedback",
            headers=_headers(user_a),
        )

    assert first.status_code == 200
    assert updated.json()["data"]["id"] == first.json()["data"]["id"]
    assert updated.json()["data"]["rating"] == "negative"
    assert citation.status_code == 200
    assert forbidden.status_code == 403
    assert len(listed.json()["data"]["items"]) == 1


@pytest.mark.asyncio
async def test_mcp_connection_api_validates_scope_and_persists_discovered_tools(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def discover(_self: LocalMcpClient) -> list[McpToolDefinition]:
        return [McpToolDefinition("SearchLog", "Search CLS logs", {"type": "object"}, "cls")]

    monkeypatch.setattr(LocalMcpClient, "discover_tools", discover)
    app = create_app(database_url=migrated_database_url, vector_store=FakeVectorStore())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        owner = await _register(client, "mcp-owner@example.com")
        other = await _register(client, "mcp-other@example.com")
        initial = await client.get("/mcp/connections", headers=_headers(owner))
        created = await client.post(
            "/mcp/connections",
            headers=_headers(owner),
            json={
                "name": "Local tools",
                "transport": "sse",
                "url": "http://127.0.0.1:3100/sse",
                "enabled": True,
                "timeoutSeconds": 10,
                "retries": 2,
            },
        )
        connection_id = created.json()["data"]["id"]
        checked = await client.post(
            f"/mcp/connections/{connection_id}:check",
            headers=_headers(owner),
        )
        forbidden = await client.delete(
            f"/mcp/connections/{connection_id}",
            headers=_headers(other),
        )
        invalid = await client.post(
            "/mcp/connections",
            headers=_headers(owner),
            json={
                "name": "Unsafe",
                "transport": "sse",
                "url": "file:///tmp/server",
                "enabled": True,
                "timeoutSeconds": 10,
                "retries": 0,
            },
        )

    assert initial.status_code == 200
    assert initial.json()["data"]["items"][0]["name"] == "腾讯云 CLS"
    assert created.status_code == 201
    assert checked.status_code == 200
    assert checked.json()["data"]["connection"]["lastCheck"]["toolCount"] == 1
    assert checked.json()["data"]["tools"][0]["name"] == "SearchLog"
    assert forbidden.status_code == 403
    assert invalid.status_code == 400


async def _wait_for_job(
    repository: SQLiteBackgroundJobRepository,
    owner_user_id: str,
    job_id: str,
    status: str,
) -> Any:
    for _ in range(100):
        current = await repository.get(owner_user_id=owner_user_id, job_id=job_id)
        if current is not None and current.status == status:
            return current
        await asyncio.sleep(0.01)
    raise AssertionError(f"job {job_id} did not reach {status}")


async def _register(client: httpx.AsyncClient, email: str) -> dict[str, Any]:
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "displayName": email.split("@", 1)[0],
            "password": "correct horse battery staple",
        },
    )
    return response.json()["data"]


def _headers(auth: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth['accessToken']}"}


@pytest.fixture
def migrated_database_url(tmp_path: Path) -> str:
    database_path = tmp_path / "extended-capabilities.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(config, "head")
    return f"sqlite+aiosqlite:///{database_path}"
