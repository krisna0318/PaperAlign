import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.domain.enums import SemanticRole
from app.domain.structure import StructureOverrides, StructureReport
from app.parsers.docx_package import sha256_file
from app.parsers.errors import DocxAnalysisError
from app.services.analyzer import analyze_docx
from app.services.structure_service import inspect_structure, load_overrides, write_structure_review
from paperalign.cli import main
from tests.support.structure_factory import paragraph, structured_docx


def test_sections_headings_parentage_and_content_preservation(tmp_path: Path) -> None:
    source = structured_docx(
        tmp_path / "sample.docx",
        [
            paragraph("本科毕业论文"),
            paragraph("摘 要"),
            paragraph("合成中文摘要。"),
            paragraph("关键词：测试；结构"),
            paragraph("Abstract"),
            paragraph("Synthetic abstract."),
            paragraph("Keywords: test; structure"),
            paragraph("目 录"),
            paragraph("1 绪论\t1", style="TOC1"),
            paragraph("1 绪论", style="Heading1"),
            paragraph("1.1 研究方法", style="Heading2"),
            paragraph("这是正文。"),
            paragraph("1.1.1.1 细节", style="Heading4"),
            paragraph("图 1-1 系统示意", style="Caption"),
            paragraph("参考文献"),
            paragraph("[1] Synthetic author. Example. 2024."),
            paragraph("附录 A 测试资料"),
            paragraph("附录资料。"),
            paragraph("致谢"),
            paragraph("合成致谢。"),
        ],
    )
    before = analyze_docx(source)
    report = inspect_structure(source)
    nodes = report.decisions
    assert report.input_sha256 == sha256_file(source)
    assert report.content_fingerprint == before.content_fingerprint.aggregate_sha256
    assert [d.block_id for d in nodes] == [b.id for b in before.document_profile.blocks]
    assert nodes[0].scope == "cover_document_type"
    assert nodes[1].scope == "abstract_zh_heading"
    assert nodes[2].scope == "abstract_zh_body"
    assert nodes[5].scope == "abstract_en_body"
    assert nodes[8].role == "table_of_contents" and nodes[8].heading_level is None
    assert nodes[9].role == "heading_1" and nodes[9].parent_id is None
    assert nodes[10].parent_id == nodes[9].block_id
    assert nodes[11].parent_id == nodes[10].block_id
    assert nodes[12].role == "heading_4"
    assert any(w.code == "heading_level_jump" for w in report.warnings)
    assert nodes[13].role == "figure_caption" and not nodes[13].requires_confirmation
    assert nodes[15].role == "reference_entry"
    assert nodes[17].role == "appendix_body"
    assert nodes[19].role == "acknowledgement_body"
    assert report.ai_used is False and report.formatting_allowed is False
    assert all(d.preview is None for d in nodes)
    Draft202012Validator(StructureReport.model_json_schema()).validate(
        report.model_dump(mode="json")
    )


def test_complex_toc_spans_paragraphs_and_nested_fields(tmp_path: Path) -> None:
    source = structured_docx(
        tmp_path / "toc.docx",
        [
            paragraph(
                "",
                runs='<w:r><w:fldChar w:fldCharType="begin"/><w:instrText> TO</w:instrText>'
                '<w:instrText>C \\o "1-3" </w:instrText>'
                '<w:fldChar w:fldCharType="separate"/></w:r>',
            ),
            paragraph(
                "1 绪论",
                style="Heading1",
                runs='<w:r><w:fldChar w:fldCharType="begin"/>'
                "<w:instrText> PAGEREF bookmark </w:instrText>"
                '<w:fldChar w:fldCharType="end"/></w:r>',
            ),
            paragraph("参考文献"),
            paragraph("", runs='<w:r><w:fldChar w:fldCharType="end"/></w:r>'),
            paragraph("1 绪论", style="Heading1"),
            paragraph("正文。"),
        ],
    )
    nodes = inspect_structure(source).decisions
    assert all(n.role == "table_of_contents" for n in nodes[:4])
    assert nodes[4].role == "heading_1"
    assert nodes[5].parent_id == nodes[4].block_id


