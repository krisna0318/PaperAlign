from pathlib import Path

from fastapi.testclient import TestClient

from app.formatting.safe_formatter import ABBREVIATION_RULE_IDS
from app.main import app
from app.settings import Settings, get_settings
from tests.support.docx_factory import create_synthetic_docx


def _client(data_dir: Path) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=data_dir)
    return TestClient(app)


def test_upload_creates_persistent_read_only_diagnosis(tmp_path: Path) -> None:
    source = create_synthetic_docx(tmp_path / "source.docx", include_unsupported=True)
    original = source.read_bytes()
    client = _client(tmp_path / "private")
    try:
        response = client.post(
            "/api/jobs",
            params={"filename": "测试论文.docx"},
            content=original,
            headers={
                "content-type": (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            },
        )
        assert response.status_code == 201
        payload = response.json()
        job_id = payload["job"]["id"]
        assert payload["job"]["status"] == "awaiting_confirmation"
        assert payload["job"]["ai_mode"] == "off"
        assert payload["summary"]["formatting_allowed"] is False
        assert payload["summary"]["conclusion"] == "diagnosis_only_not_compliance_proof"
        assert payload["summary"]["total_blocks"] > 0
        assert payload["summary"]["unsupported_object_counts"]
        assert payload["summary"]["issue_count"] >= len(payload["summary"]["issues"])
        assert len(payload["summary"]["issues"]) <= 100
        assert len(payload["summary"]["review_items"]) == payload["summary"][
            "review_root_count"
        ]
        assert all(
            len(item.get("preview") or "") <= 20
            for item in payload["summary"]["review_items"]
        )

        stored = client.get(f"/api/jobs/{job_id}")
        assert stored.status_code == 200
        assert stored.json() == payload
        assert source.read_bytes() == original
        assert (tmp_path / "private" / "jobs" / job_id / "input" / "测试论文.docx").is_file()
    finally:
        app.dependency_overrides.clear()


def test_upload_rejects_non_docx_without_creating_job(tmp_path: Path) -> None:
    client = _client(tmp_path / "private")
    try:
        response = client.post(
            "/api/jobs", params={"filename": "notes.txt"}, content=b"not a docx"
        )
        assert response.status_code == 415
        assert response.json()["detail"]["code"] == "unsupported_file_type"
        assert not (tmp_path / "private" / "jobs").exists()
    finally:
        app.dependency_overrides.clear()


def test_job_lookup_rejects_path_traversal(tmp_path: Path) -> None:
    client = _client(tmp_path / "private")
    try:
        response = client.get("/api/jobs/not-a-job-id")
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_job_id"
    finally:
        app.dependency_overrides.clear()


def test_job_can_generate_and_download_a_content_preserving_copy(tmp_path: Path) -> None:
    source = create_synthetic_docx(
        tmp_path / "source.docx",
        heading_text="缩略词表",
        include_second_table_row=True,
    )
    client = _client(tmp_path / "private")
    try:
        created = client.post(
            "/api/jobs", params={"filename": source.name}, content=source.read_bytes()
        )
        assert created.status_code == 201
        payload = created.json()
        job_id = payload["job"]["id"]
        assert payload["summary"]["formatting_candidate_count"] == 1
        assert set(payload["summary"]["formatting_rule_ids"]) == ABBREVIATION_RULE_IDS

        formatted = client.post(
            f"/api/jobs/{job_id}/format",
            json={"approved_rule_ids": sorted(ABBREVIATION_RULE_IDS)},
        )
        assert formatted.status_code == 200
        assert formatted.json()["report"]["content_preserved"] is True
        assert len(formatted.json()["report"]["operations"]) == 4

        downloaded = client.get(f"/api/jobs/{job_id}/download")
        assert downloaded.status_code == 200
        assert downloaded.content.startswith(b"PK")
        stored = client.get(f"/api/jobs/{job_id}").json()
        assert stored["job"]["status"] == "completed"
        assert any(item["kind"] == "formatted_docx" for item in stored["job"]["artifacts"])
    finally:
        app.dependency_overrides.clear()
