#!/usr/bin/env bash

set -euo pipefail

env_file="${1:-.env.demo}"

[[ -f "${env_file}" ]] || {
    echo "File environment demo tidak ditemukan: ${env_file}" >&2
    exit 1
}

read_value() {
    local key="$1"
    sed -n "s/^${key}=//p" "${env_file}" | tail -n 1
}

require_value() {
    local key="$1"
    local value
    value="$(read_value "${key}")"
    if [[ -z "${value}" ]]; then
        echo "Environment wajib belum diisi: ${key}" >&2
        return 1
    fi
    if [[ "${value}" == *replace-with* ]]; then
        echo "Environment masih memakai placeholder: ${key}" >&2
        return 1
    fi
}

required_keys=(
    APP_ENV
    DJANGO_SETTINGS_MODULE
    DJANGO_SECRET_KEY
    DJANGO_ALLOWED_HOSTS
    DJANGO_CSRF_TRUSTED_ORIGINS
    POSTGRES_PASSWORD
    DATABASE_URL
    CELERY_BROKER_URL
    DJANGO_CACHE_URL
    MINIO_ROOT_USER
    MINIO_ROOT_PASSWORD
    MINIO_ENDPOINT
    MINIO_ACCESS_KEY
    MINIO_SECRET_KEY
    APP_BASE_URL
    DEMO_ADMIN_PASSWORD
    DEMO_STAFF_PASSWORD
    DEMO_MANAGER_PASSWORD
)

for key in "${required_keys[@]}"; do
    require_value "${key}"
done

[[ "$(read_value APP_ENV)" == "demo" ]] || {
    echo "APP_ENV harus bernilai demo." >&2
    exit 1
}

[[ "$(read_value DJANGO_SETTINGS_MODULE)" == "config.settings.demo" ]] || {
    echo "DJANGO_SETTINGS_MODULE harus config.settings.demo." >&2
    exit 1
}

if [[ "$(read_value APP_BASE_URL)" != https://* ]]; then
    echo "APP_BASE_URL VPS wajib menggunakan HTTPS." >&2
    exit 1
fi

if [[ "$(read_value DJANGO_CSRF_TRUSTED_ORIGINS)" != https://* ]]; then
    echo "DJANGO_CSRF_TRUSTED_ORIGINS VPS wajib menggunakan HTTPS." >&2
    exit 1
fi

for key in DJANGO_SECURE_SSL_REDIRECT DJANGO_SESSION_COOKIE_SECURE \
    DJANGO_CSRF_COOKIE_SECURE; do
    [[ "$(read_value "${key}")" == "true" ]] || {
        echo "${key} wajib bernilai true untuk VPS publik." >&2
        exit 1
    }
done

secret_key="$(read_value DJANGO_SECRET_KEY)"
if (( ${#secret_key} < 50 )); then
    echo "DJANGO_SECRET_KEY wajib memiliki minimal 50 karakter." >&2
    exit 1
fi

for key in POSTGRES_PASSWORD MINIO_ROOT_PASSWORD MINIO_SECRET_KEY \
    DEMO_ADMIN_PASSWORD DEMO_STAFF_PASSWORD DEMO_MANAGER_PASSWORD; do
    value="$(read_value "${key}")"
    if (( ${#value} < 20 )); then
        echo "${key} wajib memiliki minimal 20 karakter." >&2
        exit 1
    fi
done

if [[ "$(read_value MINIO_ROOT_USER)" != "$(read_value MINIO_ACCESS_KEY)" ]]; then
    echo "MINIO_ROOT_USER dan MINIO_ACCESS_KEY harus sama." >&2
    exit 1
fi

if [[ "$(read_value MINIO_ROOT_PASSWORD)" != "$(read_value MINIO_SECRET_KEY)" ]]; then
    echo "MINIO_ROOT_PASSWORD dan MINIO_SECRET_KEY harus sama." >&2
    exit 1
fi

if [[ "$(read_value WEB_BIND_ADDRESS)" != "127.0.0.1" ]]; then
    echo "WEB_BIND_ADDRESS VPS wajib 127.0.0.1." >&2
    exit 1
fi

hsts_seconds="$(read_value DJANGO_SECURE_HSTS_SECONDS)"
if [[ ! "${hsts_seconds}" =~ ^[1-9][0-9]*$ ]]; then
    echo "DJANGO_SECURE_HSTS_SECONDS wajib lebih besar dari nol." >&2
    exit 1
fi

file_mode="$(stat -c '%a' "${env_file}")"
if [[ "${file_mode}" != "600" && "${file_mode}" != "400" ]]; then
    echo "Permission ${env_file} harus 600 atau 400, saat ini ${file_mode}." >&2
    exit 1
fi

echo "Preflight environment demo lulus."
