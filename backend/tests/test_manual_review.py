from pathlib import Path

from jsonschema import Draft202012Validator

from app.domain.manual_review import ManualReviewGuide
from app.services.manual_review import build_manual_review_guide, render_manual_review_markdown
from app.services.structure_service import inspect_structure, write_structure_review
from tests.support.structure_factory import paragraph, structured_docx


def test_manual_guide_is_specific_to_detected_layout_risks(tmp_path: Path) -> None:
    table = (
        '<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w="2000"/></w:tblGrid>'
        "<w:tr><w:tc><w:p><w:r><w:t>合成表格</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
    )
    source = structured_docx(
        tmp_path / "layout.docx",
        [
            paragraph("目录"),
            paragraph("1 绪论\t1", style="TOC1"),
            paragraph("1 绪论", style="Heading1"),
            paragraph("", runs="<w:r><w:drawing/></w:r>"),
            paragraph("图 1-1 合成图片", style="Caption"),
            table,
        ],
    )
    guide = build_manual_review_guide(inspect_structure(source))
    categories = {item.category for item in guide.items}
    assert {
        "final_layout",
        "toc_and_fields",
        "figure_pagination",
        "table_pagination",
        "section_page_numbering",
    } <= categories
    assert all(item.steps and item.acceptance_checks for item in guide.items)
    assert "当前不能保证" in render_manual_review_markdown(guide)
    Draft202012Validator(ManualReviewGuide.model_json_schema()).validate(
        guide.model_dump(mode="json")
    )


def test_structure_review_exports_customer_notice_and_steps(tmp_path: Path) -> None:
    source = structured_docx(tmp_path / "simple.docx", [paragraph("1 标题", style="Heading1")])
    repo = Path(__file__).resolve().parents[2]
    output = repo / ".paperalign/test-runs/manual-guide"
    write_structure_review(source, output)
    assert (output / "manual_review_guide.json").exists()
    markdown = (output / "manual_review_guide.md").read_text(encoding="utf-8")
    html = (output / "structure_review.html").read_text(encoding="utf-8")
    assert "操作步骤" in markdown and "验收检查" in markdown
    assert "必须人工完成的 Word 复核" in html
