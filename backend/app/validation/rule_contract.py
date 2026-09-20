"""Evidence selection and preflight only. Actual compliance validators are M2.4."""

from typing import Literal

from app.domain.enums import RuleStatus
from app.domain.rule_validation import (
    EvidenceCandidate,
    EvidenceSelection,
    RuleObservation,
    RuleValidationResult,
)
from app.domain.rules import FormatRule


def select_evidence(candidates: list[EvidenceCandidate]) -> EvidenceSelection:
    explicit = [c for c in candidates if c.source.type in {"school_comment", "written_spec"}]
    highest = explicit or candidates
    if not highest:
        return EvidenceSelection(status="needs_review", alternatives=[], reason="no_evidence")
    if any(c.value != highest[0].value for c in highest[1:]):
        return EvidenceSelection(
            status="needs_review",
            alternatives=candidates,
            reason="conflicting_equal_authority_evidence",
        )
    return EvidenceSelection(
        status="provisional",
        selected=highest[0],
        alternatives=candidates,
        reason="explicit_requirement" if explicit else "template_observation",
    )


def preflight_rule(rule: FormatRule, observation: RuleObservation) -> RuleValidationResult | None:
    """None means ready for a property validator, never means pass."""
    status: Literal["not_evaluated", "evidence_insufficient"] | None = None
    reason = ""
    if rule.status != RuleStatus.CONFIRMED:
        status = "evidence_insufficient"
        reason = "rule_requires_human_confirmation"
    elif not observation.supported or observation.value is None:
        status = "not_evaluated"
        reason = observation.reason or "actual_value_unresolved"
    elif observation.value.kind != rule.expected_value.kind or (
        getattr(observation.value, "unit", None) != getattr(rule.expected_value, "unit", None)
    ):
        status = "not_evaluated"
        reason = "incompatible_value_kind_or_unit"
    if status is None:
        return None
    return RuleValidationResult(
        rule_id=rule.id,
        property_path=rule.property_path,
        status=status,
        rule_status=rule.status,
        expected=rule.expected_value,
        actual=observation.value,
        source=rule.source,
        locator=observation.locator,
        actual_sources=observation.sources,
        reason=reason,
    )
