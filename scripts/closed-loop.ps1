$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw 'Missing .venv. Run .\scripts\setup.ps1 first.' }

Push-Location $ProjectRoot
try {
    docker compose -f observability/docker-compose.yml up -d --wait
    & $Python qualityctl.py platform-coverage
    & $Python qualityctl.py pipeline
    if ($LASTEXITCODE -ne 0) {
        throw "Quality pipeline failed; release decision remains blocked."
    }
    & $Python qualityctl.py release-decide --run-id latest
    & $Python qualityctl.py audit-verify
    Write-Host "Closed-loop verification completed. See reports/dashboard.html."
}
finally {
    Pop-Location
}
