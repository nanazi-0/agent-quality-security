$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $ProjectRoot
try {
    docker compose -f observability/docker-compose.yml up -d --wait
    Write-Output 'Phoenix is ready at http://127.0.0.1:6006'
}
finally {
    Pop-Location
}
