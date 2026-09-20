"""Convert an already located format snapshot to a canonical atomic observation."""

from app.domain.blocks import SourceAnchor
from app.domain.rule_validation import RuleObservation
from app.domain.rules import BooleanValue, NumberValue, PropertyPath, RuleValue, TextValue
from app.domain.template_evidence import EffectiveParagraphFormat
from app.validation.units import hundredths_to_chars, ooxml_line_spacing, twips_to_pt


def observe_format(
    snapshot: EffectiveParagraphFormat, path: PropertyPath, *, run_group: int | None = None
) -> RuleObservation:
    locator = SourceAnchor(paragraph_index=snapshot.paragraph_index)

    def unknown(reason: str) -> RuleObservation:
        return RuleObservation(supported=False, locator=locator, reason=reason)

    if snapshot.resolution_warnings:
        return unknown("incomplete_style_resolution")
    sources: dict[str, str] = {}
    value: RuleValue | None = None
    if path.value.startswith("run."):
        if run_group is None:
            if len(snapshot.runs) != 1:
                return unknown("explicit_run_group_required")
            run_group = 0
        if run_group < 0 or run_group >= len(snapshot.runs):
            return unknown("run_group_out_of_range")
        props = snapshot.runs[run_group].properties
        key = path.value.removeprefix("run.")
        if key in props.unresolved:
            return unknown(props.unresolved[key])
        raw = getattr(props, key, None)
        if isinstance(raw, bool):
            value = BooleanValue(value=raw)
        elif isinstance(raw, (float, int)):
            value = NumberValue(value=float(raw), unit="pt")
        elif isinstance(raw, str):
            value = TextValue(value=raw)
        if key in props.sources:
            sources[key] = props.sources[key]
    elif path.value.startswith("paragraph."):
        paragraph = snapshot.paragraph
        key = path.value.removeprefix("paragraph.").replace("_pt", "_twips")
        if key in paragraph.unresolved:
            return unknown(paragraph.unresolved[key])
        if path == PropertyPath.LINE_SPACING:
            value = ooxml_line_spacing(paragraph.line_value, paragraph.line_rule)
            sources = {
                k: v for k, v in paragraph.sources.items() if k in {"line_value", "line_rule"}
            }
        else:
            raw = getattr(paragraph, key, None)
            if path == PropertyPath.FIRST_LINE_PT and paragraph.first_line_indent_chars is not None:
                return unknown("character_indent_takes_precedence")
            if isinstance(raw, bool):
                value = BooleanValue(value=raw)
            elif isinstance(raw, int):
                if key.endswith("_twips"):
                    value = NumberValue(value=twips_to_pt(raw), unit="pt")
                elif key.endswith("_chars"):
                    value = NumberValue(value=hundredths_to_chars(raw), unit="chars")
                elif key == "outline_level":
                    value = NumberValue(value=float(raw), unit="level")
            elif isinstance(raw, str):
                value = TextValue(value=raw)
            if key in paragraph.sources:
                sources[key] = paragraph.sources[key]
    else:
        return unknown("property_not_supported_by_paragraph_adapter")
    if value is None:
        return unknown("actual_value_unresolved")
    return RuleObservation(value=value, locator=locator, sources=sources)
