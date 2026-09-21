import type { AnalysisJob, SourceAnchor } from "./domain";
import type { RuleScope, RuleValue } from "./rules";

export interface DiagnosticReviewItem {
  block_id: string;
  role: string;
  scope: RuleScope | null;
  confidence: number;
  preview: string | null;
  reasons: string[];
  locator: SourceAnchor;
}

export interface DiagnosticIssueItem {
  rule_id: string;
  property_path: string;
  status: "fail" | "evidence_insufficient";
  expected: RuleValue;
  actual: RuleValue | null;
  reason: string;
  locator: SourceAnchor;
}

export interface DiagnosticSummary {
  schema_version: "1.0";
  input_sha256: string;
  content_fingerprint: string;
  total_blocks: number;
  review_count: number;
  review_root_count: number;
  role_counts: Record<string, number>;
  validation_counts: Record<string, number>;
  unsupported_object_counts: Record<string, number>;
  warnings: string[];
  review_items: DiagnosticReviewItem[];
  issues: DiagnosticIssueItem[];
  issue_count: number;
  issues_truncated: boolean;
  evidence_insufficient_count: number;
  formatting_candidate_count: number;
  formatting_rule_ids: string[];
  formatting_allowed: false;
  conclusion: "diagnosis_only_not_compliance_proof";
}

export interface DiagnosticJobView {
  schema_version: "1.0";
  job: AnalysisJob;
  summary: DiagnosticSummary | null;
}

export interface FormattingOperation {
  rule_id: string;
  block_id: string;
  property_path: string;
  locator: SourceAnchor;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
}

export interface FormattingReport {
  schema_version: "1.0";
  input_sha256: string;
  output_sha256: string;
  content_fingerprint_before: string;
  content_fingerprint_after: string;
  content_preserved: boolean;
  applied_rule_ids: string[];
  operations: FormattingOperation[];
  requires_word_validation: true;
  warnings: string[];
}

export interface FormatJobResult {
  schema_version: "1.0";
  job_id: string;
  output_artifact: string;
  report: FormattingReport;
}

export interface RuleRecheck {
  rule_id: string;
  result_count: number;
  pass_count: number;
  fail_count: number;
  unresolved_count: number;
  passed: boolean;
}

export interface DeliveryValidationReport {
  schema_version: "1.0";
  content_preserved: boolean;
  package_safe: boolean;
  formatting_report_matches: boolean;
  rule_rechecks: RuleRecheck[];
  static_status: "passed" | "failed";
  word_render: {
    status: "not_requested" | "passed" | "unavailable" | "failed";
    page_count: number | null;
    pdf_sha256: string | null;
    error_code: string | null;
    note: string;
  };
  delivery_ready: boolean;
  manual_validation_required: true;
  manual_checklist: string[];
  limitations: string[];
}

export interface DeliveryValidationResult {
  schema_version: "1.0";
  job_id: string;
  report: DeliveryValidationReport;
  checklist_artifact: string;
  pdf_artifact: string | null;
}
