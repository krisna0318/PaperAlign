from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.domain.ai_review import AiReviewProposal, AiReviewRun, AiUsage
from app.domain.enums import SemanticRole
from app.domain.evaluation import EvaluationReport, GoldSet
from app.domain.rules import RuleScope
from app.parsers.errors import DocxAnalysisError
from app.services.ai_review import prepare_ai_review, write_ai_review_plan
from app.services.evaluation import (
    evaluate_review,
    prepare_gold_set,
    write_gold_set_template,
)
from tests.support.structure_factory import paragraph, structured_docx


def _numbered_source(tmp_path: Path) -> Path:
    return structured_docx(
        tmp_path / "evaluation.docx",
        [
            paragraph(
                "1 合成列表项",
                properties='<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>',
            )
        ],
    )


def _confirmed_gold_and_run(tmp_path: Path):
    plan = prepare_ai_review(_numbered_source(tmp_path))
    packet = plan.packets[0]
    template = prepare_gold_set(plan)
    annotation = template.annotations[0].model_copy(
        update={
            "status": "confirmed",
            "expected_role": SemanticRole.LIST_ITEM,
            "expected_scope": RuleScope.BODY,
            "reviewer": "synthetic-reviewer",
            "rationale": "Word 编号属性存在，合成内容不是章节标题。",
        }
    )
    gold_set = template.model_copy(update={"annotations": [annotation]})
    proposal = AiReviewProposal(
        packet_id=packet.packet_id,
        target_block_id=packet.target_block_id,
        target_text_sha256=packet.target_text_sha256,
        selected_role=SemanticRole.LIST_ITEM,
        selected_scope=RuleScope.BODY,
        confidence=0.82,
        abstained=False,
        reason="编号元数据和内容支持列表项。",
        evidence_block_ids=[packet.target_block_id],
        usage=AiUsage(
            provider="deepseek_responses",
            model="synthetic-model",
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
            elapsed_ms=30,
        ),
    )
    run = AiReviewRun(
        input_sha256=plan.input_sha256,
        content_fingerprint=plan.content_fingerprint,
        mode=plan.mode,
        provider="deepseek_responses",
        model="synthetic-model",
        status="completed",
        requested_count=1,
        completed_count=1,
        failed_count=0,
        total_input_tokens=100,
        total_output_tokens=20,
        total_tokens=120,
        elapsed_ms=30,
        proposals=[proposal],
        failures=[],
    )
    return plan, gold_set, run


def test_gold_set_template_has_hashes_but_no_manuscript_text(tmp_path: Path) -> None:
    source = _numbered_source(tmp_path)
    repo = Path(__file__).resolve().parents[2]
    plan_dir = repo / ".paperalign/test-runs/evaluation-plan"
    gold_dir = repo / ".paperalign/test-runs/evaluation-gold"
    plan = write_ai_review_plan(source, plan_dir)
    gold_set = write_gold_set_template(plan_dir / "ai_review_plan.json", gold_dir)
    payload = (gold_dir / "gold_set.template.json").read_text(encoding="utf-8")
    assert gold_set.target_count == plan.candidate_count == 1
    assert "合成列表项" not in payload
    assert gold_set.annotations[0].status == "unassessed"
    Draft202012Validator(GoldSet.model_json_schema()).validate(gold_set.model_dump(mode="json"))


def test_evaluation_counts_only_confirmed_human_labels(tmp_path: Path) -> None:
    plan, gold_set, run = _confirmed_gold_and_run(tmp_path)
    report = evaluate_review(plan, gold_set, run, gold_set_sha256="a" * 64)
    rules, model = report.systems
    assert report.status == "complete_gold_set"
    assert report.evaluated_count == 1 and report.unassessed_count == 0
    assert rules.system == "rules_only" and rules.role_accuracy == 0
    assert model.system == "model_proposal" and model.role_accuracy == 1
    assert model.scope_accuracy == 1 and model.total_tokens == 120
    Draft202012Validator(EvaluationReport.model_json_schema()).validate(
        report.model_dump(mode="json")
    )


def test_no_labels_produces_no_accuracy_claim(tmp_path: Path) -> None:
    plan, _, run = _confirmed_gold_and_run(tmp_path)
    report = evaluate_review(
        plan,
        prepare_gold_set(plan),
        run,
        gold_set_sha256="b" * 64,
    )
    assert report.status == "no_confirmed_labels"
    assert report.evaluated_count == 0 and report.unassessed_count == 1
    assert all(item.role_accuracy is None for item in report.systems)


def test_stale_or_incompatible_gold_set_is_rejected(tmp_path: Path) -> None:
    plan, gold_set, run = _confirmed_gold_and_run(tmp_path)
    stale = gold_set.model_copy(update={"input_sha256": "0" * 64})
    with pytest.raises(DocxAnalysisError, match="match"):
        evaluate_review(plan, stale, run, gold_set_sha256="c" * 64)
    bad_annotation = gold_set.annotations[0].model_copy(
        update={
            "expected_role": SemanticRole.TABLE_CAPTION,
            "expected_scope": RuleScope.BODY,
        }
    )
    incompatible = gold_set.model_copy(update={"annotations": [bad_annotation]})
    with pytest.raises(DocxAnalysisError, match="incompatible"):
        evaluate_review(plan, incompatible, run, gold_set_sha256="d" * 64)
