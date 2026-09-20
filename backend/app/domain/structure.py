from typing import Literal

from pydantic import Field

from app.domain.blocks import SourceAnchor
from app.domain.enums import BlockKind, DecisionSource, SemanticRole
from app.domain.rule_validation import RuleValidationResult
from app.domain.rules import ContractModel, RuleScope


class StructureDecision(ContractModel):
    block_id: str
    order: int = Field(ge=0)
    kind: BlockKind
    locator: SourceAnchor
    role: SemanticRole
    scope: RuleScope | None = None
    confidence: float = Field(ge=0, le=1)
    decision_source: DecisionSource
    requires_confirmation: bool
    reasons: list[str] = Field(min_length=1)
    heading_level: int | None = Field(default=None, ge=1, le=4)
    parent_id: str | None = None
    container_id: str | None = None
    region: str = "unknown"
    section_id: str | None = None
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    character_count: int = Field(ge=0)
    preview: str | None = Field(default=None, max_length=20)


class StructureWarning(ContractModel):
    code: str
    block_id: str | None = None
    message: str


class RoleOverride(ContractModel):
    block_id: str = Field(min_length=1)
    role: SemanticRole
    scope: RuleScope | None = None
    reason: str = Field(min_length=1, max_length=300)


class StructureOverrides(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewer: str = Field(min_length=1, max_length=100)
    decisions: list[RoleOverride] = Field(default_factory=list)


class StructureReport(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    classifier_version: str
    profile_id: str
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    mode: Literal["rules_only"] = "rules_only"
    ai_used: Literal[False] = False
    full_document_evaluated: Literal[False] = False
    formatting_allowed: Literal[False] = False
    previews_included: bool = False
    override_reviewer: str | None = None
    applied_overrides: StructureOverrides | None = None
    decisions: list[StructureDecision]
    warnings: list[StructureWarning]
    role_counts: dict[str, int]
    review_count: int = Field(ge=0)
    review_root_ids: list[str]
    unsupported_object_counts: dict[str, int]
    validation_counts: dict[str, int]
    rule_checks: list[RuleValidationResult]
    unapplied_rule_ids: list[str]
