"""Local, read-only manuscript structure review and located rule comparisons."""

import json
from collections import Counter
from html import escape
from pathlib import Path

from pydantic import ValidationError

from app import __version__
from app.domain.enums import BlockKind
from app.domain.profile import ProfileBundle
from app.domain.rule_validation import RuleObservation, RuleValidationResult
from app.domain.rules import FormatRule, RuleScope
from app.domain.structure import (
    StructureDecision,
    StructureOverrides,
    StructureReport,
    StructureWarning,
)
from app.domain.template_evidence import TemplateEvidenceReport
from app.parsers.docx_package import DocxPackage, sha256_file
from app.parsers.errors import DocxAnalysisError
from app.parsers.structure_signals import StructuralSignals, read_structure_signals
from app.profiles.loader import load_profile
from app.services.analyzer import analyze_docx
from app.services.manual_review import build_manual_review_guide, render_manual_review_markdown
from app.services.structure_classifier import classify_structure
from app.services.template_inspector import _write_text, inspect_template
from app.validation.comparator import validate_rule
from app.validation.object_observations import observe_section, observe_table
from app.validation.observations import observe_format


def load_overrides(path: Path) -> StructureOverrides:
    try:
        if path.stat().st_size > 1_000_000:
            raise DocxAnalysisError("invalid_overrides", "Correction file exceeds 1 MB")
        result = StructureOverrides.model_validate_json(path.read_text(encoding="utf-8"))
        if not result.reviewer.strip() or result.reviewer == "填写审查人":
            raise ValueError("Reviewer is required")
        if not result.decisions:
            raise ValueError("At least one correction is required")
        if any(not item.reason.strip() for item in result.decisions):
            raise ValueError("Correction reasons are required")
        return result
    except (ValidationError, ValueError) as exc:
        raise DocxAnalysisError("invalid_overrides", "Invalid correction JSON or reviewer") from exc


def _observation_for_rule(
    decision: StructureDecision,
    rule: FormatRule,
    evidence: TemplateEvidenceReport,
    signals: StructuralSignals,
) -> RuleObservation:
    anchor = decision.locator
    if anchor.paragraph_index is not None and decision.kind == BlockKind.PARAGRAPH:
        signal = signals.paragraphs.get(anchor.paragraph_index)
        if signal and signal.unsafe_objects:
            return RuleObservation(
                locator=anchor, supported=False, reason="unsupported_inline_object"
            )
        snapshot = next(
            (p for p in evidence.effective_formats if p.paragraph_index == anchor.paragraph_index),
            None,
        )
        if snapshot:
            return observe_format(snapshot, rule.property_path)
    if anchor.table_index is not None and decision.kind == BlockKind.TABLE:
        table = next((t for t in evidence.tables if t.table_index == anchor.table_index), None)
        if table:
            return observe_table(table, rule.property_path)
    return RuleObservation(
        locator=anchor, supported=False, reason="object_format_adapter_not_implemented"
    )


def compare_located_objects(
    decisions: list[StructureDecision],
    evidence: TemplateEvidenceReport,
    signals: StructuralSignals,
    bundle: ProfileBundle,
) -> tuple[list[RuleValidationResult], list[str]]:
    checks: list[RuleValidationResult] = []
    used: set[str] = set()
    for section in evidence.sections:
        for rule in bundle.rules:
            if rule.scope == RuleScope.DOCUMENT:
                checks.append(validate_rule(rule, observe_section(section, rule.property_path)))
                used.add(rule.id)
    scope_positions: Counter[tuple[str | None, str]] = Counter()
    for decision in decisions:
        if decision.requires_confirmation or decision.scope is None:
            continue
        position_key = (decision.section_id, decision.scope.value)
        position = scope_positions[position_key]
        scope_positions[position_key] += 1
        for rule in bundle.rules:
            if rule.scope != decision.scope:
                continue
            target = rule.target
            if target.paragraph_position == "first" and position > 0:
                continue
            if target.paragraph_position == "following" and position == 0:
                continue
            if target.text_part != "whole" or target.metadata_field is not None:
                # Do not compare the entire paragraph to a label-only or field-only requirement.
                observation = RuleObservation(
                    locator=decision.locator, supported=False, reason="target_span_not_located"
                )
            else:
                observation = _observation_for_rule(decision, rule, evidence, signals)
            checks.append(validate_rule(rule, observation))
            used.add(rule.id)
    return checks, sorted({rule.id for rule in bundle.rules} - used)


