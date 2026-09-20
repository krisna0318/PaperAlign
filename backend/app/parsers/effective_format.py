from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from lxml import etree

from app.domain.template_evidence import (
    EffectiveParagraphFormat,
    EffectiveParagraphProperties,
    EffectiveRunFormatGroup,
    EffectiveRunProperties,
)
from app.parsers.namespaces import NS, M, W, qn

type PropertyValue = str | int | float | bool


@dataclass(frozen=True)
class _StyleNode:
    style_id: str
    style_type: str
    name: str | None
    based_on: str | None
    paragraph_properties: dict[str, PropertyValue]
    run_properties: dict[str, PropertyValue]


@dataclass
class _PropertyState:
    values: dict[str, PropertyValue] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)

    def overlay(self, values: dict[str, PropertyValue], source: str) -> None:
        for key, value in values.items():
            if key.startswith("_unresolved_"):
                property_name = key.removeprefix("_unresolved_")
                self.values.pop(property_name, None)
                self.sources.pop(property_name, None)
                self.values[key] = value
                continue
            self.values.pop(f"_unresolved_{key}", None)
            # Style toggles invert inherited state; direct formatting sets absolute state.
            if key in {"bold", "italic"} and "_style:" in source:
                if value is False:
                    continue
                value = not self.values.get(key, False)
            self.values[key] = value
            self.sources[key] = source


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


def _set_if_not_none(
    target: dict[str, PropertyValue],
    name: str,
    value: PropertyValue | None,
) -> None:
    if value is not None:
        target[name] = value


def _parse_paragraph_properties(
    properties: etree._Element | None,
) -> dict[str, PropertyValue]:
    if properties is None:
        return {}
    values: dict[str, PropertyValue] = {}
    _set_if_not_none(values, "alignment", _word_value(properties.find("w:jc", namespaces=NS)))

    spacing = properties.find("w:spacing", namespaces=NS)
    _set_if_not_none(values, "line_rule", _word_value(spacing, "lineRule"))
    _set_if_not_none(values, "line_value", _safe_int(_word_value(spacing, "line")))
    _set_if_not_none(
        values,
        "space_before_twips",
        _safe_int(_word_value(spacing, "before")),
    )
    _set_if_not_none(
        values,
        "space_after_twips",
        _safe_int(_word_value(spacing, "after")),
    )
    if spacing is not None:
        for side in ("before", "after"):
            if any(
                spacing.get(qn(W, attr)) is not None
                for attr in (f"{side}Lines", f"{side}Autospacing")
            ):
                values[f"_unresolved_space_{side}_twips"] = "line_based_or_auto_spacing"

    indentation = properties.find("w:ind", namespaces=NS)
    _set_if_not_none(
        values,
        "first_line_indent_twips",
        _safe_int(_word_value(indentation, "firstLine")),
    )
    _set_if_not_none(
        values,
        "first_line_indent_chars",
        _safe_int(_word_value(indentation, "firstLineChars")),
    )
    _set_if_not_none(
        values,
        "left_indent_twips",
        _safe_int(_word_value(indentation, "left")),
    )
    _set_if_not_none(
        values,
        "right_indent_twips",
        _safe_int(_word_value(indentation, "right")),
    )
    if indentation is not None and any(
        indentation.get(qn(W, name)) is not None for name in ("hanging", "hangingChars")
    ):
        values["_unresolved_first_line_indent_twips"] = "hanging_indent_not_resolved"
        values["_unresolved_first_line_indent_chars"] = "hanging_indent_not_resolved"
    _set_if_not_none(
        values,
        "outline_level",
        _safe_int(_word_value(properties.find("w:outlineLvl", namespaces=NS))),
    )
    _set_if_not_none(
        values,
        "keep_with_next",
        _toggle_value(properties.find("w:keepNext", namespaces=NS)),
    )
    _set_if_not_none(
        values,
        "page_break_before",
        _toggle_value(properties.find("w:pageBreakBefore", namespaces=NS)),
    )
    return values


def _parse_run_properties(properties: etree._Element | None) -> dict[str, PropertyValue]:
    if properties is None:
        return {}
    values: dict[str, PropertyValue] = {}
    fonts = properties.find("w:rFonts", namespaces=NS)
    if fonts is not None:
        _set_if_not_none(values, "font_east_asia", fonts.get(qn(W, "eastAsia")))
        _set_if_not_none(
            values,
            "font_latin",
            fonts.get(qn(W, "ascii")),
        )
        _set_if_not_none(values, "font_high_ansi", fonts.get(qn(W, "hAnsi")))
        _set_if_not_none(values, "font_complex_script", fonts.get(qn(W, "cs")))
        for attribute, property_name in (
            ("asciiTheme", "font_latin"),
            ("hAnsiTheme", "font_high_ansi"),
            ("eastAsiaTheme", "font_east_asia"),
            ("cstheme", "font_complex_script"),
        ):
            if fonts.get(qn(W, attribute)) is not None:
                values[f"_unresolved_{property_name}"] = "theme_font_not_resolved"
    size_half_points = _safe_int(_word_value(properties.find("w:sz", namespaces=NS)))
    _set_if_not_none(
        values,
        "size_pt",
        size_half_points / 2 if size_half_points is not None else None,
    )
    _set_if_not_none(values, "bold", _toggle_value(properties.find("w:b", namespaces=NS)))
    _set_if_not_none(values, "italic", _toggle_value(properties.find("w:i", namespaces=NS)))
    _set_if_not_none(values, "color", _word_value(properties.find("w:color", namespaces=NS)))
    return values


