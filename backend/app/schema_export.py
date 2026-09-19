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
from app.domain.rules import FormatRule

SCHEMAS: dict[str, type[BaseModel]] = {
    "document_block.schema.json": DocumentBlock,
    "format_rule.schema.json": FormatRule,
    "diagnosis_issue.schema.json": DiagnosisIssue,
    "analysis_job.schema.json": AnalysisJob,
    "document_profile.schema.json": DocumentProfile,
    "content_fingerprint.schema.json": ContentFingerprintReport,
    "unsupported_objects.schema.json": UnsupportedObjectsReport,
}


def export_schemas(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, model in SCHEMAS.items():
        schema = model.model_json_schema()
        schema["$id"] = f"https://paperalign.local/schemas/{filename}"
        (output_dir / filename).write_text(
            json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    export_schemas(Path(__file__).resolve().parents[2] / "schemas")
