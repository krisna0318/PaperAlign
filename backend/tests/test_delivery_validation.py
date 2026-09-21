from pathlib import Path

from app.domain.delivery import WordRenderResult
from app.formatting.safe_formatter import ABBREVIATION_RULE_IDS, format_docx
from app.parsers.docx_package import sha256_file
from app.services.delivery_validation import render_delivery_checklist, validate_delivery
from tests.support.docx_factory import create_synthetic_docx


class FakeWordRenderer:
    def render(self, _input_path: Path, pdf_path: Path) -> WordRenderResult:
        pdf_path.write_bytes(b"%PDF-1.4\nsynthetic preview\n")
        return WordRenderResult(
            status="passed",
            page_count=2,
            pdf_sha256=sha256_file(pdf_path),
            note="synthetic Word adapter result",
        )


def _formatted_pair(tmp_path: Path):
    source = create_synthetic_docx(
        tmp_path / "source.docx",
        heading_text="缩略词表",
        include_second_table_row=True,
    )
    output = tmp_path / "formatted.docx"
    _plan, report = format_docx(source, output, sorted(ABBREVIATION_RULE_IDS))
    return source, output, report


def test_static_delivery_validation_rechecks_rules_and_content(tmp_path: Path) -> None:
    source, output, formatting_report = _formatted_pair(tmp_path)

    report = validate_delivery(source, output, formatting_report)

    assert report.static_status == "passed"
    assert report.delivery_ready is True
    assert report.content_preserved is True
    assert report.package_safe is True
    assert report.formatting_report_matches is True
    assert len(report.rule_rechecks) == 4
    assert all(item.passed for item in report.rule_rechecks)
    assert report.word_render.status == "not_requested"
    checklist = render_delivery_checklist(report)
    assert checklist.count("- [ ]") == len(report.manual_checklist)
    assert "不应把文件标记为学校最终验收通过" in checklist


def test_optional_word_adapter_is_separate_from_static_validation(tmp_path: Path) -> None:
    source, output, formatting_report = _formatted_pair(tmp_path)
    pdf_path = tmp_path / "preview.pdf"

    report = validate_delivery(
        source,
        output,
        formatting_report,
        render_with_word=True,
        pdf_path=pdf_path,
        renderer=FakeWordRenderer(),
    )

    assert report.static_status == "passed"
    assert report.word_render.status == "passed"
    assert report.word_render.page_count == 2
    assert pdf_path.is_file()
    assert report.manual_validation_required is True


def test_delivery_rejects_a_report_that_does_not_match_output(tmp_path: Path) -> None:
    source, output, formatting_report = _formatted_pair(tmp_path)
    mismatched = formatting_report.model_copy(update={"output_sha256": "0" * 64})

    report = validate_delivery(source, output, mismatched)

    assert report.static_status == "failed"
    assert report.delivery_ready is False
    assert report.formatting_report_matches is False
