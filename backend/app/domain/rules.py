from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import RulePriority, RuleStatus


class RuleSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1)
    document: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    locator: str | None = None


class FormatRule(BaseModel):
    """A versioned formatting requirement with evidence and a validator."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    property_path: str = Field(min_length=1)
    expected_value: Any
    status: RuleStatus
    confidence: float = Field(ge=0.0, le=1.0)
    source: RuleSource
    implementation: str = Field(min_length=1)
    validator: str = Field(min_length=1)
    priority: RulePriority = RulePriority.P1
    auto_fixable: bool = False
