# SCAU undergraduate 2026 v1

Version 1.1.0 contains 248 atomic rules mapped to the 46 P0 inventory entries. Four user-confirmed abbreviation-table border rules are authorized for the deterministic M6 adapter; the remaining rules are read-only.
Only the four previously confirmed abbreviation-table border rules are confirmed;
the other 244 rules remain provisional. All rules are read-only.

- `manifest.json`: applicability, source-template hash, file references, fixed sample map.
- `rules/*.json`: typed FormatRule 2.0 records. Targets distinguish label/value,
  first/following paragraphs, and cover metadata fields; these are selectors, not
  an implemented semantic classifier.
- `evidence/evidence-index.json`: canonical evidence sources. Comment numbers and
  OOXML locators refer to the private template; short requirement summaries do not
  reproduce the document body. Each rule source must exactly match this index.
- `coverage.json`: encoded, partial, or deferred coverage of each P0 inventory item.
  Encoded means represented in JSON, not validated, confirmed, or auto-fixable.

Applicability is SCAU current graduating undergraduates as confirmed on 2026-09-20,
excluding the School of Foreign Studies and all postgraduate students. No college
customizations are implemented. The dated cohort token is deliberately not an
inferred graduation year. Missing metadata and future cohorts require review.

`inspect-profile` exports the configuration. `verify-template` accepts only the
hash-bound official template and checks known sample objects, never arbitrary
manuscripts using fixed paragraph indexes. No API key or document modification is
involved. The known 0.5 pt / 1 pt table separator discrepancy should remain a failure.

See `docs/decisions/0003-single-template-profile.md`,
`docs/implementation/m23-execution-plan.md`, and
`docs/product/scau-p0-rule-inventory.md` for scope and remaining review items.
