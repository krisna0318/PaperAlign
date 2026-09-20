import json
import re
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest
from jsonschema import Draft202012Validator

from app.domain.profile import CoverageEntry, ProfileManifest, TemplateSample
from app.domain.rules import FormatRule
from app.parsers.docx_package import sha256_file
from app.profiles.loader import (
    ProfileLoadError,
    builtin_profile_directory,
    check_applicability,
    load_profile,
)
from app.services.profile_service import export_profile, verify_template_samples
from paperalign.cli import main
from tests.support.docx_factory import create_synthetic_docx, write_deterministic_zip


def test_builtin_profile_covers_inventory_and_all_json_passes_schema() -> None:
    bundle = load_profile()
    schema = Draft202012Validator(FormatRule.model_json_schema())
    for rule in bundle.rules:
        schema.validate(rule.model_dump(mode="json"))
    Draft202012Validator(ProfileManifest.model_json_schema()).validate(
        bundle.manifest.model_dump(mode="json")
    )
    for entry in bundle.coverage:
        Draft202012Validator(CoverageEntry.model_json_schema()).validate(
            entry.model_dump(mode="json")
        )
    text = (
        Path(__file__).resolve().parents[2] / "docs/product/scau-p0-rule-inventory.md"
    ).read_text(encoding="utf-8")
    ids = set(re.findall(r"SCAU-P0-[A-Z0-9-]+", text))
    assert ids == {entry.inventory_id for entry in bundle.coverage}
    assert len(bundle.rules) == 248
    assert sum(rule.status == "confirmed" for rule in bundle.rules) == 4
    assert all(not rule.auto_fixable for rule in bundle.rules)


@pytest.mark.parametrize(
    "level,college,cohort,expected",
    [
        ("undergraduate", "软件学院", "current_graduates_at_2026-09-20", "applicable"),
        ("undergraduate", "外国语学院", "current_graduates_at_2026-09-20", "not_applicable"),
        (
            "undergraduate",
            "华南农业大学 外国语学院",
            "current_graduates_at_2026-09-20",
            "not_applicable",
        ),
        ("master", "软件学院", "current_graduates_at_2026-09-20", "not_applicable"),
        ("doctoral", "软件学院", "current_graduates_at_2026-09-20", "not_applicable"),
        ("undergraduate", None, "current_graduates_at_2026-09-20", "needs_review"),
        ("undergraduate", "软件学院", "next_year", "needs_review"),
    ],
)
def test_applicability_is_explicit(level, college, cohort, expected) -> None:
    result = check_applicability(
        load_profile().manifest,
        school="华南农业大学",
        education_level=level,
        college=college,
        cohort=cohort,
    )
    assert result.status == expected


@pytest.mark.parametrize(
    "case",
    [
        "duplicate_id",
        "wrong_profile",
        "wrong_evidence",
        "wrong_hash",
        "path_traversal",
        "missing_coverage",
        "conflicting_target",
    ],
)
def test_invalid_profile_cannot_load(tmp_path: Path, case: str) -> None:
    root = tmp_path / "profile"
    shutil.copytree(builtin_profile_directory(), root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    rules_file = root / manifest["rule_files"][0]
    rules = json.loads(rules_file.read_text(encoding="utf-8"))
    if case == "duplicate_id":
        rules[0]["id"] = rules[1]["id"]
    elif case == "wrong_profile":
        rules[0]["profile_id"] = "other"
    elif case == "wrong_evidence":
        rules[0]["source"]["locator"] = "missing:1"
    elif case == "wrong_hash":
        manifest["template_sha256"] = "a" * 64
    elif case == "path_traversal":
        manifest["rule_files"][0] = "../outside.json"
    elif case == "conflicting_target":
        rules[1]["property_path"] = rules[0]["property_path"]
    else:
        path = root / "coverage.json"
        entries = json.loads(path.read_text(encoding="utf-8"))
        entries[0]["rule_ids"].pop()
        path.write_text(json.dumps(entries), encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    rules_file.write_text(json.dumps(rules), encoding="utf-8")
    with pytest.raises(ProfileLoadError):
        load_profile(root)


def test_export_is_deterministic_and_clears_previous_applicability(tmp_path: Path) -> None:
    bundle = load_profile()
    rejected = check_applicability(
        bundle.manifest, school="other", education_level=None, college=None, cohort=None
    )
    export_profile(bundle, tmp_path / "a", rejected)
    export_profile(bundle, tmp_path / "a")
    export_profile(bundle, tmp_path / "b")
    for name in ("profile.json", "profile_summary.md", "applicability.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    assert json.loads((tmp_path / "a/applicability.json").read_text()) is None


@pytest.mark.parametrize("separator,counts", [(8, {"pass": 4}), (4, {"fail": 1, "pass": 3})])
def test_template_pipeline_detects_known_three_line_table_deviation(
    tmp_path, separator, counts
) -> None:
    source = create_synthetic_docx(tmp_path / "test.docx", include_three_line_table=True)
    with ZipFile(source) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    parts["word/document.xml"] = parts["word/document.xml"].replace(
        b'w:sz="8"', f'w:sz="{separator}"'.encode()
    )
    write_deterministic_zip(source, parts)
    bundle = load_profile()
    # Bind the test-only sample map to this synthetic input, never to real manuscript text.
    manifest = bundle.manifest.model_copy(
        update={
            "template_sha256": sha256_file(source),
            "template_samples": [TemplateSample(kind="table", index=0, scope="abbreviation_table")],
        }
    )
    bundle = bundle.model_copy(update={"manifest": manifest})
    before = sha256_file(source)
    result = verify_template_samples(bundle, source, tmp_path / "result")
    assert result["counts"] == counts
    assert result["full_document_evaluated"] is False
    assert sha256_file(source) == before
    assert "unapplied_rule_ids" in result


def test_fixed_template_indexes_cannot_be_used_for_other_documents(tmp_path: Path) -> None:
    source = create_synthetic_docx(tmp_path / "other.docx")
    with pytest.raises(ProfileLoadError, match="hash"):
        verify_template_samples(load_profile(), source, tmp_path / "result")
    assert not (tmp_path / "result").exists()


def test_cli_inspects_builtin_profile(tmp_path: Path, capsys) -> None:
    assert main(["inspect-profile", "--out", str(tmp_path / "out")]) == 0
    assert "248 rules" in capsys.readouterr().out
