# set-db-prod.ps1
param(
  # Runtime (app) can keep the pooler (6543) if you want
  [string]$AppUrl  = "postgresql+psycopg2://postgres:Coolmints94%21@aws-0-ca-central-1.pooler.supabase.com:6543/postgres?sslmode=require",

  # Migrations should go to direct port 5432 (safer for DDL)
  [string]$MigUrl  = "postgresql+psycopg2://postgres:Coolmints94%21@db.marispwfnzezwetzmzdc.supabase.co:5432/postgres?sslmode=require",

  # Optional: if you need to force IPv4 routing, set this to the A record (e.g. 35.XXX.XXX.XXX)
  [string]$DbHostAddr = ""
)

$env:DATABASE_URL         = $AppUrl
$env:ALEMBIC_DATABASE_URL = $MigUrl
$env:ENV                  = "prod"

if ($DbHostAddr) {
  $env:DB_HOSTADDR = $DbHostAddr
}

Write-Host "⚠️  PRODUCTION TARGET" -ForegroundColor Yellow
Write-Host "   ENV=prod"
Write-Host "   DATABASE_URL         (runtime): $($env:DATABASE_URL)"
Write-Host "   ALEMBIC_DATABASE_URL (migrate): $($env:ALEMBIC_DATABASE_URL)"
if ($env:DB_HOSTADDR) { Write-Host "   DB_HOSTADDR=$($env:DB_HOSTADDR)" }
Write-Host ""

# Pre-flight info
alembic heads
alembic current