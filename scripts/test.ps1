$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing .venv. Run .\scripts\setup.ps1 first."
}

# A fresh, workspace-local run avoids stale temp/cache permissions across execution identities.
$testRunDirectory = Join-Path $RepoRoot ('.paperalign/test-runs/' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRunDirectory -Force | Out-Null
$testTempDirectory = Join-Path $testRunDirectory 'pytest'
$testCacheDirectory = Join-Path $testRunDirectory 'cache'

Push-Location (Join-Path $RepoRoot "backend")
try {
    & $Python -m ruff check .
    if ($LASTEXITCODE -ne 0) { throw 'Ruff failed' }
    & $Python -m mypy app paperalign
    if ($LASTEXITCODE -ne 0) { throw 'mypy failed' }
    & $Python -m pytest --basetemp $testTempDirectory -o "cache_dir=$testCacheDirectory" --tb=short
    if ($LASTEXITCODE -ne 0) { throw 'pytest failed' }
    & $Python -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed' }
    & $Python -m app.schema_export --check
    if ($LASTEXITCODE -ne 0) { throw 'Schemas differ from current model definitions' }
}
finally {
    Pop-Location
}

Push-Location (Join-Path $RepoRoot "frontend")
try {
    npm run typecheck
    if ($LASTEXITCODE -ne 0) { throw 'Frontend typecheck failed' }
    npm run test
    if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
    npm audit --audit-level=high
    if ($LASTEXITCODE -ne 0) { throw 'Dependency audit failed' }
}
finally {
    Pop-Location
}
