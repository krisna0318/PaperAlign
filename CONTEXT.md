# PaperAlign Working Context

## Current state

- Current milestone: M3 Rules-only structure classification implemented (application 0.7.0). Full M2 normative confirmation and M3 human review of real ambiguity remain ongoing acceptance work.
- Implemented: repository scaffold, safe DOCX package inspection, OOXML document profile, protected-content fingerprint, unsupported-object report, deterministic CLI artifacts, tests, and CI.
- Not implemented: AI ambiguity resolution, diagnostic upload UI, deterministic formatting, and final Word validation. Full school compliance is not available while 244 rules remain provisional.
- M2.0 implemented: comment-optional template evidence extraction, paragraph style usage, direct-format clusters, and table border widths with OOXML-to-point conversion.
- M2.1 implemented: document defaults, base/derived paragraph styles, character styles and direct formatting are merged into property-level effective values with provenance.
- M2.1 audit: `audit-template --include-preview` writes HTML and short previews only under ignored `.paperalign`. Real Word 16.0 check: 13 paragraphs, 92 matching properties; source SHA unchanged. This is not human visual sign-off. Browser tool denied file:// page inspection; do not claim UI visual verification.
- M2.2: FormatRule schema 2.0 (breaking from free-form 1.0); typed values/units/scopes, human confirmation record, evidence precedence, normalized observations, preflight states. Preflight None means ready for a comparator, never pass.
- M2.3: Profile 1.0.0 has 248 atomic rules (4 confirmed, 244 provisional), 36 evidence records, 46 inventory entries (14 encoded, 23 partial, 9 deferred). Loader validates references, evidence hash, duplicate definitions and coverage. Every rule is read-only.
- CLI: inspect-profile exports profile.json/profile_summary.md/applicability.json. verify-template checks hash-bound sample indexes only; rejects other documents. Real sample: 3 pass, 1 fail (abbreviation table separator 0.5 pt vs 1 pt), 108 evidence_insufficient. Never label these counts whole-document compliance.
- M3: classify produces a hash-bound StructureReport for every represented M1 block, identifies four heading levels and document regions, preserves TOC fields, detects formulas/drawings, builds parentage, allows reviewed role/scope corrections, and runs located M2 rules. Local HTML/JSON/Markdown stay under .paperalign; no-key and no-write.
- Real runs before final full regression: thesis 785 blocks, 28 priority review roots / 179 including inherited table-cell review; template 392 blocks, 9 review roots. Thesis located checks: 2 pass, 2 fail, 4379 evidence_insufficient. These are check occurrences, not unique-rule coverage or accuracy.
- Latest full verification: scripts/test.ps1 passed, 113 backend tests, strict mypy (52 source files), Ruff, schema check, dependency checks, 1 frontend test and build; npm audit 0 vulnerabilities. Two third-party deprecation warnings remain nonblocking.
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

Complete M3 real-document human review, then implement M4 AI ambiguity comparison. Keep M2 rule confirmation as a separate gate before any consequential formatting:

```text
official template evidence
  → comment-optional structural and formatting observations
  → property-level effective values and provenance
  → manually confirmed P0 rules
  → versioned manifest.json
  → validators and evidence locators (fixed template samples working)
  → M3 role recognition and hash-bound human corrections (implemented)
  → M4 model proposals for ambiguous items only, with schema validation and rules-only fallback
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

Do not re-ask the template scope or expand college-specific templates. Remaining atomic confirmation and page-layout ambiguities can be requested when needed for consequential validation or formatting, not as a blanket blocker on read-only development.

Do not infer rules from visual appearance alone. Every rule needs source evidence, status, implementation strategy, and validator. Keep M1 CLI artifacts stable while M2 evolves.
