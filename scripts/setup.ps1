$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $ProjectRoot '.venv'

if (-not (Test-Path -LiteralPath $VenvPath)) {
    python -m venv $VenvPath
}

$Python = Join-Path $VenvPath 'Scripts\python.exe'
& $Python -m pip install --upgrade pip
& $Python -m pip install -e $ProjectRoot -r (Join-Path $ProjectRoot 'requirements-observability.txt')
Push-Location $ProjectRoot
try {
    npm ci
    npx playwright install chromium
    docker compose -f observability/docker-compose.yml up -d --wait
}
finally {
    Pop-Location
}
Write-Output "Ready. Python is isolated in .venv, Node packages in node_modules, Phoenix in Docker."
