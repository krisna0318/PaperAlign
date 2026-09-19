$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing .venv. Run .\scripts\setup.ps1 first."
}

Push-Location (Join-Path $RepoRoot "backend")
try {
    & $Python -m ruff check .
    & $Python -m mypy app paperalign
    & $Python -m pytest
    & $Python -m pip check
    & $Python -m app.schema_export
    git -C $RepoRoot diff --exit-code -- schemas
}
finally {
    Pop-Location
}

Push-Location (Join-Path $RepoRoot "frontend")
try {
    npm run typecheck
    npm run test
    npm run build
    npm audit --audit-level=high
}
finally {
    Pop-Location
}
