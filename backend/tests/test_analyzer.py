from pathlib import Path

from app.domain.enums import BlockKind
from app.services.analyzer import analyze_docx, write_artifacts
from paperalign.cli import main
from tests.support.docx_factory import create_synthetic_docx


def test_builds_document_profile_and_content_fingerprint(tmp_path: Path) -> None:
    input_path = create_synthetic_docx(tmp_path / "synthetic.docx")

    artifacts = analyze_docx(input_path)
    profile = artifacts.document_profile

    assert profile.statistics.paragraph_count == 2
    assert profile.statistics.table_count == 1
    assert profile.statistics.table_cell_count == 2
    assert profile.statistics.image_count == 1
    assert profile.statistics.section_count == 1
    assert profile.statistics.field_count == 2
    assert profile.statistics.story_part_count == 3
    assert [block.kind for block in profile.blocks] == [
        BlockKind.PARAGRAPH,
        BlockKind.PARAGRAPH,
        BlockKind.TABLE,
        BlockKind.TABLE_CELL,
        BlockKind.TABLE_CELL,
    ]
    assert profile.blocks[0].style.style_id == "Heading1"
    assert profile.blocks[0].style.style_name == "heading 1"
    assert artifacts.content_fingerprint.unit_count == 10
    assert {unit.kind for unit in artifacts.content_fingerprint.units} >= {"field", "media"}
    assert artifacts.unsupported_objects.safe_for_future_formatting is True


def test_content_fingerprint_ignores_format_changes(tmp_path: Path) -> None:
    first = create_synthetic_docx(tmp_path / "song.docx", font_name="宋体")
    second = create_synthetic_docx(tmp_path / "hei.docx", font_name="黑体")

    first_result = analyze_docx(first)
    second_result = analyze_docx(second)

    assert first_result.document_profile.package.input_sha256 != (
        second_result.document_profile.package.input_sha256
    )
    assert first_result.content_fingerprint.aggregate_sha256 == (
        second_result.content_fingerprint.aggregate_sha256
    )


def test_content_fingerprint_changes_with_text(tmp_path: Path) -> None:
    first = create_synthetic_docx(tmp_path / "first.docx", body_text="原始正文")
    second = create_synthetic_docx(tmp_path / "second.docx", body_text="修改后的正文")

    assert analyze_docx(first).content_fingerprint.aggregate_sha256 != (
        analyze_docx(second).content_fingerprint.aggregate_sha256
    )


def test_detects_blocking_unsupported_objects(tmp_path: Path) -> None:
    input_path = create_synthetic_docx(
        tmp_path / "unsafe.docx",
        include_unsupported=True,
    )

    report = analyze_docx(input_path).unsupported_objects
    categories = {item.category for item in report.objects}

    assert report.safe_for_future_formatting is False
    assert {"macro", "embedded_package", "alt_chunk", "external_relationship"} <= categories
    assert report.error_count >= 3


def test_repeated_analysis_writes_identical_artifacts_without_changing_input(
    tmp_path: Path,
) -> None:
    input_path = create_synthetic_docx(tmp_path / "synthetic.docx")
    original_bytes = input_path.read_bytes()
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    write_artifacts(first_dir, analyze_docx(input_path))
    write_artifacts(second_dir, analyze_docx(input_path))

    expected_names = {
        "document_profile.json",
        "content_fingerprint.json",
        "unsupported_objects.json",
        "analysis_summary.md",
    }
    assert {item.name for item in first_dir.iterdir()} == expected_names
    for name in expected_names:
        assert (first_dir / name).read_bytes() == (second_dir / name).read_bytes()
    assert input_path.read_bytes() == original_bytes


def test_cli_writes_four_artifacts(tmp_path: Path) -> None:
    input_path = create_synthetic_docx(tmp_path / "synthetic.docx")
    output_dir = tmp_path / "artifacts"

    exit_code = main(["analyze", str(input_path), "--out", str(output_dir)])

    assert exit_code == 0
    assert (output_dir / "document_profile.json").is_file()
    assert (output_dir / "content_fingerprint.json").is_file()
    assert (output_dir / "unsupported_objects.json").is_file()
    assert (output_dir / "analysis_summary.md").is_file()
