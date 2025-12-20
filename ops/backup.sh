#!/bin/bash
# Backup script for Module 8
# Usage: ./ops/backup.sh

# Create backups directory if it doesn't exist
mkdir -p backups

# Dump the database using the container's pg_dump tool
# We exec into the 'db' container defined in docker-compose
docker-compose exec -T db pg_dump -U user crm_main > backups/db_$(date +%F_%H-%M-%S).sql

echo "✅ Backup complete: backups/db_$(date +%F_%H-%M-%S).sql"