from typing import Literal

from pydantic import Field

from app.domain.blocks import SourceAnchor
from app.domain.enums import RuleStatus
from app.domain.rules import ContractModel, RuleSource, RuleValue


class RuleObservation(ContractModel):
    value: RuleValue | None = None
    supported: bool = True
    locator: SourceAnchor
    sources: dict[str, str] = Field(default_factory=dict)
    reason: str | None = None


class RuleValidationResult(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    rule_id: str
    property_path: str
    status: Literal["pass", "fail", "not_evaluated", "evidence_insufficient"]
    rule_status: RuleStatus
    expected: RuleValue
    actual: RuleValue | None
    source: RuleSource
    locator: SourceAnchor
    actual_sources: dict[str, str]
    reason: str


class EvidenceCandidate(ContractModel):
    value: RuleValue
    source: RuleSource


class EvidenceSelection(ContractModel):
    status: Literal["provisional", "needs_review"]
    selected: EvidenceCandidate | None = None
    alternatives: list[EvidenceCandidate]
    reason: str
