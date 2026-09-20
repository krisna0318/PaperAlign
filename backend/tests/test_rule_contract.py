import copy
from datetime import UTC, datetime

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from app.domain.blocks import SourceAnchor
from app.domain.rule_validation import EvidenceCandidate, RuleObservation
from app.domain.rules import (
    FormatRule,
    NumberValue,
    PropertyPath,
    RuleConfirmation,
    RuleSource,
)
from app.domain.template_evidence import EffectiveParagraphFormat, EffectiveParagraphProperties
from app.validation.observations import observe_format
from app.validation.rule_contract import preflight_rule, select_evidence
from app.validation.units import hundredths_to_chars, ooxml_line_spacing, twips_to_mm, twips_to_pt


def rule_payload() -> dict:
    return {
        "schema_version": "2.0",
        "id": "TEST-SIZE",
        "profile_id": "synthetic",
        "scope": "body",
        "property_path": "run.size_pt",
        "expected_value": {"kind": "number", "value": 12.0, "unit": "pt"},
        "status": "provisional",
        "confidence": 0.9,
        "source": {
            "type": "school_comment",
            "document": "synthetic.docx",
            "evidence": "Synthetic requirement",
            "locator": "comment:1",
        },
        "implementation": "read_only",
        "validator": "numeric_equal",
    }


def test_rule_roundtrip_and_schema() -> None:
    rule = FormatRule.model_validate(rule_payload())
    validator = Draft202012Validator(FormatRule.model_json_schema())
    validator.check_schema(validator.schema)
    validator.validate(rule.model_dump(mode="json"))
    assert FormatRule.model_validate_json(rule.model_dump_json()) == rule


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": "1.0"},
        {"property_path": "run.size_twips"},
        {"expected_value": {"kind": "number", "value": 12, "unit": "mm"}},
        {"expected_value": {"kind": "number", "value": True, "unit": "pt"}},
        {"expected_value": {"kind": "number", "value": "12", "unit": "pt"}},
        {"expected_value": {"kind": "number", "value": 0, "unit": "pt"}},
        {"expected_value": {"kind": "text", "value": "12pt"}},
        {"expected_value": {"value": 12, "unit": "pt"}},
        {
            "property_path": "paragraph.line_spacing",
            "expected_value": {"kind": "line_spacing", "value": 1.5, "unit": "lines"},
        },
        {"status": "confirmed"},
        {"status": "confirmed", "confirmation": None},
        {"auto_fixable": True},
        {"scope": "whatever"},
        {
            "property_path": "paragraph.alignment",
            "comparison": "gte",
            "expected_value": {"kind": "text", "value": "center"},
        },
        {
            "property_path": "paragraph.alignment",
            "expected_value": {"kind": "text", "value": "foo"},
        },
        {
            "property_path": "paragraph.outline_level",
            "expected_value": {"kind": "number", "value": 1.5, "unit": "level"},
        },
    ],
)
def test_invalid_contract_rejected_by_runtime_and_json_schema(change: dict) -> None:
    payload = copy.deepcopy(rule_payload())
    payload.update(change)
    with pytest.raises(ValidationError):
        FormatRule.model_validate(payload)
    assert list(Draft202012Validator(FormatRule.model_json_schema()).iter_errors(payload))


def test_nonfinite_value_rejected() -> None:
    with pytest.raises(ValidationError):
        NumberValue(value=float("nan"), unit="pt")


def test_unit_conversions_do_not_confuse_lines_and_points() -> None:
    assert twips_to_pt(400) == 20
    assert twips_to_mm(1440) == 25.4
    assert hundredths_to_chars(200) == 2
    multiple = ooxml_line_spacing(360, "auto")
    exact = ooxml_line_spacing(400, "exact")
    assert multiple and multiple.value == 1.5 and multiple.unit == "lines"
    assert exact and exact.value == 20 and exact.unit == "pt"
    assert ooxml_line_spacing(400, None) is None
    assert ooxml_line_spacing(None, "auto") is None


def candidate(value: float, source_type: str) -> EvidenceCandidate:
    return EvidenceCandidate(
        value=NumberValue(value=value, unit="pt"),
        source=RuleSource.model_validate(
            {
                "type": source_type,
                "document": "synthetic.docx",
                "evidence": "synthetic",
                "locator": "test:1",
            }
        ),
    )


def test_explicit_evidence_overrides_observation_but_never_self_confirms() -> None:
    observation = candidate(0.5, "template_observation")
    comment = candidate(1.0, "school_comment")
    result = select_evidence([observation, comment])
    assert result.selected == comment
    assert result.status == "provisional"
    assert len(result.alternatives) == 2
    assert select_evidence([observation]).status == "provisional"
    assert select_evidence([comment, candidate(2.0, "written_spec")]).selected is None
    assert (
        select_evidence([observation, candidate(2.0, "template_observation")]).status
        == "needs_review"
    )
    assert select_evidence([]).status == "needs_review"