def inspect_structure(
    input_path: Path,
    *,
    overrides: StructureOverrides | None = None,
    include_preview: bool = False,
) -> StructureReport:
    analysis = analyze_docx(input_path)
    evidence = inspect_template(input_path).report
    with DocxPackage(input_path) as package:
        signals = read_structure_signals(package)
    input_hash = analysis.document_profile.package.input_sha256
    if input_hash != evidence.input_sha256 or input_hash != sha256_file(input_path):
        raise DocxAnalysisError(
            "input_changed_during_analysis", "Input changed during structure analysis"
        )
    decisions, warnings = classify_structure(
        analysis.document_profile, evidence.effective_formats, signals, overrides
    )
    if include_preview:
        texts = {b.id: b.text for b in analysis.document_profile.blocks}
        decisions = [d.model_copy(update={"preview": texts[d.block_id][:20]}) for d in decisions]
    bundle = load_profile()
    checks, unapplied = compare_located_objects(decisions, evidence, signals, bundle)
    unsupported = Counter(item.category for item in analysis.unsupported_objects.objects)
    review_ids = {d.block_id for d in decisions if d.requires_confirmation}
    review_roots = [
        d.block_id
        for d in decisions
        if d.requires_confirmation and d.container_id not in review_ids
    ]
    if unsupported:
        warnings.append(
            StructureWarning(
                code="unsupported_objects_present",
                message="文档包含不支持对象；需要结合 M1 报告与 Word 页面复核。",
            )
        )
    return StructureReport(
        classifier_version=__version__,
        profile_id=bundle.manifest.profile_id,
        input_sha256=input_hash,
        content_fingerprint=analysis.content_fingerprint.aggregate_sha256,
        previews_included=include_preview,
        override_reviewer=overrides.reviewer if overrides else None,
        applied_overrides=overrides,
        decisions=decisions,
        warnings=warnings,
        role_counts=dict(sorted(Counter(d.role.value for d in decisions).items())),
        review_count=sum(d.requires_confirmation for d in decisions),
        review_root_ids=review_roots,
        unsupported_object_counts=dict(sorted(unsupported.items())),
        validation_counts=dict(sorted(Counter(c.status for c in checks).items())),
        rule_checks=checks,
        unapplied_rule_ids=unapplied,
    )


def _render_html(report: StructureReport) -> str:
    manual_guide = build_manual_review_guide(report)
    cards = []
    for item in report.decisions:
        status = "待确认" if item.requires_confirmation else "已识别"
        title = f"{item.block_id} · {item.role.value} · {status}"
        description = {
            "范围": item.scope.value if item.scope else "未映射规则范围",
            "分区": item.region,
            "父节点": item.parent_id,
            "判断来源": item.decision_source.value,
            "启发式分数（不是准确率）": item.confidence,
            "依据": item.reasons,
            "原文定位": item.locator.model_dump(exclude_none=True),
        }
        preview = f"<p>{escape(item.preview)}</p>" if item.preview is not None else ""
        cards.append(
            f'<details id="{escape(item.block_id, quote=True)}" '
            f'class="{"review" if item.requires_confirmation else "identified"}">'
            f"<summary>{escape(title)}</summary>{preview}"
            f"<pre>{escape(json.dumps(description, ensure_ascii=False, indent=2))}</pre></details>"
        )
    review_links = " · ".join(
        f'<a href="#{escape(d.block_id, quote=True)}">{escape(d.block_id)}</a>'
        for d in report.decisions
        if d.block_id in report.review_root_ids
    )
    warning_list = "".join(
        f"<li>{escape(w.code)}：{escape(w.message)}</li>" for w in report.warnings
    )
    manual_items = "".join(
        '<details class="manual"><summary>'
        + escape(item.title)
        + "</summary><p><strong>注意事项：</strong>"
        + escape(item.customer_notice)
        + "</p><ol>"
        + "".join(
            f"<li>{escape(step.instruction)}<br><small>预期结果："
            f"{escape(step.expected_result)}</small></li>"
            for step in item.steps
        )
        + "</ol></details>"
        for item in manual_guide.items
    )
    return (
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;">'
        "<title>PaperAlign 结构审查</title><style>body{font:16px/1.6 system-ui;max-width:1000px;"
        "margin:32px auto;padding:0 20px;color:#172b4d;background:#f5f7fa}details{background:#fff;"
        "padding:14px;border:1px solid #dce3ec;border-radius:8px;margin:10px 0}"
        ".review{border-left:5px solid #bf7516}.manual{border-left:5px solid #235db0}"
        "summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#235db0}</style>"
        "<h1>PaperAlign 结构审查</h1>"
        f"<p>{len(report.decisions)} 个文档块；{report.review_count} 个待确认。</p>"
        f"<p>优先检查 {len(report.review_root_ids)} 个入口；"
        "其中表格确认后，其单元格的继承状态会重新计算。</p>"
        "<p>点击条目查看识别依据；预览最多 20 字。段落索引从 0 开始。"
        "本报告用于结构审查，尚未生成排版副本；识别数量不能用作准确率。</p>"
        f"<p>输入 SHA-256：{report.input_sha256}</p><ul>{warning_list}</ul>"
        "<h2>必须人工完成的 Word 复核</h2>"
        f"<p>{escape(manual_guide.scope_statement)}</p>{manual_items}"
        f"<h2>待确认定位</h2><p>{review_links or '当前没有待确认项'}</p>"
        + "".join(cards)
        + "</html>"
    )


