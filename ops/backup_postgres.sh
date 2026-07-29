#!/bin/sh
set -eu

: "${REVIEWMIND_PG_DSN:?REVIEWMIND_PG_DSN is required}"
BACKUP_DIR="${REVIEWMIND_BACKUP_DIR:-/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${BACKUP_DIR}/reviewmind-${STAMP}.dump"

mkdir -p "${BACKUP_DIR}"
umask 077
pg_dump --format=custom --no-owner --no-privileges \
  --file="${BACKUP_FILE}" "${REVIEWMIND_PG_DSN}"
sha256sum "${BACKUP_FILE}" > "${BACKUP_FILE}.sha256"
echo "${BACKUP_FILE}"
