import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.domain.profile import ApplicabilityResult, ProfileBundle
from app.domain.rules import RuleTarget
from app.profiles.loader import ProfileLoadError
from app.services.template_inspector import _write_text, inspect_template
from app.validation.comparator import validate_rule
from app.validation.object_observations import observe_section, observe_table
from app.validation.observations import observe_format


def export_profile(
    bundle: ProfileBundle, output_dir: Path, applicability: ApplicabilityResult | None = None
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_text(output_dir / "profile.json", bundle.model_dump_json(indent=2) + "\n")
    _write_text(
        output_dir / "applicability.json",
        (applicability.model_dump_json(indent=2) if applicability else "null") + "\n",
    )
    counts = Counter(rule.status.value for rule in bundle.rules)
    lines = [
        "# PaperAlign 单模板规则审查",
        "",
        f"Profile：{bundle.manifest.profile_id} / {bundle.manifest.version}",
        f"适用：{bundle.manifest.applicability.school} 当前届本科；排除外国语学院和研究生。",
        f"规则数：{len(bundle.rules)}；规则状态：{dict(counts)}。",
        "适用范围已确认；范围确认不代表每条原子规则都已经人工审核。",
        "",
    ]
    if applicability:
        lines.extend([f"本次适用判断：{applicability.status}（{applicability.reason}）", ""])
    lines.extend(
        ["## P0 覆盖", "", "| 清单项 | 原子规则数 | 覆盖 | 待实现/复核 |", "|---|---:|---|---|"]
    )
    for entry in bundle.coverage:
        lines.append(
            f"| {entry.inventory_id} | {len(entry.rule_ids)} | {entry.state} | "
            + "；".join(entry.deferred_requirements).replace("|", "\\|")
            + " |"
        )
    lines.extend(
        ["", "encoded 仅表示已编码，不能当作已通过格式检查。完整学校合规结论尚未实现。", ""]
    )
    _write_text(output_dir / "profile_summary.md", "\n".join(lines))


def verify_template_samples(
    bundle: ProfileBundle, input_path: Path, output_dir: Path
) -> dict[str, Any]:
    artifacts = inspect_template(input_path)
    if artifacts.report.input_sha256 != bundle.manifest.template_sha256:
        raise ProfileLoadError("Template hash differs; fixed sample indexes cannot be applied")
    results = []
    applied: set[str] = set()
    for sample in bundle.manifest.template_samples:
        for rule in bundle.rules:
            if rule.scope != sample.scope or rule.target != RuleTarget():
                continue
            if sample.kind == "paragraph":
                if sample.index >= len(artifacts.report.effective_formats):
                    raise ProfileLoadError("Sample paragraph index out of range")
                observation = observe_format(
                    artifacts.report.effective_formats[sample.index], rule.property_path
                )
            elif sample.kind == "table":
                if sample.index >= len(artifacts.report.tables):
                    raise ProfileLoadError("Sample table index out of range")
                observation = observe_table(
                    artifacts.report.tables[sample.index], rule.property_path
                )
            else:
                if sample.index >= len(artifacts.report.sections):
                    raise ProfileLoadError("Sample section index out of range")
                observation = observe_section(
                    artifacts.report.sections[sample.index], rule.property_path
                )
            results.append(validate_rule(rule, observation))
            applied.add(rule.id)
    counts = Counter(result.status for result in results)
    payload: dict[str, Any] = {
        "profile_id": bundle.manifest.profile_id,
        "profile_version": bundle.manifest.version,
        "input_sha256": artifacts.report.input_sha256,
        "scope": "fixed_template_samples_only",
        "full_document_evaluated": False,
        "counts": dict(sorted(counts.items())),
        "unapplied_rule_ids": sorted({rule.id for rule in bundle.rules} - applied),
        "results": [result.model_dump(mode="json") for result in results],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_text(
        output_dir / "template_rule_checks.json",
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    lines = [
        "# 模板已定位样本规则验证",
        "",
        f"结果：{dict(counts)}",
        "",
        "仅验证与模板哈希绑定的样本，不进行整篇语义识别，不代表论文合规结论。",
        "",
        "## 已确认规则的差异",
        "",
    ]
    for result in results:
        if result.status == "fail":
            actual = result.actual.model_dump_json() if result.actual else "未解析"
            lines.append(
                f"- {result.rule_id}：期望 {result.expected.model_dump_json()}；实际 {actual}；"
                f"定位 {result.locator.model_dump_json(exclude_none=True)}。"
            )
    _write_text(output_dir / "template_rule_checks.md", "\n".join(lines) + "\n")
    return payload
