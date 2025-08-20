# migrate-prod.ps1
param(
  [switch]$Apply,                 # if omitted, we only produce SQL
  [string]$OutFile = ("migrations_prod_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".sql")
)

if ($env:ENV -ne "prod") {
  Write-Host "ENV is '$($env:ENV)'; this helper is for prod only." -ForegroundColor Yellow
  exit 1
}

Write-Host "Generating dry-run SQL from Alembic…" -ForegroundColor Cyan
alembic upgrade head --sql | Tee-Object -FilePath $OutFile | Out-Null
Write-Host "SQL saved to $OutFile" -ForegroundColor Green

if (-not $Apply) {
  Write-Host "`nRun again with -Apply to execute on prod once you’ve reviewed the SQL." -ForegroundColor Yellow
  exit 0
}

# Explicit confirmation
$answer = Read-Host "Type EXACTLY 'apply prod' to execute Alembic upgrade on PRODUCTION"
if ($answer -ne "apply prod") {
  Write-Host "Aborted." -ForegroundColor Yellow
  exit 1
}

Write-Host "Applying Alembic upgrade head to PRODUCTION…" -ForegroundColor Red
alembic upgrade head