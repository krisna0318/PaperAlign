from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Literal

from lxml import etree

from app.domain.analysis import SectionSnapshot
from app.domain.template_evidence import (
    BorderObservation,
    DirectFormatCluster,
    ParagraphStyleUsage,
    TableFormatObservation,
    TemplateEvidenceReport,
)
from app.parsers.docx_package import DocxPackage
from app.parsers.effective_format import EffectiveFormatResolver
from app.parsers.namespaces import NS, M, W, qn
from app.parsers.xml_utils import parse_xml


@dataclass(frozen=True)
class _DirectFormatKey:
    style_id: str | None
    style_name: str | None
    font_east_asia: str | None
    font_latin: str | None
    size_pt: float | None
    bold: bool | None
    italic: bool | None
    alignment: str | None
    line_rule: str | None
    line_value: int | None
    first_line_indent_twips: int | None
    first_line_indent_chars: int | None


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


def _has_visible_text(run: etree._Element) -> bool:
    return any(
        (node.text or "").strip()
        for node in run.iter()
        if node.tag in {qn(W, "t"), qn(M, "t")}
    )


def _parse_style_names(root: etree._Element | None) -> dict[str, str | None]:
    if root is None:
        return {}
    names: dict[str, str | None] = {}
    for style in root.findall("./w:style", namespaces=NS):
        style_id = style.get(qn(W, "styleId"))
        if style_id:
            names[style_id] = _word_value(style.find("w:name", namespaces=NS))
    return names


def _parse_sections(root: etree._Element) -> list[SectionSnapshot]:
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
                page_number_format=_word_value(page_number, "fmt"),
                page_number_start=_safe_int(_word_value(page_number, "start")),
            )
        )
    return sections


def _parse_paragraph_evidence(
    root: etree._Element,
    style_names: dict[str, str | None],
) -> tuple[list[ParagraphStyleUsage], list[DirectFormatCluster]]:
    body = root.find("w:body", namespaces=NS)
    if body is None:
        return [], []

    style_indexes: dict[tuple[str | None, str | None], list[int]] = defaultdict(list)
    format_indexes: dict[_DirectFormatKey, list[int]] = defaultdict(list)
    paragraphs = body.findall("w:p", namespaces=NS)

    for index, paragraph in enumerate(paragraphs):
        p_pr = paragraph.find("w:pPr", namespaces=NS)
        style_id = _word_value(p_pr.find("w:pStyle", namespaces=NS) if p_pr is not None else None)
        style_name = style_names.get(style_id or "")
        style_indexes[(style_id, style_name)].append(index)

        first_run = next(
            (run for run in paragraph.findall("w:r", namespaces=NS) if _has_visible_text(run)),
            None,
        )
        r_pr = first_run.find("w:rPr", namespaces=NS) if first_run is not None else None
        fonts = r_pr.find("w:rFonts", namespaces=NS) if r_pr is not None else None
        size_half_points = _safe_int(
            _word_value(r_pr.find("w:sz", namespaces=NS) if r_pr is not None else None)
        )
        spacing = p_pr.find("w:spacing", namespaces=NS) if p_pr is not None else None
        indentation = p_pr.find("w:ind", namespaces=NS) if p_pr is not None else None
        key = _DirectFormatKey(
            style_id=style_id,
            style_name=style_name,
            font_east_asia=fonts.get(qn(W, "eastAsia")) if fonts is not None else None,
            font_latin=(
                fonts.get(qn(W, "ascii")) or fonts.get(qn(W, "hAnsi"))
                if fonts is not None
                else None
            ),
            size_pt=size_half_points / 2 if size_half_points is not None else None,
            bold=_toggle_value(r_pr.find("w:b", namespaces=NS) if r_pr is not None else None),
            italic=_toggle_value(r_pr.find("w:i", namespaces=NS) if r_pr is not None else None),
            alignment=_word_value(p_pr.find("w:jc", namespaces=NS) if p_pr is not None else None),
            line_rule=_word_value(spacing, "lineRule"),
            line_value=_safe_int(_word_value(spacing, "line")),
            first_line_indent_twips=_safe_int(_word_value(indentation, "firstLine")),
            first_line_indent_chars=_safe_int(_word_value(indentation, "firstLineChars")),
        )
        format_indexes[key].append(index)

    style_usage = [
        ParagraphStyleUsage(
            style_id=style_id,
            style_name=style_name,
            paragraph_count=len(indexes),
            sample_paragraph_indexes=indexes[:5],
        )
        for (style_id, style_name), indexes in sorted(
            style_indexes.items(), key=lambda item: (item[0][0] or "", item[0][1] or "")
        )
    ]
    clusters = [
        DirectFormatCluster(
            **{
                field: getattr(key, field)
                for field in _DirectFormatKey.__dataclass_fields__
            },
            paragraph_count=len(indexes),
            sample_paragraph_indexes=indexes[:5],
        )
        for key, indexes in sorted(
            format_indexes.items(),
            key=lambda item: (
                -len(item[1]),
                item[0].style_id or "",
                item[0].font_east_asia or "",
                item[0].font_latin or "",
            ),
        )
    ]
    return style_usage, clusters


