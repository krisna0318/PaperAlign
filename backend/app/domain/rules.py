"""M2.2 atomic rule contract. V1 free-form rules require explicit migration."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, model_validator

from app.domain.enums import RulePriority, RuleStatus


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NumberValue(ContractModel):
    model_config = ConfigDict(json_schema_extra={"required": ["kind", "value", "unit"]})
    kind: Literal["number"] = "number"
    value: StrictFloat = Field(allow_inf_nan=False)
    unit: Literal["pt", "mm", "chars", "count", "level"]


class TextValue(ContractModel):
    model_config = ConfigDict(json_schema_extra={"required": ["kind", "value"]})
    kind: Literal["text"] = "text"
    value: str = Field(min_length=1)


class BooleanValue(ContractModel):
    model_config = ConfigDict(json_schema_extra={"required": ["kind", "value"]})
    kind: Literal["boolean"] = "boolean"
    value: StrictBool


class MultipleSpacing(ContractModel):
    model_config = ConfigDict(json_schema_extra={"required": ["kind", "mode", "value"]})
    kind: Literal["line_spacing"] = "line_spacing"
    mode: Literal["multiple"] = "multiple"
    value: StrictFloat = Field(gt=0, allow_inf_nan=False)
    unit: Literal["lines"] = "lines"


class FixedSpacing(ContractModel):
    model_config = ConfigDict(json_schema_extra={"required": ["kind", "mode", "value"]})
    kind: Literal["line_spacing"] = "line_spacing"
    mode: Literal["exact", "at_least"]
    value: StrictFloat = Field(gt=0, allow_inf_nan=False)
    unit: Literal["pt"] = "pt"


LineSpacing = Annotated[MultipleSpacing | FixedSpacing, Field(discriminator="mode")]
RuleValue = Annotated[
    NumberValue | TextValue | BooleanValue | LineSpacing, Field(discriminator="kind")
]


class RuleScope(StrEnum):
    DOCUMENT = "document"
    SECTION = "section"
    COVER_TITLE = "cover_title"
    COVER_DOCUMENT_TYPE = "cover_document_type"
    COVER_METADATA = "cover_metadata"
    DECLARATION = "declaration"
    ABSTRACT_ZH_HEADING = "abstract_zh_heading"
    ABSTRACT_ZH_BODY = "abstract_zh_body"
    ABSTRACT_EN_TITLE = "abstract_en_title"
    ABSTRACT_EN_AUTHOR = "abstract_en_author"
    ABSTRACT_EN_AFFILIATION = "abstract_en_affiliation"
    ABSTRACT_EN_BODY = "abstract_en_body"
    KEYWORDS_ZH = "keywords_zh"
    KEYWORDS_EN = "keywords_en"
    TOC_HEADING = "toc_heading"
    TOC_ENTRY = "toc_entry"
    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    HEADING_4 = "heading_4"
    BODY = "body"
    ABBREVIATION_TABLE = "abbreviation_table"
    TABLE = "table"
    TABLE_TEXT = "table_text"
    TABLE_CAPTION = "table_caption"
    TABLE_NOTE = "table_note"
    FIGURE = "figure"
    FIGURE_CAPTION = "figure_caption"
    FIGURE_NOTE = "figure_note"
    EQUATION = "equation"
    FOOTNOTE = "footnote"
    REFERENCE_HEADING = "reference_heading"
    REFERENCE_ENTRY = "reference_entry"
    APPENDIX_HEADING = "appendix_heading"
    APPENDIX_BODY = "appendix_body"
    ACKNOWLEDGEMENT_HEADING = "acknowledgement_heading"
    ACKNOWLEDGEMENT_BODY = "acknowledgement_body"


class PropertyPath(StrEnum):
    PAGE_WIDTH = "page.width_mm"
    PAGE_HEIGHT = "page.height_mm"
    MARGIN_TOP = "page.margin_top_mm"
    MARGIN_BOTTOM = "page.margin_bottom_mm"
    MARGIN_LEFT = "page.margin_left_mm"
    MARGIN_RIGHT = "page.margin_right_mm"
    PAGE_NUMBER_FORMAT = "page.number_format"
    PAGE_NUMBER_START = "page.number_start"
    PAGE_NUMBER_VISIBLE = "page.number_visible"
    FONT_EAST_ASIA = "run.font_east_asia"
    FONT_LATIN = "run.font_latin"
    FONT_HIGH_ANSI = "run.font_high_ansi"
    FONT_SIZE = "run.size_pt"
    BOLD = "run.bold"
    ITALIC = "run.italic"
    ALIGNMENT = "paragraph.alignment"
    LINE_SPACING = "paragraph.line_spacing"
    BEFORE = "paragraph.space_before_pt"
    AFTER = "paragraph.space_after_pt"
    FIRST_LINE_PT = "paragraph.first_line_indent_pt"
    FIRST_LINE_CHARS = "paragraph.first_line_indent_chars"
    HANGING_CHARS = "paragraph.hanging_indent_chars"
    LEFT = "paragraph.left_indent_pt"
    RIGHT = "paragraph.right_indent_pt"
    OUTLINE = "paragraph.outline_level"
    KEEP_NEXT = "paragraph.keep_with_next"
    PAGE_BREAK = "paragraph.page_break_before"
    BORDER_TOP = "table.top_pt"
    BORDER_MIDDLE = "table.header_separator_pt"
    BORDER_BOTTOM = "table.bottom_pt"
    VERTICAL_BORDERS = "table.vertical_borders_present"
    REPEAT_HEADER = "table.repeat_header"
    TEXT_COUNT = "content.character_count"
    KEYWORD_COUNT = "content.keyword_count"
    SEPARATOR = "content.separator"


PROPERTY_SPECS: dict[PropertyPath, tuple[str, str | None]] = {}
for _path in PropertyPath:
    if _path.value.endswith("_mm"):
        PROPERTY_SPECS[_path] = ("number", "mm")
    elif _path.value.endswith("_pt"):
        PROPERTY_SPECS[_path] = ("number", "pt")
    elif _path.value.endswith("_chars"):
        PROPERTY_SPECS[_path] = ("number", "chars")
    elif _path in {
        PropertyPath.PAGE_NUMBER_START,
        PropertyPath.TEXT_COUNT,
        PropertyPath.KEYWORD_COUNT,
    }:
        PROPERTY_SPECS[_path] = ("number", "count")
    elif _path == PropertyPath.OUTLINE:
        PROPERTY_SPECS[_path] = ("number", "level")
    elif _path == PropertyPath.LINE_SPACING:
        PROPERTY_SPECS[_path] = ("line_spacing", None)
    elif _path in {
        PropertyPath.BOLD,
        PropertyPath.ITALIC,
        PropertyPath.KEEP_NEXT,
        PropertyPath.PAGE_BREAK,
        PropertyPath.VERTICAL_BORDERS,
        PropertyPath.REPEAT_HEADER,
        PropertyPath.PAGE_NUMBER_VISIBLE,
    }:
        PROPERTY_SPECS[_path] = ("boolean", None)
    else:
        PROPERTY_SPECS[_path] = ("text", None)


class RuleSource(ContractModel):
    type: Literal["school_comment", "written_spec", "template_observation"]
    document: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    document_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class RuleConfirmation(ContractModel):
    reviewer: str = Field(min_length=1)
    confirmed_at: datetime
    reference: str = Field(
        min_length=1, description="Human decision record including applicability"
    )


def _value_constraints(path: PropertyPath) -> dict[str, Any]:
    kind, unit = PROPERTY_SPECS[path]
    if path == PropertyPath.ALIGNMENT:
        return {"enum": ["left", "right", "center", "both", "distribute", "start", "end"]}
    if kind != "number":
        return {}
    if path in {PropertyPath.PAGE_WIDTH, PropertyPath.PAGE_HEIGHT, PropertyPath.FONT_SIZE}:
        return {"exclusiveMinimum": 0}
    if unit in {"level", "count"}:
        return {"minimum": 0, "multipleOf": 1, **({"maximum": 9} if unit == "level" else {})}
    if path in {
        PropertyPath.FIRST_LINE_PT,
        PropertyPath.FIRST_LINE_CHARS,
        PropertyPath.LEFT,
        PropertyPath.RIGHT,
    }:
        return {}
    return {"minimum": 0}


def _rule_schema(schema: dict[str, Any]) -> None:
    schema["allOf"] = [
        {
            "if": {
                "properties": {"property_path": {"const": path.value}},
                "required": ["property_path"],
            },
            "then": {
                "properties": {
                    "expected_value": {
                        "properties": {
                            "kind": {"const": kind},
                            "value": _value_constraints(path),
                            **({"unit": {"const": unit}} if unit else {}),
                        }
                    }
                }
            },
        }
        for path, (kind, unit) in PROPERTY_SPECS.items()
    ] + [
        {
            "if": {"properties": {"status": {"const": "confirmed"}}, "required": ["status"]},
            "then": {
                "required": ["confirmation"],
                "properties": {"confirmation": {"type": "object"}},
            },
        },
        {
            "if": {
                "properties": {"status": {"enum": ["provisional", "needs_review"]}},
                "required": ["status"],
            },
            "then": {"properties": {"auto_fixable": {"const": False}}},
        },
        {
            "if": {
                "properties": {
                    "expected_value": {
                        "properties": {"kind": {"enum": ["text", "boolean"]}},
                        "required": ["kind"],
                    }
                }
            },
            "then": {"properties": {"comparison": {"const": "eq"}, "tolerance": {"const": 0}}},
        },
    ]


class RuleTarget(ContractModel):
    text_part: Literal["whole", "label", "value"] = "whole"
    paragraph_position: Literal["all", "first", "following"] = "all"
    metadata_field: Literal["college", "major", "name", "student_id", "advisor", "date"] | None = (
        None
    )


class FormatRule(ContractModel):
    """One property, one canonical unit, with evidence and explicit confirmation."""

    model_config = ConfigDict(extra="forbid", frozen=True, json_schema_extra=_rule_schema)
    schema_version: Literal["2.0"] = "2.0"
    id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    scope: RuleScope
    target: RuleTarget = Field(default_factory=RuleTarget)
    property_path: PropertyPath
    expected_value: RuleValue
    comparison: Literal["eq", "gte", "lte"] = "eq"
    tolerance: StrictFloat = Field(default=0.0, ge=0, allow_inf_nan=False)
    status: RuleStatus
    confidence: float = Field(ge=0.0, le=1.0)
    source: RuleSource
    confirmation: RuleConfirmation | None = None
    display_alias: str | None = None
    implementation: str = Field(min_length=1)
    validator: str = Field(min_length=1)
    priority: RulePriority = RulePriority.P1
    auto_fixable: bool = False

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        kind, unit = PROPERTY_SPECS[self.property_path]
        if self.expected_value.kind != kind:
            raise ValueError("property_path and expected_value kind disagree")
        if isinstance(self.expected_value, NumberValue) and self.expected_value.unit != unit:
            raise ValueError("property_path requires its canonical unit")
        constraints = _value_constraints(self.property_path)
        value = self.expected_value.value
        if isinstance(self.expected_value, NumberValue):
            number = self.expected_value.value
            if "minimum" in constraints and number < constraints["minimum"]:
                raise ValueError("property value below minimum")
            if "exclusiveMinimum" in constraints and number <= constraints["exclusiveMinimum"]:
                raise ValueError("property value must be positive")
            if "maximum" in constraints and number > constraints["maximum"]:
                raise ValueError("property value above maximum")
            if "multipleOf" in constraints and not number.is_integer():
                raise ValueError("count and outline level must be integers")
        if "enum" in constraints and value not in constraints["enum"]:
            raise ValueError("unknown property value")
        if self.status == RuleStatus.CONFIRMED and self.confirmation is None:
            raise ValueError("confirmed rules require a human confirmation record")
        if self.status != RuleStatus.CONFIRMED and self.auto_fixable:
            raise ValueError("unconfirmed rules cannot authorize automatic fixes")
        if kind not in {"number", "line_spacing"} and (
            self.comparison != "eq" or self.tolerance != 0
        ):
            raise ValueError("text and boolean comparisons must be exact")
        return self