@pytest.mark.parametrize(
    "text,properties,reason",
    [
        ("1.1 方法", "", "heading_level_conflict"),
        ("这是一个正文句子。", "", "heading_looks_like_sentence"),
        ("1 方法", '<w:outlineLvl w:val="1"/>', "heading_level_conflict"),
    ],
)
def test_heading_conflicts_do_not_silently_reclassify_following_text(
    tmp_path, text, properties, reason
):
    source = structured_docx(
        tmp_path / "conflict.docx",
        [paragraph(text, style="Heading1", properties=properties), paragraph("待定位内容。")],
    )
    nodes = inspect_structure(source).decisions
    assert reason in nodes[0].reasons and nodes[0].requires_confirmation
    assert nodes[1].role == "unknown" and nodes[1].parent_id is None


def test_numbered_list_caption_mention_and_toc_boundary_require_review(tmp_path):
    source = structured_docx(
        tmp_path / "ambiguous.docx",
        [
            paragraph("目录"),
            paragraph("1 绪论 .... 1"),
            paragraph("1 绪论"),
            paragraph("第一章 绪论", style="Heading1"),
            paragraph(
                "1 操作步骤",
                properties='<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>',
            ),
            paragraph("图 1 是算法示意"),
            paragraph("图 1 展示了算法流程。"),
            paragraph("2 可能是编号列表"),
        ],
    )
    nodes = inspect_structure(source).decisions
    assert nodes[1].role == "table_of_contents" and not nodes[1].requires_confirmation
    assert nodes[2].requires_confirmation
    assert nodes[4].requires_confirmation and nodes[4].role == "unknown"
    assert nodes[5].requires_confirmation
    assert nodes[6].role == "body"
    assert nodes[7].requires_confirmation


def test_corrections_recompute_regions_without_modifying_document(tmp_path):
    source = structured_docx(
        tmp_path / "manual.docx",
        [
            paragraph("目录"),
            paragraph("1 引言"),
            paragraph("合成正文。"),
        ],
    )
    baseline = inspect_structure(source)
    overrides = StructureOverrides(
        input_sha256=baseline.input_sha256,
        reviewer="synthetic reviewer",
        decisions=[{"block_id": "p-0001", "role": "heading_1", "reason": "人工核对"}],
    )
    corrected = inspect_structure(source, overrides=overrides)
    assert corrected.decisions[1].decision_source == "user"
    assert corrected.applied_overrides.decisions[0].reason == "人工核对"
    assert corrected.decisions[2].role == "body"
    assert corrected.decisions[2].parent_id == "p-0001"
    assert corrected.input_sha256 == baseline.input_sha256
    assert corrected.content_fingerprint == baseline.content_fingerprint
    assert baseline.decisions[2].role == "table_of_contents"


@pytest.mark.parametrize("case", ["hash", "duplicate", "unknown_id", "wrong_kind", "wrong_scope"])
def test_invalid_corrections_rejected(tmp_path, case):
    source = structured_docx(tmp_path / "invalid.docx", [paragraph("1 标题")])
    item = {"block_id": "p-0000", "role": "heading_1", "reason": "synthetic"}
    if case == "unknown_id":
        item["block_id"] = "p-9999"
    elif case == "wrong_kind":
        item["role"] = "table"
    elif case == "wrong_scope":
        item["scope"] = "abstract_en_body"
    overrides = StructureOverrides(
        input_sha256="a" * 64 if case == "hash" else sha256_file(source),
        reviewer="test",
        decisions=[item, item] if case == "duplicate" else [item],
    )
    with pytest.raises(DocxAnalysisError):
        inspect_structure(source, overrides=overrides)


def test_table_cell_hierarchy_and_confirmed_abbreviation_checks(tmp_path):
    table = (
        '<w:tbl><w:tblPr><w:tblBorders><w:top w:val="single" w:sz="12"/>'
        '<w:bottom w:val="single" w:sz="12"/><w:insideH w:val="single" w:sz="4"/>'
        '<w:left w:val="nil"/><w:right w:val="nil"/><w:insideV w:val="nil"/>'
        '</w:tblBorders></w:tblPr><w:tblGrid><w:gridCol w:w="2000"/></w:tblGrid>'
        "<w:tr><w:tc><w:p><w:r><w:t>表头</w:t></w:r></w:p></w:tc></w:tr>"
        "<w:tr><w:tc><w:p><w:r><w:t>示例</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
    )
    source = structured_docx(tmp_path / "table.docx", [paragraph("英文缩略词表"), table])
    report = inspect_structure(source)
    assert report.decisions[1].role == "abbreviation_table"
    assert report.decisions[2].parent_id == "tbl-0000"
    separator = [c for c in report.rule_checks if c.property_path == "table.header_separator_pt"]
    assert len(separator) == 1 and separator[0].status == "fail"
    assert separator[0].actual.value == 0.5


