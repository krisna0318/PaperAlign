import type { BlockKind, DocumentBlock, SemanticRole, SourceAnchor } from "./domain";
import type { RuleScope, RuleValidationResult } from "./rules";

export interface StructureDecision {
  block_id: string;
  order: number;
  kind: BlockKind;
  locator: SourceAnchor;
  role: SemanticRole;
  scope: RuleScope | null;
  confidence: number;
  decision_source: DocumentBlock["decision_source"];
  requires_confirmation: boolean;
  reasons: string[];
  heading_level: number | null;
  parent_id: string | null;
  container_id: string | null;
  region: string;
  section_id: string | null;
  text_sha256: string;
  character_count: number;
  preview: string | null;
}

export interface StructureOverrides {
  schema_version: "1.0";
  input_sha256: string;
  reviewer: string;
  decisions: { block_id: string; role: SemanticRole; scope?: RuleScope | null; reason: string }[];
}

export interface StructureReport {
  schema_version: "1.0";
  classifier_version: string;
  profile_id: string;
  input_sha256: string;
  content_fingerprint: string;
  mode: "rules_only";
  ai_used: false;
  full_document_evaluated: false;
  formatting_allowed: false;
  previews_included: boolean;
  override_reviewer: string | null;
  applied_overrides: StructureOverrides | null;
  decisions: StructureDecision[];
  warnings: { code: string; block_id: string | null; message: string }[];
  role_counts: Record<string, number>;
  review_count: number;
  review_root_ids: string[];
  unsupported_object_counts: Record<string, number>;
  validation_counts: Record<string, number>;
  rule_checks: RuleValidationResult[];
  unapplied_rule_ids: string[];
}
