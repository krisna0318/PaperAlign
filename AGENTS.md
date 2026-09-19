# PaperAlign Agent Guide

## Product invariants

- Never overwrite an uploaded document.
- Never commit real theses, secrets, task artifacts, or full manuscript text in logs.
- AI may propose semantic decisions; deterministic code performs formatting.
- Every diagnosis must retain its rule, evidence, and decision source.
- Unknown and unsupported are valid results. Do not fabricate certainty.
- The application must remain usable in rules-only mode without an API key.

## Development order

Follow the milestone order in `docs/product/mvp-scope.md`. Do not build formatting before read-only parsing, fingerprints, and validation exist.

## Code conventions

- Python: 3.12+, typed code, Pydantic v2 models, Ruff formatting and linting.
- TypeScript: strict mode; domain field names mirror backend JSON names.
- Add a regression fixture for each document parsing or formatting bug.
- Fixtures must be synthetic or manually anonymized.
- Keep generated artifacts outside version control.

## Verification

- Backend: pytest, Ruff, mypy.
- Frontend: typecheck, Vitest, production build.
- Document work in later milestones: package validation, content fingerprints, golden outputs, and visual verification.
