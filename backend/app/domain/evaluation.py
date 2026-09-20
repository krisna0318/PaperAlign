from typing import Literal

from pydantic import Field, model_validator

from app.domain.enums import SemanticRole
from app.domain.rules import ContractModel, RuleScope


class GoldAnnotation(ContractModel):
    block_id: str = Field(min_length=1)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source: Literal["cloud_packet", "manual_only"]
    source_reason: str | None = None
    status: Literal["unassessed", "confirmed"] = "unassessed"
    expected_role: SemanticRole | None = None
    expected_scope: RuleScope | None = None
    reviewer: str | None = Field(default=None, min_length=1, max_length=100)
    rationale: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_confirmation(self) -> "GoldAnnotation":
        if self.status == "confirmed":
            if self.expected_role is None or self.reviewer is None or self.rationale is None:
                raise ValueError(
                    "Confirmed annotations require expected_role, reviewer, and rationale"
                )
        elif any(
            value is not None
            for value in (self.expected_role, self.expected_scope, self.reviewer, self.rationale)
        ):
            raise ValueError("Unassessed annotations cannot contain a partial answer")
        return self


class GoldSet(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_plan_mode: Literal["prompt_only", "hybrid"]
    target_count: int = Field(ge=0)
    annotations: list[GoldAnnotation]

    @model_validator(mode="after")
    def validate_targets(self) -> "GoldSet":
        if self.target_count != len(self.annotations):
            raise ValueError("Gold Set target count does not match annotations")
        block_ids = [item.block_id for item in self.annotations]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("Gold Set contains duplicate block IDs")
        return self


class SystemEvaluation(ContractModel):
    system: Literal["rules_only", "model_proposal"]
    evaluated_count: int = Field(ge=0)
    prediction_count: int = Field(ge=0)
    correct_role_count: int = Field(ge=0)
    scope_evaluated_count: int = Field(ge=0)
    correct_scope_count: int = Field(ge=0)
    abstained_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    disagreement_count: int = Field(ge=0)
    coverage: float | None = Field(default=None, ge=0, le=1)
    role_accuracy: float | None = Field(default=None, ge=0, le=1)
    role_precision: float | None = Field(default=None, ge=0, le=1)
    role_recall: float | None = Field(default=None, ge=0, le=1)
    role_f1: float | None = Field(default=None, ge=0, le=1)
    scope_accuracy: float | None = Field(default=None, ge=0, le=1)
    total_tokens: int = Field(default=0, ge=0)
    elapsed_ms: int = Field(default=0, ge=0)


class EvaluationReport(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    gold_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan_mode: Literal["prompt_only", "hybrid"]
    model_provider: Literal["openai_responses", "deepseek_responses"]
    model: str = Field(min_length=1)
    status: Literal["no_confirmed_labels", "partial_gold_set", "complete_gold_set"]
    target_count: int = Field(ge=0)
    evaluated_count: int = Field(ge=0)
    unassessed_count: int = Field(ge=0)
    formatting_allowed: Literal[False] = False
    systems: list[SystemEvaluation] = Field(min_length=2, max_length=2)