def test_unsupported_inline_objects_remain_unassessed_after_role_override(tmp_path):
    source = structured_docx(
        tmp_path / "objects.docx",
        [
            paragraph(
                "1 标题", style="Heading1", runs="<m:oMath><m:r><m:t>x</m:t></m:r></m:oMath>"
            ),
            "<w:sdt><w:sdtContent>" + paragraph("包装内的段落") + "</w:sdtContent></w:sdt>",
        ],
    )
    report = inspect_structure(source)
    assert report.decisions[0].role == "equation" and not report.decisions[0].requires_confirmation
    assert "unrepresented_body_wrappers" in {w.code for w in report.warnings}
    assert report.unsupported_object_counts
    overrides = StructureOverrides(
        input_sha256=report.input_sha256,
        reviewer="test",
        decisions=[{"block_id": "p-0000", "role": "heading_1", "reason": "reviewed"}],
    )
    corrected = inspect_structure(source, overrides=overrides)
    checks = [c for c in corrected.rule_checks if c.locator.paragraph_index == 0]
    assert checks and all(c.actual is None and c.status != "pass" for c in checks)


def test_review_exports_are_private_deterministic_and_escape_text(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    # Use the actual ignored local root for output; pytest still owns the synthetic input.
    from uuid import uuid4

    output = repo / ".paperalign/test-runs" / uuid4().hex
    text = "<script>alert(1)</script>PrivateSuffix"
    source = structured_docx(tmp_path / "private.docx", [paragraph(text)])
    first = write_structure_review(source, output)
    assert text not in (output / "structure_report.json").read_text(encoding="utf-8")
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    second = write_structure_review(source, output)
    assert first == second and before == {p.name: p.read_bytes() for p in output.iterdir()}
    write_structure_review(source, output, include_preview=True)
    html = (output / "structure_review.html").read_text(encoding="utf-8")
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "PrivateSuffix" not in html
    forbidden = repo / ".structure-output-must-be-private"
    with pytest.raises(DocxAnalysisError, match="Structure review"):
        write_structure_review(source, forbidden)
    assert not forbidden.exists()
    with pytest.raises(DocxAnalysisError, match="preserve inputs"):
        write_structure_review(source, output, overrides_path=output / "corrections.template.json")


def test_override_file_requires_reviewer_and_reason(tmp_path):
    path = tmp_path / "override.json"
    payload = {
        "input_sha256": "a" * 64,
        "reviewer": "填写审查人",
        "decisions": [{"block_id": "p-0000", "role": "body", "reason": "checked"}],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DocxAnalysisError):
        load_overrides(path)
    payload["reviewer"] = "Tester"
    payload["decisions"] = []
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DocxAnalysisError):
        load_overrides(path)
    payload["decisions"] = [{"block_id": "p-0000", "role": "body", "reason": "checked"}]
    payload["decisions"][0]["reason"] = " "
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DocxAnalysisError):
        load_overrides(path)


def test_frontend_semantic_roles_match_backend():
    frontend = (Path(__file__).resolve().parents[2] / "frontend/src/types/domain.ts").read_text()
    declaration = re.search(r"export type SemanticRole =(.*?);", frontend, re.S).group(1)
    assert set(re.findall(r'"([^"]+)"', declaration)) == {r.value for r in SemanticRole}


def test_classify_cli_reports_safe_output_boundary(tmp_path, capsys):
    source = structured_docx(tmp_path / "cli.docx", [paragraph("1 标题", style="Heading1")])
    forbidden = Path(__file__).resolve().parents[2] / ".structure-output-must-be-private"
    assert main(["classify", str(source), "--out", str(forbidden)]) == 2
    assert "private_output_required" in capsys.readouterr().err
    assert not forbidden.exists()


def test_inline_abstract_and_named_styles_open_correct_language_region(tmp_path):
    source = structured_docx(
        tmp_path / "abstracts.docx",
        [
            paragraph("摘 要"),
            paragraph("中文摘要。"),
            paragraph("A Synthetic Title", style="英文摘要标题"),
            paragraph("Abstract: Synthetic abstract."),
            paragraph("A second abstract paragraph."),
            paragraph("英文缩略词（符号表）"),
        ],
    )
    nodes = inspect_structure(source).decisions
    assert nodes[2].scope == "abstract_en_title"
    assert nodes[3].scope == "abstract_en_body"
    assert nodes[4].scope == "abstract_en_body" and nodes[4].region == "abstract_en"
    assert nodes[5].role == "abbreviation_heading"


