from datetime import UTC, datetime

import pytest

from app.domain.blocks import SourceAnchor
from app.domain.rule_validation import RuleObservation
from app.domain.rules import FormatRule
from app.validation.comparator import validate_rule
from app.validation.object_observations import observe_section, observe_table


def make_rule(expected, path="run.size_pt", **overrides) -> FormatRule:
    data = {
        "id": "SYNTHETIC",
        "profile_id": "synthetic",
        "scope": "body",
        "property_path": path,
        "expected_value": expected,
        "status": "confirmed",
        "confidence": 1,
        "source": {
            "type": "school_comment",
            "document": "synthetic.docx",
            "evidence": "synthetic",
            "locator": "test:1",
        },
        "confirmation": {
            "reviewer": "synthetic-test",
            "confirmed_at": datetime(2026, 9, 20, tzinfo=UTC),
            "reference": "synthetic test only",
        },
        "implementation": "read_only",
        "validator": "numeric_compare",
        **overrides,
    }
    return FormatRule.model_validate(data)


@pytest.mark.parametrize(
    "value,comparison,tolerance,status",
    [
        (12, "eq", 0, "pass"),
        (10.5, "eq", 0, "fail"),
        (12.05, "eq", 0.1, "pass"),
        (13, "gte", 0, "pass"),
        (11, "gte", 0, "fail"),
        (11, "lte", 0, "pass"),
        (13, "lte", 0, "fail"),
    ],
)
def test_numeric_comparison(value, comparison, tolerance, status) -> None:
    rule = make_rule(
        {"kind": "number", "value": 12, "unit": "pt"}, comparison=comparison, tolerance=tolerance
    )
    observation = RuleObservation.model_validate(
        {
            "value": {"kind": "number", "value": value, "unit": "pt"},
            "locator": {"paragraph_index": 1},
            "sources": {"size_pt": "direct_run"},
        }
    )
    result = validate_rule(rule, observation)
    assert result.status == status
    assert result.actual_sources == {"size_pt": "direct_run"}


@pytest.mark.parametrize(
    "path,expected,actual,status",
    [
        (
            "run.bold",
            {"kind": "boolean", "value": True},
            {"kind": "boolean", "value": False},
            "fail",
        ),
        (
            "run.font_latin",
            {"kind": "text", "value": "Arial"},
            {"kind": "text", "value": "Arial"},
            "pass",
        ),
        (
            "paragraph.line_spacing",
            {"kind": "line_spacing", "mode": "exact", "value": 20, "unit": "pt"},
            {"kind": "line_spacing", "mode": "at_least", "value": 20, "unit": "pt"},
            "fail",
        ),
        (
            "paragraph.line_spacing",
            {"kind": "line_spacing", "mode": "multiple", "value": 1.5, "unit": "lines"},
            {"kind": "line_spacing", "mode": "multiple", "value": 1.5, "unit": "lines"},
            "pass",
        ),
    ],
)
def test_comparison_handles_value_types_and_line_mode(path, expected, actual, status) -> None:
    result = validate_rule(
        make_rule(expected, path),
        RuleObservation.model_validate({"value": actual, "locator": {"paragraph_index": 1}}),
    )
    assert result.status == status


def test_uncertainty_and_unknown_validator_are_not_passes() -> None:
    expected = {"kind": "number", "value": 12, "unit": "pt"}
    observation = RuleObservation.model_validate(
        {"value": expected, "locator": {"paragraph_index": 1}}
    )
    assert (
        validate_rule(
            make_rule(expected, status="provisional", confirmation=None), observation
        ).status
        == "evidence_insufficient"
    )
    assert (
        validate_rule(make_rule(expected), RuleObservation(locator=SourceAnchor())).status
        == "not_evaluated"
    )
    assert (
        validate_rule(make_rule(expected, validator="missing"), observation).status
        == "not_evaluated"
    )


@pytest.mark.parametrize(
    "width,status", [(11906, "pass"), (10000, "fail"), (None, "not_evaluated")]
)
def test_section_adapter_preserves_unknown_and_normalizes_units(width, status) -> None:
    from app.domain.analysis import SectionSnapshot
    from app.domain.rules import PropertyPath

    observation = observe_section(
        SectionSnapshot(index=0, page_width_twips=width), PropertyPath.PAGE_WIDTH
    )
    rule = make_rule(
        {"kind": "number", "value": 210, "unit": "mm"},
        "page.width_mm",
        scope="document",
        tolerance=0.1,
    )
    assert validate_rule(rule, observation).status == status
    assert observation.locator.xml_path == "(//w:sectPr)[1]"


@pytest.mark.parametrize("pattern", ["mixed", "unknown"])
def test_ambiguous_table_borders_are_not_evaluated(pattern) -> None:
    from app.domain.rules import PropertyPath
    from app.domain.template_evidence import TableFormatObservation

    table = TableFormatObservation(
        table_index=0,
        row_count=2,
        column_count=2,
        inferred_pattern=pattern,
        confidence=0,
        outer_top_widths_pt=[1.5],
    )
    rule = make_rule(
        {"kind": "number", "value": 1.5, "unit": "pt"},
        "table.top_pt",
        scope="table",
    )
    observation = observe_table(table, PropertyPath.BORDER_TOP)
    assert validate_rule(rule, observation).status == "not_evaluated"
