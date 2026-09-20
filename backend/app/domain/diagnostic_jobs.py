from typing import Literal

from pydantic import Field

from app.domain.blocks import SourceAnchor
from app.domain.jobs import AnalysisJob
from app.domain.rules import ContractModel, RuleScope, RuleValue


class DiagnosticReviewItem(ContractModel):
    block_id: str
    role: str
    scope: RuleScope | None = None
    confidence: float = Field(ge=0, le=1)
    preview: str | None = Field(default=None, max_length=20)
    reasons: list[str]
    locator: SourceAnchor


class DiagnosticIssueItem(ContractModel):
    rule_id: str
    property_path: str
    status: Literal["fail", "evidence_insufficient"]
    expected: RuleValue
    actual: RuleValue | None = None
    reason: str
    locator: SourceAnchor


class DiagnosticSummary(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    total_blocks: int = Field(ge=0)
    review_count: int = Field(ge=0)
    review_root_count: int = Field(ge=0)
    role_counts: dict[str, int]
    validation_counts: dict[str, int]
    unsupported_object_counts: dict[str, int]
    warnings: list[str]
    review_items: list[DiagnosticReviewItem]
    issues: list[DiagnosticIssueItem]
    issue_count: int = Field(ge=0)
    issues_truncated: bool
    evidence_insufficient_count: int = Field(ge=0)
    formatting_allowed: Literal[False] = False
    conclusion: Literal["diagnosis_only_not_compliance_proof"] = (
        "diagnosis_only_not_compliance_proof"
    )


class DiagnosticJobView(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    job: AnalysisJob
    summary: DiagnosticSummary | None = None
