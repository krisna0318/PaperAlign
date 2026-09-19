# PaperAlign Working Context

## Current state

- Current milestone: M1 implementation complete; M2 is next after real-document validation.
- Implemented: repository scaffold, safe DOCX package inspection, OOXML document profile, protected-content fingerprint, unsupported-object report, deterministic CLI artifacts, tests, and CI.
- Not implemented: SCAU format rules, semantic classification, compliance diagnosis, formatting, AI calls, Word automation.

## Product decisions that must survive context changes

1. The first profile is SCAU undergraduate theses, not arbitrary templates.
2. User manuscripts are `.docx`. The official legacy `.doc` is offline rule evidence only.
3. AI resolves semantics and ambiguity; deterministic code changes formatting.
4. Rules-only mode must work without an API key.
5. Never overwrite the original document or silently alter protected content.
6. Every decision must expose its source: Word style, rule, model, hybrid, or user.
7. Unknown, unsupported, evidence-insufficient, and not-evaluated are valid outcomes.
8. Real theses, secrets, and full manuscript logs never enter Git.

## Next implementation target

Validate M1 with the user's anonymized real DOCX, then build the M2 SCAU rule profile:

```text
official template evidence
  → manually confirmed P0 rules
  → versioned manifest.json
  → validators and evidence locators
```

Do not infer rules from visual appearance alone. Every rule needs source evidence, status, implementation strategy, and validator. Keep M1 CLI artifacts stable while M2 evolves.
