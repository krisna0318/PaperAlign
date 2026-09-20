"""Pure, read-only comparison of a confirmed rule with a located observation."""

from app.domain.rule_validation import RuleObservation, RuleValidationResult
from app.domain.rules import (
    BooleanValue,
    FixedSpacing,
    FormatRule,
    MultipleSpacing,
    NumberValue,
    TextValue,
)
from app.validation.rule_contract import preflight_rule


def validate_rule(rule: FormatRule, observation: RuleObservation) -> RuleValidationResult:
    blocked = preflight_rule(rule, observation)
    if blocked is not None:
        return blocked
    actual = observation.value
    expected = rule.expected_value
    supported = True
    matches = False
    reason = "value_matches"
    if rule.validator not in {"exact_equal", "numeric_compare"}:
        supported = False
        reason = "validator_not_implemented"
    elif isinstance(expected, (TextValue, BooleanValue)) and isinstance(actual, type(expected)):
        matches = expected.value == actual.value
    elif isinstance(expected, (NumberValue, FixedSpacing, MultipleSpacing)) and isinstance(
        actual, (NumberValue, FixedSpacing, MultipleSpacing)
    ):
        if getattr(expected, "mode", None) != getattr(actual, "mode", None):
            reason = "line_spacing_mode_differs"
        elif rule.comparison == "eq":
            matches = abs(expected.value - actual.value) <= rule.tolerance
        elif rule.comparison == "gte":
            matches = actual.value >= expected.value - rule.tolerance
        else:
            matches = actual.value <= expected.value + rule.tolerance
    else:
        supported = False
        reason = "value_type_not_supported"
    if not matches and reason == "value_matches":
        reason = "value_differs"
    return RuleValidationResult(
        rule_id=rule.id,
        property_path=rule.property_path,
        status=("pass" if matches else "fail") if supported else "not_evaluated",
        rule_status=rule.status,
        expected=expected,
        actual=actual,
        source=rule.source,
        locator=observation.locator,
        actual_sources=observation.sources,
        reason=reason,
    )