def _parse_border_container(
    parent: etree._Element | None,
    container_name: str,
    source_scope: Literal["table", "table_style", "cell"],
) -> list[BorderObservation]:
    if parent is None:
        return []
    container = parent.find(f"w:{container_name}", namespaces=NS)
    if container is None:
        return []
    observations: list[BorderObservation] = []
    for border in container:
        size = _safe_int(_word_value(border, "sz"))
        observations.append(
            BorderObservation(
                edge=etree.QName(border).localname,
                line_style=_word_value(border) or "none",
                size_eighth_points=size,
                size_pt=size / 8 if size is not None else None,
                color=_word_value(border, "color"),
                source_scope=source_scope,
            )
        )
    return observations


def _table_style_borders(
    styles_root: etree._Element | None,
) -> tuple[dict[str, str | None], dict[str, list[BorderObservation]]]:
    names: dict[str, str | None] = {}
    borders: dict[str, list[BorderObservation]] = {}
    if styles_root is None:
        return names, borders
    for style in styles_root.findall("./w:style", namespaces=NS):
        if style.get(qn(W, "type")) != "table":
            continue
        style_id = style.get(qn(W, "styleId"))
        if not style_id:
            continue
        names[style_id] = _word_value(style.find("w:name", namespaces=NS))
        borders[style_id] = _parse_border_container(
            style.find("w:tblPr", namespaces=NS),
            "tblBorders",
            "table_style",
        )
    return names, borders


def _is_positive(border: BorderObservation) -> bool:
    return border.line_style not in {"none", "nil"} and (border.size_pt or 0) > 0


def _widths(observations: list[BorderObservation], edges: set[str]) -> list[float]:
    return sorted(
        {
            border.size_pt
            for border in observations
            if border.edge in edges and _is_positive(border) and border.size_pt is not None
        }
    )


def _fallback_widths(
    primary: list[BorderObservation],
    table_borders: list[BorderObservation],
    style_borders: list[BorderObservation],
    edges: set[str],
) -> list[float]:
    return _widths(primary, edges) or _widths(table_borders, edges) or _widths(
        style_borders, edges
    )


def _parse_tables(
    root: etree._Element,
    table_style_names: dict[str, str | None],
    style_border_map: dict[str, list[BorderObservation]],
) -> list[TableFormatObservation]:
    body = root.find("w:body", namespaces=NS)
    if body is None:
        return []
    observations: list[TableFormatObservation] = []
    for table_index, table in enumerate(body.findall("w:tbl", namespaces=NS)):
        table_properties = table.find("w:tblPr", namespaces=NS)
        style_id = _word_value(
            table_properties.find("w:tblStyle", namespaces=NS)
            if table_properties is not None
            else None
        )
        direct_borders = _parse_border_container(
            table_properties,
            "tblBorders",
            "table",
        )
        style_borders = style_border_map.get(style_id or "", [])
        rows = table.findall("w:tr", namespaces=NS)
        row_cell_borders: list[list[list[BorderObservation]]] = []
        cell_border_counts: Counter[tuple[str, str, int | None, str | None]] = Counter()
        repeating_headers: list[int] = []
        column_count = 0

        for row_index, row in enumerate(rows):
            row_properties = row.find("w:trPr", namespaces=NS)
            if (
                row_properties is not None
                and row_properties.find("w:tblHeader", namespaces=NS) is not None
            ):
                repeating_headers.append(row_index)
            cells = row.findall("w:tc", namespaces=NS)
            column_count = max(column_count, len(cells))
            cell_sets: list[list[BorderObservation]] = []
            for cell in cells:
                cell_borders = _parse_border_container(
                    cell.find("w:tcPr", namespaces=NS),
                    "tcBorders",
                    "cell",
                )
                cell_sets.append(cell_borders)
                for border in cell_borders:
                    cell_border_counts[
                        (
                            border.edge,
                            border.line_style,
                            border.size_eighth_points,
                            border.color,
                        )
                    ] += 1
            row_cell_borders.append(cell_sets)

        aggregated_cell_borders = [
            BorderObservation(
                edge=edge,
                line_style=line_style,
                size_eighth_points=size,
                size_pt=size / 8 if size is not None else None,
                color=color,
                count=count,
                source_scope="cell",
            )
            for (edge, line_style, size, color), count in sorted(cell_border_counts.items())
        ]
        first_row = [
            border
            for row in row_cell_borders[:1]
            for cell in row
            for border in cell
        ]
        second_row = [
            border
            for row in row_cell_borders[1:2]
            for cell in row
            for border in cell
        ]
        last_row = [
            border
            for row in row_cell_borders[-1:]
            for cell in row
            for border in cell
        ]
        top_widths = _fallback_widths(
            first_row,
            direct_borders,
            style_borders,
            {"top"},
        )
        header_widths = _widths(first_row, {"bottom"})
        header_widths = sorted(set(header_widths + _widths(second_row, {"top"})))
        if not header_widths:
            header_widths = _widths(direct_borders, {"insideH"}) or _widths(
                style_borders, {"insideH"}
            )
        bottom_widths = _fallback_widths(
            last_row,
            direct_borders,
            style_borders,
            {"bottom"},
        )
        all_borders = [*style_borders, *direct_borders, *aggregated_cell_borders]
        vertical_present = any(
            border.edge in {"left", "right", "start", "end", "insideV"}
            and _is_positive(border)
            for border in all_borders
        )
        positive_borders = [border for border in all_borders if _is_positive(border)]
        if top_widths and bottom_widths and header_widths and not vertical_present:
            pattern: Literal["three_line", "grid", "borderless", "mixed", "unknown"] = "three_line"
            widths_are_consistent = all(
                len(value) == 1
                for value in (top_widths, header_widths, bottom_widths)
            )
            confidence = 0.95 if widths_are_consistent else 0.75
        elif vertical_present:
            pattern = "grid"
            confidence = 0.9
        elif not positive_borders:
            pattern = "borderless"
            confidence = 0.85
        elif positive_borders:
            pattern = "mixed"
            confidence = 0.6
        else:
            pattern = "unknown"
            confidence = 0.4

        grid = table.find("w:tblGrid", namespaces=NS)
        grid_elements = [] if grid is None else list(grid)
        grid_widths = [
            width
            for column in grid_elements
            if (width := _safe_int(_word_value(column, "w"))) is not None
        ]
        observations.append(
            TableFormatObservation(
                table_index=table_index,
                style_id=style_id,
                style_name=table_style_names.get(style_id or ""),
                row_count=len(rows),
                column_count=column_count,
                alignment=_word_value(
                    table_properties.find("w:jc", namespaces=NS)
                    if table_properties is not None
                    else None
                ),
                layout=_word_value(
                    table_properties.find("w:tblLayout", namespaces=NS)
                    if table_properties is not None
                    else None,
                    "type",
                ),
                grid_widths_twips=grid_widths,
                repeating_header_rows=repeating_headers,
                border_declarations=sorted(
                    [*style_borders, *direct_borders, *aggregated_cell_borders],
                    key=lambda item: (
                        item.source_scope,
                        item.edge,
                        item.line_style,
                        item.size_eighth_points if item.size_eighth_points is not None else -1,
                    ),
                ),
                outer_top_widths_pt=top_widths,
                header_separator_widths_pt=header_widths,
                outer_bottom_widths_pt=bottom_widths,
                vertical_borders_present=vertical_present,
                inferred_pattern=pattern,
                confidence=confidence,
            )
        )
    return observations


