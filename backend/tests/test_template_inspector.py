import json
from pathlib import Path

from app.services.template_inspector import inspect_template, write_template_artifacts
from paperalign.cli import main
from tests.support.docx_factory import create_synthetic_docx


def test_extracts_template_evidence_without_comments(tmp_path: Path) -> None:
    input_path = create_synthetic_docx(
        tmp_path / "template.docx",
        include_three_line_table=True,
    )

    artifacts = inspect_template(input_path)
    report = artifacts.report

    assert report.comments_present is False
    assert report.comment_count == 0
    assert report.observations_are_rules is False
    assert len(report.sections) == 1
    assert len(report.tables) == 1
    assert report.tables[0].inferred_pattern == "three_line"
    assert report.tables[0].outer_top_widths_pt == [1.5]
    assert report.tables[0].header_separator_widths_pt == [1.0]
    assert report.tables[0].outer_bottom_widths_pt == [1.5]
    assert report.tables[0].vertical_borders_present is False


def test_template_evidence_does_not_copy_document_text(tmp_path: Path) -> None:
    input_path = create_synthetic_docx(
        tmp_path / "template.docx",
        heading_text="不可进入报告的标题",
        body_text="不可进入报告的正文",
        include_three_line_table=True,
    )

    payload = json.dumps(inspect_template(input_path).report.model_dump(mode="json"))

    assert "不可进入报告" not in payload
    assert "指标" not in payload
    assert "样本" not in payload


def test_resolves_effective_format_cascade_and_sources(tmp_path: Path) -> None:
    input_path = create_synthetic_docx(
        tmp_path / "cascade.docx",
        include_style_cascade=True,
    )

    report = inspect_template(input_path).report
    paragraph = report.effective_formats[2]

    assert paragraph.paragraph_style_id == "Derived"
    assert paragraph.paragraph.alignment == "center"
    assert paragraph.paragraph.line_value == 360
    assert paragraph.paragraph.sources["alignment"] == "paragraph_style:Derived"
    assert paragraph.paragraph.sources["line_value"] == "doc_defaults"

    first_run = paragraph.runs[0].properties
    assert first_run.font_east_asia == "黑体"
    assert first_run.font_latin == "Arial"
    assert first_run.size_pt == 14
    assert first_run.bold is True
    assert first_run.italic is True
    assert first_run.sources["font_east_asia"] == "paragraph_style:Base"
    assert first_run.sources["font_latin"] == "character_style:Emphasis"
    assert first_run.sources["size_pt"] == "paragraph_style:Derived"

    second_run = paragraph.runs[1].properties
    assert second_run.size_pt == 15
    assert second_run.sources["size_pt"] == "direct_run"


def test_template_evidence_artifacts_are_deterministic(tmp_path: Path) -> None:
    input_path = create_synthetic_docx(
        tmp_path / "template.docx",
        include_three_line_table=True,
    )
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    write_template_artifacts(first_dir, inspect_template(input_path))
    write_template_artifacts(second_dir, inspect_template(input_path))

    expected_names = {"template_evidence.json", "template_evidence_summary.md"}
    assert {item.name for item in first_dir.iterdir()} == expected_names
    for name in expected_names:
        assert (first_dir / name).read_bytes() == (second_dir / name).read_bytes()


def test_cli_inspect_template_writes_artifacts(tmp_path: Path) -> None:
    input_path = create_synthetic_docx(
        tmp_path / "template.docx",
        include_three_line_table=True,
    )
    output_dir = tmp_path / "evidence"

    exit_code = main(["inspect-template", str(input_path), "--out", str(output_dir)])

    assert exit_code == 0
    assert (output_dir / "template_evidence.json").is_file()
    assert (output_dir / "template_evidence_summary.md").is_file()
