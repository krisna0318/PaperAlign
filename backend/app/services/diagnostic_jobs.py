from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from app.domain.diagnostic_jobs import (
    DiagnosticIssueItem,
    DiagnosticJobView,
    DiagnosticReviewItem,
    DiagnosticSummary,
)
from app.domain.enums import AiMode, JobStatus
from app.domain.jobs import AnalysisJob, ArtifactReference
from app.parsers.docx_package import sha256_file
from app.parsers.errors import DocxAnalysisError
from app.profiles.loader import BUILTIN_PROFILE_ID
from app.services.structure_service import inspect_structure

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class DiagnosticJobError(Exception):
    def __init__(self, code: str, message: str, *, job_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.job_id = job_id


def validate_upload(filename: str, payload: bytes) -> str:
    normalized = filename.strip()
    if (
        not normalized
        or normalized != Path(normalized).name
        or "/" in normalized
        or "\\" in normalized
    ):
        raise DiagnosticJobError("invalid_filename", "文件名不安全，请重新选择 DOCX 文件。")
    if Path(normalized).suffix.lower() != ".docx":
        raise DiagnosticJobError("unsupported_file_type", "当前仅支持 .docx 文件。")
    if not payload:
        raise DiagnosticJobError("empty_upload", "上传文件为空。")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise DiagnosticJobError("upload_too_large", "文件超过 50 MB 限制。")
    return normalized


def create_diagnostic_job(data_dir: Path, filename: str, payload: bytes) -> DiagnosticJobView:
    safe_filename = validate_upload(filename, payload)
    root = data_dir.resolve()
    job_id = uuid4().hex
    job_dir = root / "jobs" / job_id
    input_dir = job_dir / "input"
    artifact_dir = job_dir / "artifacts"
    input_dir.mkdir(parents=True, exist_ok=False)
    artifact_dir.mkdir(parents=True, exist_ok=False)
    input_path = input_dir / safe_filename
    _write_bytes(input_path, payload)

    now = datetime.now(UTC)
    job = AnalysisJob(
        id=job_id,
        profile_id=BUILTIN_PROFILE_ID,
        status=JobStatus.ANALYZING,
        ai_mode=AiMode.OFF,
        created_at=now,
        updated_at=now,
        input_filename=safe_filename,
        input_sha256=sha256_file(input_path),
        artifacts=[_artifact(root, "input_copy", input_path)],
    )
    _write_json(job_dir / "job.json", DiagnosticJobView(job=job))

    try:
        report = inspect_structure(input_path, include_preview=True)
        structure_path = artifact_dir / "structure_report.json"
        _write_text(structure_path, report.model_dump_json(indent=2) + "\n")
        review_roots = set(report.review_root_ids)
        review_items = [
            DiagnosticReviewItem(
                block_id=item.block_id,
                role=item.role.value,
                scope=item.scope,
                confidence=item.confidence,
                preview=item.preview,
                reasons=item.reasons,
                locator=item.locator,
            )
            for item in report.decisions
            if item.block_id in review_roots
        ]
        all_issue_items = [
            DiagnosticIssueItem(
                rule_id=item.rule_id,
                property_path=item.property_path,
                status=item.status,
                expected=item.expected,
                actual=item.actual,
                reason=item.reason,
                locator=item.locator,
            )
            for item in report.rule_checks
            if item.status in {"fail", "evidence_insufficient"}
        ]
        all_issue_items.sort(key=lambda item: (item.status != "fail", item.rule_id))
        issue_items = all_issue_items[:100]
        summary = DiagnosticSummary(
            input_sha256=report.input_sha256,
            content_fingerprint=report.content_fingerprint,
            total_blocks=len(report.decisions),
            review_count=report.review_count,
            review_root_count=len(review_items),
            role_counts=report.role_counts,
            validation_counts=report.validation_counts,
            unsupported_object_counts=report.unsupported_object_counts,
            warnings=[item.message for item in report.warnings],
            review_items=review_items,
            issues=issue_items,
            issue_count=len(all_issue_items),
            issues_truncated=len(all_issue_items) > len(issue_items),
            evidence_insufficient_count=report.validation_counts.get(
                "evidence_insufficient", 0
            ),
        )
        summary_path = artifact_dir / "diagnostic_summary.json"
        _write_json(summary_path, summary)
        completed_at = datetime.now(UTC)
        job = job.model_copy(
            update={
                "status": JobStatus.AWAITING_CONFIRMATION,
                "updated_at": completed_at,
                "artifacts": [
                    *job.artifacts,
                    _artifact(root, "structure_report", structure_path),
                    _artifact(root, "diagnostic_summary", summary_path),
                ],
            }
        )
        view = DiagnosticJobView(job=job, summary=summary)
        _write_json(job_dir / "job.json", view)
        return view
    except (DocxAnalysisError, OSError, ValueError) as exc:
        code = exc.code if isinstance(exc, DocxAnalysisError) else "analysis_failed"
        message = exc.message if isinstance(exc, DocxAnalysisError) else "DOCX 分析失败。"
        failed = job.model_copy(
            update={
                "status": JobStatus.FAILED,
                "updated_at": datetime.now(UTC),
                "error_code": code,
                "error_message": message,
            }
        )
        _write_json(job_dir / "job.json", DiagnosticJobView(job=failed))
        raise DiagnosticJobError(code, message, job_id=job_id) from exc


def get_diagnostic_job(data_dir: Path, job_id: str) -> DiagnosticJobView:
    if len(job_id) != 32 or any(character not in "0123456789abcdef" for character in job_id):
        raise DiagnosticJobError("invalid_job_id", "任务编号格式无效。")
    path = data_dir.resolve() / "jobs" / job_id / "job.json"
    try:
        return DiagnosticJobView.model_validate_json(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DiagnosticJobError("job_not_found", "未找到该分析任务。") from exc
    except (OSError, ValidationError) as exc:
        raise DiagnosticJobError("job_unreadable", "任务记录无法读取。") from exc


def _artifact(root: Path, kind: str, path: Path) -> ArtifactReference:
    return ArtifactReference(
        kind=kind,
        relative_path=path.relative_to(root).as_posix(),
        sha256=sha256_file(path),
    )


def _write_json(path: Path, value: BaseModel) -> None:
    payload = value.model_dump(mode="json")
    _write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)
