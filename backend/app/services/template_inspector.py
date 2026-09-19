from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app import __version__
from app.domain.template_evidence import TemplateEvidenceReport
from app.parsers.docx_package import DocxPackage, sha256_file
from app.parsers.errors import DocxAnalysisError
from app.parsers.template_evidence import extract_template_evidence


@dataclass(frozen=True)
class TemplateEvidenceArtifacts:
    report: TemplateEvidenceReport
    summary: str


def inspect_template(input_path: Path) -> TemplateEvidenceArtifacts:
    input_path = input_path.resolve(strict=False)
    before_sha256 = sha256_file(input_path) if input_path.is_file() else ""

    with DocxPackage(input_path) as package:
        report = extract_template_evidence(
            package,
            extractor_version=__version__,
            file_name=input_path.name,
            input_sha256=before_sha256,
        )

    after_sha256 = sha256_file(input_path)
    if before_sha256 != after_sha256:
        raise DocxAnalysisError(
            "input_changed_during_analysis",
            "Input DOCX changed while template evidence was being extracted",
        )

    return TemplateEvidenceArtifacts(report=report, summary=render_template_summary(report))


def write_template_artifacts(
    output_dir: Path,
    artifacts: TemplateEvidenceArtifacts,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        artifacts.report.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    _write_text(output_dir / "template_evidence.json", payload + "\n")
    _write_text(output_dir / "template_evidence_summary.md", artifacts.summary)


def _write_text(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(content)
        temporary_path = Path(handle.name)
    try:
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _format_widths(widths: list[float]) -> str:
    if not widths:
        return "未检测到"
    return ", ".join(f"{width:g} pt" for width in widths)


def render_template_summary(report: TemplateEvidenceReport) -> str:
    lines = [
        "# PaperAlign 模板格式证据摘要",
        "",
        f"- 文件：`{report.file_name}`",
        f"- 文件 SHA-256：`{report.input_sha256}`",
        f"- 提取器版本：`{report.extractor_version}`",
        f"- 批注：{'有' if report.comments_present else '无'}（{report.comment_count} 条）",
        f"- 分节：{len(report.sections)}",
        f"- 段落样式种类：{len(report.paragraph_style_usage)}",
        f"- 直接格式簇：{len(report.direct_format_clusters)}",
        f"- 表格：{len(report.tables)}",
        "",
        "> 以下内容是从 DOCX 结构与格式中提取的观察值，不会自动升级为学校规则。",
        "",
        "## 表格边框观察",
        "",
        "Word 边框 `w:sz` 的单位为 1/8 磅；报告已经换算为 pt。",
        "",
        "| 表格 | 行 × 列 | 推断类型 | 上边线 | 表头分隔线 | 下边线 | 竖线 | 置信度 |",
        "|---|---:|---|---|---|---|---|---:|",
    ]
    if report.tables:
        for table in report.tables:
            lines.append(
                "| "
                f"{table.table_index} | {table.row_count} × {table.column_count} | "
                f"{table.inferred_pattern} | {_format_widths(table.outer_top_widths_pt)} | "
                f"{_format_widths(table.header_separator_widths_pt)} | "
                f"{_format_widths(table.outer_bottom_widths_pt)} | "
                f"{'有' if table.vertical_borders_present else '无'} | {table.confidence:.2f} |"
            )
    else:
        lines.append("| - | - | 未发现表格 | - | - | - | - | - |")

    lines.extend(["", "## 提取限制", ""])
    lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend(
        [
            "",
            "模板没有批注时，系统仍会输出页面、分节、样式使用、直接格式簇和表格边框证据；存在冲突时必须由用户确认。",
            "",
        ]
    )
    return "\n".join(lines)
