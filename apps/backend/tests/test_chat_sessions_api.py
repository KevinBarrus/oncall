from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from starlette.requests import Request

from super_ai.api.app import (
    _chat_memory_compaction_job_handler,  # pyright: ignore[reportPrivateUsage]
    _schedule_chat_memory_compaction,  # pyright: ignore[reportPrivateUsage]
    create_app,
)
from super_ai.jobs import BackgroundJobContext
from super_ai.memory.database import create_memory_engine, create_memory_session_factory
from super_ai.memory.sqlite import create_sqlite_memory_repositories


@pytest.mark.asyncio
async def test_chat_session_lifecycle_persists_history_and_generates_title(
    migrated_database_url: str,
) -> None:
    transport = httpx.ASGITransport(app=create_app(database_url=migrated_database_url))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        user = await _register(client, "chat-owner@example.com", "Chat Owner")
        headers = _auth_headers(user["accessToken"])

        create_response = await client.post("/chat/sessions", headers=headers, json={})
        session_id = create_response.json()["data"]["id"]
        user_message_response = await client.post(
            f"/chat/sessions/{session_id}/messages",
            headers=headers,
            json={
                "role": "user",
                "content": "How do I restart the API service during an incident?",
                "metadata": {
                    "custom": {"source": "manual"},
                    "toolCallIds": ["tool_call_1"],
                },
            },
        )
        assistant_message_response = await client.post(
            f"/chat/sessions/{session_id}/messages",
            headers=headers,
            json={
                "role": "assistant",
                "content": "Use the restart runbook.",
                "metadata": {
                    "citations": [
                        {
                            "id": "chunk_1",
                            "title": "runbook.md",
                            "sourceType": "knowledge-base",
                            "chunkId": "chunk_1",
                            "documentId": "doc_1",
                            "knowledgeBaseId": f"kb_{user['user']['id']}",
                            "source": "runbook.md",
                            "metadata": {"section": "restart"},
                            "score": 0.91,
                        }
                    ]
                },
            },
        )
        detail_response = await client.get(f"/chat/sessions/{session_id}", headers=headers)
        list_response = await client.get("/chat/sessions", headers=headers)
        clear_response = await client.post(
            f"/chat/sessions/{session_id}/messages:clear",
            headers=headers,
        )
        cleared_detail_response = await client.get(f"/chat/sessions/{session_id}", headers=headers)
        delete_response = await client.delete(f"/chat/sessions/{session_id}", headers=headers)
        after_delete_list_response = await client.get("/chat/sessions", headers=headers)

    assert create_response.status_code == 201
    assert create_response.json()["data"]["title"] == "New chat"
    assert user_message_response.status_code == 201
    assert user_message_response.json()["data"]["session"]["title"] == (
        "How do I restart the API service during an incident?"
    )
    assert user_message_response.json()["data"]["message"]["metadata"]["toolCallIds"] == [
        "tool_call_1"
    ]
    assert assistant_message_response.status_code == 201
    assert (
        assistant_message_response.json()["data"]["message"]["metadata"]["citations"][0][
            "chunkId"
        ]
        == "chunk_1"
    )

    detail_payload = detail_response.json()["data"]
    assert detail_response.status_code == 200
    assert detail_payload["session"]["id"] == session_id
    assert [message["role"] for message in detail_payload["messages"]] == ["user", "assistant"]
    assert list_response.status_code == 200
    assert list_response.json()["data"]["items"][0]["id"] == session_id
    assert clear_response.status_code == 200
    assert clear_response.json()["data"] == {
        "sessionId": session_id,
        "cleared": True,
        "deletedMessages": 2,
    }
    assert cleared_detail_response.json()["data"]["messages"] == []
    assert delete_response.status_code == 200
    assert delete_response.json()["data"] == {"sessionId": session_id, "deleted": True}
    assert after_delete_list_response.json()["data"]["items"] == []


