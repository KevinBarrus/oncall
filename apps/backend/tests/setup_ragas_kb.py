"""Seed the knowledge base with test documents for RAGAS evaluation.

Usage:
    uv run python tests/setup_ragas_kb.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, cast

import httpx

API_BASE = "http://127.0.0.1:8000"
TEST_DATA = Path(__file__).resolve().parent / "data"
DOCUMENTS = [
    TEST_DATA / "team-alert-response-spec.md",
    TEST_DATA / "service-topology.md",
    TEST_DATA / "incident-postmortems.md",
    TEST_DATA / "nginx-troubleshooting.md",
    TEST_DATA / "k8s-pod-troubleshooting.md",
    TEST_DATA / "observability-metrics.md",
]
PASSWORD = "ragas-test-123456"
EMAIL = "ragas-eval@agent-py.local"


async def _register(client: httpx.AsyncClient, email: str, display_name: str) -> str:
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "displayName": display_name,
            "password": PASSWORD,
        },
    )
    if response.status_code != 201:
        data = cast(dict[str, object], response.json())
        print(f"  Register returned {response.status_code}: {data.get('error', {})}")
        # Try login instead
        response = await client.post(
            "/auth/login",
            json={"email": email, "password": PASSWORD},
        )
        response.raise_for_status()
    data = cast(dict[str, object], response.json())
    return cast(str, cast(dict[str, object], data["data"])["accessToken"])


async def _upload_document(
    client: httpx.AsyncClient,
    token: str,
    kb_id: str,
    filepath: Path,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    filename = filepath.name
    with open(filepath, "rb") as fh:
        content = fh.read()

    # Upload
    response = await client.post(
        f"/knowledge-bases/{kb_id}/documents",
        headers=headers,
        files={"file": (filename, content, "text/markdown")},
        data={"chunking": json.dumps({"strategy": "markdown-heading"})},
    )
    response.raise_for_status()
    data = cast(dict[str, object], response.json())
    doc = cast(dict[str, Any], cast(dict[str, object], data["data"])["document"])
    doc_id = cast(str, doc["id"])
    print(f"    Uploaded: {filename} → {doc_id}")

    # Trigger indexing
    response = await client.post(
        f"/knowledge-bases/{kb_id}/documents/{doc_id}/index-tasks",
        headers=headers,
    )
    response.raise_for_status()
    data = cast(dict[str, object], response.json())
    task = cast(dict[str, Any], cast(dict[str, object], data["data"])["task"])
    task_id = cast(str, task["id"])
    print(f"    Indexing task created: {task_id}")

    # Poll until indexed
    for attempt in range(30):
        await asyncio.sleep(2)
        response = await client.get(
            f"/knowledge-bases/{kb_id}/documents/{doc_id}/index-tasks/{task_id}",
            headers=headers,
        )
        response.raise_for_status()
        data = cast(dict[str, object], response.json())
        task = cast(dict[str, Any], cast(dict[str, object], data["data"])["task"])
        status = cast(str, task.get("status", ""))
        if status == "completed":
            print(f"    Indexed ({attempt * 2}s)")
            return doc
        if status == "failed":
            error = task.get("error", "unknown")
            raise RuntimeError(f"Indexing failed: {error}")

    raise RuntimeError(f"Indexing timed out for {filename}")


async def main() -> None:
    print("=" * 60)
    print("  RAGAS 评估 — 知识库数据准备")
    print("=" * 60)
    print()

    # Check backend
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        try:
            response = await client.get("/readiness")
            print(f"[OK] Backend reachable — {response.status_code}")
        except Exception:
            print(f"[FAIL] Cannot reach backend at {API_BASE}")
            print("  Make sure the backend is running:")
            print("    cd apps/backend && uv run uvicorn super_ai.api.app:create_app --factory --host 127.0.0.1 --port 8000")
            sys.exit(1)

        # Register / login
        print()
        print(f"[1/3] Authenticating ({EMAIL}) ...")
        try:
            token = await _register(client, EMAIL, "RAGAS Eval User")
            print(f"  Token: {token[:20]}...")
        except Exception as exc:
            print(f"[FAIL] Authentication error: {exc}")
            sys.exit(1)

        headers = {"Authorization": f"Bearer {token}"}

        # Knowledge base ID
        response = await client.get("/knowledge-bases", headers=headers)
        response.raise_for_status()
        data = cast(dict[str, object], response.json())
        items = cast(list[dict[str, Any]], cast(dict[str, object], data["data"])["items"])
        kb_id = cast(str, items[0]["id"]) if items else f"kb_{EMAIL}"
        print(f"  Knowledge base: {kb_id}")

        # Upload docs
        print()
        print(f"[2/3] Uploading {len(DOCUMENTS)} test documents ...")
        for filepath in DOCUMENTS:
            if not filepath.exists():
                print(f"  [SKIP] File not found: {filepath}")
                continue
            try:
                await _upload_document(client, token, kb_id, filepath)
            except Exception as exc:
                print(f"  [WARN] {filepath.name}: {exc}")

        # Verify
        print()
        print("[3/3] Verifying indexed documents ...")
        response = await client.get(
            f"/knowledge-bases/{kb_id}/documents",
            headers=headers,
        )
        response.raise_for_status()
        data = cast(dict[str, object], response.json())
        docs = cast(list[dict[str, Any]], cast(dict[str, object], data["data"])["items"])
        indexed = [d for d in docs if d.get("indexStatus") == "indexed"]
        print(f"  Indexed documents: {len(indexed)}/{len(docs)}")
        for d in indexed:
            print(f"    - {d['filename']} ({d['sizeBytes']} bytes)")

    print()
    print("=" * 60)
    print("  Setup complete. Run the evaluation:")
    print("    uv run python tests/ragas_evaluation.py")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
