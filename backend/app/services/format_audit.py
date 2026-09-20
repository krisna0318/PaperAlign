"""Local-only, opt-in text previews for reviewing template observations."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from lxml import etree

from app.parsers.docx_package import DocxPackage, sha256_file
from app.parsers.errors import DocxAnalysisError
from app.parsers.namespaces import NS, W, qn
from app.parsers.xml_utils import parse_xml
from app.services.template_inspector import _write_text, inspect_template, write_template_artifacts

LABELS = {
    "font_east_asia": "中文字体",
    "font_latin": "ASCII 西文字体",
    "font_high_ansi": "扩展西文字体",
    "font_complex_script": "复杂文字字体",
    "size_pt": "字号",
    "bold": "粗体",
    "italic": "斜体",
    "color": "颜色",
    "alignment": "对齐",
    "line_rule": "行距模式",
    "line_value": "行距原始值",
    "space_before_twips": "段前",
    "space_after_twips": "段后",
    "first_line_indent_twips": "首行缩进（长度）",
    "first_line_indent_chars": "首行缩进（字符）",
    "left_indent_twips": "左缩进",
    "right_indent_twips": "右缩进",
    "outline_level": "大纲级别（0 基）",
    "keep_with_next": "与下段同页",
    "page_break_before": "段前分页",
}


def _property_table(properties: dict[str, Any]) -> str:
    rows = []
    for key, value in properties.items():
        if key in {"sources", "unresolved"}:
            continue
        display = "未解析" if value is None else str(value)
        if isinstance(value, bool):
            display = "是" if value else "否"
        elif isinstance(value, (float, int)):
            if key.endswith("_twips"):
                display = f"{value / 20:g} pt（原始 {value} twip）"
            elif key == "first_line_indent_chars":
                display = f"{value / 100:g} 字符（原始 {value}）"
            elif key == "size_pt":
                display = f"{value:g} pt"
            elif key == "line_value" and properties.get("line_rule") == "auto":
                display = f"{value / 240:g} 倍（原始 {value}）"
            elif key == "line_value" and properties.get("line_rule") in {"exact", "atLeast"}:
                display = f"{value / 20:g} pt（原始 {value}）"
        source = properties.get("sources", {}).get(key, "—")
        unresolved = properties.get("unresolved", {}).get(key, "")
        rows.append(
            "<tr>"
            + "".join(
                f"<td>{escape(str(cell))}</td>"
                for cell in (LABELS.get(key, key), display, source, unresolved)
            )
            + "</tr>"
        )
    return (
        "<table><thead><tr><th>属性</th><th>实际值</th><th>生效来源</th>"
        "<th>未解析说明</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def write_format_audit(
    input_path: Path, output_dir: Path, *, include_preview: bool = False
) -> Path:
    repo = Path(__file__).resolve().parents[3]
    local_root = repo / ".paperalign"
    target = output_dir.resolve()
    if local_root.resolve() != local_root or not target.is_relative_to(local_root):
        raise DocxAnalysisError(
            "private_output_required", "Audit output must stay under .paperalign"
        )
    artifacts = inspect_template(input_path)
    with DocxPackage(input_path) as package:
        root = parse_xml(package.read_part("word/document.xml"), "word/document.xml")
        paragraphs = root.findall("w:body/w:p", namespaces=NS)
        # Previews and declarations share the exact same body-only index as the resolver.
        previews = [
            "".join(
                t.text or ""
                for t in p.findall(".//w:t", namespaces=NS)
                if not any(a.tag == qn(W, "txbxContent") for a in t.iterancestors())
            )[:20]
            if include_preview
            else ""
            for p in paragraphs
        ]
    if sha256_file(input_path) != artifacts.report.input_sha256:
        raise DocxAnalysisError("input_changed_during_analysis", "Input changed during audit")
    rows = []
    for item, preview, paragraph in zip(
        artifacts.report.effective_formats, previews, paragraphs, strict=True
    ):
        payload = item.model_dump(mode="json")
        declarations = []
        for declaration in paragraph.findall("w:pPr/*", namespaces=NS):
            if len(declaration) == 0:
                declarations.append(
                    {
                        "tag": etree.QName(declaration).localname,
                        "attributes": {
                            etree.QName(k).localname: v for k, v in declaration.attrib.items()
                        },
                    }
                )
        rows.append({"preview": preview, "direct_paragraph_declarations": declarations, **payload})
    payload_json = json.dumps(rows, ensure_ascii=False, indent=2)
    cards = []
    for row in rows:
        index = row["paragraph_index"]
        details = escape(json.dumps(row, ensure_ascii=False, indent=2))
        title = escape(str(row["preview"])) if include_preview else "预览已关闭"
        properties = _property_table(row["paragraph"])
        for group_index, group in enumerate(row["runs"]):
            properties += (
                f"<h3>文字格式组 {group_index} · {group['run_count']} 个片段</h3>"
                + _property_table(group["properties"])
            )
        cards.append(
            f'<details id="p-{index}"><summary>段落 {index} · {title}</summary>'
            f"<p>定位：word/document.xml / w:body/w:p[{int(str(index)) + 1}]"
            "（段落索引从 0 开始，XML 路径从 1 开始）</p>"
            f"{properties}<details><summary>原始声明与 JSON</summary>"
            f"<pre>{details}</pre></details></details>"
        )
    warnings = "".join(f"<li>{escape(w)}</li>" for w in artifacts.report.warnings)
    html = (
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; style-src 'unsafe-inline'\">"
        "<title>PaperAlign 本地格式审计</title><style>"
        "body{font:16px/1.6 system-ui;max-width:1000px;margin:32px auto;padding:0 20px;"
        "background:#f5f7fa;color:#172b4d}details{background:white;padding:16px;margin:10px 0;"
        "border:1px solid #dce3ec;border-radius:8px}summary{cursor:pointer;font-weight:600}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}"
        "table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:8px;"
        "border-bottom:1px solid #ddd;text-align:left;overflow-wrap:anywhere}"
        "</style><h1>PaperAlign 本地格式审计</h1>"
        f"<p>版本 {escape(artifacts.report.extractor_version)} · {len(rows)} 个正文层段落</p>"
        "<p>使用浏览器查找定位短预览，点击段落展开。sources 是最终生效来源。"
        "null 表示尚未解析，不等于错误。此页只展示格式观察，不判定学校合规。</p>"
        "<p>来源：doc_defaults 文档默认；spec_default OOXML 默认；paragraph_style 段落样式；"
        "character_style 字符样式；direct_paragraph 段落直接设置；direct_run 文字直接设置。</p>"
        "<p>表格内、页眉页脚、脚注及文本框段落暂未覆盖；编号、主题及复杂样式需要复核。</p>"
        f"<p>文本预览：{'已启用（每段最多 20 字）' if include_preview else '已关闭'}。"
        "文件仅供本机审查，请勿提交或公开分享。</p>"
        f"<p>输入 SHA-256：{artifacts.report.input_sha256}</p><ul>{warnings}</ul>"
        + "".join(cards)
        + "</html>"
    )
    write_template_artifacts(target, artifacts)
    _write_text(target / "format_audit.json", payload_json + "\n")
    _write_text(target / "format_audit.html", html)
    return target / "format_audit.html"
