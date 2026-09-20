from datetime import date
from typing import Literal, Self

from pydantic import Field, model_validator

from app.domain.rules import ContractModel, FormatRule, RuleScope, RuleSource


class Applicability(ContractModel):
    school: str = Field(min_length=1)
    education_level: Literal["undergraduate"] = "undergraduate"
    cohort: str = Field(min_length=1)
    confirmed_on: date
    confirmation_reference: str = Field(min_length=1)
    excluded_colleges: list[str] = Field(min_length=1)
    college_customizations: Literal[False] = False


class TemplateSample(ContractModel):
    kind: Literal["paragraph", "table", "section"]
    index: int = Field(ge=0)
    scope: RuleScope


class ProfileManifest(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    profile_id: str = Field(pattern=r"^[a-z0-9_]+$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    format_rule_schema_version: Literal["2.0"] = "2.0"
    name: str = Field(min_length=1)
    applicability: Applicability
    template_document: str
    template_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule_files: list[str] = Field(min_length=1)
    evidence_file: str
    coverage_file: str
    template_samples: list[TemplateSample] = Field(default_factory=list)

    @model_validator(mode="after")
    def distinct_files(self) -> Self:
        files = [*self.rule_files, self.evidence_file, self.coverage_file]
        if len(files) != len(set(files)):
            raise ValueError("Profile file references must be unique")
        return self


class CoverageEntry(ContractModel):
    inventory_id: str = Field(pattern=r"^SCAU-P0-[A-Z0-9-]+$")
    state: Literal["encoded", "partial", "deferred"]
    rule_ids: list[str]
    deferred_requirements: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_coverage(self) -> Self:
        if self.state == "encoded" and (not self.rule_ids or self.deferred_requirements):
            raise ValueError("Encoded entries require rules and no deferred requirements")
        if self.state == "partial" and (not self.rule_ids or not self.deferred_requirements):
            raise ValueError("Partial entries require both rules and deferred requirements")
        if self.state == "deferred" and (self.rule_ids or not self.deferred_requirements):
            raise ValueError("Deferred entries require reasons and no rules")
        if len(self.rule_ids) != len(set(self.rule_ids)):
            raise ValueError("Duplicate rule references")
        return self


class ProfileBundle(ContractModel):
    manifest: ProfileManifest
    rules: list[FormatRule]
    evidence: list[RuleSource]
    coverage: list[CoverageEntry]


class ApplicabilityResult(ContractModel):
    status: Literal["applicable", "not_applicable", "needs_review"]
    reason: str
