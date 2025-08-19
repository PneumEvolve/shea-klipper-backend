# Dev: Docker Postgres on localhost:5433, DB=appdb, user=postgres, pass=coolmints
$env:DATABASE_URL = "postgresql+psycopg2://postgres:coolmints@127.0.0.1:5433/appdb"
"Set DATABASE_URL (DEV): $env:DATABASE_URL"