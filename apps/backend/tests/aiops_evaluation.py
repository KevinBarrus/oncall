"""量化评测 AIOps Plan-Execute-Replan 诊断链路质量。

数据源：``super_ai.aiops.fixtures.JAVA_ECOMMERCE_INCIDENTS`` 提供的 10 套已标注
故障案例，每个案例包含真实根因、恢复步骤、trace ID 与关联 SOP。评测采集诊断
报告与证据链，计算根因命中率、证据覆盖率、修复建议可执行率、无答案拒答率和
端到端延迟，并单独对比 SOP 检索排序在信念加权前后的变化（机制验证，不把后验
分数当作诊断效果证明）。
"""
# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import httpx
import jieba
import pytest

from super_ai.aiops.fixtures import JAVA_ECOMMERCE_INCIDENTS, JavaEcommerceIncident

E2E_API_BASE_URL = os.environ.get("AIOPS_EVAL_API_BASE_URL", "http://127.0.0.1:8000")
AIOPS_EVAL_EMAIL = "aiops-eval@agent-py.local"
AIOPS_EVAL_PASSWORD = "aiops-eval-123456"
ROOT_CAUSE_RECALL_THRESHOLD = 0.15
RECOVERY_RECALL_THRESHOLD = 0.12
RESULTS_DIR = Path(__file__).resolve().parent / "data" / "aiops_eval_results"
REFUSAL_MARKERS = ("证据不足", "无法确认", "未获取", "无法验证", "证据不支持")


# ---------------------------------------------------------------------------
# 确定性指标（离线可测，不需要外部服务）
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> set[str]:
    """用 jieba + 空白切分提取中英混合 token 集合。"""
    lowered = text.lower()
    tokens: set[str] = set()
    for raw_token in jieba.cut(lowered):
        token = str(raw_token).strip()
        if token and not token.isspace():
            tokens.add(token)
    for token in lowered.split():
        token = token.strip()
        if token and not token.isspace():
            tokens.add(token)
    return tokens


def _token_recall(text_a: str, text_b: str) -> float:
    """text_a 的 token 被 text_b 覆盖的比例。"""
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)
    if not tokens_a:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a)


