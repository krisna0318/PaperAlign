from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Protocol

from app import __version__
from app.domain.delivery import (
    DeliveryValidationReport,
    RuleRecheck,
    WordRenderResult,
)
from app.domain.formatting import FormattingReport
from app.parsers.docx_package import sha256_file
from app.services.analyzer import analyze_docx
from app.services.structure_service import inspect_structure

MANUAL_CHECKLIST = [
    "在桌面版 Word 中确认封面、声明、摘要、目录和正文分页没有异常。",
    "更新全部域和目录，确认标题、页码、图表编号及交叉引用正确。",
    "逐个检查图、表、公式是否完整，题注位置和跨页行为是否符合要求。",
    "检查分节符、页眉页脚、奇偶页及页码起始值。",
    "对照学校官方模板检查字体替换、行距、缩进和段前段后间距。",
    "保存并关闭后重新打开 DOCX，再抽查首页、目录页、正文首尾页和参考文献。",
]


class WordRenderer(Protocol):
    def render(self, input_path: Path, pdf_path: Path) -> WordRenderResult: ...


class PowerShellWordRenderer:
    def render(self, input_path: Path, pdf_path: Path) -> WordRenderResult:
        executable = shutil.which("powershell.exe") or shutil.which("powershell")
        if executable is None:
            return WordRenderResult(
                status="unavailable",
                error_code="powershell_unavailable",
                note="未找到 PowerShell，未执行 Word 打开与 PDF 导出探测。",
            )
        script = Path(__file__).resolve().parents[1] / "infrastructure" / "word_render.ps1"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            completed = subprocess.run(
                [
                    executable,
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                    "-InputPath",
                    str(input_path),
                    "-PdfPath",
                    str(pdf_path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired):
            pdf_path.unlink(missing_ok=True)
            return WordRenderResult(
                status="failed",
                error_code="word_render_process_failed",
                note="Word 探测进程未能完成；请按人工清单打开文件。",
            )
        payload = _last_json_line(completed.stdout)
        if (
            completed.returncode == 0
            and payload.get("status") == "passed"
            and pdf_path.is_file()
            and pdf_path.stat().st_size > 0
        ):
            page_count = payload.get("page_count")
            if not isinstance(page_count, int) or page_count < 1:
                pdf_path.unlink(missing_ok=True)
                return WordRenderResult(
                    status="failed",
                    error_code="invalid_word_page_count",
                    note="Word 已返回结果，但页数无效；请按人工清单检查。",
                )
            return WordRenderResult(
                status="passed",
                page_count=page_count,
                pdf_sha256=sha256_file(pdf_path),
                note="桌面版 Word 已只读打开、重分页并导出 PDF；这不等于视觉人工验收。",
            )
        pdf_path.unlink(missing_ok=True)
        return WordRenderResult(
            status="unavailable" if "COMException" in completed.stdout else "failed",
            error_code="word_automation_unavailable",
            note="无法通过 Word 自动化完成探测；请按人工清单打开文件。",
        )


def validate_delivery(
    original_path: Path,
    formatted_path: Path,
    formatting_report: FormattingReport,
    *,
    job_id: str | None = None,
    render_with_word: bool = False,
    pdf_path: Path | None = None,
    renderer: WordRenderer | None = None,
) -> DeliveryValidationReport:
    original = analyze_docx(original_path)
    formatted = analyze_docx(formatted_path)
    original_sha = original.document_profile.package.input_sha256
    formatted_sha = formatted.document_profile.package.input_sha256
    original_fingerprint = original.content_fingerprint.aggregate_sha256
    formatted_fingerprint = formatted.content_fingerprint.aggregate_sha256
    content_preserved = original_fingerprint == formatted_fingerprint
    report_matches = (
        formatting_report.input_sha256 == original_sha
        and formatting_report.output_sha256 == formatted_sha
        and formatting_report.content_fingerprint_before == original_fingerprint
        and formatting_report.content_fingerprint_after == formatted_fingerprint
    )
    package_safe = formatted.unsupported_objects.safe_for_future_formatting
    structure = inspect_structure(formatted_path)
    rule_rechecks = []
    for rule_id in formatting_report.applied_rule_ids:
        results = [item for item in structure.rule_checks if item.rule_id == rule_id]
        counts = Counter(item.status for item in results)
        rule_rechecks.append(
            RuleRecheck(
                rule_id=rule_id,
                result_count=len(results),
                pass_count=counts["pass"],
                fail_count=counts["fail"],
                unresolved_count=counts["not_evaluated"] + counts["evidence_insufficient"],
                passed=bool(results) and all(item.status == "pass" for item in results),
            )
        )
    static_passed = (
        content_preserved
        and report_matches
        and package_safe
        and bool(rule_rechecks)
        and all(item.passed for item in rule_rechecks)
    )
    word_result = WordRenderResult(
        status="not_requested",
        note="未请求 Word 自动化；仍需按人工清单检查最终页面。",
    )
    if render_with_word:
        if pdf_path is None:
            raise ValueError("pdf_path is required when Word rendering is requested")
        word_result = (renderer or PowerShellWordRenderer()).render(formatted_path, pdf_path)
    return DeliveryValidationReport(
        validator_version=__version__,
        job_id=job_id,
        original_sha256=original_sha,
        formatted_sha256=formatted_sha,
        content_fingerprint_original=original_fingerprint,
        content_fingerprint_formatted=formatted_fingerprint,
        content_preserved=content_preserved,
        package_safe=package_safe,
        formatting_report_matches=report_matches,
        rule_rechecks=rule_rechecks,
        static_status="passed" if static_passed else "failed",
        word_render=word_result,
        delivery_ready=static_passed,
        manual_checklist=MANUAL_CHECKLIST,
        limitations=[
            "OOXML 静态检查不能证明最终分页、字体替换和浮动对象位置。",
            "Word 成功导出 PDF 只证明可打开和可渲染，不代表视觉布局已人工确认。",
            "当前自动排版仅覆盖 4 条已确认的缩略词表边框规则。",
        ],
    )


def render_delivery_checklist(report: DeliveryValidationReport) -> str:
    lines = [
        "# PaperAlign 最终交付检查单",
        "",
        f"静态验证：{report.static_status}",
        f"内容指纹保持：{'是' if report.content_preserved else '否'}",
        f"Word 探测：{report.word_render.status}",
        "",
        "## 用户逐项确认",
        "",
    ]
    lines.extend(f"- [ ] {item}" for item in report.manual_checklist)
    lines.extend(["", "## 系统限制", ""])
    lines.extend(f"- {item}" for item in report.limitations)
    lines.extend(["", "完成以上人工确认前，不应把文件标记为学校最终验收通过。", ""])
    return "\n".join(lines)


def _last_json_line(output: str) -> dict[str, object]:
    for line in reversed(output.splitlines()):
        try:
            value = json.loads(line.strip())
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            continue
    return {}
