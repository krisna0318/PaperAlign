"""Deterministic classification; every proposal keeps its evidence and uncertainty."""

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

from app.domain.analysis import DocumentProfile
from app.domain.blocks import DocumentBlock
from app.domain.enums import BlockKind, DecisionSource, SemanticRole
from app.domain.rules import RuleScope
from app.domain.structure import StructureDecision, StructureOverrides, StructureWarning
from app.domain.template_evidence import EffectiveParagraphFormat
from app.parsers.errors import DocxAnalysisError
from app.parsers.structure_signals import ParagraphSignals, StructuralSignals

HEADING_ROLES = {level: SemanticRole(f"heading_{level}") for level in range(1, 5)}
MARKERS: dict[str, tuple[SemanticRole, RuleScope | None, str]] = {
    "摘要": (SemanticRole.ABSTRACT_ZH, RuleScope.ABSTRACT_ZH_HEADING, "abstract_zh"),
    "中文摘要": (SemanticRole.ABSTRACT_ZH, RuleScope.ABSTRACT_ZH_HEADING, "abstract_zh"),
    "abstract": (SemanticRole.ABSTRACT_EN, None, "abstract_en"),
    "目录": (SemanticRole.TABLE_OF_CONTENTS, RuleScope.TOC_HEADING, "toc"),
    "contents": (SemanticRole.TABLE_OF_CONTENTS, RuleScope.TOC_HEADING, "toc"),
    "参考文献": (SemanticRole.REFERENCE_HEADING, RuleScope.REFERENCE_HEADING, "references"),
    "references": (SemanticRole.REFERENCE_HEADING, RuleScope.REFERENCE_HEADING, "references"),
    "致谢": (
        SemanticRole.ACKNOWLEDGEMENT_HEADING,
        RuleScope.ACKNOWLEDGEMENT_HEADING,
        "acknowledgement",
    ),
    "acknowledgements": (
        SemanticRole.ACKNOWLEDGEMENT_HEADING,
        RuleScope.ACKNOWLEDGEMENT_HEADING,
        "acknowledgement",
    ),
    "英文缩略词表": (SemanticRole.ABBREVIATION_HEADING, None, "abbreviations"),
    "缩略词表": (SemanticRole.ABBREVIATION_HEADING, None, "abbreviations"),
    "缩略语表": (SemanticRole.ABBREVIATION_HEADING, None, "abbreviations"),
    "英文缩略词(符号表)": (SemanticRole.ABBREVIATION_HEADING, None, "abbreviations"),
    "独创性声明": (SemanticRole.DECLARATION, RuleScope.DECLARATION, "declaration"),
    "原创性声明": (SemanticRole.DECLARATION, RuleScope.DECLARATION, "declaration"),
    "学位论文独创性声明": (SemanticRole.DECLARATION, RuleScope.DECLARATION, "declaration"),
}
REGION_BODY = {
    "abstract_zh": (SemanticRole.ABSTRACT_ZH, RuleScope.ABSTRACT_ZH_BODY),
    "abstract_en": (SemanticRole.ABSTRACT_EN, RuleScope.ABSTRACT_EN_BODY),
    "references": (SemanticRole.REFERENCE_ENTRY, RuleScope.REFERENCE_ENTRY),
    "appendix": (SemanticRole.APPENDIX_BODY, RuleScope.APPENDIX_BODY),
    "acknowledgement": (SemanticRole.ACKNOWLEDGEMENT_BODY, RuleScope.ACKNOWLEDGEMENT_BODY),
    "declaration": (SemanticRole.DECLARATION, RuleScope.DECLARATION),
    "body": (SemanticRole.BODY, RuleScope.BODY),
}
STYLE_SECTIONS = {
    "摘要标题": (SemanticRole.ABSTRACT_ZH, RuleScope.ABSTRACT_ZH_HEADING),
    "摘要正文": (SemanticRole.ABSTRACT_ZH, RuleScope.ABSTRACT_ZH_BODY),
    "英文摘要标题": (SemanticRole.ABSTRACT_EN, RuleScope.ABSTRACT_EN_TITLE),
    "英文摘要正文": (SemanticRole.ABSTRACT_EN, RuleScope.ABSTRACT_EN_BODY),
    "英文摘要作者": (SemanticRole.ABSTRACT_EN, RuleScope.ABSTRACT_EN_AUTHOR),
    "英文摘要单位": (SemanticRole.ABSTRACT_EN, RuleScope.ABSTRACT_EN_AFFILIATION),
}
ROLE_SCOPE = {role: scope for role, scope in REGION_BODY.values()}
ROLE_SCOPE.update({role: scope for role, scope, _ in MARKERS.values() if scope is not None})
ROLE_SCOPE.update({role: RuleScope(role.value) for role in HEADING_ROLES.values()})
ROLE_SCOPE.update(
    {
        SemanticRole.TABLE: RuleScope.TABLE,
        SemanticRole.LIST_ITEM: RuleScope.BODY,
        SemanticRole.TABLE_TEXT: RuleScope.TABLE_TEXT,
        SemanticRole.ABBREVIATION_TABLE: RuleScope.ABBREVIATION_TABLE,
        SemanticRole.FIGURE_CAPTION: RuleScope.FIGURE_CAPTION,
        SemanticRole.FIGURE: RuleScope.FIGURE,
        SemanticRole.EQUATION: RuleScope.EQUATION,
        SemanticRole.TABLE_CAPTION: RuleScope.TABLE_CAPTION,
        SemanticRole.KEYWORDS_ZH: RuleScope.KEYWORDS_ZH,
        SemanticRole.KEYWORDS_EN: RuleScope.KEYWORDS_EN,
        SemanticRole.APPENDIX_HEADING: RuleScope.APPENDIX_HEADING,
    }
)
ROLE_SCOPES = {
    SemanticRole.COVER: {
        RuleScope.COVER_TITLE,
        RuleScope.COVER_DOCUMENT_TYPE,
        RuleScope.COVER_METADATA,
    },
    SemanticRole.ABSTRACT_ZH: {RuleScope.ABSTRACT_ZH_HEADING, RuleScope.ABSTRACT_ZH_BODY},
    SemanticRole.ABSTRACT_EN: {
        RuleScope.ABSTRACT_EN_TITLE,
        RuleScope.ABSTRACT_EN_AUTHOR,
        RuleScope.ABSTRACT_EN_AFFILIATION,
        RuleScope.ABSTRACT_EN_BODY,
    },
    SemanticRole.TABLE_OF_CONTENTS: {RuleScope.TOC_HEADING, RuleScope.TOC_ENTRY},
}
for semantic_role, rule_scope in ROLE_SCOPE.items():
    ROLE_SCOPES.setdefault(semantic_role, {rule_scope})


