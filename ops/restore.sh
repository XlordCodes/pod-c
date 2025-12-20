#!/bin/bash
# Restore script for Module 8
# Usage: ./ops/restore.sh backups/your-backup-file.sql

if [ -z "$1" ]; then
  echo "Usage: ./ops/restore.sh <backup_file>"
  exit 1
fi

# Pipe the file into the db container's psql tool
cat "$1" | docker-compose exec -T db psql -U user -d crm_main

echo "✅ Restoration complete from $1"