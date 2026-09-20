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
  formatting_allowed: false;
  conclusion: "diagnosis_only_not_compliance_proof";
}

export interface DiagnosticJobView {
  schema_version: "1.0";
  job: AnalysisJob;
  summary: DiagnosticSummary | null;
}
