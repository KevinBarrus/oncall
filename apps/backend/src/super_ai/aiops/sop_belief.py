"""Bayesian SOP belief registry for AIOps diagnostics.

Design inspired by Bayesian-Agent (Wu et al., 2026, arXiv:2606.08348):
- Each SOP document is a hypothesis about diagnostic success.
- Each verified diagnostic trajectory becomes evidence for updating that belief.
- SOP selection at retrieval time can incorporate posterior success probability.

Storage: ``~/.oncall/sop_beliefs.json`` — a single JSON file, no database schema changes.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

_DEFAULT_STORE_DIR = Path.home() / ".oncall"
_DEFAULT_STORE_FILE = _DEFAULT_STORE_DIR / "sop_beliefs.json"
_ALPHA = 1.0  # Laplace smoothing prior
_MAX_EVIDENCE_PER_SOP = 100  # cap stored evidence records per SOP

RewriteAction = Literal["explore", "patch", "compress", "split", "retire"]


# ---------------------------------------------------------------------------
# evidence record
# ---------------------------------------------------------------------------


@dataclass
class DiagnosticEvidence:
    """A single verified diagnostic result, ready to update SOP posteriors."""

    task_id: str
    sop_id: str
    context: str = ""
    outcome: Literal["success", "failure"] = "success"
    source: Literal["auto", "manual"] = "auto"
    failure_mode: str = ""
    total_tokens: int = 0
    turns: int = 0
    elapsed_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    @property
    def success(self) -> bool:
        return self.outcome == "success"

    @property
    def weight(self) -> float:
        """Manual feedback carries 3× the weight of automatic evidence."""
        return 3.0 if self.source == "manual" else 1.0


# ---------------------------------------------------------------------------
# SOP belief state
# ---------------------------------------------------------------------------


@dataclass
class SopBeliefState:
    """Posterior belief for one SOP document.

    Maintains:
    - Global Beta-Bernoulli posterior (alpha / beta with Laplace smoothing)
    - Failure mode distribution (which failure modes reoccur for this SOP)
    - Context distribution (in which alert scenarios this SOP was used)
    - Rolling mean of token / turn / latency statistics
    """

    sop_id: str
    alpha: float = _ALPHA  # successes + prior
    beta: float = _ALPHA  # failures + prior
    failure_modes: dict[str, int] = field(default_factory=dict)
    contexts: dict[str, int] = field(default_factory=dict)
    observations: int = 0
    mean_tokens: float = 0.0
    mean_turns: float = 0.0
    mean_elapsed_seconds: float = 0.0
    last_updated: str = ""

    @property
    def success_probability(self) -> float:
        """Beta-Bernoulli posterior mean."""
        return self.alpha / (self.alpha + self.beta)

    def update(self, evidence: DiagnosticEvidence) -> SopBeliefState:
        """Incorporate one verified diagnostic trajectory.

        Manual feedback (source="manual") carries 3× the weight of automatic
        evidence, so human judgment can quickly correct the posterior.
        """
        w = evidence.weight
        if evidence.success:
            self.alpha += w
        else:
            self.beta += w
            if evidence.failure_mode:
                self.failure_modes[evidence.failure_mode] = (
                    self.failure_modes.get(evidence.failure_mode, 0) + 1
                )

        context = evidence.context or "unknown"
        self.contexts[context] = self.contexts.get(context, 0) + 1

        self.observations += 1
        n = float(self.observations)
        self.mean_tokens += (evidence.total_tokens - self.mean_tokens) / n
        self.mean_turns += (evidence.turns - self.mean_turns) / n
        self.mean_elapsed_seconds += (
            evidence.elapsed_seconds - self.mean_elapsed_seconds
        ) / n
        self.last_updated = evidence.created_at
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "sop_id": self.sop_id,
            "alpha": self.alpha,
            "beta": self.beta,
            "success_probability": self.success_probability,
            "failure_modes": self.failure_modes,
            "contexts": self.contexts,
            "observations": self.observations,
            "mean_tokens": round(self.mean_tokens, 1),
            "mean_turns": round(self.mean_turns, 1),
            "mean_elapsed_seconds": round(self.mean_elapsed_seconds, 1),
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> SopBeliefState:
        return cls(
            sop_id=str(raw.get("sop_id") or ""),
            alpha=float(raw.get("alpha", _ALPHA)),
            beta=float(raw.get("beta", _ALPHA)),
            failure_modes=dict(raw.get("failure_modes") or {}),
            contexts=dict(raw.get("contexts") or {}),
            observations=int(raw.get("observations") or 0),
            mean_tokens=float(raw.get("mean_tokens") or 0.0),
            mean_turns=float(raw.get("mean_turns") or 0.0),
            mean_elapsed_seconds=float(raw.get("mean_elapsed_seconds") or 0.0),
            last_updated=str(raw.get("last_updated") or ""),
        )


# ---------------------------------------------------------------------------
# rewrite policy
# ---------------------------------------------------------------------------


@dataclass
class RewriteDecision:
    action: RewriteAction
    reason: str
    confidence: float = 0.0


def decide_rewrite(belief: SopBeliefState) -> RewriteDecision:
    """Map posterior belief state to a SOP rewrite action.

    Thresholds are conservative heuristics, matching Bayesian-Agent v0.5 defaults:

    ==========  =================================================
    Action      Trigger
    ==========  =================================================
    explore     no observations yet — keep collecting evidence
    retire      ≥4 failure-dominated events, success_prob < 0.45
    patch       same failure_mode observed ≥2 times
    split       evidence spans ≥3 contexts, ≥4 observations
    compress    ≥3 observations, success_prob ≥ 0.72
    ==========  =================================================
    """
    p = belief.success_probability
    n = belief.observations

    if n == 0:
        return RewriteDecision("explore", "no verified evidence yet", confidence=0.1)

    # retire: dominated by failures after enough evidence
    if belief.beta >= 4 and p < 0.45:
        return RewriteDecision(
            "retire",
            "posterior failures dominate",
            confidence=min(0.95, belief.beta / (belief.alpha + belief.beta)),
        )

    # patch: recurring failure mode — 2+ times to avoid one-off overfitting
    recurring = max(belief.failure_modes.values()) if belief.failure_modes else 0
    if recurring >= 2:
        top_mode = max(belief.failure_modes, key=lambda k: belief.failure_modes[k])
        return RewriteDecision(
            "patch",
            f"failures cluster around recurring mode: {top_mode}",
            confidence=0.75,
        )

    # split: too many different contexts
    if len(belief.contexts) >= 3 and n >= 4:
        return RewriteDecision(
            "split", "evidence spans multiple contexts", confidence=0.65
        )

    # compress: stable success after sufficient evidence
    if n >= 3 and p >= 0.72:
        return RewriteDecision(
            "compress", "success evidence is stable", confidence=p
        )

    return RewriteDecision("explore", "posterior remains uncertain", confidence=0.35)


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------


class SopBeliefRegistry:
    """JSON-backed registry of SOP posterior beliefs.

    Usage::

        registry = SopBeliefRegistry()
        registry.record(DiagnosticEvidence(...))
        belief = registry.get("sop_java_ecommerce_001")
        recommendations = registry.get_rewrite_recommendations()
    """

    def __init__(self, path: Path | str | None = None) -> None:
        resolved = Path(path) if path is not None else _DEFAULT_STORE_FILE
        self._path = resolved
        self._beliefs: dict[str, SopBeliefState] = {}
        self._evidence_log: dict[str, list[dict[str, Any]]] = {}
        self._load()

    # -- public API -----------------------------------------------------------

    def record(self, evidence: DiagnosticEvidence) -> SopBeliefState:
        """Ingest one trajectory, update the SOP belief, and persist."""
        belief = self._beliefs.get(evidence.sop_id)
        if belief is None:
            belief = SopBeliefState(sop_id=evidence.sop_id)
            self._beliefs[evidence.sop_id] = belief
        belief.update(evidence)
        self._evidence_log.setdefault(evidence.sop_id, []).append(
            {
                "task_id": evidence.task_id,
                "context": evidence.context,
                "outcome": evidence.outcome,
                "failure_mode": evidence.failure_mode,
                "total_tokens": evidence.total_tokens,
                "turns": evidence.turns,
                "elapsed_seconds": evidence.elapsed_seconds,
                "created_at": evidence.created_at,
            }
        )
        self._trim_log(evidence.sop_id)
        self._persist()
        return belief

    def record_feedback(
        self, *, task_id: str, rating: str, context: str = ""
    ) -> list[SopBeliefState]:
        """Apply human feedback for a diagnostic task.

        Finds all SOPs that were used in *task_id*, creates manual evidence
        (3× weight), and updates their posteriors.  Returns the updated beliefs.
        """
        outcome: Literal["success", "failure"] = (
            "success" if rating == "helpful" else "failure"
        )
        updated: list[SopBeliefState] = []
        seen: set[str] = set()

        for sop_id, entries in self._evidence_log.items():
            for entry in entries:
                if entry.get("task_id") != task_id:
                    continue
                if sop_id in seen:
                    break
                seen.add(sop_id)
                evidence = DiagnosticEvidence(
                    task_id=task_id,
                    sop_id=sop_id,
                    context=context or str(entry.get("context") or ""),
                    outcome=outcome,
                    source="manual",
                    failure_mode=(
                        entry.get("failure_mode", "")
                        if outcome == "failure"
                        else ""
                    ),
                    created_at=datetime.now(timezone.utc).isoformat(
                        timespec="seconds"
                    ),
                )
                updated.append(self.record(evidence))
                break
        return updated

    def get(self, sop_id: str) -> SopBeliefState | None:
        """Return the posterior belief for *sop_id*, or None."""
        return self._beliefs.get(sop_id)

    def top_sops(
        self,
        sop_ids: Sequence[str],
        *,
        retrieval_scores: Mapping[str, float] | None = None,
        belief_weight: float = 0.3,
        min_observations: int = 3,
    ) -> list[str]:
        """Reorder *sop_ids* by combined retrieval + posterior score.

        When a SOP lacks enough observations its belief is not used; it keeps
        its original retrieval rank.  *belief_weight* controls the trade-off
        between vector similarity (0.7 by default) and posterior (0.3 by default).
        """
        scores = dict(retrieval_scores or {})
        min_obs = max(min_observations, 1)

        def _key(sop_id: str) -> float:
            retrieval = scores.get(sop_id, 0.5)
            belief = self._beliefs.get(sop_id)
            if belief is None or belief.observations < min_obs:
                return retrieval  # insufficient evidence — trust retrieval
            posterior = belief.success_probability
            return retrieval * (1.0 - belief_weight) + posterior * belief_weight

        return sorted(sop_ids, key=_key, reverse=True)

    def get_rewrite_recommendations(self) -> dict[str, RewriteDecision]:
        """Return rewrite recommendations for every tracked SOP."""
        return {sid: decide_rewrite(b) for sid, b in self._beliefs.items()}

    def get_at_risk_sops(self, threshold: float = 0.5) -> list[SopBeliefState]:
        """Return SOPs whose posterior success probability is below *threshold*."""
        return [b for b in self._beliefs.values() if b.success_probability < threshold and b.observations >= 2]

    def to_dict(self) -> dict[str, Any]:
        return {
            "beliefs": {sid: b.to_dict() for sid, b in self._beliefs.items()},
            "evidence_log": dict(self._evidence_log),
        }

    # -- internal -------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        beliefs_raw = raw.get("beliefs") if isinstance(raw, dict) else {}
        if isinstance(beliefs_raw, dict):
            self._beliefs = {
                str(k): SopBeliefState.from_dict(v)
                for k, v in beliefs_raw.items()
                if isinstance(v, dict)
            }
        evidence_raw = raw.get("evidence_log") if isinstance(raw, dict) else {}
        if isinstance(evidence_raw, dict):
            self._evidence_log = {
                str(k): list(v) if isinstance(v, list) else []
                for k, v in evidence_raw.items()
            }

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.to_dict()
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def _trim_log(self, sop_id: str) -> None:
        entries = self._evidence_log.get(sop_id)
        if entries is not None and len(entries) > _MAX_EVIDENCE_PER_SOP:
            self._evidence_log[sop_id] = entries[-_MAX_EVIDENCE_PER_SOP:]
