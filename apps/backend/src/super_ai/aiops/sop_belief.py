"""Bayesian SOP belief service for AIOps diagnostics.

Design inspired by Bayesian-Agent (Wu et al., 2026, arXiv:2606.08348):
- Each SOP document is a hypothesis about diagnostic success.
- Each verified diagnostic trajectory becomes evidence for updating that belief.
- SOP selection at retrieval time can incorporate posterior success probability.

"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from super_ai.memory.repositories import SopBeliefRepository, SopBeliefStateRecord

_ALPHA = 1.0  # Laplace smoothing prior

RewriteAction = Literal["explore", "patch", "compress", "split", "retire"]


# ---------------------------------------------------------------------------
# evidence record
# ---------------------------------------------------------------------------


@dataclass
class DiagnosticEvidence:
    """A single verified diagnostic result, ready to update SOP posteriors."""

    task_id: str
    sop_id: str
    document_version: str
    context: str = ""
    outcome: Literal["success", "failure"] = "success"
    source: Literal["auto", "manual"] = "auto"
    failure_mode: str = ""
    total_tokens: int = 0
    turns: int = 0
    elapsed_seconds: float = 0.0
    attribution_stage: str = "legacy"
    evidence_strength: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
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
    failure_modes: dict[str, int] = field(default_factory=dict[str, int])
    contexts: dict[str, int] = field(default_factory=dict[str, int])
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


class SopBeliefService:
    """Apply Bayesian SOP rules through tenant-scoped persistence."""

    def __init__(self, repository: SopBeliefRepository) -> None:
        self._repository = repository

    async def record(
        self,
        *,
        owner_user_id: str,
        tenant_id: str,
        evidence: DiagnosticEvidence,
    ) -> SopBeliefState:
        state = await self._repository.record(
            owner_user_id=owner_user_id,
            tenant_id=tenant_id,
            task_id=evidence.task_id,
            document_id=evidence.sop_id,
            document_version=evidence.document_version,
            context=evidence.context,
            outcome=evidence.outcome,
            source=evidence.source,
            failure_mode=evidence.failure_mode,
            total_tokens=evidence.total_tokens,
            turns=evidence.turns,
            elapsed_seconds=evidence.elapsed_seconds,
            attribution_stage=evidence.attribution_stage,
            evidence_strength=evidence.evidence_strength,
            metadata=evidence.metadata,
            created_at=datetime.fromisoformat(evidence.created_at),
        )
        return _belief_state_from_record(state)

    async def record_exposure(
        self,
        *,
        owner_user_id: str,
        tenant_id: str,
        task_id: str,
        document_id: str,
        document_version: str,
        metadata: dict[str, Any],
    ) -> None:
        await self._repository.record_exposure(
            owner_user_id=owner_user_id,
            tenant_id=tenant_id,
            task_id=task_id,
            document_id=document_id,
            document_version=document_version,
            attribution_stage="retrieval",
            evidence_strength="candidate",
            metadata=metadata,
        )

    async def record_feedback(
        self,
        *,
        owner_user_id: str,
        tenant_id: str,
        task_id: str,
        rating: str,
        context: str = "",
    ) -> list[SopBeliefState]:
        outcome: Literal["success", "failure"] = "success" if rating == "helpful" else "failure"
        evidence_records = await self._repository.list_evidence_for_task(
            owner_user_id=owner_user_id,
            tenant_id=tenant_id,
            task_id=task_id,
        )
        updated: list[SopBeliefState] = []
        seen: set[tuple[str, str]] = set()
        for record in evidence_records:
            key = (record.document_id, record.document_version)
            if key in seen:
                continue
            seen.add(key)
            updated.append(
                await self.record(
                    owner_user_id=owner_user_id,
                    tenant_id=tenant_id,
                    evidence=DiagnosticEvidence(
                        task_id=task_id,
                        sop_id=record.document_id,
                        document_version=record.document_version,
                        context=context or record.context,
                        outcome=outcome,
                        source="manual",
                        failure_mode=record.failure_mode if outcome == "failure" else "",
                    ),
                )
            )
        return updated

    async def top_sops(
        self,
        *,
        owner_user_id: str,
        tenant_id: str,
        document_versions: Mapping[str, str],
        retrieval_scores: Mapping[str, float] | None = None,
        belief_weight: float = 0.3,
        min_observations: int = 3,
    ) -> list[str]:
        states = await self._repository.list_states(
            owner_user_id=owner_user_id,
            tenant_id=tenant_id,
            document_versions=document_versions,
        )
        beliefs = {state.document_id: _belief_state_from_record(state) for state in states}
        scores = dict(retrieval_scores or {})
        min_obs = max(min_observations, 1)

        def key(sop_id: str) -> float:
            retrieval = scores.get(sop_id, 0.5)
            belief = beliefs.get(sop_id)
            if belief is None or belief.observations < min_obs:
                return retrieval
            return retrieval * (1.0 - belief_weight) + belief.success_probability * belief_weight

        return sorted(document_versions, key=key, reverse=True)


def _belief_state_from_record(record: SopBeliefStateRecord) -> SopBeliefState:
    return SopBeliefState(
        sop_id=record.document_id,
        alpha=record.alpha,
        beta=record.beta,
        failure_modes=dict(record.failure_modes),
        contexts=dict(record.contexts),
        observations=record.observations,
        mean_tokens=record.mean_tokens,
        mean_turns=record.mean_turns,
        mean_elapsed_seconds=record.mean_elapsed_seconds,
        last_updated=record.last_updated.isoformat(timespec="seconds"),
    )
