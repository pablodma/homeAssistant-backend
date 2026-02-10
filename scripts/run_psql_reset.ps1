# Ejecutar: railway run powershell -ExecutionPolicy Bypass -File homeai-api/scripts/run_psql_reset.ps1
# O con URL manual: $env:DATABASE_PUBLIC_URL="postgresql://..."; .\run_psql_reset.ps1

$psql = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
$url = $env:DATABASE_PUBLIC_URL ?? $env:DATABASE_URL
if (-not $url) {
    Write-Error "DATABASE_PUBLIC_URL o DATABASE_URL no definida"
    exit 1
}
$scriptPath = Join-Path $PSScriptRoot "db\reset_oauth_users.sql"
& $psql $url -f $scriptPath
