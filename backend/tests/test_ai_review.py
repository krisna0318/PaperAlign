from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.domain.ai_review import AiReviewPlan, AiReviewProposal, AiUsage
from app.domain.enums import SemanticRole
from app.parsers.errors import DocxAnalysisError
from app.services.ai_review import prepare_ai_review, validate_ai_proposal, write_ai_review_plan
from paperalign.cli import main
from tests.support.structure_factory import paragraph, structured_docx


def test_hybrid_plan_only_contains_review_roots_and_bounded_context(tmp_path: Path) -> None:
    source = structured_docx(
        tmp_path / "ambiguous.docx",
        [
            paragraph("1 正式标题", style="Heading1"),
            paragraph(
                "1 可能是列表",
                properties='<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>',
            ),
            paragraph("这是一段超过限制长度的合成上下文。" * 20),
        ],
    )
    plan = prepare_ai_review(source, mode="hybrid", context_radius=1, max_characters=40)
    assert plan.status == "prepared_not_sent"
    assert plan.ai_used is False and plan.formatting_allowed is False
    assert plan.packet_count == 1
    assert plan.packets[0].rules_only_reasons
    assert all(len(item.text) <= 40 for item in plan.packets[0].context)
    assert any(item.truncated for item in plan.packets[0].context)
    assert len(plan.packets[0].context) <= 3
    target = next(item for item in plan.packets[0].context if item.selection_reason == "target")
    assert target.has_numbering is True
    Draft202012Validator(AiReviewPlan.model_json_schema()).validate(plan.model_dump(mode="json"))


def test_prompt_only_plan_hides_rules_only_answer(tmp_path: Path) -> None:
    source = structured_docx(
        tmp_path / "baseline.docx",
        [paragraph("1 标题", style="Heading1"), paragraph("合成正文。")],
    )
    plan = prepare_ai_review(source, mode="prompt_only", context_radius=0)
    assert plan.packet_count == 2
    assert all(packet.rules_only_role is None for packet in plan.packets)
    assert all(not packet.rules_only_reasons for packet in plan.packets)
    assert all(item.current_role is None for packet in plan.packets for item in packet.context)


def test_context_has_hard_three_block_and_240_character_limits(tmp_path: Path) -> None:
    long_text = "开头证据" + "合成内容" * 100 + "结尾证据"
    source = structured_docx(
        tmp_path / "bounded.docx",
        [paragraph(long_text), paragraph("1 可能是列表"), paragraph(long_text)],
    )
    plan = prepare_ai_review(source, context_radius=2, max_characters=240)
    packet = next(item for item in plan.packets if item.target_block_id == "p-0001")
    assert len(packet.context) == 3
    assert all(len(item.text) <= 240 for item in packet.context)
    previous = next(item for item in packet.context if item.selection_reason == "previous")
    following = next(item for item in packet.context if item.selection_reason == "next")
    assert previous.text.startswith("…") and previous.text.endswith("结尾证据")
    assert following.text.startswith("开头证据") and following.text.endswith("…")


def test_empty_or_visual_target_is_not_sent_to_text_model(tmp_path: Path) -> None:
    source = structured_docx(
        tmp_path / "visual.docx",
        [
            paragraph("1 标题", style="Heading1"),
            paragraph("", runs="<w:r><w:drawing/></w:r>"),
        ],
    )
    plan = prepare_ai_review(source)
    assert plan.candidate_count == plan.packet_count + plan.skipped_count
    assert plan.packet_count == 0
    assert plan.skipped_targets[0].reason == "no_text_evidence"
    assert plan.skipped_targets[0].action == "manual_review"


def test_ai_proposal_is_hash_bound_and_schema_constrained(tmp_path: Path) -> None:
    source = structured_docx(tmp_path / "proposal.docx", [paragraph("1 可能是列表")])
    packet = prepare_ai_review(source).packets[0]
    proposal = AiReviewProposal(
        packet_id=packet.packet_id,
        target_block_id=packet.target_block_id,
        target_text_sha256=packet.target_text_sha256,
        selected_role=SemanticRole.HEADING_1,
        confidence=0.7,
        abstained=False,
        reason="编号形式类似一级标题，但仍需人工确认。",
        evidence_block_ids=[packet.target_block_id],
        usage=AiUsage(provider="synthetic", model="fake", elapsed_ms=3),
    )
    validate_ai_proposal(packet, proposal)
    Draft202012Validator(AiReviewProposal.model_json_schema()).validate(
        proposal.model_dump(mode="json")
    )
    with pytest.raises(DocxAnalysisError, match="hash"):
        validate_ai_proposal(packet, proposal.model_copy(update={"target_text_sha256": "a" * 64}))
    with pytest.raises(DocxAnalysisError, match="allowed_roles"):
        validate_ai_proposal(
            packet, proposal.model_copy(update={"selected_role": SemanticRole.TABLE})
        )


def test_numbered_paragraph_can_be_proposed_as_body_list_item(tmp_path: Path) -> None:
    source = structured_docx(
        tmp_path / "list-item.docx",
        [
            paragraph(
                "1 可能是列表",
                properties='<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>',
            )
        ],
    )
    packet = prepare_ai_review(source).packets[0]
    assert SemanticRole.LIST_ITEM in packet.allowed_roles
    proposal = AiReviewProposal(
        packet_id=packet.packet_id,
        target_block_id=packet.target_block_id,
        target_text_sha256=packet.target_text_sha256,
        selected_role=SemanticRole.LIST_ITEM,
        selected_scope="body",
        confidence=0.84,
        abstained=False,
        reason="段落带有列表编号元数据，且内容不是章节标题。",
        evidence_block_ids=[packet.target_block_id],
        usage=AiUsage(provider="synthetic", model="fake", elapsed_ms=3),
    )
    validate_ai_proposal(packet, proposal)


def test_ai_plan_must_remain_private_and_cli_does_not_call_model(tmp_path: Path, capsys) -> None:
    source = structured_docx(tmp_path / "cli.docx", [paragraph("1 可能是列表")])
    repo = Path(__file__).resolve().parents[2]
    forbidden = repo / ".ai-plan-must-be-private"
    with pytest.raises(DocxAnalysisError, match="paperalign"):
        write_ai_review_plan(source, forbidden)
    output = repo / ".paperalign/test-runs/ai-plan"
    assert main(["prepare-ai-review", str(source), "--out", str(output)]) == 0
    stdout = capsys.readouterr().out
    assert "No model was contacted" in stdout
    assert (output / "ai_review_plan.json").exists()
