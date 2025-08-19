# db-reset-dev.ps1
# Recreate local dev DB in Docker, restore latest dump, run alembic upgrade.
# Requires: Docker Desktop running, postgres:17 image available, alembic installed in your venv.
# Run this from your backend repo root (where alembic.ini lives).

[CmdletBinding()]
param(
  [string]$ContainerName = "pg17-dev",
  [int]   $HostPort      = 5433,
  [string]$DbName        = "appdb",
  [string]$DbUser        = "postgres",
  [string]$DbPass        = "coolmints",                 # local postgres container password
  [string]$BackupDir     = "$(Resolve-Path .)\db_backup\backup",
  [string]$PgDataDir     = "$(Resolve-Path .)\db_backup\pg17data",
  [string]$DumpFile      # optional explicit path to a .dump file; if omitted, uses latest in $BackupDir
)

$ErrorActionPreference = "Stop"

function Ensure-Directory($path) {
  if (-not (Test-Path $path)) { New-Item -ItemType Directory -Path $path | Out-Null }
}

function Ensure-Container {
  param([string]$Name, [string]$PgDataDir, [int]$HostPort, [string]$DbPass)
  $running = (docker ps --format '{{.Names}}' | Where-Object { $_ -eq $Name })
  $exists  = (docker ps -a --format '{{.Names}}' | Where-Object { $_ -eq $Name })

  if ($running) { return }

  if (-not $exists) {
    Write-Host "Starting new postgres:17 container '$Name' on port $HostPort..."
    docker run -d --name $Name `
      -e "POSTGRES_PASSWORD=$DbPass" `
      -p "$HostPort:5432" `
      -v "${PgDataDir}:/var/lib/postgresql/data" `
      postgres:17 | Out-Null
  } else {
    Write-Host "Starting existing container '$Name'..."
    docker start $Name | Out-Null
  }

  Write-Host "Waiting for Postgres to accept connections..."
  Start-Sleep -Seconds 3
}

function Recreate-Database {
  param([string]$Name, [string]$DbName, [string]$DbUser)
  Write-Host "Dropping and creating database '$DbName'..."
  docker exec -i $Name psql -U $DbUser -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $DbName;" | Out-Null
  docker exec -i $Name psql -U $DbUser -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $DbName;" | Out-Null
}

function Find-LatestDump {
  param([string]$BackupDir)
  $file = Get-ChildItem -Path $BackupDir -Filter *.dump -File -ErrorAction SilentlyContinue |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $file) { throw "No .dump file found in '$BackupDir'. Create a prod dump first." }
  return $file.FullName
}

# --- main ---
Ensure-Directory $BackupDir
Ensure-Directory $PgDataDir
Ensure-Container -Name $ContainerName -PgDataDir $PgDataDir -HostPort $HostPort -DbPass $DbPass

Recreate-Database -Name $ContainerName -DbName $DbName -DbUser $DbUser

if (-not $DumpFile) { $DumpFile = Find-LatestDump -BackupDir $BackupDir }
Write-Host "Restoring from dump: $DumpFile"

# Use a transient postgres:17 container to run pg_restore against host DB (host.docker.internal:5433)
docker run --rm `
  -v "${BackupDir}:/backup" `
  postgres:17 `
  pg_restore --verbose --no-owner --no-privileges `
    --dbname "postgresql://$DbUser:$DbPass@host.docker.internal:$HostPort/$DbName" `
    "/backup/$(Split-Path $DumpFile -Leaf)"

# Run alembic migrations locally (host), using dev DATABASE_URL that points to the container
$env:DATABASE_URL = "postgresql://$DbUser:$DbPass@127.0.0.1:$HostPort/$DbName"
Write-Host "Running Alembic upgrade on local dev DB..."
alembic upgrade head

Write-Host "Done. Local DB reset + restored + migrated."