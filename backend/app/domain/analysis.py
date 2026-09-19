from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.blocks import DocumentBlock


class PackageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str
    file_size_bytes: int = Field(ge=0)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    part_count: int = Field(ge=0)
    compressed_size_bytes: int = Field(ge=0)
    uncompressed_size_bytes: int = Field(ge=0)
    main_document_part: str
    macro_enabled: bool = False


class StyleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style_id: str
    name: str | None = None
    style_type: str | None = None
    based_on: str | None = None


class SectionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    start_type: str | None = None
    page_width_twips: int | None = Field(default=None, ge=0)
    page_height_twips: int | None = Field(default=None, ge=0)
    margin_top_twips: int | None = Field(default=None, ge=0)
    margin_right_twips: int | None = Field(default=None, ge=0)
    margin_bottom_twips: int | None = Field(default=None, ge=0)
    margin_left_twips: int | None = Field(default=None, ge=0)
    header_relationship_ids: list[str] = Field(default_factory=list)
    footer_relationship_ids: list[str] = Field(default_factory=list)
    page_number_format: str | None = None
    page_number_start: int | None = Field(default=None, ge=0)


class StoryPartSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_name: str
    kind: Literal["header", "footer", "footnotes", "endnotes", "comments"]
    text: str
    paragraph_count: int = Field(ge=0)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FieldSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_name: str
    instruction: str
    result_text: str = ""
    simple: bool = False


class MediaAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_name: str
    content_type: str | None = None
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class DocumentStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_count: int = Field(ge=0)
    paragraph_count: int = Field(ge=0)
    table_count: int = Field(ge=0)
    table_cell_count: int = Field(ge=0)
    image_count: int = Field(ge=0)
    section_count: int = Field(ge=0)
    field_count: int = Field(ge=0)
    story_part_count: int = Field(ge=0)
    character_count: int = Field(ge=0)


class DocumentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    analyzer_version: str
    package: PackageSummary
    statistics: DocumentStatistics
    blocks: list[DocumentBlock]
    styles: list[StyleDefinition] = Field(default_factory=list)
    sections: list[SectionSnapshot] = Field(default_factory=list)
    story_parts: list[StoryPartSnapshot] = Field(default_factory=list)
    fields: list[FieldSnapshot] = Field(default_factory=list)
    media: list[MediaAsset] = Field(default_factory=list)


class FingerprintUnit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor: str
    kind: str
    text_length: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ContentFingerprintReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    algorithm: Literal["sha256"] = "sha256"
    normalization: str
    aggregate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    unit_count: int = Field(ge=0)
    total_characters: int = Field(ge=0)
    units: list[FingerprintUnit]


class UnsupportedObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category: str
    severity: Literal["error", "warning", "info"]
    policy: Literal["block_formatting", "manual_review", "report_only"]
    part_name: str
    message: str
    relationship_type: str | None = None
    target: str | None = None
    external: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class UnsupportedObjectsReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    safe_for_future_formatting: bool
    object_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    info_count: int = Field(ge=0)
    objects: list[UnsupportedObject]
