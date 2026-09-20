from app.domain.analysis import SectionSnapshot
from app.domain.blocks import SourceAnchor
from app.domain.rule_validation import RuleObservation
from app.domain.rules import BooleanValue, NumberValue, PropertyPath, RuleValue
from app.domain.template_evidence import TableFormatObservation
from app.validation.units import twips_to_mm


def observe_table(table: TableFormatObservation, path: PropertyPath) -> RuleObservation:
    locator = SourceAnchor(table_index=table.table_index)
    widths = {
        PropertyPath.BORDER_TOP: table.outer_top_widths_pt,
        PropertyPath.BORDER_MIDDLE: table.header_separator_widths_pt,
        PropertyPath.BORDER_BOTTOM: table.outer_bottom_widths_pt,
    }
    value: RuleValue | None = None
    if table.inferred_pattern not in {"mixed", "unknown"}:
        if path in widths and len(widths[path]) == 1:
            value = NumberValue(value=widths[path][0], unit="pt")
        elif path == PropertyPath.VERTICAL_BORDERS:
            value = BooleanValue(value=table.vertical_borders_present)
    return RuleObservation(
        value=value,
        supported=value is not None,
        locator=locator,
        sources={path.value: f"template_table:{table.table_index}"},
        reason=None if value is not None else "table_property_ambiguous_or_unsupported",
    )


def observe_section(section: SectionSnapshot, path: PropertyPath) -> RuleObservation:
    mapping = {
        PropertyPath.PAGE_WIDTH: section.page_width_twips,
        PropertyPath.PAGE_HEIGHT: section.page_height_twips,
        PropertyPath.MARGIN_TOP: section.margin_top_twips,
        PropertyPath.MARGIN_BOTTOM: section.margin_bottom_twips,
        PropertyPath.MARGIN_LEFT: section.margin_left_twips,
        PropertyPath.MARGIN_RIGHT: section.margin_right_twips,
    }
    raw = mapping.get(path)
    locator = SourceAnchor(xml_path=f"(//w:sectPr)[{section.index + 1}]")
    return RuleObservation(
        value=NumberValue(value=twips_to_mm(raw), unit="mm") if raw is not None else None,
        supported=raw is not None,
        locator=locator,
        sources={path.value: "section_ooxml"},
        reason=None if raw is not None else "section_property_unresolved",
    )
