"""Multi-strategy RAG evaluation — 4 retrieval strategies, 6 metrics, error classification.

Strategies:
  1. vector-only        — pure Milvus vector search
  2. bm25-only          — pure BM25 keyword search
  3. hybrid             — vector + BM25 + RRF fusion (no rerank)
  4. hybrid+rerank      — vector + BM25 + RRF + SiliconFlow BGE rerank

Metrics:
  - Deterministic (no LLM):  MRR, NDCG@5, Recall@5 (via token-overlap relevance)
  - LLM-as-judge (DeepSeek): Context Precision, Faithfulness, Answer Relevancy, Context Recall
  - Latency:  retrieval ms, generation ms per question
  - Error taxonomy:  data-gap / chunking / ranking / generation

Clean-room baseline:
  Inject the ground-truth document text directly as context to measure generation upper bound.

Usage:
    uv run python tests/ragas_evaluation.py
    uv run python tests/ragas_evaluation.py --limit 5
    uv run python tests/ragas_evaluation.py --strategy hybrid+rerank
    uv run python tests/ragas_evaluation.py --e2e --limit 5
    uv run python tests/ragas_evaluation.py --report     # print cached report
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, cast

import httpx
import jieba
from dotenv import load_dotenv

from super_ai.llm import LlmProvider, build_default_llm_provider
from super_ai.llm.rerank import SiliconFlowRerankModel, RerankResult
from super_ai.retrieval import (
    KnowledgeRetrievalTool,
    KnowledgeRetrievalToolInput,
)
from super_ai.retrieval.hybrid import (
    BM25_CANDIDATE_LIMIT,
    RRF_K,
    Bm25Rank,
    rank_bm25_documents,
    reciprocal_rank_fusion,
)
from super_ai.vector_store import (
    MilvusHealthCheckResult,
    MilvusVectorStore,
    build_default_milvus_vector_store,
)

# ---------------------------------------------------------------------------
# paths & keys
# ---------------------------------------------------------------------------

_TEST_DIR = Path(__file__).resolve().parent
_DATA_DIR = _TEST_DIR / "data"
_QA_FILE = _DATA_DIR / "ragas_test_qa.json"
_RESULTS_DIR = _DATA_DIR / "eval_results"
_ENV_FILE = _TEST_DIR / ".env.test"

load_dotenv(_ENV_FILE)

StrategyId = Literal["vector-only", "bm25-only", "hybrid", "hybrid+rerank", "cag-kvcache"]
ALL_STRATEGIES: tuple[StrategyId, ...] = (
    "vector-only",
    "bm25-only",
    "hybrid",
    "hybrid+rerank",
    "cag-kvcache",
)

DEEPSEEK_CHAT_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
E2E_API_BASE_URL = os.environ.get("RAGAS_API_BASE_URL", "http://127.0.0.1:8000")
TOP_K = 5
MAX_CONTEXT_CHARS_PER_QUESTION = 6000
GOLD_RELEVANCE_TOKEN_OVERLAP_THRESHOLD = 0.15  # jieba 分词后阈值（中文+英文混合）

# ---------------------------------------------------------------------------
# key loading
# ---------------------------------------------------------------------------


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"[FAIL] Missing API key: {name}")
        print(f"  Set it in {_ENV_FILE} or export {name}=...")
        sys.exit(1)
    return value


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------


def _load_qa_pairs(limit: int | None = None) -> list[dict[str, Any]]:
    if not _QA_FILE.exists():
        print(f"[ERROR] Test QA file not found: {_QA_FILE}")
        sys.exit(1)
    with open(_QA_FILE, encoding="utf-8") as fh:
        data: object = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("ragas_test_qa.json must contain a JSON array.")
    items = cast(list[dict[str, Any]], data)
    for idx, item in enumerate(items):
        for field in ("question", "ground_truth"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"Item {idx}: '{field}' missing or empty.")
    return items[:limit] if limit else items


# ---------------------------------------------------------------------------
# retrieval strategies
# ---------------------------------------------------------------------------


async def _load_chunks_corpus(
    vector_store: MilvusVectorStore,
    owner_user_id: str,
    knowledge_base_ids: list[str],
) -> list[Any]:
    """Return all indexed chunks for the tenant (used by BM25)."""
    return await asyncio.to_thread(
        vector_store.list_chunks,
        tenant_id=owner_user_id,
        knowledge_base_ids=knowledge_base_ids,
    )


async def _retrieve_vector_only(
    vector_store: MilvusVectorStore,
    embedding_model: Any,
    question: str,
    owner_user_id: str,
    knowledge_base_ids: list[str],
) -> tuple[list[str], float]:
    t0 = time.monotonic()
    vectors = await embedding_model.aembed_documents([question])
    hits = await asyncio.to_thread(
        vector_store.search_chunks,
        query_vector=vectors[0],
        tenant_id=owner_user_id,
        knowledge_base_ids=knowledge_base_ids,
        limit=TOP_K,
    )
    elapsed = (time.monotonic() - t0) * 1000
    return [h.content for h in hits], elapsed


async def _retrieve_bm25_only(
    chunks_corpus: list[Any],
    question: str,
) -> tuple[list[str], float]:
    t0 = time.monotonic()
    documents = [c.content for c in chunks_corpus]
    ranks = await asyncio.to_thread(
        rank_bm25_documents,
        query=question,
        documents=documents,
        limit=TOP_K,
    )
    elapsed = (time.monotonic() - t0) * 1000
    return [chunks_corpus[r.index].content for r in ranks[:TOP_K]], elapsed


async def _retrieve_hybrid(
    vector_store: MilvusVectorStore,
    embedding_model: Any,
    chunks_corpus: list[Any],
    question: str,
    owner_user_id: str,
    knowledge_base_ids: list[str],
) -> tuple[list[str], float]:
    t0 = time.monotonic()
    vectors = await embedding_model.aembed_documents([question])
    vector_hits_task = asyncio.to_thread(
        vector_store.search_chunks,
        query_vector=vectors[0],
        tenant_id=owner_user_id,
        knowledge_base_ids=knowledge_base_ids,
        limit=BM25_CANDIDATE_LIMIT,
    )
    bm25_task = asyncio.to_thread(
        rank_bm25_documents,
        query=question,
        documents=[c.content for c in chunks_corpus],
        limit=BM25_CANDIDATE_LIMIT,
    )
    vector_hits, bm25_ranks = await asyncio.gather(vector_hits_task, bm25_task)

    bm25_chunks = [chunks_corpus[r.index] for r in bm25_ranks]
    fused = reciprocal_rank_fusion(
        vector_keys=[h.chunk_id for h in vector_hits],
        bm25_keys=[c.chunk_id for c in bm25_chunks],
        limit=TOP_K,
        k=RRF_K,
    )
    chunk_by_id: dict[str, Any] = {h.chunk_id: h for h in vector_hits}
    chunk_by_id.update({c.chunk_id: c for c in bm25_chunks})

    elapsed = (time.monotonic() - t0) * 1000
    return [chunk_by_id[f.key].content for f in fused if f.key in chunk_by_id], elapsed


async def _retrieve_hybrid_rerank(
    vector_store: MilvusVectorStore,
    embedding_model: Any,
    chunks_corpus: list[Any],
    rerank_model: SiliconFlowRerankModel,
    question: str,
    owner_user_id: str,
    knowledge_base_ids: list[str],
) -> tuple[list[str], float]:
    t0 = time.monotonic()

    # Same hybrid retrieval first
    vectors = await embedding_model.aembed_documents([question])
    vector_hits_task = asyncio.to_thread(
        vector_store.search_chunks,
        query_vector=vectors[0],
        tenant_id=owner_user_id,
        knowledge_base_ids=knowledge_base_ids,
        limit=BM25_CANDIDATE_LIMIT,
    )
    bm25_task = asyncio.to_thread(
        rank_bm25_documents,
        query=question,
        documents=[c.content for c in chunks_corpus],
        limit=BM25_CANDIDATE_LIMIT,
    )
    vector_hits, bm25_ranks = await asyncio.gather(vector_hits_task, bm25_task)

    bm25_chunks = [chunks_corpus[r.index] for r in bm25_ranks]
    fused = reciprocal_rank_fusion(
        vector_keys=[h.chunk_id for h in vector_hits],
        bm25_keys=[c.chunk_id for c in bm25_chunks],
        limit=BM25_CANDIDATE_LIMIT,
        k=RRF_K,
    )
    chunk_by_id: dict[str, Any] = {h.chunk_id: h for h in vector_hits}
    chunk_by_id.update({c.chunk_id: c for c in bm25_chunks})

    fused_docs = [
        chunk_by_id[f.key].content for f in fused if f.key in chunk_by_id
    ]

    # Then rerank with SiliconFlow BGE
    try:
        rankings = await rerank_model.arerank(
            query=question,
            documents=fused_docs,
            top_n=TOP_K,
        )
        reranked = [fused_docs[r.index] for r in rankings]
    except Exception:
        # Fallback: RRF order
        reranked = fused_docs[:TOP_K]

    elapsed = (time.monotonic() - t0) * 1000
    return reranked, elapsed


# ---------------------------------------------------------------------------
# generation
# ---------------------------------------------------------------------------


def _extract_text(value: object) -> str:
    content = getattr(value, "content", value)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in cast(list[object], content)
        )
    return str(content)


async def _generate_answer(
    model: Any,
    question: str,
    contexts: list[str],
) -> tuple[str, float]:
    t0 = time.monotonic()
    ctx_block = "\n\n---\n\n".join(
        f"[src {i}] {ctx}" for i, ctx in enumerate(contexts, start=1)
    ) if contexts else "（无检索结果）"
    prompt = (
        "你是运维专家助手。请回答用户问题，遵循以下原则：\n"
        "1. 优先基于检索到的文档内容回答\n"
        "2. 文档覆盖的部分，必须引用文档中的具体信息（如阈值、流程、历史案例）\n"
        "3. 文档未覆盖的部分，可以基于运维常识补充，但必须在回答中用标记区分：\n"
        "   - 📄 开头的内容 = 来自团队文档\n"
        "   - 💡 开头的内容 = 来自运维常识（非团队文档）\n"
        "4. 不要编造'文档中有但实际上没有'的信息\n\n"
        f"## 用户问题\n{question}\n\n"
        f"## 检索文档\n{ctx_block}\n\n"
        "请用中文给出简洁准确的回答，必要时分段标注来源。"
    )
    response = await model.ainvoke(prompt)
    elapsed = (time.monotonic() - t0) * 1000
    return _extract_text(response), elapsed


# ---------------------------------------------------------------------------
# deterministic metrics (no LLM — token-overlap relevance)
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> set[str]:
    """Tokenize mixed Chinese+English text via jieba + whitespace splitting.

    jieba handles Chinese segmentation; whitespace splitting handles English
    words, numbers, and punctuation.  Both are combined into a single token set.
    """
    lowered = text.lower()
    tokens: set[str] = set()
    # jieba for Chinese segmentation
    for token in jieba.cut(lowered):
        token = token.strip()
        if token and not token.isspace():
            tokens.add(token)
    # whitespace splitting for English / numbers / operators
    for token in lowered.split():
        token = token.strip()
        if token and not token.isspace():
            tokens.add(token)
    return tokens


def _token_overlap(text_a: str, text_b: str) -> float:
    """Jaccard-like token overlap between two strings (jieba + whitespace)."""
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / min(len(tokens_a), len(tokens_b))


def _relevance_labels(
    contexts: list[str],
    ground_truth: str,
) -> list[int]:
    """Binary relevance: 1 if token overlap with ground_truth exceeds threshold."""
    labels: list[int] = []
    for ctx in contexts:
        overlap = _token_overlap(ctx, ground_truth)
        labels.append(1 if overlap >= GOLD_RELEVANCE_TOKEN_OVERLAP_THRESHOLD else 0)
    return labels


def _mrr(contexts: list[str], ground_truth: str) -> float:
    """Mean Reciprocal Rank — position of first relevant document."""
    labels = _relevance_labels(contexts, ground_truth)
    for rank, rel in enumerate(labels, start=1):
        if rel == 1:
            return 1.0 / rank
    return 0.0


def _dcg_at_k(labels: list[int], k: int) -> float:
    scores = []
    for i, rel in enumerate(labels[:k]):
        scores.append(rel / __import__("math").log2(i + 2))  # i+2 = position 1 → log2(2)=1
    return sum(scores)


def _ndcg_at_k(contexts: list[str], ground_truth: str, k: int = 5) -> float:
    """NDCG@k — normalized by ideal ranking (all relevant docs first)."""
    labels = _relevance_labels(contexts, ground_truth)
    actual = _dcg_at_k(labels, k)
    ideal_labels = sorted(labels, reverse=True)
    ideal = _dcg_at_k(ideal_labels, k)
    return actual / ideal if ideal > 0 else 0.0


def _recall_at_k(contexts: list[str], ground_truth: str, k: int = 5) -> float:
    """Fraction of ground-truth tokens covered by retrieved contexts (jieba)."""
    gt_tokens = _tokenize(ground_truth)
    if not gt_tokens:
        return 0.0
    ctx_tokens: set[str] = set()
    for ctx in contexts[:k]:
        ctx_tokens.update(_tokenize(ctx))
    return len(gt_tokens & ctx_tokens) / len(gt_tokens)


# ---------------------------------------------------------------------------
# LLM scoring (DeepSeek judge)
# ---------------------------------------------------------------------------


def _parse_score(text: str) -> float:
    text = text.strip()
    match = re.search(r"(\d+\.?\d*)", text)
    if match:
        return round(max(0.0, min(1.0, float(match.group(1)))), 4)
    return 0.5


async def _llm_score(
    judge_model: Any,
    prompt: str,
) -> float:
    try:
        resp = await judge_model.ainvoke(prompt)
        return _parse_score(_extract_text(resp))
    except Exception:
        return 0.5


async def _score_one_question(
    judge_model: Any,
    question: str,
    answer: str,
    contexts: list[str],
    ground_truth: str,
) -> dict[str, float]:
    scores: dict[str, float] = {}

    # Context Precision — per-chunk relevance average (all chunks)
    cp_vals: list[float] = []
    for ctx in contexts:
        cp_vals.append(
            await _llm_score(
                judge_model,
                f"这个文档片段与问题直接相关吗？\n"
                f"问题：{question}\n片段：{ctx[:500]}\n"
                f"只输出0.0到1.0的数字。1.0=高度相关，0.0=不相关。",
            )
        )
    scores["context_precision"] = round(sum(cp_vals) / len(cp_vals), 4) if cp_vals else 0.0
    # CP@3 — only top-3 chunks (less noise for small-KB scenarios)
    top3 = cp_vals[:3] if len(cp_vals) >= 3 else cp_vals
    scores["context_precision_at_3"] = round(sum(top3) / len(top3), 4) if top3 else 0.0

    # Faithfulness — penalize false attribution to documents
    doc_text = chr(10).join(contexts)[:2000]
    scores["faithfulness"] = await _llm_score(
        judge_model,
        f"评估回答的忠实度。回答可能包含两种信息：📄标记的（声称来自文档）和💡标记的（来自常识）。\n"
        f"评分标准：\n"
        f"- 1.0: 📄部分的所有事实都在文档中找到原文依据，没有将常识包装成文档内容\n"
        f"- 0.5: 📄部分混入了一些文档中没有的事实\n"
        f"- 0.0: 📄部分大量编造、或文档根本没有的内容却被声称来自文档\n\n"
        f"文档内容：\n{doc_text}\n\n"
        f"回答：{answer[:1500]}\n\n"
        f"只输出0.0-1.0的数字。",
    )

    # Answer Relevancy
    scores["answer_relevancy"] = await _llm_score(
        judge_model,
        f"评估这个回答是否直接回答了用户问题。\n"
        f"问题：{question}\n回答：{answer[:1000]}\n"
        f"只输出0.0-1.0的数字，1.0=直接完整回答，0.0=完全偏离。",
    )

    # Context Recall
    scores["context_recall"] = await _llm_score(
        judge_model,
        f"评估文档片段覆盖了标准答案中多少个关键要点。\n"
        f"标准答案：{ground_truth[:1500]}\n"
        f"文档片段：{chr(10).join(contexts)[:2000]}\n"
        f"只输出0.0-1.0的数字，1.0=覆盖全部要点，0.0=未覆盖任何要点。",
    )

    return scores


# ---------------------------------------------------------------------------
# error classification
# ---------------------------------------------------------------------------

ErrorCategory = Literal["data-gap", "chunking", "ranking", "generation", "attribution", "partial-hit", "unknown"]


def _classify_error(
    contexts: list[str],
    ground_truth: str,
    cp_score: float,
    cr_score: float,
    faithfulness: float,
    answer_relevancy: float = 0.0,
) -> ErrorCategory:
    """Auto-classify WHY a question scored poorly (jieba-aware)."""
    if not contexts:
        return "data-gap"

    max_overlap = max(_token_overlap(c, ground_truth) for c in contexts)

    # -- good retrieval (CP+CR both decent) --
    if cp_score >= 0.5 and cr_score >= 0.5:
        if faithfulness < 0.6:
            return "generation"
        return "unknown"  # good scores, no error classification needed

    # -- true data gap: no relevant tokens found AND very low CP --
    if max_overlap < GOLD_RELEVANCE_TOKEN_OVERLAP_THRESHOLD and cp_score <= 0.3:
        return "data-gap"

    # -- hallucination: good retrieval, bad faithfulness --
    if faithfulness < 0.6 and cp_score >= 0.4:
        return "attribution"

    # -- chunking: good precision but poor recall (chunks too small) --
    if cp_score >= 0.5 and cr_score < 0.4:
        return "chunking"

    # -- partial hit: some relevant chunks found, answer usable --
    if 0.3 <= cp_score < 0.5 and answer_relevancy >= 0.7:
        return "partial-hit"

    # -- ranking: both precision and recall low (wrong stuff retrieved) --
    if cp_score < 0.4 and cr_score < 0.4:
        return "ranking"

    # -- generation issues with ok context --
    if cp_score >= 0.5 and cr_score >= 0.4 and faithfulness < 0.6:
        return "generation"

    return "unknown"


# ---------------------------------------------------------------------------
# clean-room baseline
# ---------------------------------------------------------------------------


async def _clean_room_baseline(
    model: Any,
    judge_model: Any,
    qa_pairs: list[dict[str, Any]],
) -> dict[str, object]:
    """Measure generation upper bound by injecting ground truth as context."""
    results: list[dict[str, object]] = []
    scores_agg: dict[str, list[float]] = defaultdict(list)

    for qa in qa_pairs:
        question = cast(str, qa["question"])
        ground_truth = cast(str, qa["ground_truth"])

        # Use ground truth itself as "perfect context"
        answer, gen_ms = await _generate_answer(model, question, [ground_truth])
        llm_scores = await _score_one_question(
            judge_model, question, answer, [ground_truth], ground_truth
        )

        for k, v in llm_scores.items():
            scores_agg[k].append(v)

        results.append(
            {
                "question": question[:120],
                "answer": answer[:800],
                "scores": llm_scores,
                "latencyGenMs": round(gen_ms, 1),
            }
        )

    averages = {
        k: round(sum(v) / len(v), 4) if v else None for k, v in scores_agg.items()
    }
    return {"averages": averages, "perItem": results}


# ---------------------------------------------------------------------------
# end-to-end chat evaluation
# ---------------------------------------------------------------------------


def _parse_sse(text: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for block in text.strip().split("\n\n"):
        fields = dict(
            line.split(": ", 1)
            for line in block.splitlines()
            if ": " in line
        )
        if "event" in fields and "data" in fields:
            events.append({"event": fields["event"], "data": json.loads(fields["data"])})
    return events


async def _discover_eval_credentials(
    client: httpx.AsyncClient,
) -> tuple[str, str] | None:
    response = await client.post(
        "/auth/login",
        json={"email": "ragas-eval@agent-py.local", "password": "ragas-test-123456"},
    )
    if response.status_code != 200:
        response = await client.post(
            "/auth/register",
            json={
                "email": "ragas-eval@agent-py.local",
                "displayName": "RAGAS Eval",
                "password": "ragas-test-123456",
            },
        )
    if response.status_code not in {200, 201}:
        return None
    data = cast(dict[str, object], response.json()["data"])
    token = cast(str, data["accessToken"])
    user = cast(dict[str, object], data["user"])
    return token, cast(str, user["id"])


async def _end_to_end_chat_evaluation(
    qa_pairs: list[dict[str, Any]],
    judge_model: Any,
) -> dict[str, object]:
    """Evaluate the production HTTP/SSE chat path, including Agent execution."""
    results: list[dict[str, object]] = []
    scores_agg: dict[str, list[float]] = defaultdict(list)
    started = time.monotonic()

    async with httpx.AsyncClient(base_url=E2E_API_BASE_URL, timeout=180) as client:
        credentials = await _discover_eval_credentials(client)
        if credentials is None:
            return {"status": "unavailable", "error": "evaluation account unavailable"}
        token, owner_id = credentials
        headers = {"Authorization": f"Bearer {token}"}

        for qa in qa_pairs:
            question = cast(str, qa["question"])
            ground_truth = cast(str, qa["ground_truth"])
            item_started = time.monotonic()
            session_response = await client.post("/chat/sessions", headers=headers, json={})
            session_response.raise_for_status()
            session = cast(dict[str, object], session_response.json()["data"])
            session_id = cast(str, session["id"])
            response = await client.post(
                f"/chat/sessions/{session_id}/messages:stream",
                headers=headers,
                json={"content": question},
            )
            response.raise_for_status()
            events = _parse_sse(response.text)

            answer = "".join(
                cast(str, cast(dict[str, object], event["data"])["delta"])
                for event in events
                if event["event"] == "content.delta"
            )
            contexts = [
                cast(str, reference["excerpt"])
                for event in events
                if event["event"] == "reference.source"
                and isinstance(cast(dict[str, object], event["data"]).get("reference"), dict)
                for reference in [
                    cast(dict[str, object], cast(dict[str, object], event["data"])["reference"])
                ]
                if isinstance(reference.get("excerpt"), str)
            ]
            llm_scores = await _score_one_question(
                judge_model, question, answer, contexts, ground_truth
            )
            for key, value in llm_scores.items():
                scores_agg[key].append(value)
            results.append(
                {
                    "question": question,
                    "groundTruth": ground_truth[:500],
                    "answer": answer[:1000],
                    "contexts": [context[:300] for context in contexts],
                    "contextCount": len(contexts),
                    "scores": llm_scores,
                    "sseEventCount": len(events),
                    "toolCallCount": sum(event["event"] == "tool.call" for event in events),
                    "completed": any(event["event"] == "complete" for event in events),
                    "latencyMs": round((time.monotonic() - item_started) * 1000, 1),
                }
            )

    return {
        "status": "completed",
        "ownerUserId": owner_id,
        "durationMs": round((time.monotonic() - started) * 1000, 1),
        "averages": {
            key: round(sum(values) / len(values), 4) if values else None
            for key, values in scores_agg.items()
        },
        "perItem": results,
    }


# ---------------------------------------------------------------------------
# main evaluation pipeline
# ---------------------------------------------------------------------------


@dataclass
class EvalRun:
    strategy: StrategyId
    metrics: dict[str, float] = field(default_factory=dict)
    per_item: list[dict[str, object]] = field(default_factory=list)


async def run_evaluation(
    limit: int | None = None,
    strategies: Sequence[StrategyId] = ALL_STRATEGIES,
    e2e: bool = False,
) -> dict[str, object]:
    print("[0/6] Loading API keys & data ...")
    siliconflow_key = _require_env("SILICONFLOW_API_KEY")
    deepseek_key = _require_env("DEEPSEEK_API_KEY")
    qa_pairs = _load_qa_pairs(limit)
    print(f"      {len(qa_pairs)} questions loaded.")

    # Providers
    print("[1/6] Initializing providers ...")
    llm_provider = build_default_llm_provider()
    chat_model = llm_provider.create_chat_model()  # default LLM for answer generation
    rerank_model = SiliconFlowRerankModel(api_key=siliconflow_key)

    # DeepSeek judge
    from langchain_openai import ChatOpenAI

    deepseek_judge = cast(
        Any,
        ChatOpenAI(
            api_key=deepseek_key,
            base_url=DEEPSEEK_BASE_URL,
            model=DEEPSEEK_CHAT_MODEL,
            temperature=0.0,
            timeout=60,
            max_retries=1,
        ),
    )
    print(f"      LLM judge: {DEEPSEEK_CHAT_MODEL} @ {DEEPSEEK_BASE_URL}")
    print(f"      Rerank: BAAI/bge-reranker-v2-m3 @ SiliconFlow")

    # Vector store
    print("[2/6] Checking vector store ...")
    vector_store = build_default_milvus_vector_store()
    health = vector_store.health_check()
    if not health.ok:
        print(f"      [FAIL] Milvus unavailable: {health.error}")
        sys.exit(1)
    print(f"      {health.collection_name} @ {health.uri} ({health.latency_ms:.1f}ms)")

    # Knowledge base
    kb_id = await _discover_knowledge_base_id()
    kb_ids = [kb_id] if kb_id else []
    owner_id = kb_id[3:] if kb_id and kb_id.startswith("kb_") else "ragas-eval"
    print(f"      KB: {kb_id or 'N/A'}")

    # Embedding model & chunks corpus
    embedding_model = llm_provider.create_embedding_model()
    chunks_corpus = (
        await _load_chunks_corpus(vector_store, owner_id, kb_ids)
        if kb_ids
        else []
    )
    print(f"      Chunks corpus: {len(chunks_corpus)} chunks")

    # ── CAG: one-time local model load + KV Cache precomputation ──
    cag_state: dict[str, Any] | None = None
    if "cag-kvcache" in strategies:
        from cag_runner import (
            answer_question as _cag_answer,
            ensure_model,
            prepare_cache,
        )

        print("\n[cag] Initializing local model + KV Cache (one-time setup)...")
        ensure_model()
        kv, kv_len, cache_setup_sec = await asyncio.to_thread(prepare_cache)
        cag_state = {
            "kv": kv,
            "kv_len": kv_len,
            "cache_setup_sec": cache_setup_sec,
            "answer_fn": _cag_answer,
        }
        print(f"[cag] Ready — cache setup took {cache_setup_sec:.1f}s\n")

    # Strategy dispatch
    strategy_runners: dict[str, Any] = {
        "vector-only": lambda q: _retrieve_vector_only(
            vector_store, embedding_model, q, owner_id, kb_ids
        ),
        "bm25-only": lambda q: _retrieve_bm25_only(chunks_corpus, q),
        "hybrid": lambda q: _retrieve_hybrid(
            vector_store, embedding_model, chunks_corpus, q, owner_id, kb_ids
        ),
        "hybrid+rerank": lambda q: _retrieve_hybrid_rerank(
            vector_store, embedding_model, chunks_corpus, rerank_model, q, owner_id, kb_ids
        ),
        "cag-kvcache": lambda q: ([], 0.0),  # handled separately via cag_state
    }

    eval_runs: dict[str, EvalRun] = {}

    for strategy_id in strategies:
        print(f"\n{'='*60}")
        print(f"  [{list(strategies).index(strategy_id)+3}/{len(strategies)+2}] Strategy: {strategy_id}")
        print(f"{'='*60}")

        run = EvalRun(strategy=strategy_id)
        retriever = strategy_runners[strategy_id]

        for idx, qa in enumerate(qa_pairs):
            question = cast(str, qa["question"])
            ground_truth = cast(str, qa["ground_truth"])
            print(f"  [{idx+1}/{len(qa_pairs)}] {question[:70]}...")

            cache_load_ms = 0.0
            try:
                if strategy_id == "cag-kvcache" and cag_state:
                    # CAG: local model generates directly from KV Cache (no retrieval)
                    contexts, answer, gen_sec = await asyncio.to_thread(
                        cag_state["answer_fn"],
                        cag_state["kv"],
                        cag_state["kv_len"],
                        question,
                    )
                    retrieval_ms = 0.0
                    generation_ms = gen_sec * 1000
                    cache_load_ms = (cag_state["cache_setup_sec"] * 1000) / max(len(qa_pairs), 1)
                else:
                    # Standard: retrieve → generate
                    contexts, retrieval_ms = await retriever(question)
                    answer, generation_ms = await _generate_answer(chat_model, question, contexts)
            except Exception as exc:
                print(f"      [WARN] Failed: {exc}")
                contexts, retrieval_ms, answer, generation_ms = [], 0.0, "", 0.0

            # Deterministic metrics
            mrr_val = _mrr(contexts, ground_truth)
            ndcg_val = _ndcg_at_k(contexts, ground_truth, k=TOP_K)
            recall_val = _recall_at_k(contexts, ground_truth, k=TOP_K)

            # LLM scores
            llm_scores = await _score_one_question(
                deepseek_judge, question, answer, contexts, ground_truth
            )

            # Error classification
            error_cat = _classify_error(
                contexts,
                ground_truth,
                llm_scores["context_precision"],
                llm_scores["context_recall"],
                llm_scores["faithfulness"],
                llm_scores["answer_relevancy"],
            )

            item: dict[str, object] = {
                "question": question,
                "groundTruth": ground_truth[:500],
                "answer": answer[:1000],
                "contexts": [c[:300] for c in contexts],
                "contextCount": len(contexts),
                "scores": {
                    **llm_scores,
                    "mrr": round(mrr_val, 4),
                    "ndcg_at_5": round(ndcg_val, 4),
                    "recall_at_5": round(recall_val, 4),
                },
                "latency": {
                    "retrievalMs": round(retrieval_ms, 1),
                    "generationMs": round(generation_ms, 1),
                    **({"cacheLoadMs": round(cache_load_ms, 1)} if cache_load_ms > 0 else {}),
                },
                "errorCategory": error_cat,
            }
            run.per_item.append(item)

            # Print per-item summary
            cp = llm_scores["context_precision"]
            cp3 = llm_scores.get("context_precision_at_3", cp)
            cr = llm_scores["context_recall"]
            ar = llm_scores["answer_relevancy"]
            fai = llm_scores["faithfulness"]
            gen_display = f" gen={generation_ms:.0f}ms" if generation_ms > 0 else ""
            print(
                f"      CP={cp:.2f} CP@3={cp3:.2f} CR={cr:.2f} AR={ar:.2f} F={fai:.2f} "
                f"MRR={mrr_val:.2f} NDCG={ndcg_val:.2f} R@5={recall_val:.2f} "
                f"| ret={retrieval_ms:.0f}ms{gen_display} | [{error_cat}]"
            )

            await asyncio.sleep(0.3)  # rate limit

        # Aggregate metrics
        agg: dict[str, float] = {}
        for key in ("context_precision", "context_precision_at_3", "faithfulness",
                     "answer_relevancy", "context_recall",
                     "mrr", "ndcg_at_5", "recall_at_5"):
            vals = [
                cast(dict[str, object], cast(dict[str, object], i["scores"]))[key]
                for i in run.per_item
                if isinstance(cast(dict[str, object], i["scores"]).get(key), (int, float))
            ]
            agg[key] = round(sum(cast(float, v) for v in vals) / len(vals), 4) if vals else 0.0

        agg["avg_retrieval_ms"] = round(
            sum(cast(float, cast(dict[str, object], i["latency"])["retrievalMs"]) for i in run.per_item)
            / max(len(run.per_item), 1), 1
        )
        agg["avg_generation_ms"] = round(
            sum(cast(float, cast(dict[str, object], i["latency"])["generationMs"]) for i in run.per_item)
            / max(len(run.per_item), 1), 1
        )
        # CAG-specific: one-time cache load amortized across questions
        cache_loads = [
            cast(float, cast(dict[str, object], i["latency"]).get("cacheLoadMs", 0))
            for i in run.per_item
        ]
        if any(v > 0 for v in cache_loads):
            agg["avg_cache_load_ms"] = round(sum(cache_loads) / len(cache_loads), 1)

        # Error distribution
        error_dist: dict[str, int] = defaultdict(int)
        for i in run.per_item:
            cat = cast(str, i.get("errorCategory", "unknown"))
            error_dist[cat] += 1
        agg["error_distribution"] = cast(Any, dict(error_dist))

        run.metrics = agg
        eval_runs[strategy_id] = run

        print(f"\n  ── {strategy_id} 汇总 ──")
        print(f"  CP={agg['context_precision']:.4f}  CP@3={agg.get('context_precision_at_3', 0):.4f}  "
              f"CR={agg['context_recall']:.4f}  AR={agg['answer_relevancy']:.4f}  F={agg['faithfulness']:.4f}")
        print(f"  MRR={agg['mrr']:.4f}  NDCG@5={agg['ndcg_at_5']:.4f}  R@5={agg['recall_at_5']:.4f}")
        print(f"  Latency: retrieval {agg['avg_retrieval_ms']:.0f}ms  generation {agg['avg_generation_ms']:.0f}ms")
        print(f"  Errors: {dict(error_dist)}")

    # -------------------------------------------------------------------
    # clean-room baseline
    # -------------------------------------------------------------------
    print(f"\n{'='*60}")
    print(f"  [{len(strategies)+3}/{len(strategies)+2}] Clean-room baseline (gold context)")
    print(f"{'='*60}")
    clean_room = await _clean_room_baseline(chat_model, deepseek_judge, qa_pairs)
    print(f"  AR={clean_room['averages']['answer_relevancy']:.4f}  "
          f"F={clean_room['averages']['faithfulness']:.4f}")

    end_to_end: dict[str, object] | None = None
    if e2e:
        print(f"\n{'='*60}")
        print("  End-to-end chat evaluation (HTTP → SSE → Agent)")
        print(f"{'='*60}")
        end_to_end = await _end_to_end_chat_evaluation(qa_pairs, deepseek_judge)
        print(f"  status={end_to_end['status']}")

    # -------------------------------------------------------------------
    # persist results
    # -------------------------------------------------------------------
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result_file = _RESULTS_DIR / f"eval_{timestamp}.json"
    summary_file = _RESULTS_DIR / "eval_latest.json"

    payload: dict[str, object] = {
        "evaluatedAt": datetime.now(timezone.utc).isoformat(),
        "config": {
            "topK": TOP_K,
            "strategies": list(strategies),
            "qaCount": len(qa_pairs),
            "judgeModel": DEEPSEEK_CHAT_MODEL,
            "rerankModel": "BAAI/bge-reranker-v2-m3",
            "e2e": e2e,
        },
        "strategies": {
            sid: {
                "metrics": run.metrics,
                "perItem": run.per_item,
            }
            for sid, run in eval_runs.items()
        },
        "cleanRoom": clean_room,
        **({"endToEnd": end_to_end} if end_to_end is not None else {}),
        "lowScoreSamples": _low_score_samples(eval_runs, top_n=5),
    }

    for path in (result_file, summary_file):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"\n  Results → {result_file}")
    print(f"  Latest  → {summary_file}")

    return payload


def _low_score_samples(
    eval_runs: dict[str, EvalRun],
    top_n: int = 5,
) -> list[dict[str, object]]:
    """Collect the worst-scoring items across all strategies for manual review."""
    scored: list[tuple[float, str, dict[str, object]]] = []
    for sid, run in eval_runs.items():
        for item in run.per_item:
            scores = cast(dict[str, object], item["scores"])
            avg = (
                cast(float, scores.get("context_precision", 0))
                + cast(float, scores.get("context_recall", 0))
            ) / 2
            scored.append((avg, sid, item))
    scored.sort(key=lambda x: x[0])
    return [
        {
            "strategy": s[1],
            "cp_cr_avg": round(s[0], 4),
            "question": cast(str, s[2]["question"])[:150],
            "answer": cast(str, s[2]["answer"])[:400],
            "errorCategory": s[2].get("errorCategory", "unknown"),
            "scores": s[2]["scores"],
        }
        for s in scored[:top_n]
    ]


# ---------------------------------------------------------------------------
# knowledge base discovery
# ---------------------------------------------------------------------------

async def _discover_knowledge_base_id() -> str | None:
    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10) as client:
            resp = await client.post(
                "/auth/login",
                json={"email": "ragas-eval@agent-py.local", "password": "ragas-test-123456"},
            )
            if resp.status_code != 200:
                resp = await client.post(
                    "/auth/register",
                    json={
                        "email": "ragas-eval@agent-py.local",
                        "displayName": "RAGAS Eval",
                        "password": "ragas-test-123456",
                    },
                )
                resp.raise_for_status()
            token = resp.json()["data"]["accessToken"]
            headers = {"Authorization": f"Bearer {token}"}
            resp = await client.get("/knowledge-bases", headers=headers)
            resp.raise_for_status()
            items = resp.json()["data"]["items"]
            if items:
                return cast(str, items[0]["id"])
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# comparison report
# ---------------------------------------------------------------------------


def _print_comparison_report(payload: dict[str, object]) -> None:
    strategies_data = cast(dict[str, object], payload.get("strategies", {}))
    clean_room = cast(dict[str, object], payload.get("cleanRoom", {}))
    config = cast(dict[str, object], payload.get("config", {}))

    print()
    print("=" * 80)
    print("  RAG 多策略对比评测报告")
    print("=" * 80)
    print(f"  时间: {payload.get('evaluatedAt', 'N/A')}")
    print(f"  题目数: {config.get('qaCount', 'N/A')}  |  Top-K: {config.get('topK', 'N/A')}")
    print(f"  Judge: {config.get('judgeModel', 'N/A')}  |  Rerank: {config.get('rerankModel', 'N/A')}")
    print()

    # Dynamically determine which strategies are present in the data
    present_strategies = [sid for sid in ALL_STRATEGIES if sid in strategies_data]
    n_cols = len(present_strategies)

    # Metric comparison table
    metric_labels: list[tuple[str, str, bool]] = [
        ("context_precision", "Context Precision", True),
        ("context_precision_at_3", "Context Prec@3", True),
        ("context_recall", "Context Recall", True),
        ("faithfulness", "Faithfulness", True),
        ("answer_relevancy", "Answer Relevancy", True),
        ("mrr", "MRR", False),
        ("ndcg_at_5", "NDCG@5", False),
        ("recall_at_5", "Recall@5", False),
        ("avg_retrieval_ms", "Retrieval (ms)", False),
        ("avg_generation_ms", "Generation (ms)", False),
        ("avg_cache_load_ms", "Cache Load (ms)", False),
    ]
    # Latency metrics should not compete for "best"
    _latency_keys = {"avg_retrieval_ms", "avg_generation_ms", "avg_cache_load_ms"}

    # Header
    header = "  │ {:<20}".format("指标")
    for sid in present_strategies:
        header += " │ {:>12}".format(sid[:12])
    header += " │ {:>12} │".format("Clean-room")
    print(header)
    # Dynamic separator
    sep = "  ├" + "─" * 21 + "┼" + "─" * 14 + "┼".join(["─" * 12] * (n_cols - 1))
    if n_cols > 0:
        sep += "─" * 14 + "┼"
    sep += "─" * 14 + "┤"
    print(sep)

    # Rows
    for key, label, is_llm in metric_labels:
        row = "  │ {:<20}".format(label)
        best_val = -1.0
        best_sid = ""
        for sid in present_strategies:
            sdata = strategies_data.get(sid)
            if sdata and isinstance(sdata, dict):
                metrics = cast(dict[str, object], sdata.get("metrics", {}))
                val = metrics.get(key)
                if isinstance(val, (int, float)):
                    row += " │ {:>12.4f}".format(float(val))
                    if key not in _latency_keys:
                        if float(val) > best_val:
                            best_val = float(val)
                            best_sid = sid
                else:
                    row += " │ {:>12}".format("—")
            else:
                row += " │ {:>12}".format("—")
        # Clean-room column (only for LLM metrics)
        if is_llm:
            cr_avg = cast(dict[str, object], clean_room.get("averages", {}))
            cr_val = cr_avg.get(key)
            if isinstance(cr_val, (int, float)):
                row += " │ {:>12.4f}".format(float(cr_val))
            else:
                row += " │ {:>12}".format("—")
        else:
            row += " │ {:>12}".format("—")
        row += " │"
        print(row)

    # Dynamic bottom border
    bottom = "  └" + "─" * 21 + "┴" + "─" * 14 + "┴".join(["─" * 12] * (n_cols - 1))
    if n_cols > 0:
        bottom += "─" * 14 + "┴"
    bottom += "─" * 14 + "┘"
    print(bottom)
    print()
    print("  Clean-room = 直接把标准答案作为上下文喂给 LLM，衡量生成质量上界")
    print("  LLM 指标 (CP/CR/F/AR) 用 DeepSeek 评分，确定性指标 (MRR/NDCG/R@5) 用 jieba token overlap 计算")
    print("  CP@3 = 仅取 top-3 chunk 的 Context Precision（减少 small-KB 场景下噪音 chunk 的惩罚）")
    print()

    # Error distribution
    print("─" * 80)
    print("  错误分类分布")
    print("─" * 80)
    for sid in ALL_STRATEGIES:
        sdata = strategies_data.get(sid)
        if sdata and isinstance(sdata, dict):
            metrics = cast(dict[str, object], sdata.get("metrics", {}))
            error_dist = metrics.get("error_distribution")
            if isinstance(error_dist, dict):
                print(f"  {sid:<18} {error_dist}")

    # Low score samples
    low_samples = payload.get("lowScoreSamples")
    if isinstance(low_samples, list) and low_samples:
        print()
        print("─" * 80)
        print("  低分样本 TOP 5（需人工抽查）")
        print("─" * 80)
        for i, s in enumerate(cast(list[dict[str, object]], low_samples), 1):
            print(f"\n  [{i}] [{s.get('strategy', '?')}] CP+CR avg = {s.get('cp_cr_avg', '?')}")
            print(f"      问题: {cast(str, s.get('question', ''))[:120]}")
            print(f"      回答: {cast(str, s.get('answer', ''))[:200]}")
            print(f"      分类: {s.get('errorCategory', '?')}")
            print(f"      评分: {s.get('scores', {})}")


# ---------------------------------------------------------------------------
# entry points
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-strategy RAG evaluation")
    parser.add_argument("--limit", type=int, default=None, help="Limit QA pairs (default: all)")
    parser.add_argument(
        "--strategy",
        type=str,
        default=None,
        choices=list(ALL_STRATEGIES),
        help="Run a single strategy instead of all 4",
    )
    parser.add_argument("--report", action="store_true", help="Print report from cached results")
    parser.add_argument(
        "--e2e",
        action="store_true",
        help="Also evaluate the real HTTP/SSE chat Agent path",
    )
    args = parser.parse_args()

    if args.report:
        summary_file = _RESULTS_DIR / "eval_latest.json"
        if not summary_file.exists():
            print("No cached results. Run without --report first.")
            sys.exit(1)
        with open(summary_file, encoding="utf-8") as fh:
            _print_comparison_report(cast(dict[str, object], json.load(fh)))
        return

    strategies = (cast(StrategyId, args.strategy),) if args.strategy else ALL_STRATEGIES
    payload = asyncio.run(run_evaluation(args.limit, strategies=strategies, e2e=args.e2e))
    _print_comparison_report(payload)


# ---------------------------------------------------------------------------
# pytest
# ---------------------------------------------------------------------------


class TestRagasEvaluation:
    def test_qa_dataset_loads(self) -> None:
        pairs = _load_qa_pairs()
        assert len(pairs) >= 10, f"Expected >=10 QA pairs, got {len(pairs)}"
        for idx, qa in enumerate(pairs):
            assert qa["question"].strip(), f"Item {idx}: empty question"
            assert qa["ground_truth"].strip(), f"Item {idx}: empty ground_truth"

    def test_token_overlap(self) -> None:
        assert _token_overlap("nginx 502 error", "nginx 502 bad gateway") > 0.1
        assert _token_overlap("nginx", "redis cluster") == 0.0
        # Chinese + English mixed
        en_cn = _token_overlap("api-gateway P99 延迟超过 800ms 触发 P0 告警",
                               "api-gateway P99 延迟 > 800ms 持续 5 分钟触发 P0-Critical")
        assert en_cn > 0.15, f"Chinese+English overlap too low: {en_cn}"

    def test_parse_score(self) -> None:
        assert _parse_score("0.85") == 0.85
        assert _parse_score("blah 0.42 blah") == 0.42
        assert _parse_score("nothing") == 0.5

    def test_parse_sse_keeps_agent_and_reference_events(self) -> None:
        events = _parse_sse(
            'event: tool.call\ndata: {"data": 1}\n\n'
            'event: reference.source\ndata: {"reference": {"excerpt": "evidence"}}\n\n'
            'event: complete\ndata: {"ok": true}'
        )
        assert [event["event"] for event in events] == [
            "tool.call",
            "reference.source",
            "complete",
        ]
        assert cast(dict[str, object], events[1]["data"])["reference"] == {
            "excerpt": "evidence"
        }

    def test_mrr_first_relevant(self) -> None:
        ctxs = ["nginx 502 error upstream failed", "redis memory config", "irrelevant doc"]
        gt = "nginx 502 bad gateway upstream connection failed"
        mrr = _mrr(ctxs, gt)
        assert mrr == 1.0, f"First doc should be relevant, got MRR={mrr}"

    def test_mrr_none_relevant(self) -> None:
        ctxs = ["redis cluster config", "mysql slow query tuning"]
        gt = "nginx upstream connection timeout"
        mrr = _mrr(ctxs, gt)
        assert mrr == 0.0, f"No relevant docs, MRR should be 0, got {mrr}"

    def test_error_classification_data_gap(self) -> None:
        cat = _classify_error([], "nginx error", 0.0, 0.0, 1.0, 0.0)
        assert cat == "data-gap"

    def test_error_classification_ranking(self) -> None:
        ctxs = ["unrelated doc about python", "javascript basics"]
        cat = _classify_error(ctxs, "nginx upstream failed", 0.3, 0.3, 0.9, 0.5)
        assert cat in ("data-gap", "ranking")

    def test_error_classification_partial_hit(self) -> None:
        ctxs = ["nginx reverse proxy config upstream", "server block examples"]
        cat = _classify_error(ctxs, "nginx upstream timeout configuration",
                              cp_score=0.35, cr_score=0.5, faithfulness=0.9, answer_relevancy=0.85)
        assert cat == "partial-hit", f"Expected partial-hit, got {cat}"


if __name__ == "__main__":
    main()
