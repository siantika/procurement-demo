#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${PROJECT_ROOT}/.env}"
if [[ "${ENV_FILE}" != /* ]]; then
    ENV_FILE="${PROJECT_ROOT}/${ENV_FILE}"
fi
BACKUP_ROOT="${PROJECT_ROOT}/backups"

[[ -f "${ENV_FILE}" ]] || {
    echo "File environment tidak ditemukan: ${ENV_FILE}" >&2
    exit 1
}
grep -qx 'APP_ENV=demo' "${ENV_FILE}" || {
    echo "Backup hanya boleh berjalan untuk APP_ENV=demo." >&2
    exit 1
}

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_name="demo-${timestamp}"
backup_dir="${BACKUP_ROOT}/${backup_name}"
mkdir -p "${backup_dir}"

cd "${PROJECT_ROOT}"
compose=(docker compose --env-file "${ENV_FILE}")
"${compose[@]}" exec -T postgres pg_dump \
    -U procurement -d procurement -Fc > "${backup_dir}/postgres.dump"
"${compose[@]}" run --rm --no-deps minio-client \
    "mc alias set local http://minio:9000 \"\${MINIO_ROOT_USER}\" \"\${MINIO_ROOT_PASSWORD}\" >/dev/null && mc mirror --overwrite --preserve \"local/\${MINIO_BUCKET}\" \"/backups/${backup_name}/minio\""
git rev-parse HEAD > "${backup_dir}/release-commit.txt"
"${compose[@]}" exec -T web python manage.py showmigrations \
    > "${backup_dir}/migrations.txt"

echo "Backup demo selesai: ${backup_dir}"
