# db-migrate-prod.ps1
# Back up prod (Supabase) then run Alembic migrations on prod.
# Requires: Docker Desktop, postgres:17 image, alembic installed locally.
# Run this from your backend repo root (where alembic.ini lives).

[CmdletBinding()]
param(
  [switch]$Preview,   # if set, outputs SQL to a file instead of applying
  [string]$BackupDir = "$(Resolve-Path .)\db_backup\backup",

  # Prod (Supabase)
  [string]$ProdHost = "db.marispwfnzezwetzmzdc.supabase.co",
  [int]   $ProdPort = 5432,
  [string]$ProdDb   = "postgres",
  [string]$ProdUser = "postgres",
  [string]$ProdPass = "Coolmints94!"     # prod password
)

$ErrorActionPreference = "Stop"
$today = Get-Date -Format 'yyyyMMdd_HHmmss'
if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir | Out-Null }

Write-Host "Creating PRODUCTION backup (custom format dump)..."
docker run --rm `
  -e PGSSLMODE=require `
  -e PGPASSWORD="$ProdPass" `
  -v "${BackupDir}:/backup" `
  postgres:17 `
  pg_dump `
    -h $ProdHost `
    -p $ProdPort `
    -U $ProdUser `
    -d $ProdDb `
    --format=custom `
    --blobs `
    --no-owner `
    --no-privileges `
    --verbose `
    -f "/backup/prod_full_$today.dump"

Write-Host "Prod backup created: $BackupDir\prod_full_$today.dump"

# Now run Alembic against prod
$prodUrl = "postgresql://$ProdUser:$ProdPass@$ProdHost:$ProdPort/$ProdDb?sslmode=require"
$env:DATABASE_URL = $prodUrl

if ($Preview) {
  $sqlFile = ".\alembic_prod_preview_$today.sql"
  Write-Host "Preview mode: generating SQL only -> $sqlFile"
  alembic upgrade head --sql > $sqlFile
  Write-Host "Preview SQL written to $sqlFile. Review before live run."
} else {
  Write-Host "Applying Alembic migrations to PROD..."
  alembic upgrade head
  Write-Host "Prod migrations complete."
}