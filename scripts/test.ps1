$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw 'Missing .venv. Run .\scripts\setup.ps1 first.' }
Push-Location $ProjectRoot
try {
    & $Python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python qualityctl.py demo
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python qualityctl.py pipeline
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
