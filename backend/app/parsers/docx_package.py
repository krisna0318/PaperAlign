from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile, is_zipfile

from app.parsers.errors import DocxAnalysisError

REQUIRED_PARTS = frozenset(
    {
        "[Content_Types].xml",
        "_rels/.rels",
        "word/document.xml",
    }
)


@dataclass(frozen=True)
class PackageLimits:
    max_parts: int = 5_000
    max_part_size_bytes: int = 100 * 1024 * 1024
    max_total_uncompressed_bytes: int = 500 * 1024 * 1024
    max_compression_ratio: float = 1_000.0


@dataclass(frozen=True)
class PackageInspection:
    part_count: int
    compressed_size_bytes: int
    uncompressed_size_bytes: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DocxPackage:
    """Validated, read-only access to an OPC package."""

    def __init__(self, path: Path, limits: PackageLimits | None = None) -> None:
        self.path = path
        self.limits = limits or PackageLimits()
        self._archive: ZipFile | None = None
        self._parts: dict[str, str] = {}
        self.inspection: PackageInspection | None = None

    def __enter__(self) -> DocxPackage:
        self.open()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def open(self) -> None:
        if self.path.suffix.lower() != ".docx":
            raise DocxAnalysisError("unsupported_extension", "Input must use the .docx extension")
        if not self.path.is_file():
            raise DocxAnalysisError("input_not_found", f"Input file does not exist: {self.path}")
        if not is_zipfile(self.path):
            raise DocxAnalysisError(
                "not_a_docx_package",
                "Input is not a valid ZIP-based DOCX package",
            )

        try:
            archive = ZipFile(self.path, mode="r")
        except (BadZipFile, OSError) as exc:
            raise DocxAnalysisError("invalid_zip", "DOCX package is damaged or unreadable") from exc
        try:
            inspection, parts = self._inspect(archive)
            broken_part = archive.testzip()
        except DocxAnalysisError:
            archive.close()
            raise
        except (BadZipFile, OSError, RuntimeError) as exc:
            archive.close()
            raise DocxAnalysisError("invalid_zip", "DOCX package is damaged or unreadable") from exc

        if broken_part is not None:
            archive.close()
            raise DocxAnalysisError(
                "corrupt_part",
                f"CRC check failed for package part: {broken_part}",
            )

        self._archive = archive
        self._parts = parts
        self.inspection = inspection

    def close(self) -> None:
        if self._archive is not None:
            self._archive.close()
            self._archive = None

    def part_names(self) -> tuple[str, ...]:
        self._require_open()
        return tuple(sorted(self._parts.values()))

    def has_part(self, part_name: str) -> bool:
        self._require_open()
        return part_name.casefold() in self._parts

    def read_part(self, part_name: str) -> bytes:
        archive = self._require_open()
        actual_name = self._parts.get(part_name.casefold())
        if actual_name is None:
            raise DocxAnalysisError("missing_part", f"DOCX package part is missing: {part_name}")
        try:
            return archive.read(actual_name)
        except (BadZipFile, RuntimeError, OSError) as exc:
            raise DocxAnalysisError(
                "unreadable_part",
                f"Cannot read DOCX part: {part_name}",
            ) from exc

    def _require_open(self) -> ZipFile:
        if self._archive is None:
            raise RuntimeError("DOCX package is not open")
        return self._archive

    def _inspect(self, archive: ZipFile) -> tuple[PackageInspection, dict[str, str]]:
        infos = archive.infolist()
        if len(infos) > self.limits.max_parts:
            raise DocxAnalysisError(
                "too_many_parts",
                f"DOCX has {len(infos)} package parts; limit is {self.limits.max_parts}",
            )

        parts: dict[str, str] = {}
        compressed_total = 0
        uncompressed_total = 0

        for info in infos:
            name = info.filename
            self._validate_part_name(name)
            folded = name.casefold()
            if folded in parts:
                raise DocxAnalysisError("duplicate_part", f"Duplicate package part: {name}")
            parts[folded] = name

            if info.flag_bits & 0x1:
                raise DocxAnalysisError(
                    "encrypted_part",
                    f"Encrypted package part is unsupported: {name}",
                )
            if info.file_size > self.limits.max_part_size_bytes:
                raise DocxAnalysisError(
                    "part_too_large",
                    f"Package part exceeds size limit: {name}",
                )

            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > self.limits.max_compression_ratio:
                raise DocxAnalysisError(
                    "suspicious_compression_ratio",
                    f"Package part has a suspicious compression ratio: {name}",
                )

            compressed_total += info.compress_size
            uncompressed_total += info.file_size

        if uncompressed_total > self.limits.max_total_uncompressed_bytes:
            raise DocxAnalysisError(
                "package_too_large",
                "DOCX uncompressed content exceeds the configured safety limit",
            )

        missing = sorted(part for part in REQUIRED_PARTS if part.casefold() not in parts)
        if missing:
            raise DocxAnalysisError(
                "missing_required_part",
                f"DOCX is missing required package parts: {', '.join(missing)}",
            )

        return (
            PackageInspection(
                part_count=len(infos),
                compressed_size_bytes=compressed_total,
                uncompressed_size_bytes=uncompressed_total,
            ),
            parts,
        )

    @staticmethod
    def _validate_part_name(name: str) -> None:
        if not name or "\\" in name or name.startswith(("/", "\\")):
            raise DocxAnalysisError("unsafe_part_name", f"Unsafe package part name: {name!r}")
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "." in path.parts:
            raise DocxAnalysisError("unsafe_part_name", f"Unsafe package part name: {name!r}")
