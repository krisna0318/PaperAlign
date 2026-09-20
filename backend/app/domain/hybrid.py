from typing import Literal

from pydantic import Field, model_validator

from app.domain.enums import SemanticRole
from app.domain.rules import ContractModel, RuleScope


class HybridDecision(ContractModel):
    block_id: str = Field(min_length=1)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome: Literal["auto_accept", "manual_review"]
    selected_role: SemanticRole | None = None
    selected_scope: RuleScope | None = None
    rules_role: SemanticRole | None = None
    rules_scope: RuleScope | None = None
    model_role: SemanticRole | None = None
    model_scope: RuleScope | None = None
    model_confidence: float | None = Field(default=None, ge=0, le=1)
    reasons: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_outcome(self) -> "HybridDecision":
        if self.outcome == "auto_accept":
            if self.selected_role in {None, SemanticRole.UNKNOWN} or self.selected_scope is None:
                raise ValueError("Accepted Hybrid decisions require a resolved role and scope")
        elif self.selected_role is not None or self.selected_scope is not None:
            raise ValueError("Manual Hybrid decisions cannot expose an accepted role or scope")
        return self


class HybridReview(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    policy_version: Literal["1.0"] = "1.0"
    policy_status: Literal["provisional_not_accuracy_validated"] = (
        "provisional_not_accuracy_validated"
    )
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan_mode: Literal["prompt_only", "hybrid"]
    model_provider: Literal["openai_responses", "deepseek_responses"]
    model: str = Field(min_length=1)
    confidence_threshold: float = Field(ge=0, le=1)
    formatting_allowed: Literal[False] = False
    target_count: int = Field(ge=0)
    auto_accept_count: int = Field(ge=0)
    manual_review_count: int = Field(ge=0)
    decisions: list[HybridDecision]

    @model_validator(mode="after")
    def validate_counts(self) -> "HybridReview":
        if self.target_count != len(self.decisions):
            raise ValueError("Hybrid target count does not match decisions")
        accepted = sum(item.outcome == "auto_accept" for item in self.decisions)
        if self.auto_accept_count != accepted:
            raise ValueError("Hybrid auto-accept count is stale")
        if self.manual_review_count != self.target_count - accepted:
            raise ValueError("Hybrid manual-review count is stale")
        block_ids = [item.block_id for item in self.decisions]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("Hybrid review contains duplicate block IDs")
        return self
