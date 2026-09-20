"""Prepare human Gold Sets and evaluate M4 predictions without document text."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from app.domain.ai_review import AiReviewPlan, AiReviewProposal, AiReviewRun
from app.domain.enums import SemanticRole
from app.domain.evaluation import (
    EvaluationReport,
    GoldAnnotation,
    GoldSet,
    SystemEvaluation,
)
from app.domain.hybrid import HybridReview
from app.domain.rules import RuleScope
from app.parsers.errors import DocxAnalysisError
from app.services.ai_review import validate_ai_proposal
from app.services.ai_runner import load_ai_review_plan
from app.services.structure_classifier import ROLE_SCOPES
from app.services.template_inspector import _write_text


@dataclass(frozen=True)
class Prediction:
    role: SemanticRole | None
    scope: RuleScope | None
    abstained: bool


def _private_root() -> Path:
    return Path(__file__).resolve().parents[3] / ".paperalign"


def _require_private(path: Path, message: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(_private_root().resolve()):
        raise DocxAnalysisError("private_evaluation_required", message)
    return resolved


def prepare_gold_set(plan: AiReviewPlan) -> GoldSet:
    annotations = [
        GoldAnnotation(
            block_id=packet.target_block_id,
            text_sha256=packet.target_text_sha256,
            source="cloud_packet",
        )
        for packet in plan.packets
    ]
    annotations.extend(
        GoldAnnotation(
            block_id=target.target_block_id,
            text_sha256=target.target_text_sha256,
            source="manual_only",
            source_reason=target.reason,
        )
        for target in plan.skipped_targets
    )
    annotations.sort(key=lambda item: item.block_id)
    return GoldSet(
        input_sha256=plan.input_sha256,
        content_fingerprint=plan.content_fingerprint,
        source_plan_mode=plan.mode,
        target_count=len(annotations),
        annotations=annotations,
    )


def write_gold_set_template(plan_path: Path, output_dir: Path) -> GoldSet:
    output_dir = _require_private(output_dir, "Gold Set templates must stay under .paperalign")
    plan = load_ai_review_plan(plan_path)
    gold_set = prepare_gold_set(plan)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_text(output_dir / "gold_set.template.json", gold_set.model_dump_json(indent=2) + "\n")
    _write_text(
        output_dir / "annotation_instructions.md",
        "# PaperAlign Gold Set 标注说明\n\n"
        "复制 `gold_set.template.json` 为 `gold_set.json`。只修改 annotations 中的字段：\n\n"
        "- 确认后把 `status` 改为 `confirmed`；\n"
        "- 填写 `expected_role`，能确认格式范围时填写 `expected_scope`；\n"
        "- 填写真实标注人 `reviewer` 和可复核依据 `rationale`；\n"
        "- 暂时无法判断的项目保持 `unassessed`，其余答案字段保持 null；\n"
        "- 不修改 block_id、text_sha256、source 或顶层哈希。\n\n"
        "模型建议不能作为 Gold Set 依据。请结合原 DOCX、学校规范和 Word 结构人工判断。\n",
    )
    return gold_set


def load_gold_set(path: Path) -> GoldSet:
    path = _require_private(path, "Gold Sets must stay under .paperalign")
    try:
        if path.stat().st_size > 5_000_000:
            raise DocxAnalysisError("invalid_gold_set", "Gold Set exceeds 5 MB")
        return GoldSet.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise DocxAnalysisError("invalid_gold_set", "Could not load Gold Set") from exc


def load_ai_review_run(path: Path) -> AiReviewRun:
    path = _require_private(path, "AI review runs must stay under .paperalign")
    try:
        if path.stat().st_size > 10_000_000:
            raise DocxAnalysisError("invalid_ai_run", "AI review run exceeds 10 MB")
        return AiReviewRun.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise DocxAnalysisError("invalid_ai_run", "Could not load AI review run") from exc


def load_hybrid_review(path: Path) -> HybridReview:
    path = _require_private(path, "Hybrid review results must stay under .paperalign")
    try:
        if path.stat().st_size > 10_000_000:
            raise DocxAnalysisError("invalid_hybrid_review", "Hybrid review exceeds 10 MB")
        return HybridReview.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise DocxAnalysisError("invalid_hybrid_review", "Could not load Hybrid review") from exc


def _validate_inputs(plan: AiReviewPlan, gold_set: GoldSet, run: AiReviewRun) -> None:
    identity = (plan.input_sha256, plan.content_fingerprint)
    if (gold_set.input_sha256, gold_set.content_fingerprint) != identity:
        raise DocxAnalysisError("stale_gold_set", "Gold Set does not match the review plan")
    if (run.input_sha256, run.content_fingerprint) != identity or run.mode != plan.mode:
        raise DocxAnalysisError("stale_ai_run", "AI review run does not match the plan")
    if gold_set.source_plan_mode != plan.mode:
        raise DocxAnalysisError("stale_gold_set", "Gold Set plan mode does not match")
    expected_hashes = {packet.target_block_id: packet.target_text_sha256 for packet in plan.packets}
    expected_hashes.update(
        {target.target_block_id: target.target_text_sha256 for target in plan.skipped_targets}
    )
    supplied_hashes = {item.block_id: item.text_sha256 for item in gold_set.annotations}
    if supplied_hashes != expected_hashes:
        raise DocxAnalysisError("stale_gold_set", "Gold Set targets or text hashes changed")
    packet_by_id = {packet.packet_id: packet for packet in plan.packets}
    for proposal in run.proposals:
        packet = packet_by_id.get(proposal.packet_id)
        if packet is None:
            raise DocxAnalysisError("stale_ai_run", "AI run contains an unknown packet")
        validate_ai_proposal(packet, proposal)
    for annotation in gold_set.annotations:
        if annotation.status != "confirmed" or annotation.expected_scope is None:
            continue
        expected_role = annotation.expected_role
        if expected_role is None:
            raise DocxAnalysisError("invalid_gold_set", "Confirmed Gold Set role is missing")
        if annotation.expected_scope not in ROLE_SCOPES.get(expected_role, set()):
            raise DocxAnalysisError("invalid_gold_set", "Gold Set role and scope are incompatible")


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _evaluate_system(
    system: Literal["rules_only", "model_proposal", "hybrid"],
    annotations: list[GoldAnnotation],
    predictions: dict[str, Prediction],
    *,
    total_tokens: int = 0,
    elapsed_ms: int = 0,
) -> SystemEvaluation:
    prediction_count = correct_role = scope_evaluated = correct_scope = 0
    abstained = unknown = disagreements = 0
    for gold in annotations:
        prediction = predictions.get(gold.block_id)
        if prediction is None or prediction.abstained or prediction.role is None:
            abstained += 1
            disagreements += 1
            continue
        prediction_count += 1
        unknown += prediction.role == SemanticRole.UNKNOWN
        role_matches = prediction.role == gold.expected_role
        correct_role += role_matches
        scope_matches = True
        if gold.expected_scope is not None:
            scope_evaluated += 1
            scope_matches = prediction.scope == gold.expected_scope
            correct_scope += scope_matches
        if not role_matches or not scope_matches:
            disagreements += 1
    evaluated = len(annotations)
    precision = _safe_ratio(correct_role, prediction_count)
    recall = _safe_ratio(correct_role, evaluated)
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall > 0
        else None
    )
    return SystemEvaluation(
        system=system,
        evaluated_count=evaluated,
        prediction_count=prediction_count,
        correct_role_count=correct_role,
        scope_evaluated_count=scope_evaluated,
        correct_scope_count=correct_scope,
        abstained_count=abstained,
        unknown_count=unknown,
        disagreement_count=disagreements,
        coverage=_safe_ratio(prediction_count, evaluated),
        role_accuracy=_safe_ratio(correct_role, evaluated),
        role_precision=precision,
        role_recall=recall,
        role_f1=f1,
        scope_accuracy=_safe_ratio(correct_scope, scope_evaluated),
        total_tokens=total_tokens,
        elapsed_ms=elapsed_ms,
    )


def evaluate_review(
    plan: AiReviewPlan,
    gold_set: GoldSet,
    run: AiReviewRun,
    *,
    gold_set_sha256: str,
    hybrid_review: HybridReview | None = None,
) -> EvaluationReport:
    _validate_inputs(plan, gold_set, run)
    confirmed = [item for item in gold_set.annotations if item.status == "confirmed"]
    packets_by_block = {packet.target_block_id: packet for packet in plan.packets}
    rules_predictions = {
        block_id: Prediction(
            role=packet.rules_only_role,
            scope=packet.rules_only_scope,
            abstained=packet.rules_only_role is None,
        )
        for block_id, packet in packets_by_block.items()
    }
    proposals_by_block: dict[str, AiReviewProposal] = {
        proposal.target_block_id: proposal for proposal in run.proposals
    }
    model_predictions = {
        block_id: Prediction(
            role=proposal.selected_role,
            scope=proposal.selected_scope,
            abstained=proposal.abstained,
        )
        for block_id, proposal in proposals_by_block.items()
    }
    systems = [
        _evaluate_system("rules_only", confirmed, rules_predictions),
        _evaluate_system(
            "model_proposal",
            confirmed,
            model_predictions,
            total_tokens=run.total_tokens,
            elapsed_ms=run.elapsed_ms,
        ),
    ]
    if hybrid_review is not None:
        if (
            hybrid_review.input_sha256 != plan.input_sha256
            or hybrid_review.content_fingerprint != plan.content_fingerprint
            or hybrid_review.plan_mode != plan.mode
            or hybrid_review.model_provider != run.provider
            or hybrid_review.model != run.model
        ):
            raise DocxAnalysisError(
                "stale_hybrid_review", "Hybrid review does not match plan and model run"
            )
        expected_hashes = {item.block_id: item.text_sha256 for item in gold_set.annotations}
        hybrid_hashes = {item.block_id: item.text_sha256 for item in hybrid_review.decisions}
        if hybrid_hashes != expected_hashes:
            raise DocxAnalysisError(
                "stale_hybrid_review", "Hybrid review targets or hashes changed"
            )
        hybrid_predictions = {
            item.block_id: Prediction(
                role=item.selected_role,
                scope=item.selected_scope,
                abstained=item.outcome != "auto_accept",
            )
            for item in hybrid_review.decisions
        }
        systems.append(
            _evaluate_system(
                "hybrid",
                confirmed,
                hybrid_predictions,
                total_tokens=run.total_tokens,
                elapsed_ms=run.elapsed_ms,
            )
        )
    status: Literal["no_confirmed_labels", "partial_gold_set", "complete_gold_set"] = (
        "no_confirmed_labels"
        if not confirmed
        else "complete_gold_set"
        if len(confirmed) == gold_set.target_count
        else "partial_gold_set"
    )
    return EvaluationReport(
        input_sha256=plan.input_sha256,
        content_fingerprint=plan.content_fingerprint,
        gold_set_sha256=gold_set_sha256,
        plan_mode=plan.mode,
        model_provider=run.provider,
        model=run.model,
        status=status,
        target_count=gold_set.target_count,
        evaluated_count=len(confirmed),
        unassessed_count=gold_set.target_count - len(confirmed),
        systems=systems,
    )


def _percent(value: float | None) -> str:
    return "未评估" if value is None else f"{value:.1%}"


def render_evaluation_summary(report: EvaluationReport) -> str:
    rows = []
    for item in report.systems:
        rows.append(
            f"| {item.system} | {item.prediction_count}/{item.evaluated_count} | "
            f"{_percent(item.role_accuracy)} | {_percent(item.scope_accuracy)} | "
            f"{item.disagreement_count} | {item.total_tokens} | {item.elapsed_ms} |"
        )
    return (
        "# PaperAlign M4.2 评测摘要\n\n"
        f"状态：`{report.status}`。人工已确认 {report.evaluated_count}/{report.target_count}，"
        f"未评估 {report.unassessed_count}。\n\n"
        "| 系统 | 覆盖数量 | 角色准确率 | 范围准确率 | 需复核 | Token | 耗时 ms |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |\n"
        + "\n".join(rows)
        + "\n\n未人工确认的对象不进入准确率。模型置信度不等于正确概率，评测结果不能直接触发排版。\n"
    )


def write_evaluation_report(
    plan_path: Path,
    gold_set_path: Path,
    run_path: Path,
    output_dir: Path,
    hybrid_path: Path | None = None,
) -> EvaluationReport:
    output_dir = _require_private(output_dir, "Evaluation results must stay under .paperalign")
    plan = load_ai_review_plan(plan_path)
    gold_set = load_gold_set(gold_set_path)
    run = load_ai_review_run(run_path)
    hybrid_review = load_hybrid_review(hybrid_path) if hybrid_path is not None else None
    gold_sha = hashlib.sha256(gold_set_path.read_bytes()).hexdigest()
    report = evaluate_review(
        plan,
        gold_set,
        run,
        gold_set_sha256=gold_sha,
        hybrid_review=hybrid_review,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_text(output_dir / "evaluation_report.json", report.model_dump_json(indent=2) + "\n")
    _write_text(output_dir / "evaluation_summary.md", render_evaluation_summary(report))
    return report
