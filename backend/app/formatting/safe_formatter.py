from __future__ import annotations

import os
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree

from app import __version__
from app.domain.enums import BlockKind, RuleStatus
from app.domain.formatting import (
    FormattingOperation,
    FormattingPlan,
    FormattingReport,
    FormattingTarget,
)
from app.domain.rules import BooleanValue, FormatRule, NumberValue, PropertyPath, RuleScope
from app.parsers.docx_package import DocxPackage, sha256_file
from app.parsers.errors import DocxAnalysisError
from app.parsers.namespaces import NS, W, qn
from app.parsers.xml_utils import parse_xml
from app.profiles.loader import load_profile
from app.services.analyzer import analyze_docx
from app.services.structure_service import inspect_structure

ABBREVIATION_RULE_IDS = frozenset(
    {
        "SCAU-P0-ABBREVIATION-TABLE-001-01",
        "SCAU-P0-ABBREVIATION-TABLE-001-02",
        "SCAU-P0-ABBREVIATION-TABLE-001-03",
        "SCAU-P0-ABBREVIATION-TABLE-001-04",
    }
)


def build_formatting_plan(input_path: Path, approved_rule_ids: list[str]) -> FormattingPlan:
    approved = set(approved_rule_ids)
    if len(approved) != len(approved_rule_ids):
        raise DocxAnalysisError("duplicate_rule_approval", "Approved rule IDs must be unique")
    if approved != ABBREVIATION_RULE_IDS:
        raise DocxAnalysisError(
            "incomplete_rule_group",
            "The four confirmed abbreviation-table border rules must be approved together",
        )
    bundle = load_profile()
    rules = {rule.id: rule for rule in bundle.rules if rule.id in approved}
    if set(rules) != approved:
        raise DocxAnalysisError("unknown_format_rule", "Formatting approval contains unknown rules")
    if any(
        rule.status != RuleStatus.CONFIRMED
        or not rule.auto_fixable
        or rule.scope != RuleScope.ABBREVIATION_TABLE
        for rule in rules.values()
    ):
        raise DocxAnalysisError(
            "rule_not_format_authorized", "A selected rule is not confirmed and auto-fixable"
        )
    analysis = analyze_docx(input_path)
    blocking = [
        item for item in analysis.unsupported_objects.objects if item.policy == "block_formatting"
    ]
    if blocking:
        raise DocxAnalysisError(
            "unsupported_object_blocks_formatting",
            "The document contains objects that make automatic formatting unsafe",
        )
    structure = inspect_structure(input_path)
    targets = [
        FormattingTarget(
            block_id=item.block_id,
            table_index=item.locator.table_index,
            rule_ids=sorted(approved),
            locator=item.locator,
        )
        for item in structure.decisions
        if item.kind == BlockKind.TABLE
        and item.scope == RuleScope.ABBREVIATION_TABLE
        and not item.requires_confirmation
        and item.locator.table_index is not None
    ]
    if not targets:
        raise DocxAnalysisError(
            "no_confirmed_format_target",
            "No unambiguous abbreviation table was found; confirm document structure first",
        )
    return FormattingPlan(
        engine_version=__version__,
        profile_id=bundle.manifest.profile_id,
        input_sha256=analysis.document_profile.package.input_sha256,
        content_fingerprint_before=analysis.content_fingerprint.aggregate_sha256,
        approved_rule_ids=sorted(approved),
        targets=targets,
    )


