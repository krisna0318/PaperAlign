from typing import Literal

from pydantic import Field, model_validator

from app.domain.blocks import StyleSnapshot
from app.domain.enums import BlockKind, SemanticRole
from app.domain.rules import ContractModel, RuleScope


class AiContextExcerpt(ContractModel):
    block_id: str = Field(min_length=1)
    relative_position: int
    kind: BlockKind
    current_role: SemanticRole | None = None
    style: StyleSnapshot
    has_numbering: bool
    numbering_level: str | None = None
    has_drawing: bool
    text: str = Field(max_length=240)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    truncated: bool
    selection_reason: Literal["target", "parent_heading", "previous", "next"]


class AiReviewPacket(ContractModel):
    packet_id: str = Field(min_length=1)
    target_block_id: str = Field(min_length=1)
    target_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    allowed_roles: list[SemanticRole] = Field(min_length=1)
    allowed_scopes: list[RuleScope] = Field(default_factory=list)
    rules_only_role: SemanticRole | None = None
    rules_only_scope: RuleScope | None = None
    rules_only_reasons: list[str] = Field(default_factory=list)
    system_instruction: str = Field(min_length=1)
    task_instruction: str = Field(min_length=1)
    context: list[AiContextExcerpt] = Field(min_length=1)


class AiSkippedTarget(ContractModel):
    target_block_id: str = Field(min_length=1)
    target_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: Literal["no_text_evidence", "unsupported_object", "unsupported_kind"]
    action: Literal["manual_review"] = "manual_review"


class AiReviewPlan(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    mode: Literal["prompt_only", "hybrid"]
    status: Literal["prepared_not_sent"] = "prepared_not_sent"
    ai_used: Literal[False] = False
    formatting_allowed: Literal[False] = False
    contains_private_text: Literal[True] = True
    context_radius: int = Field(ge=0, le=2)
    max_context_blocks: Literal[3] = 3
    max_characters_per_block: int = Field(ge=1, le=240)
    candidate_count: int = Field(ge=0)
    packet_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    total_context_characters: int = Field(ge=0)
    privacy_notice: str = Field(min_length=1)
    packets: list[AiReviewPacket]
    skipped_targets: list[AiSkippedTarget]


class AiUsage(ContractModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    elapsed_ms: int = Field(ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    cost_currency: Literal["USD"] | None = None


class AiModelDecision(ContractModel):
    selected_role: SemanticRole | None
    selected_scope: RuleScope | None
    confidence: float = Field(ge=0, le=1)
    abstained: bool
    reason: str = Field(min_length=1, max_length=500)
    evidence_block_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_abstention(self) -> "AiModelDecision":
        if self.abstained and (self.selected_role is not None or self.selected_scope is not None):
            raise ValueError("Abstained decisions cannot select a role or scope")
        if not self.abstained and self.selected_role is None:
            raise ValueError("Non-abstained decisions must select a role")
        return self


class AiReviewProposal(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    packet_id: str = Field(min_length=1)
    target_block_id: str = Field(min_length=1)
    target_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_role: SemanticRole | None = None
    selected_scope: RuleScope | None = None
    confidence: float = Field(ge=0, le=1)
    abstained: bool
    reason: str = Field(min_length=1, max_length=500)
    evidence_block_ids: list[str] = Field(default_factory=list)
    usage: AiUsage

    @model_validator(mode="after")
    def validate_abstention(self) -> "AiReviewProposal":
        if self.abstained and (self.selected_role is not None or self.selected_scope is not None):
            raise ValueError("Abstained proposals cannot select a role or scope")
        if not self.abstained and self.selected_role is None:
            raise ValueError("Non-abstained proposals must select a role")
        return self


class AiCallFailure(ContractModel):
    packet_id: str = Field(min_length=1)
    target_block_id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=300)
    retryable: bool
    attempts: int = Field(ge=1)


class AiReviewRun(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    mode: Literal["prompt_only", "hybrid"]
    provider: Literal["openai_responses", "deepseek_responses"]
    model: str = Field(min_length=1)
    status: Literal["completed", "partial", "failed"]
    ai_used: Literal[True] = True
    formatting_allowed: Literal[False] = False
    response_store_requested: Literal[False] = False
    raw_prompts_logged: Literal[False] = False
    rules_only_fallback_available: Literal[True] = True
    requested_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    elapsed_ms: int = Field(ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    cost_currency: Literal["USD"] | None = None
    proposals: list[AiReviewProposal]
    failures: list[AiCallFailure]
