# PaperAlign Working Context

## Current state

- Current milestone: M5 local read-only diagnostic UI completed (application 0.12.0). Accuracy remains unassessed because the real Gold Set has zero human-confirmed labels; full M2 normative confirmation and M3/M4 human review remain acceptance work.
- Implemented: repository scaffold, safe DOCX package inspection, OOXML document profile, protected-content fingerprint, unsupported-object report, deterministic CLI artifacts, tests, and CI.
- Live DeepSeek proposals and conservative Hybrid adjudication are verified. The local upload/diagnostic UI is implemented; deterministic formatting and final Word validation are not. Full school compliance is not available while 244 rules remain provisional.
- M2.0 implemented: comment-optional template evidence extraction, paragraph style usage, direct-format clusters, and table border widths with OOXML-to-point conversion.
- M2.1 implemented: document defaults, base/derived paragraph styles, character styles and direct formatting are merged into property-level effective values with provenance.
- M2.1 audit: `audit-template --include-preview` writes HTML and short previews only under ignored `.paperalign`. Real Word 16.0 check: 13 paragraphs, 92 matching properties; source SHA unchanged. This is not human visual sign-off. Browser tool denied file:// page inspection; do not claim UI visual verification.
- M2.2: FormatRule schema 2.0 (breaking from free-form 1.0); typed values/units/scopes, human confirmation record, evidence precedence, normalized observations, preflight states. Preflight None means ready for a comparator, never pass.
- M2.3: Profile 1.0.0 has 248 atomic rules (4 confirmed, 244 provisional), 36 evidence records, 46 inventory entries (14 encoded, 23 partial, 9 deferred). Loader validates references, evidence hash, duplicate definitions and coverage. Every rule is read-only.
- CLI: inspect-profile exports profile.json/profile_summary.md/applicability.json. verify-template checks hash-bound sample indexes only; rejects other documents. Real sample: 3 pass, 1 fail (abbreviation table separator 0.5 pt vs 1 pt), 108 evidence_insufficient. Never label these counts whole-document compliance.
- M3: classify produces a hash-bound StructureReport for every represented M1 block, identifies four heading levels and document regions, preserves TOC fields, detects formulas/drawings, builds parentage, allows reviewed role/scope corrections, and runs located M2 rules. Local HTML/JSON/Markdown stay under .paperalign; no-key and no-write.
- Final-page fallback: classify also writes a customer-readable manual review guide. It states which layout results cannot be guaranteed statically and gives applicable Word steps plus acceptance checks for final layout, fields/TOC, figures, tables, sections/page numbering and unsupported objects.
- M4.0: prepare-ai-review creates local-only, bounded Prompt-only or Hybrid packets and a strict hash-bound response contract. Hybrid targets review roots; Prompt-only hides rules answers. No provider is called, no API key is read, and formatting remains disabled.
- M4.1: DeepSeek and OpenAI Responses adapters use JSON Schema output contracts. DeepSeek uses its native stateless Responses endpoint; OpenAI sets store=false. Context is adaptive but hard-capped at 3 blocks and 240 characters each. Cloud execution requires both AI_MODE and --confirm-send-cloud; records validated proposals, failures, usage/time and optional user-configured cost, never raw responses. This does not imply account-level zero data retention.
- Current real M4.1 preparation: 28 M3 review roots became 11 cloud-eligible packets and 17 manual-only no-text targets; 756 total context characters, at most 3 blocks per packet, actual longest excerpt 68 characters. A prior current-model qualitative review grouped the 11 packets into 6 list items and 5 table captions; it is not a Gold Set.
- Live test on 2026-09-21: deepseek-flash, reasoning=none, 11/11 valid responses, 0 failures/abstentions, 15,262 input + 1,165 output = 16,427 tokens, 41,019 ms. Roles: 5 list_item, 1 heading_4, 5 table_caption. p-0123 (0.57) disagrees with prior qualitative review; 3 null scopes and 4 confidence scores below 0.70 need review. No model output was applied to the DOCX. Original source hash unchanged. Local result: .paperalign/m4-review/runs/2026-09-21-deepseek-live/ai_review_run.json. Earlier one-packet connectivity probe used 1,507 tokens (17,934 known successful tokens for the session).
- Local .env stays AI_MODE=off; this authorized test temporarily set ambiguous_only in the process environment. Optional blank configuration values now fall back to defaults. Never print .env or secret values.
- M4.2: prepare-gold-set creates a no-manuscript-text template for every plan target, including manual-only items; evaluate-ai-review validates plan/run/Gold Set identity and reports Rules-only versus model proposal coverage, role and scope metrics, disagreements, Token and latency. Only confirmed human labels count. Real no-label smoke result is 0/28 evaluated and all accuracy fields remain unassessed. Local template: .paperalign/m4-review/gold-set-v1; baseline: .paperalign/m4-review/evaluations/2026-09-21-no-label-baseline.
- M4.3: adjudicate-review consumes plan plus model run and writes a separate HybridReview. Policy v1 requires resolved rules/model role and scope agreement plus model confidence >= configured threshold; unique role scopes may be deterministically derived. Any conflict, missing proposal, low confidence, unknown, abstention or manual-only target routes to human review. Real threshold 0.90 run: 5 semantic auto-accept, 23 manual; policy remains provisional_not_accuracy_validated and formatting_allowed=false. Local result: .paperalign/m4-review/hybrid/2026-09-21-policy-v1.
- M4.4: the three-system engineering path is closed out. With 0/28 human labels, all accuracy metrics correctly remain unassessed. M5/M6 engineering may continue, but Hybrid output cannot authorize formatting until independent labels calibrate the policy.
- M5: POST /api/jobs accepts a raw DOCX body (50 MB cap), creates an isolated local task, runs Rules-only structure analysis and persists hash-bound results; GET /api/jobs/{id} reloads the task. The UI displays bounded 20-character review previews, counts, warnings and at most 100 prioritized issue summaries. It never formats, calls AI or claims full compliance.
- Real runs before final full regression: thesis 785 blocks, 28 priority review roots / 179 including inherited table-cell review; template 392 blocks, 9 review roots. Thesis located checks: 2 pass, 2 fail, 4379 evidence_insufficient. These are check occurrences, not unique-rule coverage or accuracy.
- Latest verification after M5 (2026-09-21): 139 backend tests, strict mypy (63 source files), Ruff, frontend typecheck, Vitest and production build passed. Two third-party TestClient deprecation warnings remain nonblocking.
- M3 implementation follows pushed M2 commit 7406931; use `git log -1 --oneline` for the current delivery commit.

