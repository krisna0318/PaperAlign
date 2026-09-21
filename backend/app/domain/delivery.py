from typing import Literal

from pydantic import Field

from app.domain.rules import ContractModel


class RuleRecheck(ContractModel):
    rule_id: str
    result_count: int = Field(ge=0)
    pass_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    unresolved_count: int = Field(ge=0)
    passed: bool


class WordRenderResult(ContractModel):
    status: Literal["not_requested", "passed", "unavailable", "failed"]
    page_count: int | None = Field(default=None, ge=1)
    pdf_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    error_code: str | None = None
    note: str


class DeliveryValidationReport(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    validator_version: str
    job_id: str | None = None
    original_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    formatted_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_fingerprint_original: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_fingerprint_formatted: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_preserved: bool
    package_safe: bool
    formatting_report_matches: bool
    rule_rechecks: list[RuleRecheck]
    static_status: Literal["passed", "failed"]
    word_render: WordRenderResult
    delivery_ready: bool
    manual_validation_required: Literal[True] = True
    manual_checklist: list[str]
    limitations: list[str]


class DeliveryValidationRequest(ContractModel):
    render_with_word: bool = False


class DeliveryValidationResult(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    job_id: str
    report: DeliveryValidationReport
    checklist_artifact: str
    pdf_artifact: str | None = None