def test_preflight_never_passes_unconfirmed_or_unknown_values() -> None:
    payload = rule_payload()
    rule = FormatRule.model_validate(payload)
    observation = RuleObservation(
        value=NumberValue(value=12, unit="pt"), locator=SourceAnchor(paragraph_index=2)
    )
    blocked = preflight_rule(rule, observation)
    assert blocked and blocked.status == "evidence_insufficient"
    payload["status"] = "confirmed"
    payload["confirmation"] = RuleConfirmation(
        reviewer="synthetic-reviewer",
        confirmed_at=datetime(2026, 9, 20, tzinfo=UTC),
        reference="synthetic decision",
    ).model_dump()
    confirmed = FormatRule.model_validate(payload)
    assert preflight_rule(confirmed, observation) is None  # Ready, not a compliance pass.
    unknown = preflight_rule(confirmed, RuleObservation(locator=observation.locator))
    assert unknown and unknown.status == "not_evaluated"
    wrong_units = preflight_rule(
        confirmed,
        RuleObservation(value=NumberValue(value=12, unit="mm"), locator=observation.locator),
    )
    assert wrong_units and wrong_units.status == "not_evaluated"


def test_adapter_prefers_character_indent_and_refuses_unresolved_values() -> None:
    snapshot = EffectiveParagraphFormat(
        paragraph_index=1,
        paragraph=EffectiveParagraphProperties(
            first_line_indent_twips=480,
            first_line_indent_chars=200,
            line_rule="auto",
            line_value=360,
            sources={"first_line_indent_chars": "direct_paragraph"},
        ),
    )
    indent = observe_format(snapshot, PropertyPath.FIRST_LINE_CHARS)
    assert indent.value == NumberValue(value=2, unit="chars")
    assert indent.sources == {"first_line_indent_chars": "direct_paragraph"}
    assert not observe_format(snapshot, PropertyPath.FIRST_LINE_PT).supported
    assert not observe_format(snapshot, PropertyPath.FONT_SIZE).supported
    assert observe_format(snapshot, PropertyPath.LINE_SPACING).value == ooxml_line_spacing(
        360, "auto"
    )


def test_snapshot_to_canonical_run_properties() -> None:
    from app.domain.template_evidence import EffectiveRunFormatGroup, EffectiveRunProperties

    snapshot = EffectiveParagraphFormat(
        paragraph_index=3,
        paragraph=EffectiveParagraphProperties(),
        runs=[
            EffectiveRunFormatGroup(
                properties=EffectiveRunProperties(
                    size_pt=12, bold=False, font_latin="Arial", sources={"size_pt": "direct_run"}
                ),
                run_count=1,
            )
        ],
    )
    assert observe_format(snapshot, PropertyPath.FONT_SIZE).value == NumberValue(
        value=12, unit="pt"
    )
    assert observe_format(snapshot, PropertyPath.BOLD).value.value is False
    assert observe_format(snapshot, PropertyPath.FONT_LATIN).value.value == "Arial"
    assert not observe_format(snapshot, PropertyPath.PAGE_WIDTH).supported
    assert not observe_format(snapshot, PropertyPath.FONT_SIZE, run_group=5).supported
    snapshot.runs[0].properties.unresolved["font_latin"] = "theme_font_not_resolved"
    assert not observe_format(snapshot, PropertyPath.FONT_LATIN).supported
    snapshot.resolution_warnings.append("missing_style")
    assert not observe_format(snapshot, PropertyPath.FONT_SIZE).supported


def test_frontend_rule_enums_match_backend_contract() -> None:
    import re
    from pathlib import Path

    from app.domain.rules import RuleScope

    frontend = (Path(__file__).resolve().parents[2] / "frontend/src/types/rules.ts").read_text()
    for name, enum in (("RuleScope", RuleScope), ("PropertyPath", PropertyPath)):
        declaration = re.search(rf"export type {name} = (.*?);", frontend, re.S).group(1)
        assert set(re.findall(r'"([^"]+)"', declaration)) == {item.value for item in enum}


def test_schema_check_is_read_only_and_independent_of_git(tmp_path) -> None:
    from app.schema_export import export_schemas

    assert export_schemas(tmp_path / "missing", check=True)
    assert not (tmp_path / "missing").exists()
    export_schemas(tmp_path)
    assert export_schemas(tmp_path, check=True) == []