def format_docx(
    input_path: Path,
    output_path: Path,
    approved_rule_ids: list[str],
) -> tuple[FormattingPlan, FormattingReport]:
    input_path = input_path.resolve()
    output_path = output_path.resolve()
    if input_path == output_path:
        raise DocxAnalysisError("output_input_collision", "Formatting output cannot replace input")
    if output_path.exists():
        raise DocxAnalysisError("output_exists", "Formatting output already exists")
    if output_path.suffix.lower() != ".docx":
        raise DocxAnalysisError("invalid_output_type", "Formatting output must be .docx")
    plan = build_formatting_plan(input_path, approved_rule_ids)
    rules = {rule.id: rule for rule in load_profile().rules if rule.id in plan.approved_rule_ids}
    with DocxPackage(input_path) as package:
        document_xml = package.read_part("word/document.xml")
    root = parse_xml(document_xml, "word/document.xml")
    body = root.find("w:body", namespaces=NS)
    if body is None:
        raise DocxAnalysisError("missing_document_body", "DOCX has no document body")
    tables = body.findall("w:tbl", namespaces=NS)
    operations: list[FormattingOperation] = []
    for target in plan.targets:
        if target.table_index >= len(tables):
            raise DocxAnalysisError("format_target_moved", "Formatting target no longer exists")
        table = tables[target.table_index]
        operations.extend(_format_abbreviation_table(table, target, rules))
    formatted_xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _rewrite_package(input_path, output_path.parent, formatted_xml)
    try:
        after = analyze_docx(temporary)
        after_fingerprint = after.content_fingerprint.aggregate_sha256
        if after_fingerprint != plan.content_fingerprint_before:
            raise DocxAnalysisError(
                "content_fingerprint_changed",
                "Formatting changed protected document content; output was rejected",
            )
        os.replace(temporary, output_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    report = FormattingReport(
        engine_version=__version__,
        profile_id=plan.profile_id,
        input_sha256=plan.input_sha256,
        output_sha256=sha256_file(output_path),
        content_fingerprint_before=plan.content_fingerprint_before,
        content_fingerprint_after=after_fingerprint,
        content_preserved=True,
        applied_rule_ids=plan.approved_rule_ids,
        operations=operations,
        warnings=[
            "Static OOXML validation cannot prove final pagination or Word rendering.",
            "Open the output in desktop Word and complete the M7 checklist.",
        ],
    )
    return plan, report


def _format_abbreviation_table(
    table: etree._Element,
    target: FormattingTarget,
    rules: dict[str, FormatRule],
) -> list[FormattingOperation]:
    before_xml = etree.tostring(table, encoding="unicode")
    by_path = {rule.property_path: rule for rule in rules.values()}
    top = _number_value(by_path[PropertyPath.BORDER_TOP])
    middle = _number_value(by_path[PropertyPath.BORDER_MIDDLE])
    bottom = _number_value(by_path[PropertyPath.BORDER_BOTTOM])
    vertical = by_path[PropertyPath.VERTICAL_BORDERS].expected_value
    if not isinstance(vertical, BooleanValue) or vertical.value:
        raise DocxAnalysisError("invalid_format_rule", "Vertical border rule must be false")

    table_properties = _ensure_child(table, "tblPr", first=True)
    table_borders = _ensure_child(table_properties, "tblBorders")
    _set_border(table_borders, "top", top)
    _set_border(table_borders, "bottom", bottom)
    _set_border(table_borders, "insideH", None)
    for edge in ("left", "right", "start", "end", "insideV"):
        _set_border(table_borders, edge, None)
    rows = table.findall("w:tr", namespaces=NS)
    if len(rows) < 2:
        raise DocxAnalysisError(
            "insufficient_table_rows",
            "Abbreviation table needs a header row and at least one data row",
        )
    for row_index, row in enumerate(rows):
        for cell in row.findall("w:tc", namespaces=NS):
            cell_properties = _ensure_child(cell, "tcPr", first=True)
            cell_borders = _ensure_child(cell_properties, "tcBorders")
            for edge in ("left", "right", "start", "end", "insideV"):
                _set_border(cell_borders, edge, None)
            _set_border(cell_borders, "top", top if row_index == 0 else None)
            bottom_width = middle if row_index == 0 else None
            if row_index == len(rows) - 1:
                bottom_width = bottom
            _set_border(cell_borders, "bottom", bottom_width)
    after_xml = etree.tostring(table, encoding="unicode")
    paths = [
        PropertyPath.BORDER_TOP,
        PropertyPath.BORDER_MIDDLE,
        PropertyPath.BORDER_BOTTOM,
        PropertyPath.VERTICAL_BORDERS,
    ]
    return [
        FormattingOperation(
            rule_id=by_path[path].id,
            block_id=target.block_id,
            property_path=path,
            locator=target.locator,
            before={"table_xml_sha256": _text_sha256(before_xml)},
            after={"table_xml_sha256": _text_sha256(after_xml)},
        )
        for path in paths
    ]


def _number_value(rule: FormatRule) -> float:
    value = rule.expected_value
    if not isinstance(value, NumberValue) or value.unit != "pt":
        raise DocxAnalysisError("invalid_format_rule", "Border width rule must use points")
    return value.value


def _ensure_child(
    parent: etree._Element, local_name: str, *, first: bool = False
) -> etree._Element:
    child = parent.find(f"w:{local_name}", namespaces=NS)
    if child is None:
        child = etree.Element(qn(W, local_name))
        if first:
            parent.insert(0, child)
        else:
            parent.append(child)
    return child


def _set_border(container: etree._Element, edge: str, width_pt: float | None) -> None:
    border = _ensure_child(container, edge)
    if width_pt is None:
        border.set(qn(W, "val"), "nil")
        border.set(qn(W, "sz"), "0")
    else:
        border.set(qn(W, "val"), "single")
        border.set(qn(W, "sz"), str(round(width_pt * 8)))
        border.set(qn(W, "color"), "auto")


def _rewrite_package(input_path: Path, output_dir: Path, document_xml: bytes) -> Path:
    with tempfile.NamedTemporaryFile(dir=output_dir, suffix=".docx", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with ZipFile(input_path, "r") as source, ZipFile(
            temporary, "w", compression=ZIP_DEFLATED
        ) as destination:
            for info in source.infolist():
                payload = (
                    document_xml if info.filename == "word/document.xml" else source.read(info)
                )
                destination.writestr(info, payload)
        return temporary
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _text_sha256(value: str) -> str:
    from hashlib import sha256

    return sha256(value.encode("utf-8")).hexdigest()
