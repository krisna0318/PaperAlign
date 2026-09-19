from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.analysis import UnsupportedObject, UnsupportedObjectsReport
from app.parsers.content_types import ContentTypeMap
from app.parsers.document_parser import iter_xml_parts
from app.parsers.docx_package import DocxPackage
from app.parsers.namespaces import OFFICE, M, V, W, qn
from app.parsers.relationships import Relationship
from app.parsers.xml_utils import parse_xml


@dataclass(frozen=True)
class Finding:
    category: str
    severity: str
    policy: str
    part_name: str
    message: str
    relationship_type: str | None = None
    target: str | None = None
    external: bool = False
    details: dict[str, object] = field(default_factory=dict)


RELATIONSHIP_CATEGORIES = (
    ("/oleObject", "ole_object", "error", "block_formatting"),
    ("/package", "embedded_package", "error", "block_formatting"),
    ("/aFChunk", "alt_chunk", "error", "block_formatting"),
    ("/activeX", "active_x", "error", "block_formatting"),
    ("/chart", "chart", "warning", "manual_review"),
    ("/diagram", "smart_art", "warning", "manual_review"),
)


ELEMENT_CATEGORIES = (
    (qn(W, "altChunk"), "alt_chunk", "error", "block_formatting", "altChunk content"),
    (qn(OFFICE, "OLEObject"), "ole_object", "error", "block_formatting", "OLE object"),
    (qn(W, "object"), "embedded_object", "error", "block_formatting", "embedded object"),
    (qn(W, "sdt"), "content_control", "warning", "manual_review", "content control"),
    (qn(M, "oMath"), "equation", "warning", "manual_review", "Office Math equation"),
    (qn(M, "oMathPara"), "equation", "warning", "manual_review", "Office Math equation"),
    (qn(V, "textbox"), "text_box", "warning", "manual_review", "VML text box"),
    (qn(W, "txbxContent"), "text_box", "warning", "manual_review", "text box content"),
    (qn(W, "ins"), "tracked_changes", "warning", "manual_review", "tracked insertion"),
    (qn(W, "del"), "tracked_changes", "warning", "manual_review", "tracked deletion"),
)


def detect_unsupported_objects(
    package: DocxPackage,
    content_types: ContentTypeMap,
    relationships: list[Relationship],
) -> UnsupportedObjectsReport:
    findings: list[Finding] = []
    part_names = set(package.part_names())

    if content_types.macro_enabled or any(
        part_name.casefold().endswith("vbaproject.bin") for part_name in part_names
    ):
        findings.append(
            Finding(
                category="macro",
                severity="error",
                policy="block_formatting",
                part_name="word/vbaProject.bin",
                message="Macro-enabled content requires manual review before formatting",
            )
        )

    for part_name in sorted(part_names):
        folded = part_name.casefold()
        if folded.startswith("word/activex/"):
            findings.append(
                Finding(
                    "active_x",
                    "error",
                    "block_formatting",
                    part_name,
                    "ActiveX control is not safe for automatic formatting",
                )
            )
        elif folded.startswith("word/embeddings/"):
            findings.append(
                Finding(
                    "embedded_package",
                    "error",
                    "block_formatting",
                    part_name,
                    "Embedded package is not safe for automatic formatting",
                )
            )
        elif folded.startswith("customxml/"):
            findings.append(
                Finding(
                    "custom_xml",
                    "info",
                    "report_only",
                    part_name,
                    "Custom XML is preserved but not semantically interpreted",
                )
            )
        elif folded.startswith("_xmlsignatures/"):
            findings.append(
                Finding(
                    "digital_signature",
                    "warning",
                    "manual_review",
                    part_name,
                    "Editing may invalidate the package digital signature",
                )
            )

    for relationship in relationships:
        if not relationship.external:
            if relationship.resolved_target is None:
                findings.append(
                    Finding(
                        "unsafe_relationship_target",
                        "error",
                        "block_formatting",
                        relationship.source_part or "_rels/.rels",
                        "Relationship target escapes the package boundary",
                        relationship.relationship_type,
                        relationship.target,
                    )
                )
            elif relationship.resolved_target not in part_names:
                findings.append(
                    Finding(
                        "broken_relationship",
                        "error",
                        "block_formatting",
                        relationship.source_part or "_rels/.rels",
                        "Internal relationship target is missing from the package",
                        relationship.relationship_type,
                        relationship.resolved_target,
                    )
                )

        for suffix, category, severity, policy in RELATIONSHIP_CATEGORIES:
            if relationship.relationship_type.endswith(suffix):
                findings.append(
                    Finding(
                        category,
                        severity,
                        policy,
                        relationship.source_part or "_rels/.rels",
                        f"Relationship type is not fully supported: {category}",
                        relationship.relationship_type,
                        relationship.target,
                        relationship.external,
                    )
                )

        if relationship.external:
            policy = (
                "block_formatting"
                if relationship.relationship_type.endswith(("/oleObject", "/attachedTemplate"))
                else "manual_review"
            )
            findings.append(
                Finding(
                    "external_relationship",
                    "error" if policy == "block_formatting" else "warning",
                    policy,
                    relationship.source_part or "_rels/.rels",
                    "Document contains a relationship to an external resource",
                    relationship.relationship_type,
                    relationship.target,
                    True,
                )
            )

    for part_name in iter_xml_parts(package):
        root = parse_xml(package.read_part(part_name), part_name)
        for tag, category, severity, policy, label in ELEMENT_CATEGORIES:
            count = len(root.findall(f".//{tag}"))
            if count:
                findings.append(
                    Finding(
                        category,
                        severity,
                        policy,
                        part_name,
                        f"Detected {label}; automatic formatting support is incomplete",
                        details={"count": count},
                    )
                )
        nested_table_count = len(root.findall(".//w:tc/w:tbl", namespaces={"w": W}))
        if nested_table_count:
            findings.append(
                Finding(
                    "nested_table",
                    "warning",
                    "manual_review",
                    part_name,
                    "Nested tables require manual review before automatic formatting",
                    details={"count": nested_table_count},
                )
            )

    unique_findings: dict[tuple[object, ...], Finding] = {}
    for finding in findings:
        key = (
            finding.category,
            finding.part_name,
            finding.relationship_type,
            finding.target,
            finding.message,
            tuple(sorted((name, repr(value)) for name, value in finding.details.items())),
        )
        unique_findings.setdefault(key, finding)

    deduplicated = sorted(
        unique_findings.values(),
        key=lambda item: (
            item.category,
            item.part_name,
            item.relationship_type or "",
            item.target or "",
            item.message,
        ),
    )
    objects = [
        UnsupportedObject(
            id=f"unsupported-{index:04d}",
            category=finding.category,
            severity=finding.severity,
            policy=finding.policy,
            part_name=finding.part_name,
            message=finding.message,
            relationship_type=finding.relationship_type,
            target=finding.target,
            external=finding.external,
            details=finding.details,
        )
        for index, finding in enumerate(deduplicated, start=1)
    ]
    return UnsupportedObjectsReport(
        safe_for_future_formatting=not any(
            item.policy == "block_formatting" for item in objects
        ),
        object_count=len(objects),
        error_count=sum(item.severity == "error" for item in objects),
        warning_count=sum(item.severity == "warning" for item in objects),
        info_count=sum(item.severity == "info" for item in objects),
        objects=objects,
    )
