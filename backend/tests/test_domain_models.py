from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.blocks import DocumentBlock, SourceAnchor
from app.domain.enums import BlockKind, DecisionSource, SemanticRole
from app.domain.jobs import AnalysisJob


def test_document_block_serializes_stable_contract() -> None:
    block = DocumentBlock(
        id="p-0001",
        order=1,
        kind=BlockKind.PARAGRAPH,
        text="1 绪论",
        role=SemanticRole.HEADING_1,
        confidence=0.95,
        decision_source=DecisionSource.RULE,
        source_anchor=SourceAnchor(paragraph_index=1),
    )

    payload = block.model_dump(mode="json")
    assert payload["kind"] == "paragraph"
    assert payload["role"] == "heading_1"
    assert payload["protected"] is True


def test_document_block_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        DocumentBlock(
            id="p-0001",
            order=1,
            kind=BlockKind.PARAGRAPH,
            confidence=1.1,
            source_anchor=SourceAnchor(paragraph_index=1),
        )


def test_analysis_job_defaults_to_rules_only_mode() -> None:
    now = datetime.now(UTC)
    job = AnalysisJob(
        id="job-0001",
        profile_id="scau-undergraduate-2026-v1",
        created_at=now,
        updated_at=now,
        input_filename="synthetic.docx",
    )

    assert job.ai_mode == "off"
    assert job.artifacts == []
