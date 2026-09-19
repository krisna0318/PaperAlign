import hashlib
import json
import unicodedata

from app.domain.analysis import (
    ContentFingerprintReport,
    DocumentProfile,
    FingerprintUnit,
)
from app.domain.enums import BlockKind

NORMALIZATION_DESCRIPTION = (
    "Unicode NFC; CRLF and CR converted to LF; empty text units excluded; "
    "field instructions and media bytes included"
)


def normalize_protected_text(text: str) -> str:
    return unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_content_fingerprint(profile: DocumentProfile) -> ContentFingerprintReport:
    units: list[FingerprintUnit] = []
    canonical_units: list[dict[str, str]] = []

    for block in profile.blocks:
        if block.kind not in {BlockKind.PARAGRAPH, BlockKind.TABLE_CELL}:
            continue
        normalized = normalize_protected_text(block.text)
        if not normalized:
            continue
        units.append(
            FingerprintUnit(
                anchor=block.id,
                kind=block.kind.value,
                text_length=len(normalized),
                sha256=_sha256_text(normalized),
            )
        )
        canonical_units.append({"kind": block.kind.value, "text": normalized})

    for story in profile.story_parts:
        normalized = normalize_protected_text(story.text)
        if not normalized:
            continue
        units.append(
            FingerprintUnit(
                anchor=story.part_name,
                kind=story.kind,
                text_length=len(normalized),
                sha256=_sha256_text(normalized),
            )
        )
        canonical_units.append(
            {"kind": story.kind, "part_name": story.part_name, "text": normalized}
        )

    for index, field in enumerate(profile.fields):
        normalized = normalize_protected_text(f"{field.instruction}\u0000{field.result_text}")
        units.append(
            FingerprintUnit(
                anchor=f"field-{index:04d}:{field.part_name}",
                kind="field",
                text_length=len(normalized),
                sha256=_sha256_text(normalized),
            )
        )
        canonical_units.append(
            {
                "kind": "field",
                "part_name": field.part_name,
                "text": normalized,
            }
        )

    for media in profile.media:
        units.append(
            FingerprintUnit(
                anchor=media.part_name,
                kind="media",
                text_length=0,
                sha256=media.sha256,
            )
        )
        canonical_units.append(
            {
                "kind": "media",
                "part_name": media.part_name,
                "sha256": media.sha256,
            }
        )

    canonical = json.dumps(
        canonical_units,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return ContentFingerprintReport(
        normalization=NORMALIZATION_DESCRIPTION,
        aggregate_sha256=_sha256_text(canonical),
        unit_count=len(units),
        total_characters=sum(unit.text_length for unit in units),
        units=units,
    )
