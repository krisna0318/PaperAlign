$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Push-Location (Join-Path $RepoRoot "frontend")
try {
    npm run dev
}
finally {
    Pop-Location
}
