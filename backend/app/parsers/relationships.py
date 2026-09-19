from __future__ import annotations

import posixpath
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.parsers.docx_package import DocxPackage
from app.parsers.namespaces import NS
from app.parsers.xml_utils import parse_xml


@dataclass(frozen=True)
class Relationship:
    source_part: str
    relationship_id: str
    relationship_type: str
    target: str
    target_mode: str | None
    resolved_target: str | None

    @property
    def external(self) -> bool:
        return (self.target_mode or "").casefold() == "external"


def source_part_for_relationships(rels_part: str) -> str:
    if rels_part == "_rels/.rels":
        return ""
    path = PurePosixPath(rels_part)
    if len(path.parts) < 3 or path.parts[-2] != "_rels" or not path.name.endswith(".rels"):
        return ""
    source_name = path.name.removesuffix(".rels")
    return str(PurePosixPath(*path.parts[:-2], source_name))


def resolve_relationship_target(source_part: str, target: str) -> str | None:
    if target.startswith("/"):
        candidate = target.lstrip("/")
    else:
        source_dir = posixpath.dirname(source_part)
        candidate = posixpath.normpath(posixpath.join(source_dir, target))
    if candidate == ".." or candidate.startswith("../"):
        return None
    return candidate


def parse_all_relationships(package: DocxPackage) -> list[Relationship]:
    relationships: list[Relationship] = []
    for part_name in package.part_names():
        if not part_name.endswith(".rels"):
            continue
        source_part = source_part_for_relationships(part_name)
        root = parse_xml(package.read_part(part_name), part_name)
        for element in root.findall("./pr:Relationship", namespaces=NS):
            target = element.get("Target", "")
            target_mode = element.get("TargetMode")
            external = (target_mode or "").casefold() == "external"
            relationships.append(
                Relationship(
                    source_part=source_part,
                    relationship_id=element.get("Id", ""),
                    relationship_type=element.get("Type", ""),
                    target=target,
                    target_mode=target_mode,
                    resolved_target=None
                    if external
                    else resolve_relationship_target(source_part, target),
                )
            )
    return sorted(
        relationships,
        key=lambda item: (
            item.source_part,
            item.relationship_id,
            item.relationship_type,
            item.target,
        ),
    )
