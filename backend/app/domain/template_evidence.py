from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.analysis import SectionSnapshot


class ParagraphStyleUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style_id: str | None = None
    style_name: str | None = None
    paragraph_count: int = Field(ge=1)
    sample_paragraph_indexes: list[int] = Field(default_factory=list, max_length=5)


class DirectFormatCluster(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style_id: str | None = None
    style_name: str | None = None
    font_east_asia: str | None = None
    font_latin: str | None = None
    size_pt: float | None = Field(default=None, gt=0)
    bold: bool | None = None
    italic: bool | None = None
    alignment: str | None = None
    line_rule: str | None = None
    line_value: int | None = Field(default=None, ge=0)
    first_line_indent_twips: int | None = None
    first_line_indent_chars: int | None = None
    paragraph_count: int = Field(ge=1)
    sample_paragraph_indexes: list[int] = Field(default_factory=list, max_length=5)
    source_method: Literal["direct_first_text_run"] = "direct_first_text_run"


class EffectiveParagraphProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alignment: str | None = None
    line_rule: str | None = None
    line_value: int | None = Field(default=None, ge=0)
    space_before_twips: int | None = Field(default=None, ge=0)
    space_after_twips: int | None = Field(default=None, ge=0)
    first_line_indent_twips: int | None = None
    first_line_indent_chars: int | None = None
    left_indent_twips: int | None = None
    right_indent_twips: int | None = None
    outline_level: int | None = Field(default=None, ge=0)
    keep_with_next: bool | None = None
    page_break_before: bool | None = None
    sources: dict[str, str] = Field(default_factory=dict)
    unresolved: dict[str, str] = Field(default_factory=dict)


class EffectiveRunProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    font_east_asia: str | None = None
    font_latin: str | None = None
    font_high_ansi: str | None = None
    font_complex_script: str | None = None
    size_pt: float | None = Field(default=None, gt=0)
    bold: bool | None = None
    italic: bool | None = None
    color: str | None = None
    sources: dict[str, str] = Field(default_factory=dict)
    unresolved: dict[str, str] = Field(default_factory=dict)


class EffectiveRunFormatGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_style_id: str | None = None
    character_style_name: str | None = None
    properties: EffectiveRunProperties
    run_count: int = Field(ge=1)
    sample_run_indexes: list[int] = Field(default_factory=list, max_length=5)


class EffectiveParagraphFormat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paragraph_index: int = Field(ge=0)
    paragraph_style_id: str | None = None
    paragraph_style_name: str | None = None
    paragraph: EffectiveParagraphProperties
    runs: list[EffectiveRunFormatGroup] = Field(default_factory=list)
    resolution_warnings: list[str] = Field(default_factory=list)


class BorderObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge: str
    line_style: str
    size_eighth_points: int | None = Field(default=None, ge=0)
    size_pt: float | None = Field(default=None, ge=0)
    color: str | None = None
    count: int = Field(default=1, ge=1)
    source_scope: Literal["table", "table_style", "cell"]


class TableFormatObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_index: int = Field(ge=0)
    style_id: str | None = None
    style_name: str | None = None
    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    alignment: str | None = None
    layout: str | None = None
    grid_widths_twips: list[int] = Field(default_factory=list)
    repeating_header_rows: list[int] = Field(default_factory=list)
    border_declarations: list[BorderObservation] = Field(default_factory=list)
    outer_top_widths_pt: list[float] = Field(default_factory=list)
    header_separator_widths_pt: list[float] = Field(default_factory=list)
    outer_bottom_widths_pt: list[float] = Field(default_factory=list)
    vertical_borders_present: bool = False
    inferred_pattern: Literal["three_line", "grid", "borderless", "mixed", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    requires_confirmation: bool = True


class TemplateEvidenceReport(BaseModel):
    """Formatting observations extracted from a DOCX without treating them as rules."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    extractor_version: str
    file_name: str
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    comments_present: bool
    comment_count: int = Field(ge=0)
    observations_are_rules: Literal[False] = False
    evidence_sources: list[str] = Field(default_factory=list)
    sections: list[SectionSnapshot] = Field(default_factory=list)
    paragraph_style_usage: list[ParagraphStyleUsage] = Field(default_factory=list)
    direct_format_clusters: list[DirectFormatCluster] = Field(default_factory=list)
    effective_formats: list[EffectiveParagraphFormat] = Field(default_factory=list)
    tables: list[TableFormatObservation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
