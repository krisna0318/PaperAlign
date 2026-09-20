"""Validated loading of a single versioned local Profile, never executing profile code."""

import json
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.domain.profile import (
    ApplicabilityResult,
    CoverageEntry,
    ProfileBundle,
    ProfileManifest,
)
from app.domain.rules import FormatRule, RuleSource

BUILTIN_PROFILE_ID = "scau_undergraduate_2026_v1"


class ProfileLoadError(ValueError):
    pass


def builtin_profile_directory() -> Path:
    return Path(__file__).resolve().parent / BUILTIN_PROFILE_ID


def _read_json(root: Path, relative: str) -> Any:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
        raise ProfileLoadError("Unsafe profile file reference")
    target = (root / relative).resolve()
    if not target.is_relative_to(root) or target.suffix != ".json":
        raise ProfileLoadError("Profile files must be local JSON files")
    if target.stat().st_size > 5_000_000:
        raise ProfileLoadError("Profile file exceeds size limit")
    return json.loads(target.read_text(encoding="utf-8"))


def load_profile(directory: Path | None = None) -> ProfileBundle:
    root = (directory or builtin_profile_directory()).resolve()
    try:
        manifest = ProfileManifest.model_validate(_read_json(root, "manifest.json"))
        rules = [
            rule
            for file in manifest.rule_files
            for rule in TypeAdapter(list[FormatRule]).validate_python(_read_json(root, file))
        ]
        evidence = TypeAdapter(list[RuleSource]).validate_python(
            _read_json(root, manifest.evidence_file)
        )
        coverage = TypeAdapter(list[CoverageEntry]).validate_python(
            _read_json(root, manifest.coverage_file)
        )
        ids = [rule.id for rule in rules]
        if len(ids) != len(set(ids)) or not ids:
            raise ProfileLoadError("Empty rules or duplicate rule IDs")
        locators = [item.locator for item in evidence]
        if len(locators) != len(set(locators)):
            raise ProfileLoadError("Duplicate evidence locators")
        index = {item.locator: item for item in evidence}
        for item in evidence:
            if (
                item.document_sha256 != manifest.template_sha256
                or item.document != manifest.template_document
            ):
                raise ProfileLoadError("Evidence document or hash disagrees with manifest")
        seen_definitions: set[tuple[str, str, str, str]] = set()
        for rule in rules:
            if rule.profile_id != manifest.profile_id:
                raise ProfileLoadError("Rule belongs to a different Profile")
            if rule.source != index.get(rule.source.locator):
                raise ProfileLoadError("Rule source is missing or differs from evidence index")
            if rule.auto_fixable:
                raise ProfileLoadError("M2 Profiles are read-only")
            key = (rule.scope, rule.target.model_dump_json(), rule.property_path, rule.comparison)
            if key in seen_definitions:
                raise ProfileLoadError("Duplicate or conflicting atomic target definition")
            seen_definitions.add(key)
        inventory_ids = [entry.inventory_id for entry in coverage]
        if len(inventory_ids) != len(set(inventory_ids)):
            raise ProfileLoadError("Duplicate inventory IDs")
        references = [rid for entry in coverage for rid in entry.rule_ids]
        if len(references) != len(set(references)) or set(references) != set(ids):
            raise ProfileLoadError("Coverage must reference every rule exactly once")
        return ProfileBundle(
            manifest=manifest,
            rules=sorted(rules, key=lambda rule: rule.id),
            evidence=sorted(evidence, key=lambda item: item.locator),
            coverage=sorted(coverage, key=lambda entry: entry.inventory_id),
        )
    except (OSError, ValueError, ValidationError) as exc:
        if isinstance(exc, ProfileLoadError):
            raise
        raise ProfileLoadError("Invalid or unreadable profile data") from exc


def check_applicability(
    manifest: ProfileManifest,
    *,
    school: str | None,
    education_level: str | None,
    college: str | None,
    cohort: str | None,
) -> ApplicabilityResult:
    scope = manifest.applicability
    if school and school.strip() != scope.school:
        return ApplicabilityResult(status="not_applicable", reason="different_school")
    if education_level and education_level != scope.education_level:
        return ApplicabilityResult(status="not_applicable", reason="unsupported_education_level")
    normalized_college = (college or "").strip().removeprefix(scope.school).strip()
    if normalized_college in scope.excluded_colleges:
        return ApplicabilityResult(status="not_applicable", reason="excluded_college")
    if cohort and cohort != scope.cohort:
        return ApplicabilityResult(status="needs_review", reason="cohort_not_confirmed")
    if not all((school and school.strip(), education_level, normalized_college, cohort)):
        return ApplicabilityResult(
            status="needs_review", reason="missing_applicability_information"
        )
    return ApplicabilityResult(status="applicable", reason="confirmed_single_template_scope")