## Product decisions that must survive context changes

1. The first profile is SCAU undergraduate theses, not arbitrary templates.
2. User manuscripts are `.docx`. The official legacy `.doc` is offline rule evidence only.
3. AI resolves semantics and ambiguity; deterministic code changes formatting.
4. Rules-only mode must work without an API key.
5. Never overwrite the original document or silently alter protected content.
6. Every decision must expose its source: Word style, rule, model, hybrid, or user.
7. Unknown, unsupported, evidence-insufficient, and not-evaluated are valid outcomes.
8. Real theses, secrets, and full manuscript logs never enter Git.
9. Explicit school comments or written specifications override conflicting template formatting. Without explicit guidance, observed template formatting creates provisional rules only.
10. ASCII and high-ANSI font slots must stay separate. Theme/line-based spacing/hanging-indent values not resolved must carry unresolved markers. Mixed run groups require an explicit target when converting to observations.
11. User confirmed current graduating SCAU undergraduates excluding Foreign Studies and all postgraduates, no college customizations. Scope is no longer an open question. Cohort token current_graduates_at_2026-09-20 anchors this confirmation, not an inferred graduation year. Scope confirmation does not approve every atomic rule.

## Next implementation target

Next module is M6 deterministic safe formatting. The real 28-target Gold Set still needs independent human review before any Hybrid threshold can be accepted. DeepSeek connectivity is already verified; do not repeat paid calls just to rediscover this. Keep M2 rule confirmation as a separate gate before consequential formatting:

```text
official template evidence
  → comment-optional structural and formatting observations
  → property-level effective values and provenance
  → manually confirmed P0 rules
  → versioned manifest.json
  → validators and evidence locators (fixed template samples working)
  → M3 role recognition and hash-bound human corrections (implemented)
  → M4.0 bounded local model packets and response validation (implemented)
  → M4.1 provider calls, metrics and rules-only fallback (implemented; DeepSeek live test complete)
  → M4.2 Gold Set template and evaluation runner (implemented; human labels pending)
  → M4.3 Hybrid adjudication and optional third evaluation system (implemented; policy calibration pending)
  → M4.4 three-system engineering closeout (implemented; accuracy unassessed)
  → M5 read-only diagnostic UI (implemented)
  → M6 deterministic safe formatting
```

Planning references:

- `docs/implementation/m2-execution-plan.md`
- `docs/product/scau-p0-rule-inventory.md`
- `docs/reports/m21-audit-m22-report.md`
- `docs/architecture/rule-contract-v2.md`
- `docs/decisions/0003-single-template-profile.md`
- `docs/reports/m23-profile-report.md`
- `docs/implementation/m3-execution-plan.md`
- `docs/reports/m3-structure-report.md`
- `docs/implementation/m4-execution-plan.md`
- `docs/reports/m40-review-safety-report.md`
- `docs/reports/m41-cloud-provider-report.md`
- `docs/reports/m41-deepseek-live-test.md`
- `docs/reports/m42-gold-set-report.md`
- `docs/reports/m43-hybrid-report.md`
- `docs/reports/m44-evaluation-closeout.md`
- `docs/implementation/m5-execution-plan.md`
- `docs/reports/m5-diagnostic-ui-report.md`
- `docs/README.md`

Do not re-ask the template scope or expand college-specific templates. Remaining atomic confirmation and page-layout ambiguities can be requested when needed for consequential validation or formatting, not as a blanket blocker on read-only development.

Do not infer rules from visual appearance alone. Every rule needs source evidence, status, implementation strategy, and validator. Keep M1 CLI artifacts stable while M2 evolves.
