import argparse
import json
from pathlib import Path

from pydantic import BaseModel

from app.domain.analysis import (
    ContentFingerprintReport,
    DocumentProfile,
    UnsupportedObjectsReport,
)
from app.domain.blocks import DocumentBlock
from app.domain.issues import DiagnosisIssue
from app.domain.jobs import AnalysisJob
from app.domain.profile import CoverageEntry, ProfileManifest
from app.domain.rule_validation import EvidenceSelection, RuleValidationResult
from app.domain.rules import FormatRule
from app.domain.structure import StructureOverrides, StructureReport
from app.domain.template_evidence import TemplateEvidenceReport

SCHEMAS: dict[str, type[BaseModel]] = {
    "structure_report.schema.json": StructureReport,
    "structure_overrides.schema.json": StructureOverrides,
    "profile_manifest.schema.json": ProfileManifest,
    "profile_coverage_entry.schema.json": CoverageEntry,
    "rule_validation.schema.json": RuleValidationResult,
    "evidence_selection.schema.json": EvidenceSelection,
    "document_block.schema.json": DocumentBlock,
    "format_rule.schema.json": FormatRule,
    "diagnosis_issue.schema.json": DiagnosisIssue,
    "analysis_job.schema.json": AnalysisJob,
    "document_profile.schema.json": DocumentProfile,
    "content_fingerprint.schema.json": ContentFingerprintReport,
    "unsupported_objects.schema.json": UnsupportedObjectsReport,
    "template_evidence.schema.json": TemplateEvidenceReport,
}


def export_schemas(output_dir: Path, *, check: bool = False) -> list[str]:
    if not check:
        output_dir.mkdir(parents=True, exist_ok=True)
    stale = []
    for filename, model in SCHEMAS.items():
        schema = model.model_json_schema()
        schema["$id"] = f"https://paperalign.local/schemas/{filename}"
        content = json.dumps(schema, ensure_ascii=False, indent=2) + "\n"
        path = output_dir / filename
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(filename)
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
    return stale


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    stale = export_schemas(Path(__file__).resolve().parents[2] / "schemas", check=arguments.check)
    if stale:
        print("Stale schemas: " + ", ".join(stale))
        raise SystemExit(1)
