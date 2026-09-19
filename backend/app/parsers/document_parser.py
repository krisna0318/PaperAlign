from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Literal

from lxml import etree

from app.domain.analysis import (
    DocumentStatistics,
    FieldSnapshot,
    MediaAsset,
    SectionSnapshot,
    StoryPartSnapshot,
    StyleDefinition,
)
from app.domain.blocks import DocumentBlock, SourceAnchor, StyleSnapshot
from app.domain.enums import BlockKind
from app.parsers.content_types import ContentTypeMap
from app.parsers.docx_package import DocxPackage
from app.parsers.namespaces import NS, M, R, W, qn
from app.parsers.relationships import Relationship
from app.parsers.xml_utils import parse_xml

StoryKind = Literal["header", "footer", "footnotes", "endnotes", "comments"]

STORY_PARTS: tuple[tuple[str, StoryKind], ...] = (
    ("word/header", "header"),
    ("word/footer", "footer"),
    ("word/footnotes.xml", "footnotes"),
    ("word/endnotes.xml", "endnotes"),
    ("word/comments.xml", "comments"),
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _word_value(element: etree._Element | None, name: str = "val") -> str | None:
    if element is None:
        return None
    return element.get(qn(W, name))


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _toggle_value(element: etree._Element | None) -> bool | None:
    if element is None:
        return None
    value = _word_value(element)
    if value is None:
        return True
    return value.casefold() not in {"0", "false", "off", "no"}


def visible_text(element: etree._Element) -> str:
    pieces: list[str] = []
    for node in element.iter():
        if node.tag in {qn(W, "t"), qn(W, "delText"), qn(M, "t")}:
            pieces.append(node.text or "")
        elif node.tag == qn(W, "tab"):
            pieces.append("\t")
        elif node.tag in {qn(W, "br"), qn(W, "cr")}:
            pieces.append("\n")
        elif node.tag == qn(W, "noBreakHyphen"):
            pieces.append("‑")
        elif node.tag == qn(W, "softHyphen"):
            pieces.append("\u00ad")
    return "".join(pieces)


class DocumentParser:
    def __init__(
        self,
        package: DocxPackage,
        content_types: ContentTypeMap,
        relationships: list[Relationship],
    ) -> None:
        self.package = package
        self.content_types = content_types
        self.relationships = relationships
        self._styles = self._parse_styles()
        self._style_by_id = {style.style_id: style for style in self._styles}

    def parse(
        self,
    ) -> tuple[
        list[DocumentBlock],
        list[StyleDefinition],
        list[SectionSnapshot],
        list[StoryPartSnapshot],
        list[FieldSnapshot],
        list[MediaAsset],
        DocumentStatistics,
    ]:
        main_root = parse_xml(
            self.package.read_part("word/document.xml"),
            "word/document.xml",
        )
        blocks = self._parse_main_blocks(main_root)
        sections = self._parse_sections(main_root)
        story_parts, story_fields = self._parse_story_parts()
        fields = self._parse_fields(main_root, "word/document.xml") + story_fields
        media = self._parse_media()

        statistics = DocumentStatistics(
            block_count=len(blocks),
            paragraph_count=sum(block.kind == BlockKind.PARAGRAPH for block in blocks),
            table_count=sum(block.kind == BlockKind.TABLE for block in blocks),
            table_cell_count=sum(block.kind == BlockKind.TABLE_CELL for block in blocks),
            image_count=len(media),
            section_count=len(sections),
            field_count=len(fields),
            story_part_count=len(story_parts),
            character_count=sum(len(block.text) for block in blocks)
            + sum(len(part.text) for part in story_parts),
        )
        return (
            blocks,
            self._styles,
            sections,
            story_parts,
            sorted(fields, key=lambda item: (item.part_name, item.instruction, item.result_text)),
            media,
            statistics,
        )

    def _parse_styles(self) -> list[StyleDefinition]:
        if not self.package.has_part("word/styles.xml"):
            return []
        root = parse_xml(self.package.read_part("word/styles.xml"), "word/styles.xml")
        styles: list[StyleDefinition] = []
        for element in root.findall("./w:style", namespaces=NS):
            style_id = element.get(qn(W, "styleId"))
            if not style_id:
                continue
            styles.append(
                StyleDefinition(
                    style_id=style_id,
                    name=_word_value(element.find("w:name", namespaces=NS)),
                    style_type=element.get(qn(W, "type")),
                    based_on=_word_value(element.find("w:basedOn", namespaces=NS)),
                )
            )
        return sorted(styles, key=lambda style: style.style_id)

    def _parse_main_blocks(self, root: etree._Element) -> list[DocumentBlock]:
        body = root.find("w:body", namespaces=NS)
        if body is None:
            return []

        blocks: list[DocumentBlock] = []
        paragraph_index = 0
        table_index = 0
        order = 0

        for child in body:
            if child.tag == qn(W, "p"):
                blocks.append(self._paragraph_block(child, paragraph_index, order))
                paragraph_index += 1
                order += 1
            elif child.tag == qn(W, "tbl"):
                table_id = f"tbl-{table_index:04d}"
                rows = child.findall("w:tr", namespaces=NS)
                cells = child.findall("./w:tr/w:tc", namespaces=NS)
                blocks.append(
                    DocumentBlock(
                        id=table_id,
                        order=order,
                        kind=BlockKind.TABLE,
                        source_anchor=SourceAnchor(
                            table_index=table_index,
                            xml_path=child.getroottree().getpath(child),
                        ),
                        metadata={
                            "row_count": len(rows),
                            "cell_count": len(cells),
                        },
                    )
                )
                order += 1
                for row_index, row in enumerate(rows):
                    for cell_index, cell in enumerate(row.findall("w:tc", namespaces=NS)):
                        paragraphs = cell.findall("w:p", namespaces=NS)
                        text = "\n".join(visible_text(paragraph) for paragraph in paragraphs)
                        blocks.append(
                            DocumentBlock(
                                id=f"{table_id}-r{row_index:03d}-c{cell_index:03d}",
                                order=order,
                                kind=BlockKind.TABLE_CELL,
                                text=text,
                                parent_id=table_id,
                                source_anchor=SourceAnchor(
                                    table_index=table_index,
                                    row_index=row_index,
                                    cell_index=cell_index,
                                    xml_path=cell.getroottree().getpath(cell),
                                ),
                                metadata={"paragraph_count": len(paragraphs)},
                            )
                        )
                        order += 1
                table_index += 1
        return blocks

    def _paragraph_block(
        self,
        paragraph: etree._Element,
        paragraph_index: int,
        order: int,
    ) -> DocumentBlock:
        p_pr = paragraph.find("w:pPr", namespaces=NS)
        style_id = _word_value(
            p_pr.find("w:pStyle", namespaces=NS) if p_pr is not None else None
        )
        style_definition = self._style_by_id.get(style_id or "")
        r_pr = paragraph.find("w:r/w:rPr", namespaces=NS)
        fonts = r_pr.find("w:rFonts", namespaces=NS) if r_pr is not None else None
        size_half_points = _safe_int(
            _word_value(r_pr.find("w:sz", namespaces=NS) if r_pr is not None else None)
        )
        numbering = p_pr.find("w:numPr", namespaces=NS) if p_pr is not None else None
        breaks = paragraph.findall(".//w:br", namespaces=NS)

        metadata: dict[str, object] = {
            "page_break_count": sum(
                (_word_value(item, "type") or "textWrapping") == "page" for item in breaks
            ),
            "column_break_count": sum(
                (_word_value(item, "type") or "textWrapping") == "column" for item in breaks
            ),
            "has_drawing": bool(paragraph.findall(".//w:drawing", namespaces=NS)),
            "has_hyperlink": bool(paragraph.findall(".//w:hyperlink", namespaces=NS)),
        }
        if numbering is not None:
            metadata["numbering"] = {
                "num_id": _word_value(numbering.find("w:numId", namespaces=NS)),
                "level": _word_value(numbering.find("w:ilvl", namespaces=NS)),
            }

        return DocumentBlock(
            id=f"p-{paragraph_index:04d}",
            order=order,
            kind=BlockKind.PARAGRAPH,
            text=visible_text(paragraph),
            style=StyleSnapshot(
                style_id=style_id,
                style_name=style_definition.name if style_definition else None,
                font_east_asia=fonts.get(qn(W, "eastAsia")) if fonts is not None else None,
                font_latin=(
                    fonts.get(qn(W, "ascii")) or fonts.get(qn(W, "hAnsi"))
                    if fonts is not None
                    else None
                ),
                size_pt=size_half_points / 2 if size_half_points is not None else None,
                bold=_toggle_value(r_pr.find("w:b", namespaces=NS) if r_pr is not None else None),
                italic=_toggle_value(r_pr.find("w:i", namespaces=NS) if r_pr is not None else None),
                alignment=_word_value(
                    p_pr.find("w:jc", namespaces=NS) if p_pr is not None else None
                ),
            ),
            source_anchor=SourceAnchor(
                paragraph_index=paragraph_index,
                xml_path=paragraph.getroottree().getpath(paragraph),
            ),
            metadata=metadata,
        )

    def _parse_sections(self, root: etree._Element) -> list[SectionSnapshot]:
        sections: list[SectionSnapshot] = []
        for index, section in enumerate(root.findall(".//w:sectPr", namespaces=NS)):
            page_size = section.find("w:pgSz", namespaces=NS)
            margins = section.find("w:pgMar", namespaces=NS)
            page_number = section.find("w:pgNumType", namespaces=NS)
            sections.append(
                SectionSnapshot(
                    index=index,
                    start_type=_word_value(section.find("w:type", namespaces=NS)),
                    page_width_twips=_safe_int(_word_value(page_size, "w")),
                    page_height_twips=_safe_int(_word_value(page_size, "h")),
                    margin_top_twips=_safe_int(_word_value(margins, "top")),
                    margin_right_twips=_safe_int(_word_value(margins, "right")),
                    margin_bottom_twips=_safe_int(_word_value(margins, "bottom")),
                    margin_left_twips=_safe_int(_word_value(margins, "left")),
                    header_relationship_ids=sorted(
                        reference.get(qn(R, "id"), "")
                        for reference in section.findall("w:headerReference", namespaces=NS)
                    ),
                    footer_relationship_ids=sorted(
                        reference.get(qn(R, "id"), "")
                        for reference in section.findall("w:footerReference", namespaces=NS)
                    ),
                    page_number_format=_word_value(page_number, "fmt"),
                    page_number_start=_safe_int(_word_value(page_number, "start")),
                )
            )
        return sections

    def _parse_story_parts(self) -> tuple[list[StoryPartSnapshot], list[FieldSnapshot]]:
        stories: list[StoryPartSnapshot] = []
        fields: list[FieldSnapshot] = []
        for part_name in self.package.part_names():
            kind = self._story_kind(part_name)
            if kind is None:
                continue
            root = parse_xml(self.package.read_part(part_name), part_name)
            paragraphs = root.findall(".//w:p", namespaces=NS)
            text = "\n".join(visible_text(paragraph) for paragraph in paragraphs)
            stories.append(
                StoryPartSnapshot(
                    part_name=part_name,
                    kind=kind,
                    text=text,
                    paragraph_count=len(paragraphs),
                    text_sha256=_sha256_bytes(text.encode("utf-8")),
                )
            )
            fields.extend(self._parse_fields(root, part_name))
        return sorted(stories, key=lambda story: story.part_name), fields

    @staticmethod
    def _story_kind(part_name: str) -> StoryKind | None:
        for prefix, kind in STORY_PARTS:
            if part_name == prefix or (
                prefix in {"word/header", "word/footer"}
                and part_name.startswith(prefix)
                and part_name.endswith(".xml")
            ):
                return kind
        return None

    def _parse_fields(self, root: etree._Element, part_name: str) -> list[FieldSnapshot]:
        fields: list[FieldSnapshot] = []
        for field in root.findall(".//w:fldSimple", namespaces=NS):
            instruction = field.get(qn(W, "instr"), "").strip()
            fields.append(
                FieldSnapshot(
                    part_name=part_name,
                    instruction=instruction,
                    result_text=visible_text(field),
                    simple=True,
                )
            )
        for paragraph in root.findall(".//w:p", namespaces=NS):
            instruction_nodes = paragraph.findall(".//w:instrText", namespaces=NS)
            if not instruction_nodes:
                continue
            instruction = "".join(
                node.text or "" for node in instruction_nodes
            ).strip()
            if instruction:
                fields.append(
                    FieldSnapshot(
                        part_name=part_name,
                        instruction=instruction,
                        result_text=visible_text(paragraph),
                        simple=False,
                    )
                )
        return fields

    def _parse_media(self) -> list[MediaAsset]:
        assets: list[MediaAsset] = []
        for part_name in self.package.part_names():
            if not part_name.startswith("word/media/"):
                continue
            data = self.package.read_part(part_name)
            assets.append(
                MediaAsset(
                    part_name=part_name,
                    content_type=self.content_types.for_part(part_name),
                    size_bytes=len(data),
                    sha256=_sha256_bytes(data),
                )
            )
        return sorted(assets, key=lambda asset: asset.part_name)


def iter_xml_parts(package: DocxPackage, prefixes: Iterable[str] = ("word/",)) -> list[str]:
    return [
        part_name
        for part_name in package.part_names()
        if part_name.endswith(".xml") and any(part_name.startswith(prefix) for prefix in prefixes)
    ]
