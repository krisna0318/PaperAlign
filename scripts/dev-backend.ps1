$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing .venv. Run .\scripts\setup.ps1 first."
}

& $Python -m uvicorn app.main:app --app-dir (Join-Path $RepoRoot "backend") --reload