@dataclass
class State:
    region: str = "preamble"
    region_anchor: str | None = None
    headings: list[tuple[int, str]] = field(default_factory=list)


def normalized(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip()


def compact(text: str) -> str:
    return re.sub(r"\s+", "", normalized(text)).casefold()


def style_heading_level(block: DocumentBlock) -> int | None:
    for value in (block.style.style_name, block.style.style_id):
        name = compact(value or "")
        match = re.fullmatch(r"(?:heading|标题)([1-4])|([1-4])级标题", name)
        if match:
            return int(match.group(1) or match.group(2))
    return None


def numbering_heading_level(text: str) -> int | None:
    if len(text) > 100 or re.search(r"[。！？；;!?]", text):
        return None
    if re.match(r"^第[一二三四五六七八九十百零〇\d]+章\s*\S", text):
        return 1
    match = re.match(r"^(\d+(?:\.\d+){0,3})(?:[、.]?\s+)(\S.*)$", text)
    if not match:
        match = re.match(r"^(\d+(?:\.\d+){1,3})(?=[^\d.\s])(.+)$", text)
    if match:
        return match.group(1).count(".") + 1
    return None


def is_toc_style(block: DocumentBlock) -> bool:
    return any(
        re.fullmatch(r"(?:toc|目录)[1-9]", compact(value or ""))
        for value in (block.style.style_name, block.style.style_id)
    )


def _proposal(
    block: DocumentBlock,
    role: SemanticRole,
    reason: str,
    *,
    scope: RuleScope | None = None,
    confidence: float = 0.95,
    review: bool = False,
    source: DecisionSource = DecisionSource.RULE,
    level: int | None = None,
) -> StructureDecision:
    return StructureDecision(
        block_id=block.id,
        order=block.order,
        kind=block.kind,
        locator=block.source_anchor,
        role=role,
        scope=scope,
        confidence=confidence,
        decision_source=source,
        requires_confirmation=review,
        reasons=[reason],
        heading_level=level,
        container_id=block.parent_id,
        text_sha256=hashlib.sha256(block.text.encode("utf-8")).hexdigest(),
        character_count=len(block.text),
    )


def _classify_paragraph(
    block: DocumentBlock,
    snapshot: EffectiveParagraphFormat | None,
    signal: ParagraphSignals,
    state: State,
) -> StructureDecision:
    text = normalized(block.text)
    key = compact(text)
    unsafe = set(signal.unsafe_objects)
    if unsafe and unsafe <= {"oMath", "oMathPara"}:
        return _proposal(
            block,
            SemanticRole.EQUATION,
            "word_math_object",
            scope=RuleScope.EQUATION,
            confidence=0.95,
        )
    if unsafe:
        return _proposal(
            block, SemanticRole.UNKNOWN, "unsupported_inline_object", confidence=0, review=True
        )
    if signal.in_toc_field or is_toc_style(block):
        return _proposal(
            block,
            SemanticRole.TABLE_OF_CONTENTS,
            "toc_field" if signal.in_toc_field else "toc_style",
            scope=RuleScope.TOC_ENTRY,
        )
    if not text:
        if block.metadata.get("has_drawing"):
            return _proposal(
                block,
                SemanticRole.FIGURE,
                "drawing_without_text",
                scope=RuleScope.FIGURE,
                confidence=0.75,
                review=True,
            )
        return _proposal(block, SemanticRole.UNKNOWN, "empty_paragraph", confidence=0)
    # Page-number tails prevent TOC text from opening a real section.
    if state.region == "toc" and re.search(r"(?:\t|\.{2,}|…|·{2,})\s*(?:\d+|[IVXLCDM]+)\s*$", text):
        return _proposal(
            block, SemanticRole.TABLE_OF_CONTENTS, "toc_page_number_tail", scope=RuleScope.TOC_ENTRY
        )
    marker = MARKERS.get(key)
    if marker:
        return _proposal(block, marker[0], "exact_section_marker", scope=marker[1])
    if len(key) <= 60 and re.search(r"(?:原创性声明|独创性声明|使用授权声明|使用授权书)$", key):
        return _proposal(
            block, SemanticRole.DECLARATION, "declaration_heading", scope=RuleScope.DECLARATION
        )
    if re.match(r"^abstract\s*[:：]\s*\S", text, re.I):
        return _proposal(
            block,
            SemanticRole.ABSTRACT_EN,
            "inline_abstract_label",
            scope=RuleScope.ABSTRACT_EN_BODY,
        )
    if re.match(r"^摘\s*要\s*[:：]\s*\S", text):
        return _proposal(
            block,
            SemanticRole.ABSTRACT_ZH,
            "inline_abstract_label",
            scope=RuleScope.ABSTRACT_ZH_BODY,
        )
    section_style = STYLE_SECTIONS.get(compact(block.style.style_name or ""))
    if section_style:
        return _proposal(
            block,
            section_style[0],
            "explicit_section_style",
            scope=section_style[1],
            source=DecisionSource.WORD_STYLE,
        )
    if re.match(r"^(?:附录|appendix)(?:\s*[A-Z一二三四五六七八九十\d](?:\s+.*)?|\s*)$", text, re.I):
        return _proposal(
            block,
            SemanticRole.APPENDIX_HEADING,
            "appendix_marker",
            scope=RuleScope.APPENDIX_HEADING,
        )
    if re.match(r"^关\s*键\s*词\s*[:：]", text):
        return _proposal(
            block, SemanticRole.KEYWORDS_ZH, "keyword_label", scope=RuleScope.KEYWORDS_ZH
        )
    if re.match(r"^key\s*words?\s*[:：]", text, re.I):
        return _proposal(
            block, SemanticRole.KEYWORDS_EN, "keyword_label", scope=RuleScope.KEYWORDS_EN
        )
    style_level = style_heading_level(block)
    outline_level = None
    if snapshot and not snapshot.resolution_warnings:
        raw = snapshot.paragraph.outline_level
        if raw is not None and raw in range(4):
            outline_level = raw + 1
    number_level = numbering_heading_level(text)
    levels = [n for n in (style_level, outline_level, number_level) if n is not None]
    if style_level or outline_level:
        level = style_level or outline_level
        assert level is not None
        conflict = len(set(levels)) > 1
        suspicious = len(text) > 100 or bool(re.search(r"[。！？；;!?]", text))
        decision = _proposal(
            block,
            HEADING_ROLES[level],
            "heading_style" if style_level else "outline_level",
            scope=RuleScope(f"heading_{level}"),
            level=level,
            confidence=0.55 if conflict or suspicious else 0.95,
            review=conflict or suspicious,
            source=DecisionSource.WORD_STYLE,
        )
        if conflict:
            decision.reasons.append("heading_level_conflict")
        if suspicious:
            decision.reasons.append("heading_looks_like_sentence")
        return decision
    if state.region == "toc":
        # A numbering-only heading may be another TOC entry; require an explicit correction.
        return _proposal(
            block,
            SemanticRole.TABLE_OF_CONTENTS,
            "toc_boundary_ambiguous",
            scope=RuleScope.TOC_ENTRY,
            confidence=0.5,
            review=True,
        )
    # In reference and front-matter regions, numbering alone is not a new body heading.
    if state.region in {"body", "appendix", "preamble", "abbreviations"}:
        if len(text) <= 100 and not re.search(r"[。！？；;!?]", text):
            caption = re.match(
                r"^(图|表|figure|fig\.?|table)\s*[A-Z]?\d+(?:[-.]\d+)*(?:\s+|[:：])\S", text, re.I
            )
            if caption:
                role = (
                    SemanticRole.TABLE_CAPTION
                    if caption.group(1).casefold() in {"表", "table"}
                    else SemanticRole.FIGURE_CAPTION
                )
                caption_style = compact(block.style.style_name or "")
                corroborated = "caption" in caption_style or caption_style in {"图题", "表题"}
                return _proposal(
                    block,
                    role,
                    "caption_pattern_and_style" if corroborated else "caption_number_pattern",
                    scope=ROLE_SCOPE[role],
                    confidence=0.95 if corroborated else 0.8,
                    review=not corroborated,
                )
        if signal.has_numbering and not style_level and not outline_level:
            return _proposal(
                block,
                SemanticRole.UNKNOWN,
                "list_numbering_without_heading_evidence",
                confidence=0.4,
                review=True,
            )
        if number_level:
            return _proposal(
                block,
                HEADING_ROLES[number_level],
                "numbering_only_candidate",
                scope=RuleScope(f"heading_{number_level}"),
                level=number_level,
                confidence=0.6,
                review=True,
            )
    if state.region in REGION_BODY:
        role, scope = REGION_BODY[state.region]
        return _proposal(block, role, "section_context", scope=scope, confidence=0.9)
    if state.region in {"preamble", "cover"}:
        if key in {
            "本科毕业论文",
            "本科毕业论文(设计)",
            "本科毕业论文(或设计)",
            "本科毕业设计",
        }:
            return _proposal(
                block,
                SemanticRole.COVER,
                "cover_document_label",
                scope=RuleScope.COVER_DOCUMENT_TYPE,
            )
        if re.match(r"^(?:学院|专业|姓名|学生姓名|学号|指导教师|指导老师|提交日期)[:：]", key):
            return _proposal(
                block, SemanticRole.COVER, "cover_metadata_label", scope=RuleScope.COVER_METADATA
            )
        if state.region == "cover" and (
            key in {"论文(或设计)题目", "论文(设计)题目"}
            or (len(text) <= 100 and not re.search(r"[。！？；;!?]", text))
        ):
            return _proposal(
                block,
                SemanticRole.COVER,
                "cover_title_context",
                scope=RuleScope.COVER_TITLE,
                confidence=0.9,
            )
    return _proposal(
        block, SemanticRole.UNKNOWN, "insufficient_structure_evidence", confidence=0, review=True
    )


def _set_hierarchy(
    decision: StructureDecision, state: State, warnings: list[StructureWarning]
) -> StructureDecision:
    # Uncertain candidates cannot redirect all following paragraphs into a guessed section.
    if not decision.requires_confirmation:
        region = next(
            (
                region
                for role, scope, region in MARKERS.values()
                if role == decision.role and scope == decision.scope
            ),
            None,
        )
        if decision.role == SemanticRole.APPENDIX_HEADING:
            region = "appendix"
        if decision.role == SemanticRole.COVER and decision.scope == RuleScope.COVER_DOCUMENT_TYPE:
            region = "cover"
        if decision.role == SemanticRole.DECLARATION and "section_context" in decision.reasons:
            region = None
        if any(r in decision.reasons for r in {"explicit_section_style", "inline_abstract_label"}):
            abstract_region = (
                "abstract_en" if decision.role == SemanticRole.ABSTRACT_EN else "abstract_zh"
            )
            region = abstract_region if state.region != abstract_region else None
        if decision.decision_source == DecisionSource.USER and region is None:
            # Correcting the first body/abstract paragraph can resolve an ambiguous boundary.
            region = next(
                (
                    r
                    for r, pair in REGION_BODY.items()
                    if pair == (decision.role, decision.scope) and r != state.region
                ),
                None,
            )
        if region:
            state.region, state.region_anchor = region, decision.block_id
            state.headings.clear()
        if decision.heading_level:
            level = decision.heading_level
            while state.headings and state.headings[-1][0] >= level:
                state.headings.pop()
            prior = state.headings[-1][0] if state.headings else 0
            if level > prior + 1:
                warnings.append(
                    StructureWarning(
                        code="heading_level_jump",
                        block_id=decision.block_id,
                        message="标题层级存在跳级，需要检查其父级。",
                    )
                )
                decision.reasons.append("heading_level_jump")
            if state.region != "appendix":
                state.region = "body"
                state.region_anchor = None
            decision = decision.model_copy(
                update={
                    "parent_id": state.headings[-1][1] if state.headings else state.region_anchor
                }
            )
            state.headings.append((level, decision.block_id))
    if not decision.heading_level and decision.block_id != state.region_anchor:
        decision = decision.model_copy(
            update={"parent_id": state.headings[-1][1] if state.headings else state.region_anchor}
        )
    return decision.model_copy(update={"region": state.region, "section_id": state.region_anchor})


def classify_structure(
    profile: DocumentProfile,
    formats: list[EffectiveParagraphFormat],
    signals: StructuralSignals,
    overrides: StructureOverrides | None = None,
) -> tuple[list[StructureDecision], list[StructureWarning]]:
    overrides_by_id = {item.block_id: item for item in overrides.decisions} if overrides else {}
    blocks_by_id = {block.id: block for block in profile.blocks}
    if overrides:
        if overrides.input_sha256 != profile.package.input_sha256:
            raise DocxAnalysisError(
                "override_hash_mismatch", "Corrections belong to a different document"
            )
        if len(overrides_by_id) != len(overrides.decisions):
            raise DocxAnalysisError("duplicate_override", "A block may only be corrected once")
        if set(overrides_by_id) - set(blocks_by_id):
            raise DocxAnalysisError(
                "unknown_override_block", "Correction contains an unknown block ID"
            )
    by_index = {item.paragraph_index: item for item in formats}
    state = State()
    decisions: list[StructureDecision] = []
    decided: dict[str, StructureDecision] = {}
    warnings = [
        StructureWarning(code=code, message="存在未完整解析的结构，请在 Word 中复核。")
        for code in sorted(set(signals.warnings))
    ]
    for block in profile.blocks:
        if block.kind == BlockKind.PARAGRAPH:
            index = block.source_anchor.paragraph_index
            decision = _classify_paragraph(
                block,
                by_index.get(index) if index is not None else None,
                signals.paragraphs.get(index, ParagraphSignals())
                if index is not None
                else ParagraphSignals(),
                state,
            )
        elif block.kind == BlockKind.TABLE:
            role = (
                SemanticRole.ABBREVIATION_TABLE
                if state.region == "abbreviations"
                else SemanticRole.TABLE
            )
            decision = _proposal(
                block,
                role,
                "table_object_and_region",
                scope=ROLE_SCOPE[role],
                review=state.region not in {"body", "appendix", "abbreviations"},
            )
        elif block.kind == BlockKind.TABLE_CELL:
            parent = decided.get(block.parent_id or "")
            decision = _proposal(
                block,
                SemanticRole.TABLE_TEXT,
                "table_cell_container",
                scope=RuleScope.TABLE_TEXT,
                review=parent is None or parent.requires_confirmation,
            )
        else:
            decision = _proposal(
                block, SemanticRole.UNKNOWN, "unsupported_block_kind", confidence=0, review=True
            )
        correction = overrides_by_id.get(block.id)
        if correction:
            tables = {SemanticRole.TABLE, SemanticRole.ABBREVIATION_TABLE}
            allowed = (
                (
                    block.kind == BlockKind.PARAGRAPH
                    and correction.role not in tables | {SemanticRole.TABLE_TEXT}
                )
                or (block.kind == BlockKind.TABLE and correction.role in tables)
                or (
                    block.kind == BlockKind.TABLE_CELL
                    and correction.role == SemanticRole.TABLE_TEXT
                )
            )
            if not allowed:
                raise DocxAnalysisError(
                    "override_kind_mismatch", "Correction role does not match the block kind"
                )
            scope = correction.scope or ROLE_SCOPE.get(correction.role)
            # Abstract roles can represent a heading or body; preserve known marker boundaries.
            if correction.scope is None and correction.role in {
                SemanticRole.ABSTRACT_ZH,
                SemanticRole.ABSTRACT_EN,
                SemanticRole.TABLE_OF_CONTENTS,
            }:
                marker = MARKERS.get(compact(block.text))
                scope = (
                    marker[1]
                    if marker and marker[0] == correction.role
                    else {
                        SemanticRole.ABSTRACT_ZH: RuleScope.ABSTRACT_ZH_BODY,
                        SemanticRole.ABSTRACT_EN: RuleScope.ABSTRACT_EN_BODY,
                        SemanticRole.TABLE_OF_CONTENTS: RuleScope.TOC_ENTRY,
                    }[correction.role]
                )
            if correction.scope is not None and correction.scope not in ROLE_SCOPES.get(
                correction.role, set()
            ):
                raise DocxAnalysisError(
                    "override_scope_mismatch", "Correction scope does not match its semantic role"
                )
            level = next((n for n, role in HEADING_ROLES.items() if role == correction.role), None)
            decision = _proposal(
                block,
                correction.role,
                "human_override",
                scope=scope,
                level=level,
                confidence=1,
                review=correction.role == SemanticRole.UNKNOWN,
                source=DecisionSource.USER,
            )
            # A role correction does not resolve unsupported inline formatting.
            decision.reasons.append("reviewer_reason_recorded_in_override_file")
        decision = _set_hierarchy(decision, state, warnings)
        if block.kind == BlockKind.TABLE_CELL:
            decision = decision.model_copy(update={"parent_id": block.parent_id})
        decided[block.id] = decision
        decisions.append(decision)
    return decisions, warnings
