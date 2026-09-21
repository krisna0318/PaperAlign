from pathlib import Path

import pytest

from app.formatting.safe_formatter import ABBREVIATION_RULE_IDS, format_docx
from app.parsers.errors import DocxAnalysisError
from app.services.analyzer import analyze_docx
from app.services.template_inspector import inspect_template
from tests.support.docx_factory import create_synthetic_docx


def test_formats_confirmed_abbreviation_table_without_changing_content(tmp_path: Path) -> None:
    source = create_synthetic_docx(
        tmp_path / "source.docx", heading_text="缩略词表", include_second_table_row=True
    )
    output = tmp_path / "formatted.docx"
    original = source.read_bytes()

    plan, report = format_docx(source, output, sorted(ABBREVIATION_RULE_IDS))

    assert output.is_file()
    assert source.read_bytes() == original
    assert report.content_preserved is True
    assert report.content_fingerprint_before == report.content_fingerprint_after
    output_fingerprint = analyze_docx(output).content_fingerprint.aggregate_sha256
    assert report.content_fingerprint_after == output_fingerprint
    assert len(plan.targets) == 1
    assert len(report.operations) == 4
    table = inspect_template(output).report.tables[0]
    assert table.inferred_pattern == "three_line"
    assert table.outer_top_widths_pt == [1.5]
    assert table.header_separator_widths_pt == [1.0]
    assert table.outer_bottom_widths_pt == [1.5]
    assert table.vertical_borders_present is False


def test_formatter_requires_complete_approved_rule_group(tmp_path: Path) -> None:
    source = create_synthetic_docx(tmp_path / "source.docx", heading_text="缩略词表")

    with pytest.raises(DocxAnalysisError, match="four confirmed") as exc:
        format_docx(source, tmp_path / "formatted.docx", [next(iter(ABBREVIATION_RULE_IDS))])

    assert exc.value.code == "incomplete_rule_group"
    assert not (tmp_path / "formatted.docx").exists()


def test_formatter_refuses_ambiguous_table_target(tmp_path: Path) -> None:
    source = create_synthetic_docx(tmp_path / "source.docx")

    with pytest.raises(DocxAnalysisError, match="No unambiguous") as exc:
        format_docx(source, tmp_path / "formatted.docx", sorted(ABBREVIATION_RULE_IDS))

    assert exc.value.code == "no_confirmed_format_target"


def test_formatter_refuses_blocking_unsupported_objects(tmp_path: Path) -> None:
    source = create_synthetic_docx(
        tmp_path / "source.docx", heading_text="缩略词表", include_unsupported=True
    )

    with pytest.raises(DocxAnalysisError, match="unsafe") as exc:
        format_docx(source, tmp_path / "formatted.docx", sorted(ABBREVIATION_RULE_IDS))

    assert exc.value.code == "unsupported_object_blocks_formatting"


def test_formatter_never_overwrites_an_existing_output(tmp_path: Path) -> None:
    source = create_synthetic_docx(tmp_path / "source.docx", heading_text="缩略词表")
    output = tmp_path / "formatted.docx"
    output.write_bytes(b"keep me")

    with pytest.raises(DocxAnalysisError, match="already exists"):
        format_docx(source, output, sorted(ABBREVIATION_RULE_IDS))

    assert output.read_bytes() == b"keep me"
