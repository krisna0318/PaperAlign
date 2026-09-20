"""Conservative semantic adjudication over rules and model proposals."""

from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from app.domain.ai_review import AiReviewPacket, AiReviewProposal
from app.domain.enums import SemanticRole
from app.domain.hybrid import HybridDecision, HybridReview
from app.domain.rules import RuleScope
from app.parsers.errors import DocxAnalysisError
from app.services.ai_review import validate_ai_proposal
from app.services.ai_runner import load_ai_review_plan
from app.services.evaluation import load_ai_review_run
from app.services.structure_classifier import ROLE_SCOPES
from app.services.template_inspector import _write_text


def _private_root() -> Path:
    return Path(__file__).resolve().parents[3] / ".paperalign"


def _require_private(path: Path, message: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(_private_root().resolve()):
        raise DocxAnalysisError("private_hybrid_required", message)
    return resolved


def _unique_scope(role: SemanticRole | None, scope: RuleScope | None) -> RuleScope | None:
    if scope is not None or role is None:
        return scope
    scopes = ROLE_SCOPES.get(role, set())
    return next(iter(scopes)) if len(scopes) == 1 else None


def adjudicate_packet(
    packet: AiReviewPacket,
    proposal: AiReviewProposal | None,
    *,
    confidence_threshold: float,
) -> HybridDecision:
    reasons: list[str] = []
    rules_role = packet.rules_only_role
    rules_scope = _unique_scope(rules_role, packet.rules_only_scope)
    if packet.rules_only_scope is None and rules_scope is not None:
        reasons.append("rules_scope_derived_from_unique_role_scope")
    if proposal is None:
        reasons.append("model_proposal_missing")
        return HybridDecision(
            block_id=packet.target_block_id,
            text_sha256=packet.target_text_sha256,
            outcome="manual_review",
            rules_role=rules_role,
            rules_scope=rules_scope,
            reasons=reasons,
        )
    validate_ai_proposal(packet, proposal)
    model_role = proposal.selected_role
    model_scope = _unique_scope(model_role, proposal.selected_scope)
    if proposal.selected_scope is None and model_scope is not None:
        reasons.append("model_scope_derived_from_unique_role_scope")
    if proposal.abstained:
        reasons.append("model_abstained")
    if proposal.confidence < confidence_threshold:
        reasons.append("model_confidence_below_threshold")
    if rules_role in {None, SemanticRole.UNKNOWN}:
        reasons.append("rules_role_unresolved")
    if model_role in {None, SemanticRole.UNKNOWN}:
        reasons.append("model_role_unresolved")
    if rules_role != model_role:
        reasons.append("role_disagreement")
    if rules_scope is None or model_scope is None:
        reasons.append("scope_unresolved")
    elif rules_scope != model_scope:
        reasons.append("scope_disagreement")
    blockers = {
        "model_abstained",
        "model_confidence_below_threshold",
        "rules_role_unresolved",
        "model_role_unresolved",
        "role_disagreement",
        "scope_unresolved",
        "scope_disagreement",
    }
    if blockers.intersection(reasons):
        outcome: Literal["auto_accept", "manual_review"] = "manual_review"
        selected_role = None
        selected_scope = None
    else:
        outcome = "auto_accept"
        selected_role = model_role
        selected_scope = model_scope
        reasons.append("rules_and_model_agree")
    return HybridDecision(
        block_id=packet.target_block_id,
        text_sha256=packet.target_text_sha256,
        outcome=outcome,
        selected_role=selected_role,
        selected_scope=selected_scope,
        rules_role=rules_role,
        rules_scope=rules_scope,
        model_role=model_role,
        model_scope=model_scope,
        model_confidence=proposal.confidence,
        reasons=reasons,
    )


def adjudicate_review(
    plan_path: Path,
    run_path: Path,
    *,
    confidence_threshold: float = 0.9,
) -> HybridReview:
    if not 0 <= confidence_threshold <= 1:
        raise DocxAnalysisError("invalid_hybrid_threshold", "Threshold must be between 0 and 1")
    plan = load_ai_review_plan(plan_path)
    run = load_ai_review_run(run_path)
    if (
        run.input_sha256 != plan.input_sha256
        or run.content_fingerprint != plan.content_fingerprint
        or run.mode != plan.mode
    ):
        raise DocxAnalysisError("stale_ai_run", "AI review run does not match the plan")
    proposals = {item.target_block_id: item for item in run.proposals}
    decisions = [
        adjudicate_packet(
            packet,
            proposals.get(packet.target_block_id),
            confidence_threshold=confidence_threshold,
        )
        for packet in plan.packets
    ]
    decisions.extend(
        HybridDecision(
            block_id=target.target_block_id,
            text_sha256=target.target_text_sha256,
            outcome="manual_review",
            reasons=[f"manual_only_{target.reason}"],
        )
        for target in plan.skipped_targets
    )
    decisions.sort(key=lambda item: item.block_id)
    auto_accept_count = sum(item.outcome == "auto_accept" for item in decisions)
    return HybridReview(
        input_sha256=plan.input_sha256,
        content_fingerprint=plan.content_fingerprint,
        plan_mode=plan.mode,
        model_provider=run.provider,
        model=run.model,
        confidence_threshold=confidence_threshold,
        target_count=len(decisions),
        auto_accept_count=auto_accept_count,
        manual_review_count=len(decisions) - auto_accept_count,
        decisions=decisions,
    )


def write_hybrid_review(
    plan_path: Path,
    run_path: Path,
    output_dir: Path,
    *,
    confidence_threshold: float = 0.9,
) -> HybridReview:
    output_dir = _require_private(output_dir, "Hybrid review results must stay under .paperalign")
    review = adjudicate_review(
        plan_path,
        run_path,
        confidence_threshold=confidence_threshold,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_text(output_dir / "hybrid_review.json", review.model_dump_json(indent=2) + "\n")
    _write_text(
        output_dir / "hybrid_summary.md",
        "# PaperAlign Hybrid 裁决摘要\n\n"
        f"策略状态：`{review.policy_status}`；阈值：{review.confidence_threshold:.2f}。\n\n"
        f"- 总目标：{review.target_count}\n"
        f"- 语义自动接受：{review.auto_accept_count}\n"
        f"- 人工复核：{review.manual_review_count}\n\n"
        "本结果只裁决语义结构，不能触发排版。阈值需在人工 Gold Set 上验证。\n",
    )
    return review


def load_hybrid_review(path: Path) -> HybridReview:
    path = _require_private(path, "Hybrid review results must stay under .paperalign")
    try:
        if path.stat().st_size > 10_000_000:
            raise DocxAnalysisError("invalid_hybrid_review", "Hybrid review exceeds 10 MB")
        return HybridReview.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise DocxAnalysisError("invalid_hybrid_review", "Could not load Hybrid review") from exc
