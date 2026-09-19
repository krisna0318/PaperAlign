from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import BlockKind, DecisionSource, SemanticRole


class StyleSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style_id: str | None = None
    style_name: str | None = None
    font_east_asia: str | None = None
    font_latin: str | None = None
    size_pt: float | None = Field(default=None, gt=0)
    bold: bool | None = None
    italic: bool | None = None
    alignment: str | None = None
    line_spacing: float | None = Field(default=None, gt=0)
    space_before_pt: float | None = Field(default=None, ge=0)
    space_after_pt: float | None = Field(default=None, ge=0)
    first_line_indent_pt: float | None = None


class SourceAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_name: str = "word/document.xml"
    paragraph_index: int | None = Field(default=None, ge=0)
    table_index: int | None = Field(default=None, ge=0)
    row_index: int | None = Field(default=None, ge=0)
    cell_index: int | None = Field(default=None, ge=0)
    xml_path: str | None = None


class DocumentBlock(BaseModel):
    """A locatable and classifiable unit extracted from a DOCX package."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    id: str = Field(min_length=1)
    order: int = Field(ge=0)
    kind: BlockKind
    text: str = ""
    role: SemanticRole = SemanticRole.UNKNOWN
    parent_id: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    decision_source: DecisionSource = DecisionSource.UNKNOWN
    requires_confirmation: bool = False
    style: StyleSnapshot = Field(default_factory=StyleSnapshot)
    source_anchor: SourceAnchor
    protected: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
