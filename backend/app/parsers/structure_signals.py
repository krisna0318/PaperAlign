"""Read structural signals without treating field instructions as executable content."""

from dataclasses import dataclass, field

from app.parsers.docx_package import DocxPackage
from app.parsers.namespaces import NS, W, qn
from app.parsers.xml_utils import parse_xml


@dataclass(frozen=True)
class ParagraphSignals:
    in_toc_field: bool = False
    unsafe_objects: tuple[str, ...] = ()
    has_numbering: bool = False


@dataclass
class FieldState:
    instruction: str = ""

    @property
    def is_toc(self) -> bool:
        words = self.instruction.strip().upper().split()
        return bool(words and words[0] == "TOC")


@dataclass
class StructuralSignals:
    paragraphs: dict[int, ParagraphSignals] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def read_structure_signals(package: DocxPackage) -> StructuralSignals:
    root = parse_xml(package.read_part("word/document.xml"), "word/document.xml")
    body = root.find("w:body", NS)
    result = StructuralSignals()
    if body is None:
        return result
    # Match the M1 body-only indexes. Unrepresented wrappers are explicitly reported.
    if any(c.tag not in {qn(W, "p"), qn(W, "tbl"), qn(W, "sectPr")} for c in body):
        result.warnings.append("unrepresented_body_wrappers")
    stack: list[FieldState] = []
    for index, paragraph in enumerate(body.findall("w:p", NS)):
        toc = any(state.is_toc for state in stack)
        unsafe: set[str] = set()
        for node in paragraph.iter():
            local = node.tag.rsplit("}", 1)[-1] if isinstance(node.tag, str) else ""
            if local in {
                "txbxContent",
                "ins",
                "del",
                "moveFrom",
                "moveTo",
                "sdt",
                "oMath",
                "oMathPara",
            }:
                unsafe.add(local)
            # Nested textbox fields must not alter the main story's field stack.
            if any(a.tag == qn(W, "txbxContent") for a in node.iterancestors()):
                continue
            if node.tag == qn(W, "fldSimple"):
                instruction = node.get(qn(W, "instr"), "")
                toc = toc or FieldState(instruction).is_toc
            elif node.tag == qn(W, "fldChar"):
                kind = node.get(qn(W, "fldCharType"))
                if kind == "begin":
                    stack.append(FieldState())
                elif kind == "end":
                    if stack:
                        stack.pop()
                    else:
                        result.warnings.append("unbalanced_field_end")
            elif node.tag == qn(W, "instrText") and stack:
                stack[-1].instruction += node.text or ""
            toc = toc or any(state.is_toc for state in stack)
        result.paragraphs[index] = ParagraphSignals(
            in_toc_field=toc,
            unsafe_objects=tuple(sorted(unsafe)),
            has_numbering=paragraph.find("w:pPr/w:numPr", NS) is not None,
        )
    if stack:
        result.warnings.append("unclosed_complex_field")
    if body.findall(".//w:tbl/w:tr/w:tc/w:tbl", NS):
        result.warnings.append("nested_tables_not_classified")
    return result