def test_declaration_title_and_spaced_cover_metadata(tmp_path):
    source = structured_docx(
        tmp_path / "front.docx",
        [
            paragraph("学  院：合成学院"),
            paragraph("华南农业大学本科毕业论文（设计）原创性声明"),
            paragraph("此为合成声明。"),
        ],
    )
    nodes = inspect_structure(source).decisions
    assert nodes[0].scope == "cover_metadata"
    assert nodes[1].role == "declaration"
    assert nodes[2].role == "declaration"
    assert nodes[2].parent_id == nodes[1].block_id


def test_cover_context_and_math_drawing_roles(tmp_path):
    source = structured_docx(
        tmp_path / "objects.docx",
        [
            paragraph("本科毕业论文（或设计）"),
            paragraph("论文（或设计）题目"),
            paragraph("", runs="<m:oMath><m:r><m:t>x</m:t></m:r></m:oMath>"),
            paragraph("", runs="<w:r><w:drawing/></w:r>"),
        ],
    )
    nodes = inspect_structure(source).decisions
    assert nodes[0].scope == "cover_document_type"
    assert nodes[1].scope == "cover_title"
    assert nodes[2].role == "equation" and not nodes[2].requires_confirmation
    assert nodes[3].role == "figure" and nodes[3].requires_confirmation


def test_simple_and_unclosed_toc_fields_do_not_become_headings(tmp_path):
    simple = structured_docx(
        tmp_path / "simple.docx",
        [
            paragraph(
                "", runs='<w:fldSimple w:instr="TOC"><w:r><w:t>1 标题</w:t></w:r></w:fldSimple>'
            ),
            paragraph("1 标题", style="Heading1"),
        ],
    )
    nodes = inspect_structure(simple).decisions
    assert nodes[0].role == "table_of_contents" and nodes[1].role == "heading_1"
    unclosed = structured_docx(
        tmp_path / "unclosed.docx",
        [
            paragraph(
                "",
                runs='<w:r><w:fldChar w:fldCharType="begin"/><w:instrText>TOC</w:instrText></w:r>',
            ),
            paragraph("1 标题", style="Heading1"),
        ],
    )
    report = inspect_structure(unclosed)
    assert report.decisions[1].role == "table_of_contents"
    assert "unclosed_complex_field" in {w.code for w in report.warnings}


def test_inline_abstract_first_and_following_targets_use_same_section(tmp_path):
    from app.profiles.loader import load_profile

    source = structured_docx(
        tmp_path / "positions.docx",
        [
            paragraph("Abstract: First paragraph."),
            paragraph("Second paragraph."),
        ],
    )
    report = inspect_structure(source)
    assert report.decisions[0].section_id == report.decisions[1].section_id
    rules = load_profile().rules
    first_ids = {
        r.id
        for r in rules
        if r.scope == "abstract_en_body" and r.target.paragraph_position == "first"
    }
    following_ids = {
        r.id
        for r in rules
        if r.scope == "abstract_en_body" and r.target.paragraph_position == "following"
    }
    first_checks = {c.rule_id for c in report.rule_checks if c.locator.paragraph_index == 0}
    following_checks = {c.rule_id for c in report.rule_checks if c.locator.paragraph_index == 1}
    assert first_ids and following_ids
    assert first_ids <= first_checks and not first_ids & following_checks
    assert following_ids <= following_checks and not following_ids & first_checks


def test_override_can_select_a_precise_scope_for_a_coarse_role(tmp_path):
    source = structured_docx(tmp_path / "scope.docx", [paragraph("Synthetic title")])
    baseline = inspect_structure(source)
    overrides = StructureOverrides(
        input_sha256=baseline.input_sha256,
        reviewer="test",
        decisions=[
            {
                "block_id": "p-0000",
                "role": "abstract_en",
                "scope": "abstract_en_title",
                "reason": "checked against the manuscript",
            }
        ],
    )
    corrected = inspect_structure(source, overrides=overrides)
    assert corrected.decisions[0].scope == "abstract_en_title"
