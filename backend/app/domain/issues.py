from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import IssueSeverity, IssueStatus


class DiagnosisIssue(BaseModel):
    """A traceable mismatch between one block and one formatting rule."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    id: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    block_id: str = Field(min_length=1)
    severity: IssueSeverity
    expected: Any
    actual: Any
    message: str = Field(min_length=1)
    auto_fixable: bool = False
    requires_confirmation: bool = False
    status: IssueStatus = IssueStatus.OPEN
