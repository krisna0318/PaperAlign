$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    py -3.13 -m venv (Join-Path $RepoRoot ".venv")
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -e "$RepoRoot\backend[dev]"

Push-Location (Join-Path $RepoRoot "frontend")
try {
    npm install
}
finally {
    Pop-Location
}

Write-Host "PaperAlign development dependencies are ready."
