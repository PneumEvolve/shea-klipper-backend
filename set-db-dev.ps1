# set-db-dev.ps1
param(
  [string]$Url = "postgresql+psycopg2://postgres:coolmints@127.0.0.1:5433/appdb?sslmode=disable"
)

$env:DATABASE_URL = $Url
$env:ALEMBIC_DATABASE_URL = $env:DATABASE_URL   # migrations = app URL for dev
$env:ENV = "dev"

Write-Host "✅ Using DEV DB:" -ForegroundColor Cyan
Write-Host "   ENV=dev"
Write-Host "   DATABASE_URL=$($env:DATABASE_URL)"
Write-Host "   ALEMBIC_DATABASE_URL=$($env:ALEMBIC_DATABASE_URL)"
Write-Host ""

# Quick sanity
alembic heads
alembic current