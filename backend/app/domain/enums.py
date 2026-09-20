from enum import StrEnum


class BlockKind(StrEnum):
    PARAGRAPH = "paragraph"
    TABLE = "table"
    TABLE_CELL = "table_cell"
    IMAGE = "image"
    SECTION_BREAK = "section_break"
    PAGE_BREAK = "page_break"
    FIELD = "field"
    UNKNOWN = "unknown"


class SemanticRole(StrEnum):
    COVER = "cover"
    DECLARATION = "declaration"
    ABSTRACT_ZH = "abstract_zh"
    ABSTRACT_EN = "abstract_en"
    KEYWORDS_ZH = "keywords_zh"
    KEYWORDS_EN = "keywords_en"
    TABLE_OF_CONTENTS = "table_of_contents"
    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    HEADING_4 = "heading_4"
    BODY = "body"
    TABLE = "table"
    TABLE_TEXT = "table_text"
    ABBREVIATION_TABLE = "abbreviation_table"
    ABBREVIATION_HEADING = "abbreviation_heading"
    FIGURE = "figure"
    EQUATION = "equation"
    FIGURE_CAPTION = "figure_caption"
    TABLE_CAPTION = "table_caption"
    REFERENCE_HEADING = "reference_heading"
    REFERENCE_ENTRY = "reference_entry"
    APPENDIX_HEADING = "appendix_heading"
    APPENDIX_BODY = "appendix_body"
    ACKNOWLEDGEMENT_HEADING = "acknowledgement_heading"
    ACKNOWLEDGEMENT_BODY = "acknowledgement_body"
    UNKNOWN = "unknown"


class DecisionSource(StrEnum):
    WORD_STYLE = "word_style"
    RULE = "rule"
    MODEL = "model"
    HYBRID = "hybrid"
    USER = "user"
    UNKNOWN = "unknown"


class RuleStatus(StrEnum):
    CONFIRMED = "confirmed"
    PROVISIONAL = "provisional"
    NEEDS_REVIEW = "needs_review"


class RulePriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class IssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueStatus(StrEnum):
    OPEN = "open"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    FIXED = "fixed"
    NOT_EVALUATED = "not_evaluated"


class JobStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    ANALYZING = "analyzing"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    FORMATTING = "formatting"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class AiMode(StrEnum):
    OFF = "off"
    AMBIGUOUS_ONLY = "ambiguous_only"
    FULL_BASELINE = "full_baseline"
