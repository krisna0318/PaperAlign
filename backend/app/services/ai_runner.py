"""Execute an inspected AI review plan with retries and rules-only fallback records."""

import time
from pathlib import Path
from typing import Literal, Protocol

from pydantic import ValidationError

from app.ai.openai_responses import AiProviderError
from app.domain.ai_review import (
    AiCallFailure,
    AiReviewPacket,
    AiReviewPlan,
    AiReviewProposal,
    AiReviewRun,
)
from app.parsers.errors import DocxAnalysisError
from app.services.template_inspector import _write_text


class ReviewProvider(Protocol):
    provider_name: Literal["openai_responses", "deepseek_responses"]
    model: str

    def review(self, packet: AiReviewPacket) -> AiReviewProposal: ...


def load_ai_review_plan(path: Path) -> AiReviewPlan:
    local_root = Path(__file__).resolve().parents[3] / ".paperalign"
    if not path.resolve().is_relative_to(local_root.resolve()):
        raise DocxAnalysisError(
            "private_input_required", "AI review plan must stay under .paperalign"
        )
    try:
        if path.stat().st_size > 10_000_000:
            raise DocxAnalysisError("invalid_ai_plan", "AI review plan exceeds 10 MB")
        return AiReviewPlan.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise DocxAnalysisError("invalid_ai_plan", "Could not load AI review plan") from exc


def run_ai_review(
    plan: AiReviewPlan,
    provider: ReviewProvider,
    *,
    max_retries: int = 1,
) -> AiReviewRun:
    proposals: list[AiReviewProposal] = []
    failures: list[AiCallFailure] = []
    started = time.perf_counter()
    for packet in plan.packets:
        attempts = 0
        while True:
            attempts += 1
            try:
                proposals.append(provider.review(packet))
                break
            except AiProviderError as exc:
                if exc.retryable and attempts <= max_retries:
                    continue
                failures.append(
                    AiCallFailure(
                        packet_id=packet.packet_id,
                        target_block_id=packet.target_block_id,
                        code=exc.code,
                        message=exc.message,
                        retryable=exc.retryable,
                        attempts=attempts,
                    )
                )
                break
            except DocxAnalysisError as exc:
                failures.append(
                    AiCallFailure(
                        packet_id=packet.packet_id,
                        target_block_id=packet.target_block_id,
                        code=exc.code,
                        message=exc.message,
                        retryable=False,
                        attempts=attempts,
                    )
                )
                break
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    if proposals and not failures:
        status: Literal["completed", "partial", "failed"] = "completed"
    elif proposals:
        status = "partial"
    else:
        status = "failed"
    input_tokens = sum(item.usage.input_tokens or 0 for item in proposals)
    output_tokens = sum(item.usage.output_tokens or 0 for item in proposals)
    total_tokens = sum(
        item.usage.total_tokens
        if item.usage.total_tokens is not None
        else (item.usage.input_tokens or 0) + (item.usage.output_tokens or 0)
        for item in proposals
    )
    costs = [item.usage.estimated_cost for item in proposals]
    estimated_cost = (
        sum(cost for cost in costs if cost is not None)
        if costs and all(cost is not None for cost in costs)
        else None
    )
    return AiReviewRun(
        input_sha256=plan.input_sha256,
        content_fingerprint=plan.content_fingerprint,
        mode=plan.mode,
        provider=provider.provider_name,
        model=provider.model,
        status=status,
        requested_count=len(plan.packets),
        completed_count=len(proposals),
        failed_count=len(failures),
        total_input_tokens=input_tokens,
        total_output_tokens=output_tokens,
        total_tokens=total_tokens,
        elapsed_ms=elapsed_ms,
        estimated_cost=estimated_cost,
        cost_currency="USD" if estimated_cost is not None else None,
        proposals=proposals,
        failures=failures,
    )


def write_ai_review_run(
    plan_path: Path,
    output_dir: Path,
    provider: ReviewProvider,
    *,
    confirmed_cloud_send: bool,
    max_retries: int = 1,
) -> AiReviewRun:
    if not confirmed_cloud_send:
        raise DocxAnalysisError(
            "cloud_send_not_confirmed",
            "Cloud sending requires the explicit --confirm-send-cloud flag",
        )
    local_root = Path(__file__).resolve().parents[3] / ".paperalign"
    output_dir = output_dir.resolve()
    if not output_dir.is_relative_to(local_root.resolve()):
        raise DocxAnalysisError("private_output_required", "AI results must stay under .paperalign")
    output_path = output_dir / "ai_review_run.json"
    if plan_path.resolve() == output_path:
        raise DocxAnalysisError("output_input_collision", "AI result cannot replace its plan")
    plan = load_ai_review_plan(plan_path)
    result = run_ai_review(plan, provider, max_retries=max_retries)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_text(output_path, result.model_dump_json(indent=2) + "\n")
    return result
