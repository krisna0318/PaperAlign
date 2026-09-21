from typing import Any, Literal, Self

from pydantic import Field, model_validator

from app.domain.blocks import SourceAnchor
from app.domain.rules import ContractModel, PropertyPath


class FormattingTarget(ContractModel):
    block_id: str
    table_index: int = Field(ge=0)
    rule_ids: list[str] = Field(min_length=1)
    locator: SourceAnchor


class FormattingPlan(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    engine_version: str
    profile_id: str
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_fingerprint_before: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_rule_ids: list[str] = Field(min_length=1)
    targets: list[FormattingTarget] = Field(min_length=1)
    formatting_allowed: Literal[True] = True


class FormattingOperation(ContractModel):
    rule_id: str
    block_id: str
    property_path: PropertyPath
    locator: SourceAnchor
    before: dict[str, Any]
    after: dict[str, Any]


class FormattingReport(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    engine_version: str
    profile_id: str
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_fingerprint_before: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_fingerprint_after: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_preserved: bool
    applied_rule_ids: list[str] = Field(min_length=1)
    operations: list[FormattingOperation] = Field(min_length=1)
    requires_word_validation: Literal[True] = True
    warnings: list[str]

    @model_validator(mode="after")
    def require_preserved_content(self) -> Self:
        if not self.content_preserved:
            raise ValueError("Formatting report cannot accept changed manuscript content")
        return self


class FormatJobRequest(ContractModel):
    approved_rule_ids: list[str] = Field(min_length=1)


class FormatJobResult(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    job_id: str
    output_artifact: str
    report: FormattingReport
