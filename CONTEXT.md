# PaperAlign Working Context

## Current state

- Current milestone: M0 complete; M1 is next.
- Implemented: repository scaffold, local environments, health endpoint, core domain contracts, schema export, tests, CI.
- Not implemented: DOCX parsing, semantic classification, diagnosis, formatting, AI calls, Word automation.

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

Build the M1 read-only analyzer before business UI or model integration:

```text
DOCX package inspection
  → document_profile.json
  → content_fingerprint.json
  → unsupported_objects.json
  → analysis_summary.md
```

The first public interface should be a CLI with deterministic output. Add API and UI only after the parser contract and golden fixtures are stable.