def _has_visible_text(run: etree._Element) -> bool:
    return any(
        (node.text or "").strip() for node in run.iter() if node.tag in {qn(W, "t"), qn(M, "t")}
    )


def _string_property(values: dict[str, PropertyValue], name: str) -> str | None:
    value = values.get(name)
    return value if isinstance(value, str) else None


def _int_property(values: dict[str, PropertyValue], name: str) -> int | None:
    value = values.get(name)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _float_property(values: dict[str, PropertyValue], name: str) -> float | None:
    value = values.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _bool_property(values: dict[str, PropertyValue], name: str) -> bool | None:
    value = values.get(name)
    return value if isinstance(value, bool) else None


def _effective_paragraph_properties(state: _PropertyState) -> EffectiveParagraphProperties:
    return EffectiveParagraphProperties(
        alignment=_string_property(state.values, "alignment"),
        line_rule=_string_property(state.values, "line_rule"),
        line_value=_int_property(state.values, "line_value"),
        space_before_twips=_int_property(state.values, "space_before_twips"),
        space_after_twips=_int_property(state.values, "space_after_twips"),
        first_line_indent_twips=_int_property(state.values, "first_line_indent_twips"),
        first_line_indent_chars=_int_property(state.values, "first_line_indent_chars"),
        left_indent_twips=_int_property(state.values, "left_indent_twips"),
        right_indent_twips=_int_property(state.values, "right_indent_twips"),
        outline_level=_int_property(state.values, "outline_level"),
        keep_with_next=_bool_property(state.values, "keep_with_next"),
        page_break_before=_bool_property(state.values, "page_break_before"),
        sources=dict(state.sources),
        unresolved=_unresolved(state),
    )


def _effective_run_properties(state: _PropertyState) -> EffectiveRunProperties:
    return EffectiveRunProperties(
        font_east_asia=_string_property(state.values, "font_east_asia"),
        font_latin=_string_property(state.values, "font_latin"),
        font_high_ansi=_string_property(state.values, "font_high_ansi"),
        font_complex_script=_string_property(state.values, "font_complex_script"),
        size_pt=_float_property(state.values, "size_pt"),
        bold=_bool_property(state.values, "bold"),
        italic=_bool_property(state.values, "italic"),
        color=_string_property(state.values, "color"),
        sources=dict(state.sources),
        unresolved=_unresolved(state),
    )


def _unresolved(state: _PropertyState) -> dict[str, str]:
    return {
        key.removeprefix("_unresolved_"): str(value)
        for key, value in state.values.items()
        if key.startswith("_unresolved_")
    }