def _normalise(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def root_cause_hit(report_text: str, incident: JavaEcommerceIncident) -> bool:
    """诊断报告是否命中标注根因：识别受影响服务且根因关键词可追溯。"""
    if incident.service not in _normalise(report_text):
        return False
    return _token_recall(incident.root_cause, report_text) >= ROOT_CAUSE_RECALL_THRESHOLD


def evidence_coverage(
    evidence: Sequence[Mapping[str, object]],
    tool_calls: Sequence[Mapping[str, object]],
    incident: JavaEcommerceIncident,
) -> dict[str, bool]:
    """检查证据链是否覆盖 SOP 引用、CLS 日志证据与工具调用。"""
    kinds = {str(item.get("kind") or "") for item in evidence}
    serialized = json.dumps([dict(item) for item in evidence], ensure_ascii=False, default=str)
    return {
        "sop_reference": "knowledge_reference" in kinds,
        "log_evidence": incident.trace_id in serialized,
        "tool_audit": bool(tool_calls),
    }


def recovery_action_hit(report_text: str, incident: JavaEcommerceIncident) -> bool:
    """诊断报告的处理建议是否覆盖标注恢复步骤的关键动作。"""
    recovery = " ".join(incident.recovery_steps)
    return _token_recall(recovery, report_text) >= RECOVERY_RECALL_THRESHOLD


def refusal_detected(report_text: str) -> bool:
    """报告在证据不足时是否诚实拒答而不是编造根因。"""
    return any(marker in report_text for marker in REFUSAL_MARKERS)


def sop_ranking_compare(
    retrieval_scores: Mapping[str, float],
    belief_scores: Mapping[str, float],
    correct_sop_id: str,
    belief_weight: float = 0.3,
) -> dict[str, object]:
    """对比纯检索排序与信念加权排序中正确 SOP 的排名。

    模拟 ``SopBeliefService.top_sops`` 的加权逻辑（检索分 ×0.7 + 后验分 ×0.3），
    仅验证"信念能改变排序"这一机制，不作为信念提升诊断效果的证明。
    """

    def rank(scores: Mapping[str, float]) -> int:
        ordered = sorted(scores, key=lambda sop_id: scores[sop_id], reverse=True)
        if correct_sop_id in ordered:
            return ordered.index(correct_sop_id) + 1
        return len(ordered) + 1

    weighted = {
        sop_id: retrieval_scores[sop_id] * (1.0 - belief_weight)
        + belief_scores.get(sop_id, 0.0) * belief_weight
        for sop_id in retrieval_scores
    }
    return {
        "retrieval_rank": rank(retrieval_scores),
        "belief_rank": rank(weighted),
    }


# ---------------------------------------------------------------------------
# 端到端评测（需要真实后端、Milvus、LLM 与 CLS MCP）
# ---------------------------------------------------------------------------


def _alert_payload(incident: JavaEcommerceIncident) -> dict[str, object]:
    return {
        "alertName": incident.alert_name,
        "severity": incident.severity,
        "service": incident.service,
        "labels": {
            "alertname": incident.alert_name,
            "service": incident.service,
            "severity": incident.severity,
        },
        "annotations": {"trace_id": incident.trace_id, "sop": incident.sop_id},
        "startsAt": "2026-07-11T06:00:00Z",
        "status": "active",
    }


async def _discover_eval_credentials(client: httpx.AsyncClient) -> tuple[str, str] | None:
    response = await client.post(
        "/auth/login",
        json={"email": AIOPS_EVAL_EMAIL, "password": AIOPS_EVAL_PASSWORD},
    )
    if response.status_code != 200:
        response = await client.post(
            "/auth/register",
            json={
                "email": AIOPS_EVAL_EMAIL,
                "displayName": "AIOps Eval",
                "password": AIOPS_EVAL_PASSWORD,
            },
        )
    if response.status_code not in {200, 201}:
        return None
    data = cast(dict[str, object], response.json()["data"])
    token = cast(str, data["accessToken"])
    user = cast(dict[str, object], data["user"])
    return token, cast(str, user["id"])


async def _wait_for_diagnostic(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    task_id: str,
    timeout_seconds: float = 300.0,
) -> dict[str, object]:
    started = time.monotonic()
    while time.monotonic() - started < timeout_seconds:
        response = await client.get(f"/aiops/diagnostics/{task_id}", headers=headers)
        response.raise_for_status()
        task = cast(dict[str, object], response.json()["data"])
        if task.get("status") in {"succeeded", "failed", "cancelled"}:
            return task
        await asyncio.sleep(2)
    return {"status": "timeout"}


async def _evaluate_one_incident(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    incident: JavaEcommerceIncident,
) -> dict[str, object]:
    started = time.monotonic()
    response = await client.post(
        "/aiops/diagnostics",
        headers=headers,
        json={
            "query": f"诊断 {incident.alert_name}（服务 {incident.service}）的根因并给出处理建议",
            "alert": _alert_payload(incident),
        },
    )
    response.raise_for_status()
    task = cast(dict[str, object], response.json()["data"])
    task_id = str(task["id"])
    completed = await _wait_for_diagnostic(client, headers, task_id)
    elapsed = round(time.monotonic() - started, 1)

    chain_response = await client.get(
        f"/aiops/diagnostics/{task_id}/evidence-chain", headers=headers
    )
    chain_response.raise_for_status()
    chain = cast(dict[str, object], chain_response.json()["data"])
    reports = cast(list[dict[str, object]], chain.get("reports") or [])
    evidence = cast(list[dict[str, object]], chain.get("evidence") or [])
    tool_calls = cast(list[dict[str, object]], chain.get("toolCalls") or [])
    report_text = str(reports[-1].get("content") or "") if reports else ""

    return {
        "incidentId": incident.incident_id,
        "status": str(completed.get("status") or "unknown"),
        "rootCauseHit": root_cause_hit(report_text, incident),
        "recoveryHit": recovery_action_hit(report_text, incident),
        "refusalDetected": refusal_detected(report_text),
        "coverage": evidence_coverage(evidence, tool_calls, incident),
        "elapsedSeconds": elapsed,
        "evidenceCount": len(evidence),
        "toolCallCount": len(tool_calls),
    }


def _coverage_value(item: Mapping[str, object], key: str) -> bool:
    coverage = item.get("coverage")
    if not isinstance(coverage, Mapping):
        return False
    return bool(cast(Mapping[str, object], coverage).get(key))


def _elapsed_seconds(item: Mapping[str, object]) -> float:
    value = item.get("elapsedSeconds")
    return value if isinstance(value, (int, float)) else 0.0


def _summary(results: Sequence[Mapping[str, object]]) -> dict[str, object]:
    completed = [item for item in results if str(item.get("status")) == "succeeded"]
    base = len(completed) or 1
    root_cause_rate = round(
        sum(bool(item.get("rootCauseHit")) for item in completed) / base, 3
    )
    recovery_rate = round(
        sum(bool(item.get("recoveryHit")) for item in completed) / base, 3
    )
    refusal_rate = round(
        sum(bool(item.get("refusalDetected")) for item in completed) / base, 3
    )
    sop_rate = round(
        sum(_coverage_value(item, "sop_reference") for item in completed) / base, 3
    )
    log_rate = round(
        sum(_coverage_value(item, "log_evidence") for item in completed) / base, 3
    )
    return {
        "caseCount": len(results),
        "succeededCount": len(completed),
        "rootCauseHitRate": root_cause_rate,
        "recoveryHitRate": recovery_rate,
        "refusalRate": refusal_rate,
        "sopCoverageRate": sop_rate,
        "logCoverageRate": log_rate,
        "averageElapsedSeconds": round(
            sum(_elapsed_seconds(item) for item in completed) / base, 1
        ),
    }


async def run_evaluation(limit: int | None = None, mock: bool = False) -> dict[str, object]:
    incidents = (
        list(JAVA_ECOMMERCE_INCIDENTS)[:limit]
        if limit is not None
        else list(JAVA_ECOMMERCE_INCIDENTS)
    )
    results: list[dict[str, object]] = []
    if mock:
        for incident in incidents:
            result = _mock_evaluate_one_incident(incident)
            results.append(result)
            print(
                f"  {incident.incident_id}: status={result['status']} "
                f"rootCause={result['rootCauseHit']}"
            )
        return {
            "status": "completed",
            "mock": True,
            "summary": _summary(results),
            "results": results,
        }
    async with httpx.AsyncClient(base_url=E2E_API_BASE_URL, timeout=300.0) as client:
        credentials = await _discover_eval_credentials(client)
        if credentials is None:
            return {"status": "unavailable", "error": "evaluation account unavailable"}
        token, _owner_id = credentials
        headers = {"Authorization": f"Bearer {token}"}
        for incident in incidents:
            result = await _evaluate_one_incident(client, headers, incident)
            results.append(result)
            print(
                f"  {incident.incident_id}: status={result['status']} "
                f"rootCause={result['rootCauseHit']}"
            )
    return {"status": "completed", "summary": _summary(results), "results": results}


def _mock_evaluate_one_incident(incident: JavaEcommerceIncident) -> dict[str, object]:
    """离线路演：用确定性 mock 报告走同一套指标计算，不访问后端。"""
    report_text = (
        f"服务 {incident.service} 出现 {incident.symptom}。\n"
        f"根因：{incident.root_cause}。\n"
        f"处理建议：{'；'.join(incident.recovery_steps)}。"
    )
    evidence = [
        {"kind": "knowledge_reference", "source": "sop", "summary": incident.sop_id},
        {"kind": "log", "source": "cls", "summary": f"trace {incident.trace_id}"},
    ]
    tool_calls = [{"toolName": "SearchLog", "status": "completed"}]
    return {
        "incidentId": incident.incident_id,
        "status": "succeeded",
        "rootCauseHit": root_cause_hit(report_text, incident),
        "recoveryHit": recovery_action_hit(report_text, incident),
        "refusalDetected": refusal_detected(report_text),
        "coverage": evidence_coverage(evidence, tool_calls, incident),
        "elapsedSeconds": 0.0,
        "evidenceCount": len(evidence),
        "toolCallCount": len(tool_calls),
    }


def _print_report(payload: dict[str, object]) -> None:
    if payload.get("status") != "completed":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    summary = cast(dict[str, object], payload["summary"])
    print("=== AIOps 诊断质量评测 ===")
    print(f"案例数: {summary['caseCount']}  诊断成功: {summary['succeededCount']}")
    print(f"根因命中率: {summary['rootCauseHitRate']}")
    print(f"修复建议可执行率: {summary['recoveryHitRate']}")
    print(f"无答案拒答率: {summary['refusalRate']}")
    print(f"SOP 证据覆盖率: {summary['sopCoverageRate']}")
    print(f"日志证据覆盖率: {summary['logCoverageRate']}")
    print(f"平均端到端延迟(秒): {summary['averageElapsedSeconds']}")
    for item in cast(list[dict[str, object]], payload["results"]):
        print(f"  - {item['incidentId']}: status={item['status']} "
              f"rootCause={item['rootCauseHit']} recovery={item['recoveryHit']} "
              f"coverage={item['coverage']} elapsed={item['elapsedSeconds']}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="AIOps diagnosis quality evaluation")
    parser.add_argument("--limit", type=int, default=None, help="Limit incident cases")
    parser.add_argument("--report", action="store_true", help="Print report from cached results")
    parser.add_argument(
        "--mock", action="store_true", help="Run offline with deterministic fixtures"
    )
    args = parser.parse_args()

    if args.report:
        summary_file = RESULTS_DIR / "eval_latest.json"
        if not summary_file.exists():
            print("No cached results. Run without --report first.")
            raise SystemExit(1)
        with open(summary_file, encoding="utf-8") as fh:
            _print_report(cast(dict[str, object], json.load(fh)))
        return

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = asyncio.run(run_evaluation(limit=args.limit, mock=args.mock))
    if payload.get("status") == "completed":
        with open(RESULTS_DIR / "eval_latest.json", "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
    _print_report(payload)


# ---------------------------------------------------------------------------
# 离线辅助函数测试（在 CI 中显式运行，不需要外部服务）
# ---------------------------------------------------------------------------


class TestAiopsEvaluation:
    def test_incident_dataset_is_complete(self) -> None:
        assert len(JAVA_ECOMMERCE_INCIDENTS) == 10
        for incident in JAVA_ECOMMERCE_INCIDENTS:
            assert incident.incident_id
            assert incident.service
            assert incident.alert_name
            assert incident.root_cause
            assert incident.recovery_steps
            assert incident.trace_id
            assert incident.sop_id

    def test_root_cause_hit_accepts_matching_report(self) -> None:
        incident = JAVA_ECOMMERCE_INCIDENTS[0]
        report = f"受影响服务 {incident.service}。根因：{incident.root_cause}"
        assert root_cause_hit(report, incident) is True

    def test_root_cause_hit_rejects_unrelated_report(self) -> None:
        incident = JAVA_ECOMMERCE_INCIDENTS[0]
        report = f"受影响服务 {incident.service}。根因：数据库连接池配置不合理导致慢查询。"
        assert root_cause_hit(report, incident) is False

    def test_evidence_coverage_detects_sop_log_and_tool(self) -> None:
        incident = JAVA_ECOMMERCE_INCIDENTS[0]
        evidence: list[dict[str, object]] = [
            {"kind": "alert", "summary": "original alert", "payload": {}},
            {"kind": "knowledge_reference", "summary": "SOP hit", "payload": {}},
            {
                "kind": "log",
                "summary": "structured cluster sample",
                "payload": {
                    "output": [
                        {
                            "text": json.dumps(
                                [
                                    {
                                        "LogJson": json.dumps(
                                            {
                                                "trace_id": incident.trace_id,
                                                "message": "timeout",
                                            }
                                        )
                                    }
                                ]
                            )
                        }
                    ]
                },
            },
        ]
        tool_calls: list[dict[str, object]] = [{"name": "SearchLog"}]
        coverage = evidence_coverage(evidence, tool_calls, incident)
        assert coverage == {"sop_reference": True, "log_evidence": True, "tool_audit": True}

    def test_evidence_coverage_missing_log_and_tool(self) -> None:
        incident = JAVA_ECOMMERCE_INCIDENTS[0]
        evidence: list[dict[str, object]] = [
            {"kind": "alert", "summary": "original alert", "payload": {}}
        ]
        coverage = evidence_coverage(evidence, [], incident)
        assert coverage == {"sop_reference": False, "log_evidence": False, "tool_audit": False}

    def test_recovery_action_hit_accepts_matching_report(self) -> None:
        incident = JAVA_ECOMMERCE_INCIDENTS[0]
        report = f"处理建议：{incident.recovery_steps[0]}"
        assert recovery_action_hit(report, incident) is True

    def test_recovery_action_hit_rejects_unrelated_report(self) -> None:
        incident = JAVA_ECOMMERCE_INCIDENTS[0]
        report = "处理建议：重启全部实例并等待业务恢复。"
        assert recovery_action_hit(report, incident) is False

    def test_refusal_detected(self) -> None:
        assert refusal_detected("证据不足，无法确认根因。") is True
        assert refusal_detected("根因已确认：缓存未刷新导致验签失败。") is False

    def test_sop_ranking_belief_promotes_correct_sop(self) -> None:
        retrieval = {"sop-a": 0.9, "sop-b": 0.8, "sop-c": 0.7}
        belief = {"sop-a": 0.4, "sop-b": 0.5, "sop-c": 0.9}
        result = sop_ranking_compare(retrieval, belief, "sop-c")
        assert result["retrieval_rank"] == 3
        assert result["belief_rank"] == 1

    def test_sop_ranking_keeps_order_without_belief_evidence(self) -> None:
        retrieval = {"sop-a": 0.9, "sop-b": 0.8, "sop-c": 0.7}
        result = sop_ranking_compare(retrieval, {}, "sop-a")
        assert result["retrieval_rank"] == 1
        assert result["belief_rank"] == 1

    @pytest.mark.asyncio
    async def test_mock_evaluation_pipeline_completes(self) -> None:
        payload = await run_evaluation(mock=True)
        assert payload["status"] == "completed"
        assert payload["mock"] is True
        summary = cast(dict[str, object], payload["summary"])
        assert summary["caseCount"] == len(JAVA_ECOMMERCE_INCIDENTS)
        assert summary["succeededCount"] == len(JAVA_ECOMMERCE_INCIDENTS)
        assert 0 <= float(cast(float, summary["rootCauseHitRate"])) <= 1
        assert 0 <= float(cast(float, summary["logCoverageRate"])) <= 1
        assert len(cast(list[dict[str, object]], payload["results"])) == len(
            JAVA_ECOMMERCE_INCIDENTS
        )


if __name__ == "__main__":
    main()