def extract_template_evidence(
    package: DocxPackage,
    *,
    extractor_version: str,
    file_name: str,
    input_sha256: str,
) -> TemplateEvidenceReport:
    document_root = parse_xml(package.read_part("word/document.xml"), "word/document.xml")
    styles_root = (
        parse_xml(package.read_part("word/styles.xml"), "word/styles.xml")
        if package.has_part("word/styles.xml")
        else None
    )
    style_names = _parse_style_names(styles_root)
    style_usage, format_clusters = _parse_paragraph_evidence(document_root, style_names)
    effective_format_resolver = EffectiveFormatResolver(styles_root)
    effective_formats = effective_format_resolver.resolve(document_root)
    table_style_names, style_borders = _table_style_borders(styles_root)
    tables = _parse_tables(document_root, table_style_names, style_borders)

    comment_count = 0
    if package.has_part("word/comments.xml"):
        comments_root = parse_xml(package.read_part("word/comments.xml"), "word/comments.xml")
        comment_count = len(comments_root.findall("./w:comment", namespaces=NS))

    sources = ["word/document.xml"]
    if styles_root is not None:
        sources.append("word/styles.xml")
    if package.has_part("word/comments.xml"):
        sources.append("word/comments.xml")

    warnings = [
        "Direct-format clusters use the first visible text run and are not "
        "resolved effective styles."
    ]
    warnings.extend(effective_format_resolver.warnings)
    if comment_count == 0:
        warnings.append(
            "No comments were present; observations were derived from document "
            "structure and formatting."
        )
    for table in tables:
        if any(
            len(widths) > 1
            for widths in (
                table.outer_top_widths_pt,
                table.header_separator_widths_pt,
                table.outer_bottom_widths_pt,
            )
        ):
            warnings.append(
                f"Table {table.table_index} has conflicting border widths and "
                "requires confirmation."
            )

    return TemplateEvidenceReport(
        extractor_version=extractor_version,
        file_name=file_name,
        input_sha256=input_sha256,
        comments_present=comment_count > 0,
        comment_count=comment_count,
        evidence_sources=sorted(sources),
        sections=_parse_sections(document_root),
        paragraph_style_usage=style_usage,
        direct_format_clusters=format_clusters,
        effective_formats=effective_formats,
        tables=tables,
        warnings=warnings,
    )