def write_structure_review(
    input_path: Path,
    output_dir: Path,
    *,
    overrides_path: Path | None = None,
    include_preview: bool = False,
) -> StructureReport:
    local_root = Path(__file__).resolve().parents[3] / ".paperalign"
    output_dir = output_dir.resolve()
    if local_root.resolve() != local_root or not output_dir.is_relative_to(local_root):
        raise DocxAnalysisError(
            "private_output_required", "Structure review must stay under .paperalign"
        )
    reserved = {
        output_dir / name
        for name in (
            "structure_report.json",
            "structure_summary.md",
            "structure_review.html",
            "corrections.template.json",
            "manual_review_guide.json",
            "manual_review_guide.md",
        )
    }
    if input_path.resolve() in reserved or (
        overrides_path and overrides_path.resolve() in reserved
    ):
        raise DocxAnalysisError(
            "output_input_collision", "Choose another output directory to preserve inputs"
        )
    overrides = load_overrides(overrides_path) if overrides_path else None
    report = inspect_structure(input_path, overrides=overrides, include_preview=include_preview)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_text(output_dir / "structure_report.json", report.model_dump_json(indent=2) + "\n")
    _write_text(output_dir / "structure_review.html", _render_html(report))
    manual_guide = build_manual_review_guide(report)
    _write_text(
        output_dir / "manual_review_guide.json", manual_guide.model_dump_json(indent=2) + "\n"
    )
    _write_text(output_dir / "manual_review_guide.md", render_manual_review_markdown(manual_guide))
    lines = [
        "# PaperAlign 结构识别摘要",
        "",
        f"输入 SHA-256：{report.input_sha256}",
        f"文档块：{len(report.decisions)}；待确认：{report.review_count}。",
        f"优先复核入口：{len(report.review_root_ids)}；父表待确认时不重复列出单元格入口。",
        "启发式分数不是准确率；范围限于当前解析器已表示的文档块，嵌套/包装结构见警告。",
        "",
        "| 角色 | 数量 |",
        "|---|---:|",
    ]
    lines.extend(f"| {role} | {count} |" for role, count in report.role_counts.items())
    lines.extend(
        [
            "",
            "## 已定位对象的规则检查",
            "",
            f"状态次数：{report.validation_counts}",
            f"尚未应用的规则：{len(report.unapplied_rule_ids)} 条。",
            "规则暂定、无法解析、目标片段尚未定位均保留原有状态；尚未得出全文合规结论。",
            "",
            "## 待确认文档块",
            "",
            "| ID | 候选角色 | 依据 |",
            "|---|---|---|",
        ]
    )
    lines.extend(
        f"| {d.block_id} | {d.role.value} | {', '.join(d.reasons)} |"
        for d in report.decisions
        if d.block_id in report.review_root_ids
    )
    lines.extend(["", "## 警告", ""])
    lines.extend(f"- {w.code}（{w.block_id or '文档'}）：{w.message}" for w in report.warnings)
    lines.extend(
        [
            "",
            "## 人工纠正",
            "",
            "复制 corrections.template.json 为 corrections.json，填写 reviewer 和 decisions。",
            'decisions 中每项为 {"block_id":"p-0000","role":"heading_1",'
            '"scope":"heading_1","reason":"人工核对为一级标题"}；'
            "同一角色可能对应多种格式范围时必须填写 scope。",
            "以 --overrides 指定 corrections.json 再运行 classify，"
            "后续分区与层级会重算；原 DOCX 不变。",
            "",
            "## 最终页面注意事项",
            "",
            "系统不能从 DOCX 静态结构可靠证明最终分页。请按 manual_review_guide.md "
            "在桌面版 Word 中完成逐项复核。",
            "",
        ]
    )
    _write_text(output_dir / "structure_summary.md", "\n".join(lines))
    template = StructureOverrides(input_sha256=report.input_sha256, reviewer="填写审查人")
    _write_text(output_dir / "corrections.template.json", template.model_dump_json(indent=2) + "\n")
    return report
