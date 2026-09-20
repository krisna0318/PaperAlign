// Canonical M2.2 values; keep enums aligned with backend/app/domain/rules.py.
import type { SourceAnchor } from "./domain";

export type RuleScope = "document" | "section" | "cover_title" | "cover_document_type" | "cover_metadata" | "declaration" | "abstract_zh_heading" | "abstract_zh_body" | "abstract_en_title" | "abstract_en_author" | "abstract_en_affiliation" | "abstract_en_body" | "keywords_zh" | "keywords_en" | "toc_heading" | "toc_entry" | "heading_1" | "heading_2" | "heading_3" | "heading_4" | "body" | "abbreviation_table" | "table" | "table_text" | "table_caption" | "table_note" | "figure" | "figure_caption" | "figure_note" | "equation" | "footnote" | "reference_heading" | "reference_entry" | "appendix_heading" | "appendix_body" | "acknowledgement_heading" | "acknowledgement_body";
export type PropertyPath = "page.width_mm" | "page.height_mm" | "page.margin_top_mm" | "page.margin_bottom_mm" | "page.margin_left_mm" | "page.margin_right_mm" | "page.number_format" | "page.number_start" | "page.number_visible" | "run.font_east_asia" | "run.font_latin" | "run.font_high_ansi" | "run.size_pt" | "run.bold" | "run.italic" | "paragraph.alignment" | "paragraph.line_spacing" | "paragraph.space_before_pt" | "paragraph.space_after_pt" | "paragraph.first_line_indent_pt" | "paragraph.first_line_indent_chars" | "paragraph.hanging_indent_chars" | "paragraph.left_indent_pt" | "paragraph.right_indent_pt" | "paragraph.outline_level" | "paragraph.keep_with_next" | "paragraph.page_break_before" | "table.top_pt" | "table.header_separator_pt" | "table.bottom_pt" | "table.vertical_borders_present" | "table.repeat_header" | "content.character_count" | "content.keyword_count" | "content.separator";
export type RuleValue =
  | { kind: "number"; value: number; unit: "pt" | "mm" | "chars" | "count" | "level" }
  | { kind: "text"; value: string }
  | { kind: "boolean"; value: boolean }
  | { kind: "line_spacing"; mode: "multiple"; value: number; unit: "lines" }
  | { kind: "line_spacing"; mode: "exact" | "at_least"; value: number; unit: "pt" };

export interface RuleSource {
  type: "school_comment" | "written_spec" | "template_observation";
  document: string;
  evidence: string;
  locator: string;
  document_sha256?: string | null;
}
export interface RuleConfirmation {
  reviewer: string;
  confirmed_at: string;
  reference: string;
}
export interface RuleTarget {
  text_part: "whole" | "label" | "value";
  paragraph_position: "all" | "first" | "following";
  metadata_field?: "college" | "major" | "name" | "student_id" | "advisor" | "date" | null;
}

export interface FormatRule {
  schema_version: "2.0";
  id: string;
  profile_id: string;
  scope: RuleScope;
  target: RuleTarget;
  property_path: PropertyPath;
  expected_value: RuleValue;
  comparison: "eq" | "gte" | "lte";
  tolerance: number;
  status: "confirmed" | "provisional" | "needs_review";
  confidence: number;
  source: RuleSource;
  confirmation?: RuleConfirmation | null;
  display_alias?: string | null;
  implementation: string;
  validator: string;
  priority: "P0" | "P1" | "P2";
  auto_fixable: boolean;
}
export interface RuleValidationResult {
  schema_version: "1.0";
  rule_id: string;
  property_path: string;
  status: "pass" | "fail" | "not_evaluated" | "evidence_insufficient";
  rule_status: FormatRule["status"];
  expected: RuleValue;
  actual: RuleValue | null;
  source: RuleSource;
  locator: SourceAnchor;
  actual_sources: Record<string, string>;
  reason: string;
}
export interface RuleObservation {
  value: RuleValue | null;
  supported: boolean;
  locator: SourceAnchor;
  sources: Record<string, string>;
  reason?: string | null;
}
export interface EvidenceCandidate { value: RuleValue; source: RuleSource }
export interface EvidenceSelection {
  status: "provisional" | "needs_review";
  selected: EvidenceCandidate | null;
  alternatives: EvidenceCandidate[];
  reason: string;
}
