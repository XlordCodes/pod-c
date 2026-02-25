# rebuild.ps1
$ErrorActionPreference = "Stop"

Write-Host "======================================"
Write-Host "🔄 CRM Database Rebuild & Seed Utility"
Write-Host "======================================"

Write-Host "🚨 1. Dropping all existing tables..."
docker exec -it crm_backend_api python -c "from app.database import engine, Base; from app.models import auth, crm, chat, bulk, extensions, audit; Base.metadata.drop_all(bind=engine)"

Write-Host "🏗️ 2. Applying existing migrations (Rebuilding baseline)..."
docker exec -it crm_backend_api alembic upgrade head

Write-Host "🔍 3. Checking for new model changes (Autogenerate)..."
docker exec -it crm_backend_api alembic revision --autogenerate -m "dev_schema_update"

Write-Host "🚀 4. Applying any newly generated migrations..."
docker exec -it crm_backend_api alembic upgrade head

Write-Host "🌱 5. Seeding the database with test data..."
docker exec -it crm_backend_api python -m app.seeds

Write-Host "======================================"
Write-Host "✅ All done! The database is fresh, migrated, and seeded."
Write-Host "======================================"