@pytest.mark.asyncio
async def test_chat_sessions_are_ordered_by_recent_updates(migrated_database_url: str) -> None:
    transport = httpx.ASGITransport(app=create_app(database_url=migrated_database_url))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        user = await _register(client, "ordered@example.com", "Ordered User")
        headers = _auth_headers(user["accessToken"])

        first = (
            await client.post("/chat/sessions", headers=headers, json={"title": "First"})
        ).json()["data"]
        second = (
            await client.post("/chat/sessions", headers=headers, json={"title": "Second"})
        ).json()["data"]
        await client.post(
            f"/chat/sessions/{first['id']}/messages",
            headers=headers,
            json={"role": "user", "content": "touch first"},
        )

        list_response = await client.get("/chat/sessions", headers=headers)

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["data"]["items"]][:2] == [
        first["id"],
        second["id"],
    ]


@pytest.mark.asyncio
async def test_chat_session_access_is_scoped_to_current_user(
    migrated_database_url: str,
) -> None:
    transport = httpx.ASGITransport(app=create_app(database_url=migrated_database_url))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        user_a = await _register(client, "chat-a@example.com", "Chat A")
        user_b = await _register(client, "chat-b@example.com", "Chat B")
        session = (
            await client.post(
                "/chat/sessions",
                headers=_auth_headers(user_a["accessToken"]),
                json={"title": "Private"},
            )
        ).json()["data"]

        anonymous_list = await client.get("/chat/sessions")
        user_b_read = await client.get(
            f"/chat/sessions/{session['id']}",
            headers=_auth_headers(user_b["accessToken"]),
        )
        user_b_append = await client.post(
            f"/chat/sessions/{session['id']}/messages",
            headers=_auth_headers(user_b["accessToken"]),
            json={"role": "user", "content": "cross tenant"},
        )
        user_b_clear = await client.post(
            f"/chat/sessions/{session['id']}/messages:clear",
            headers=_auth_headers(user_b["accessToken"]),
        )
        user_b_delete = await client.delete(
            f"/chat/sessions/{session['id']}",
            headers=_auth_headers(user_b["accessToken"]),
        )
        owner_detail = await client.get(
            f"/chat/sessions/{session['id']}",
            headers=_auth_headers(user_a["accessToken"]),
        )

    assert anonymous_list.status_code == 401
    assert anonymous_list.json()["error"]["code"] == "AUTH_UNAUTHENTICATED"
    for response in [user_b_read, user_b_append, user_b_clear, user_b_delete]:
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "AUTH_FORBIDDEN"
    assert owner_detail.status_code == 200
    assert owner_detail.json()["data"]["session"]["id"] == session["id"]


@pytest.mark.asyncio
async def test_manual_memory_operations_return_owner_scoped_background_jobs(
    migrated_database_url: str,
) -> None:
    transport = httpx.ASGITransport(app=create_app(database_url=migrated_database_url))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        owner = await _register(client, "memory-owner@example.com", "Memory Owner")
        other = await _register(client, "memory-other@example.com", "Memory Other")
        owner_headers = _auth_headers(owner["accessToken"])
        session = (
            await client.post("/chat/sessions", headers=owner_headers, json={})
        ).json()["data"]

        mode_response = await client.put(
            f"/chat/sessions/{session['id']}/memory",
            headers=owner_headers,
            json={"mode": "manual"},
        )
        compact_response = await client.post(
            f"/chat/sessions/{session['id']}/memory:compact",
            headers=owner_headers,
        )
        forbidden = await client.get(
            f"/background-jobs/{mode_response.json()['data']['job']['id']}",
            headers=_auth_headers(other["accessToken"]),
        )

    mode_payload = mode_response.json()["data"]
    compact_payload = compact_response.json()["data"]
    assert mode_response.status_code == 200
    assert mode_payload["session"]["memory"]["mode"] == "manual"
    assert mode_payload["job"]["kind"] == "chat_memory_compaction"
    assert mode_payload["job"]["resourceId"] == session["id"]
    assert compact_response.status_code == 200
    assert compact_payload["job"]["id"] != mode_payload["job"]["id"]
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_automatic_compaction_dedupes_enqueue_for_same_session(
    migrated_database_url: str,
) -> None:
    """回归（问题2）：同一会话已有排队/执行中的压缩 job 时不再重复入队。"""
    app = create_app(database_url=migrated_database_url)
    request = Request(scope={"type": "http", "app": app, "server": ("testserver", 80)})
    first = await _schedule_chat_memory_compaction(
        request, owner_user_id="user-a", session_id="session-1"
    )
    duplicate = await _schedule_chat_memory_compaction(
        request, owner_user_id="user-a", session_id="session-1"
    )
    other_session = await _schedule_chat_memory_compaction(
        request, owner_user_id="user-a", session_id="session-2"
    )
    other_owner = await _schedule_chat_memory_compaction(
        request, owner_user_id="user-b", session_id="session-1"
    )

    assert first is not None and first.status == "queued"
    assert duplicate is None
    assert other_session is not None
    assert other_owner is not None


