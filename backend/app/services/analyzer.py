from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from app import __version__
from app.domain.analysis import (
    ContentFingerprintReport,
    DocumentProfile,
    PackageSummary,
    UnsupportedObjectsReport,
)
from app.parsers.content_types import parse_content_types
from app.parsers.document_parser import DocumentParser
from app.parsers.docx_package import DocxPackage, sha256_file
from app.parsers.errors import DocxAnalysisError
from app.parsers.relationships import parse_all_relationships
from app.parsers.unsupported import detect_unsupported_objects
from app.validation.content_fingerprint import build_content_fingerprint


@dataclass(frozen=True)
class AnalysisArtifacts:
    document_profile: DocumentProfile
    content_fingerprint: ContentFingerprintReport
    unsupported_objects: UnsupportedObjectsReport
    analysis_summary: str


def analyze_docx(input_path: Path) -> AnalysisArtifacts:
    input_path = input_path.resolve(strict=False)
    before_sha256 = sha256_file(input_path) if input_path.is_file() else ""

    with DocxPackage(input_path) as package:
        content_types = parse_content_types(package)
        relationships = parse_all_relationships(package)
        parser = DocumentParser(package, content_types, relationships)
        (
            blocks,
            styles,
            sections,
            story_parts,
            fields,
            media,
            statistics,
        ) = parser.parse()
        unsupported = detect_unsupported_objects(package, content_types, relationships)

        if package.inspection is None:
            raise RuntimeError("Package inspection is unavailable")
        profile = DocumentProfile(
            analyzer_version=__version__,
            package=PackageSummary(
                file_name=input_path.name,
                file_size_bytes=input_path.stat().st_size,
                input_sha256=before_sha256,
                part_count=package.inspection.part_count,
                compressed_size_bytes=package.inspection.compressed_size_bytes,
                uncompressed_size_bytes=package.inspection.uncompressed_size_bytes,
                main_document_part="word/document.xml",
                macro_enabled=content_types.macro_enabled,
            ),
            statistics=statistics,
            blocks=blocks,
            styles=styles,
            sections=sections,
            story_parts=story_parts,
            fields=fields,
            media=media,
        )

    after_sha256 = sha256_file(input_path)
    if before_sha256 != after_sha256:
        raise DocxAnalysisError(
            "input_changed_during_analysis",
            "Input DOCX changed while it was being analyzed; no result was written",
        )

    fingerprint = build_content_fingerprint(profile)
    summary = render_analysis_summary(profile, fingerprint, unsupported)
    return AnalysisArtifacts(profile, fingerprint, unsupported, summary)


def write_artifacts(output_dir: Path, artifacts: AnalysisArtifacts) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "document_profile.json", artifacts.document_profile)
    _write_json(output_dir / "content_fingerprint.json", artifacts.content_fingerprint)
    _write_json(output_dir / "unsupported_objects.json", artifacts.unsupported_objects)
    _write_text(output_dir / "analysis_summary.md", artifacts.analysis_summary)


def _write_json(path: Path, model: BaseModel) -> None:
    payload = json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    _write_text(path, payload + "\n")


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


def render_analysis_summary(
    profile: DocumentProfile,
    fingerprint: ContentFingerprintReport,
    unsupported: UnsupportedObjectsReport,
) -> str:
    status = "可进入后续人工确认流程" if unsupported.safe_for_future_formatting else "存在阻断项"
    lines = [
        "# PaperAlign 只读分析摘要",
        "",
        f"- 文件：`{profile.package.file_name}`",
        f"- 文件 SHA-256：`{profile.package.input_sha256}`",
        f"- 分析器版本：`{profile.analyzer_version}`",
        f"- 安全结论：**{status}**",
        "",
        "## 文档画像",
        "",
        f"- 段落：{profile.statistics.paragraph_count}",
        f"- 表格：{profile.statistics.table_count}",
        f"- 表格单元格：{profile.statistics.table_cell_count}",
        f"- 图片资源：{profile.statistics.image_count}",
        f"- 分节：{profile.statistics.section_count}",
        f"- 字段：{profile.statistics.field_count}",
        f"- 页眉、页脚及其他文本部件：{profile.statistics.story_part_count}",
        "",
        "## 内容保护",
        "",
        f"- 聚合内容指纹：`{fingerprint.aggregate_sha256}`",
        f"- 指纹单元：{fingerprint.unit_count}",
        f"- 受保护字符：{fingerprint.total_characters}",
        f"- 规范化：{fingerprint.normalization}",
        "",
        "## 不支持对象",
        "",
        f"- 总数：{unsupported.object_count}",
        f"- 错误：{unsupported.error_count}",
        f"- 警告：{unsupported.warning_count}",
        f"- 信息：{unsupported.info_count}",
    ]
    if unsupported.objects:
        lines.extend(["", "| 类别 | 级别 | 部件 | 处置 |", "|---|---|---|---|"])
        lines.extend(
            f"| {item.category} | {item.severity} | `{item.part_name}` | {item.policy} |"
            for item in unsupported.objects
        )
    else:
        lines.extend(["", "未检测到当前规则集定义的不支持对象。"])
    lines.extend(
        [
            "",
            "> 本报告只描述文档结构与处理风险，不判断论文格式是否符合学校要求。",
            "",
        ]
    )
    return "\n".join(lines)
