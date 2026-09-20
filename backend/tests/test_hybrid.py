from pathlib import Path

from app.domain.ai_review import AiReviewProposal, AiUsage
from app.domain.enums import SemanticRole
from app.domain.rules import RuleScope
from app.services.ai_review import prepare_ai_review
from app.services.hybrid import adjudicate_packet
from tests.support.structure_factory import paragraph, structured_docx


def _packet_and_proposal(tmp_path: Path, *, confidence: float = 0.95):
    source = structured_docx(tmp_path / "hybrid.docx", [paragraph("1 合成歧义段落")])
    packet = (
        prepare_ai_review(source)
        .packets[0]
        .model_copy(
            update={
                "rules_only_role": SemanticRole.LIST_ITEM,
                "rules_only_scope": RuleScope.BODY,
            }
        )
    )
    proposal = AiReviewProposal(
        packet_id=packet.packet_id,
        target_block_id=packet.target_block_id,
        target_text_sha256=packet.target_text_sha256,
        selected_role=SemanticRole.LIST_ITEM,
        selected_scope=None,
        confidence=confidence,
        abstained=False,
        reason="合成模型建议。",
        evidence_block_ids=[packet.target_block_id],
        usage=AiUsage(provider="synthetic", model="synthetic", elapsed_ms=1),
    )
    return packet, proposal


def test_hybrid_accepts_only_high_confidence_agreement_and_derives_unique_scope(
    tmp_path: Path,
) -> None:
    packet, proposal = _packet_and_proposal(tmp_path)
    decision = adjudicate_packet(packet, proposal, confidence_threshold=0.9)
    assert decision.outcome == "auto_accept"
    assert decision.selected_role == SemanticRole.LIST_ITEM
    assert decision.selected_scope == RuleScope.BODY
    assert "model_scope_derived_from_unique_role_scope" in decision.reasons


def test_hybrid_routes_low_confidence_or_disagreement_to_manual_review(tmp_path: Path) -> None:
    packet, low_confidence = _packet_and_proposal(tmp_path, confidence=0.6)
    low = adjudicate_packet(packet, low_confidence, confidence_threshold=0.9)
    assert low.outcome == "manual_review"
    assert "model_confidence_below_threshold" in low.reasons
    disagreement = low_confidence.model_copy(
        update={
            "selected_role": SemanticRole.HEADING_4,
            "selected_scope": RuleScope.HEADING_4,
            "confidence": 0.99,
        }
    )
    conflict = adjudicate_packet(packet, disagreement, confidence_threshold=0.9)
    assert conflict.outcome == "manual_review"
    assert "role_disagreement" in conflict.reasons


def test_hybrid_routes_missing_proposal_to_manual_review(tmp_path: Path) -> None:
    packet, _ = _packet_and_proposal(tmp_path)
    decision = adjudicate_packet(packet, None, confidence_threshold=0.9)
    assert decision.outcome == "manual_review"
    assert decision.reasons == ["model_proposal_missing"]
