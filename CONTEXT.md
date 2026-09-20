# PaperAlign Working Context

## Current state

- Current milestone: M2.3 single-template Profile implemented (application 0.6.0), with bounded M2.4 comparisons and M2.5 fixed-template sample checks. Full M2 acceptance is not complete.
- Implemented: repository scaffold, safe DOCX package inspection, OOXML document profile, protected-content fingerprint, unsupported-object report, deterministic CLI artifacts, tests, and CI.
- Not implemented: whole-manuscript semantic classification, full compliance checks, formatting, AI calls. Read-only Word cross-check exists as a development script, not production Word automation.
- M2.0 implemented: comment-optional template evidence extraction, paragraph style usage, direct-format clusters, and table border widths with OOXML-to-point conversion.
- M2.1 implemented: document defaults, base/derived paragraph styles, character styles and direct formatting are merged into property-level effective values with provenance.
- M2.1 audit: `audit-template --include-preview` writes HTML and short previews only under ignored `.paperalign`. Real Word 16.0 check: 13 paragraphs, 92 matching properties; source SHA unchanged. This is not human visual sign-off. Browser tool denied file:// page inspection; do not claim UI visual verification.
- M2.2: FormatRule schema 2.0 (breaking from free-form 1.0); typed values/units/scopes, human confirmation record, evidence precedence, normalized observations, preflight states. Preflight None means ready for a comparator, never pass.
- M2.3: Profile 1.0.0 has 248 atomic rules (4 confirmed, 244 provisional), 36 evidence records, 46 inventory entries (14 encoded, 23 partial, 9 deferred). Loader validates references, evidence hash, duplicate definitions and coverage. Every rule is read-only.
- CLI: inspect-profile exports profile.json/profile_summary.md/applicability.json. verify-template checks hash-bound sample indexes only; rejects other documents. Real sample: 3 pass, 1 fail (abbreviation table separator 0.5 pt vs 1 pt), 108 evidence_insufficient. Never label these counts whole-document compliance.
- Latest full verification: scripts/test.ps1 passed, 89 backend tests, strict mypy (48 source files), Ruff, schema check, dependency checks, 1 frontend test and build; npm audit 0 vulnerabilities. Two third-party deprecation warnings remain nonblocking.
- Latest pushed commit remains e043724 (M2.0). M2.1–M2.3 and bounded M2.4 changes remain local and uncommitted.

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

Continue bounded M2.4 adapter/validator coverage and M2 acceptance evidence; then implement M3 Rules-only structural classification. Keep unresolved normative/layout decisions separate from supported code:

```text
official template evidence
  → comment-optional structural and formatting observations
  → property-level effective values and provenance
  → manually confirmed P0 rules
  → versioned manifest.json
  → validators and evidence locators (fixed template samples working)
  → M3 role recognition for arbitrary manuscript objects
```

Planning references:

- `docs/implementation/m2-execution-plan.md`
- `docs/product/scau-p0-rule-inventory.md`
- `docs/reports/m21-audit-m22-report.md`
- `docs/architecture/rule-contract-v2.md`
- `docs/decisions/0003-single-template-profile.md`
- `docs/reports/m23-profile-report.md`

Do not re-ask the template scope or expand college-specific templates. Remaining atomic confirmation and page-layout ambiguities can be requested when needed for consequential validation or formatting, not as a blanket blocker on read-only development.

Do not infer rules from visual appearance alone. Every rule needs source evidence, status, implementation strategy, and validator. Keep M1 CLI artifacts stable while M2 evolves.
