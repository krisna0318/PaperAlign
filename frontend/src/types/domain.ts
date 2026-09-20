export type BlockKind =
  | "paragraph"
  | "table"
  | "table_cell"
  | "image"
  | "section_break"
  | "page_break"
  | "field"
  | "unknown";

export type SemanticRole =
  | "cover"
  | "declaration"
  | "abstract_zh"
  | "abstract_en"
  | "keywords_zh"
  | "keywords_en"
  | "table_of_contents"
  | "heading_1"
  | "heading_2"
  | "heading_3"
  | "body"
  | "figure_caption"
  | "table_caption"
  | "reference_heading"
  | "reference_entry"
  | "appendix_heading"
  | "appendix_body"
  | "acknowledgement_heading"
  | "acknowledgement_body"
  | "unknown";

export interface SourceAnchor {
  part_name: string;
  paragraph_index?: number | null;
  table_index?: number | null;
  row_index?: number | null;
  cell_index?: number | null;
  xml_path?: string | null;
}

export interface StyleSnapshot {
  style_id?: string | null;
  style_name?: string | null;
  font_east_asia?: string | null;
  font_latin?: string | null;
  size_pt?: number | null;
  bold?: boolean | null;
  italic?: boolean | null;
  alignment?: string | null;
  line_spacing?: number | null;
  space_before_pt?: number | null;
  space_after_pt?: number | null;
  first_line_indent_pt?: number | null;
}

export interface DocumentBlock {
  schema_version: "1.0";
  id: string;
  order: number;
  kind: BlockKind;
  text: string;
  role: SemanticRole;
  parent_id?: string | null;
  confidence: number;
  decision_source: "word_style" | "rule" | "model" | "hybrid" | "user" | "unknown";
  requires_confirmation: boolean;
  style: StyleSnapshot;
  source_anchor: SourceAnchor;
  protected: boolean;
  metadata: Record<string, unknown>;
}

export type { FormatRule, RuleSource, RuleValidationResult } from "./rules";

export interface DiagnosisIssue {
  schema_version: "1.0";
  id: string;
  rule_id: string;
  block_id: string;
  severity: "error" | "warning" | "info";
  expected: unknown;
  actual: unknown;
  message: string;
  auto_fixable: boolean;
  requires_confirmation: boolean;
  status: "open" | "confirmed" | "dismissed" | "fixed" | "not_evaluated";
}

export interface ArtifactReference {
  kind: string;
  relative_path: string;
  sha256?: string | null;
}

export interface AnalysisJob {
  schema_version: "1.0";
  id: string;
  profile_id: string;
  status:
    | "created"
    | "queued"
    | "analyzing"
    | "awaiting_confirmation"
    | "formatting"
    | "validating"
    | "completed"
    | "failed";
  ai_mode: "off" | "ambiguous_only" | "full_baseline";
  created_at: string;
  updated_at: string;
  input_filename: string;
  input_sha256?: string | null;
  artifacts: ArtifactReference[];
  error_code?: string | null;
  error_message?: string | null;
}
