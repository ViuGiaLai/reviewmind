#!/bin/sh
set -eu

: "${REVIEWMIND_PG_DSN:?REVIEWMIND_PG_DSN is required}"
: "${1:?usage: restore_postgres.sh BACKUP_FILE}"
BACKUP_FILE="$1"

sha256sum -c "${BACKUP_FILE}.sha256"
pg_restore --clean --if-exists --no-owner --no-privileges \
  --dbname="${REVIEWMIND_PG_DSN}" "${BACKUP_FILE}"