class EffectiveFormatResolver:
    def __init__(self, styles_root: etree._Element | None) -> None:
        self.styles: dict[str, _StyleNode] = {}
        self.warnings: list[str] = []
        self.default_paragraph_style_id: str | None = None
        self.default_paragraph_properties: dict[str, PropertyValue] = {}
        self.default_run_properties: dict[str, PropertyValue] = {}
        self._parse_styles(styles_root)

    def _parse_styles(self, root: etree._Element | None) -> None:
        if root is None:
            return
        document_defaults = root.find("w:docDefaults", namespaces=NS)
        if document_defaults is not None:
            paragraph_default = document_defaults.find(
                "w:pPrDefault/w:pPr",
                namespaces=NS,
            )
            run_default = document_defaults.find("w:rPrDefault/w:rPr", namespaces=NS)
            self.default_paragraph_properties = _parse_paragraph_properties(paragraph_default)
            self.default_run_properties = _parse_run_properties(run_default)

        for style_element in root.findall("./w:style", namespaces=NS):
            style_id = style_element.get(qn(W, "styleId"))
            style_type = style_element.get(qn(W, "type"))
            if not style_id or not style_type:
                continue
            node = _StyleNode(
                style_id=style_id,
                style_type=style_type,
                name=_word_value(style_element.find("w:name", namespaces=NS)),
                based_on=_word_value(style_element.find("w:basedOn", namespaces=NS)),
                paragraph_properties=_parse_paragraph_properties(
                    style_element.find("w:pPr", namespaces=NS)
                ),
                run_properties=_parse_run_properties(style_element.find("w:rPr", namespaces=NS)),
            )
            self.styles[style_id] = node
            if style_type == "paragraph":
                default_value = style_element.get(qn(W, "default"))
                if default_value is not None and default_value.casefold() not in {
                    "0",
                    "false",
                    "off",
                    "no",
                }:
                    self.default_paragraph_style_id = style_id

        if self.default_paragraph_style_id is None:
            for candidate in ("Normal", "1"):
                candidate_style = self.styles.get(candidate)
                if candidate_style is not None and candidate_style.style_type == "paragraph":
                    self.default_paragraph_style_id = candidate
                    break

    def _style_chain(self, style_id: str | None, expected_type: str) -> list[_StyleNode]:
        if style_id is None:
            return []
        chain: list[_StyleNode] = []
        seen: set[str] = set()
        current_id: str | None = style_id
        while current_id is not None:
            if current_id in seen:
                self.warnings.append(f"Style inheritance cycle detected at {current_id}.")
                break
            seen.add(current_id)
            style = self.styles.get(current_id)
            if style is None:
                self.warnings.append(f"Referenced style {current_id} is missing.")
                break
            if style.style_type != expected_type:
                self.warnings.append(
                    f"Style {current_id} has type {style.style_type}, expected {expected_type}."
                )
                break
            chain.append(style)
            current_id = style.based_on
        chain.reverse()
        return chain

    def resolve(self, document_root: etree._Element) -> list[EffectiveParagraphFormat]:
        body = document_root.find("w:body", namespaces=NS)
        if body is None:
            return []
        results: list[EffectiveParagraphFormat] = []
        for paragraph_index, paragraph in enumerate(body.findall("w:p", namespaces=NS)):
            warning_start = len(self.warnings)
            paragraph_properties = paragraph.find("w:pPr", namespaces=NS)
            explicit_style_id = _word_value(
                paragraph_properties.find("w:pStyle", namespaces=NS)
                if paragraph_properties is not None
                else None
            )
            style_id = explicit_style_id or self.default_paragraph_style_id
            paragraph_chain = self._style_chain(style_id, "paragraph")
            paragraph_state = _PropertyState()
            paragraph_state.overlay(self.default_paragraph_properties, "doc_defaults")
            run_base_state = _PropertyState()
            run_base_state.overlay({"bold": False, "italic": False}, "spec_default")
            run_base_state.overlay(self.default_run_properties, "doc_defaults")
            for style in paragraph_chain:
                source = f"paragraph_style:{style.style_id}"
                paragraph_state.overlay(style.paragraph_properties, source)
                run_base_state.overlay(style.run_properties, source)
            paragraph_state.overlay(
                _parse_paragraph_properties(paragraph_properties),
                "direct_paragraph",
            )

            grouped_runs: dict[
                tuple[
                    str | None,
                    str | None,
                    tuple[tuple[str, PropertyValue], ...],
                    tuple[tuple[str, str], ...],
                ],
                list[int],
            ] = defaultdict(list)
            run_properties_by_key: dict[
                tuple[
                    str | None,
                    str | None,
                    tuple[tuple[str, PropertyValue], ...],
                    tuple[tuple[str, str], ...],
                ],
                EffectiveRunProperties,
            ] = {}
            for run_index, run in enumerate(paragraph.findall(".//w:r", namespaces=NS)):
                if any(a.tag in {qn(W, "txbxContent"), qn(W, "del")} for a in run.iterancestors()):
                    continue
                if not _has_visible_text(run):
                    continue
                direct_run_properties = run.find("w:rPr", namespaces=NS)
                character_style_id = _word_value(
                    direct_run_properties.find("w:rStyle", namespaces=NS)
                    if direct_run_properties is not None
                    else None
                )
                character_chain = self._style_chain(character_style_id, "character")
                run_state = _PropertyState(
                    values=dict(run_base_state.values),
                    sources=dict(run_base_state.sources),
                )
                for style in character_chain:
                    run_state.overlay(
                        style.run_properties,
                        f"character_style:{style.style_id}",
                    )
                run_state.overlay(_parse_run_properties(direct_run_properties), "direct_run")
                character_style_name = (
                    self.styles[character_style_id].name
                    if character_style_id in self.styles
                    else None
                )
                key = (
                    character_style_id,
                    character_style_name,
                    tuple(sorted(run_state.values.items())),
                    tuple(sorted(run_state.sources.items())),
                )
                grouped_runs[key].append(run_index)
                run_properties_by_key[key] = _effective_run_properties(run_state)

            run_groups = [
                EffectiveRunFormatGroup(
                    character_style_id=key[0],
                    character_style_name=key[1],
                    properties=run_properties_by_key[key],
                    run_count=len(indexes),
                    sample_run_indexes=indexes[:5],
                )
                for key, indexes in sorted(
                    grouped_runs.items(),
                    key=lambda item: (item[1][0], item[0][0] or ""),
                )
            ]
            paragraph_style_name = self.styles[style_id].name if style_id in self.styles else None
            results.append(
                EffectiveParagraphFormat(
                    paragraph_index=paragraph_index,
                    paragraph_style_id=style_id,
                    paragraph_style_name=paragraph_style_name,
                    paragraph=_effective_paragraph_properties(paragraph_state),
                    runs=run_groups,
                    resolution_warnings=list(dict.fromkeys(self.warnings[warning_start:])),
                )
            )
        return results