@pytest.mark.asyncio
async def test_rest_append_respects_execution_lease(
    migrated_database_url: str,
) -> None:
    """回归（问题7）：流式执行中（持租约）REST append 用户消息返回 CHAT_SESSION_BUSY。"""
    transport = httpx.ASGITransport(app=create_app(database_url=migrated_database_url))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        owner = await _register(client, "lease-owner@example.com", "Lease Owner")
        headers = _auth_headers(owner["accessToken"])
        session = (await client.post("/chat/sessions", headers=headers, json={})).json()["data"]
        engine = create_memory_engine(migrated_database_url)
        try:
            repositories = create_sqlite_memory_repositories(
                create_memory_session_factory(engine)
            )
            await repositories.chat.acquire_execution_lease(
                owner_user_id=owner["user"]["id"],
                session_id=session["id"],
                token="external-lease",
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
            )
            response = await client.post(
                f"/chat/sessions/{session['id']}/messages",
                headers=headers,
                json={"role": "user", "content": "hello"},
            )
        finally:
            await engine.dispose()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CHAT_SESSION_BUSY"


@pytest.mark.asyncio
async def test_compaction_job_failure_records_session_error(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """回归（问题9）：后台压缩 job 失败同样写会话可见的 last_compaction_error。"""
    app = create_app(database_url=migrated_database_url)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        owner = await _register(client, "compaction-owner@example.com", "Compaction Owner")
        headers = _auth_headers(owner["accessToken"])
        session = (await client.post("/chat/sessions", headers=headers, json={})).json()["data"]

    repositories = app.state.memory_repositories
    job = await repositories.background_jobs.enqueue(
        owner_user_id=owner["user"]["id"],
        job_id="job-compaction-fail",
        kind="chat_memory_compaction",
        resource_type="chat_session",
        resource_id=session["id"],
    )
    context = BackgroundJobContext(job=job, repository=repositories.background_jobs)

    class BoomService:
        async def compact_once(self, **kwargs: object) -> object:
            raise RuntimeError("summary unavailable")

    async def fake_context(_request: object, *, owner_user_id: str) -> tuple[object, str]:
        return BoomService(), "system prompt"

    monkeypatch.setattr("super_ai.api.app._chat_memory_context", fake_context)
    handler = _chat_memory_compaction_job_handler(app)
    with pytest.raises(RuntimeError):
        await handler(context)

    session_after = await repositories.chat.get_session(
        owner_user_id=owner["user"]["id"], session_id=session["id"]
    )
    assert session_after is not None
    assert session_after.last_compaction_error == "RuntimeError"
    assert session_after.last_compaction_failed_at is not None


async def _register(client: httpx.AsyncClient, email: str, display_name: str) -> dict[str, Any]:
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "displayName": display_name,
            "password": "correct horse battery staple",
        },
    )
    return response.json()["data"]


def _auth_headers(token: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def migrated_database_url(tmp_path: Path) -> str:
    database_path = tmp_path / "chat-sessions-api.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(config, "head")
    return f"sqlite+aiosqlite:///{database_path}"
