#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${PROJECT_ROOT}/.run"
LOG_DIR="${RUN_DIR}/logs"
ENV_FILE="${PROJECT_ROOT}/.env"
MINIO_CONTAINER="procurement-minio"

services=(web worker_optimization worker_documents beat)

mkdir -p "${LOG_DIR}"

pid_file() {
    printf '%s/%s.pid' "${RUN_DIR}" "$1"
}

log_file() {
    printf '%s/%s.log' "${LOG_DIR}" "$1"
}

service_token() {
    case "$1" in
        web) printf '%s' 'manage.py runserver' ;;
        worker_optimization) printf '%s' 'worker-optimization' ;;
        worker_documents) printf '%s' 'worker-documents' ;;
        beat) printf '%s' 'celery -A config beat' ;;
        *) return 1 ;;
    esac
}

is_project_process() {
    local name="$1"
    local pid="$2"
    local cwd
    local command
    [[ "${pid}" =~ ^[0-9]+$ ]] || return 1
    kill -0 "${pid}" 2>/dev/null || return 1
    cwd="$(readlink -f "/proc/${pid}/cwd" 2>/dev/null || true)"
    command="$(tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true)"
    [[ "${cwd}" == "${PROJECT_ROOT}" ]] || return 1
    [[ "${command}" == *"$(service_token "${name}")"* ]]
}

service_pid() {
    local name="$1"
    local file
    local pid
    file="$(pid_file "${name}")"
    [[ -f "${file}" ]] || return 1
    pid="$(<"${file}")"
    if is_project_process "${name}" "${pid}"; then
        printf '%s' "${pid}"
        return 0
    fi
    rm -f "${file}"
    return 1
}

unmanaged_service_pid() {
    local name="$1"
    local process_path
    local pid
    for process_path in /proc/[0-9]*; do
        pid="${process_path##*/}"
        if is_project_process "${name}" "${pid}"; then
            printf '%s' "${pid}"
            return 0
        fi
    done
    return 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Perintah '$1' tidak ditemukan." >&2
        exit 1
    }
}

read_env_value() {
    local name="$1"
    sed -n "s/^${name}=//p" "${ENV_FILE}" | tail -n 1
}

ensure_dependencies() {
    require_command uv
    require_command docker
    require_command curl
    [[ -f "${ENV_FILE}" ]] || {
        echo "File .env tidak ditemukan." >&2
        exit 1
    }
    pg_isready >/dev/null 2>&1 || {
        echo "PostgreSQL belum aktif. Jalankan: sudo systemctl start postgresql" >&2
        exit 1
    }
    redis-cli ping 2>/dev/null | grep -qx PONG || {
        echo "Redis belum aktif. Jalankan: sudo systemctl start redis-server" >&2
        exit 1
    }
}

start_minio() {
    if docker container inspect "${MINIO_CONTAINER}" >/dev/null 2>&1; then
        if [[ "$(docker inspect -f '{{.State.Running}}' "${MINIO_CONTAINER}")" != "true" ]]; then
            docker start "${MINIO_CONTAINER}" >/dev/null
        fi
    else
        local access_key
        local secret_key
        access_key="$(read_env_value MINIO_ACCESS_KEY)"
        secret_key="$(read_env_value MINIO_SECRET_KEY)"
        [[ -n "${access_key}" && -n "${secret_key}" ]] || {
            echo "Credential MinIO di .env belum lengkap." >&2
            exit 1
        }
        docker run -d \
            --name "${MINIO_CONTAINER}" \
            -p 9000:9000 \
            -p 9001:9001 \
            -e MINIO_ROOT_USER="${access_key}" \
            -e MINIO_ROOT_PASSWORD="${secret_key}" \
            -v procurement-minio-data:/data \
            quay.io/minio/minio server /data \
            --console-address ':9001' >/dev/null
    fi

    local attempt
    for attempt in {1..20}; do
        if curl -fsS \
            http://127.0.0.1:9000/minio/health/live \
            >/dev/null 2>&1; then
            echo "MinIO aktif."
            return 0
        fi
        sleep 1
    done
    echo "MinIO tidak sehat setelah 20 detik." >&2
    exit 1
}

start_service() {
    local name="$1"
    local existing
    local pid
    if existing="$(service_pid "${name}")"; then
        echo "${name} sudah aktif (PID ${existing})."
        return 0
    fi
    if existing="$(unmanaged_service_pid "${name}")"; then
        echo "${name} aktif di luar Makefile (PID ${existing})." >&2
        echo "Hentikan proses tersebut sebelum menjalankan make start." >&2
        exit 1
    fi

    cd "${PROJECT_ROOT}"
    case "${name}" in
        web)
            setsid uv run --env-file .env python manage.py runserver \
                127.0.0.1:8000 --noreload \
                >"$(log_file "${name}")" 2>&1 < /dev/null &
            ;;
        worker_optimization)
            setsid uv run --env-file .env celery -A config worker \
                -l info -Q optimization --concurrency=2 \
                --hostname='worker-optimization@%h' \
                >"$(log_file "${name}")" 2>&1 < /dev/null &
            ;;
        worker_documents)
            setsid uv run --env-file .env celery -A config worker \
                -l info -Q documents --concurrency=1 \
                --hostname='worker-documents@%h' \
                >"$(log_file "${name}")" 2>&1 < /dev/null &
            ;;
        beat)
            setsid uv run --env-file .env celery -A config beat \
                -l info --schedule "${RUN_DIR}/celerybeat-schedule" \
                >"$(log_file "${name}")" 2>&1 < /dev/null &
            ;;
    esac
    pid=$!
    printf '%s\n' "${pid}" > "$(pid_file "${name}")"
    sleep 1
    if ! is_project_process "${name}" "${pid}"; then
        echo "${name} gagal dijalankan. Periksa $(log_file "${name}")." >&2
        exit 1
    fi
    echo "${name} aktif (PID ${pid})."
}

stop_service() {
    local name="$1"
    local pid
    local attempt
    if ! pid="$(service_pid "${name}")"; then
        echo "${name} tidak dikelola atau sudah berhenti."
        return 0
    fi
    kill -TERM -- "-${pid}" 2>/dev/null || kill -TERM "${pid}"
    for attempt in {1..10}; do
        kill -0 "${pid}" 2>/dev/null || break
        sleep 1
    done
    if kill -0 "${pid}" 2>/dev/null; then
        echo "${name} belum berhenti setelah 10 detik." >&2
        return 1
    fi
    rm -f "$(pid_file "${name}")"
    echo "${name} berhenti."
}

start_all() {
    ensure_dependencies
    start_minio
    cd "${PROJECT_ROOT}"
    if ! uv run --env-file .env python manage.py shell -c \
        "from apps.documents.storage import _client, _ensure_bucket; _ensure_bucket(_client())" \
        >/dev/null; then
        echo "Credential atau koneksi MinIO tidak valid." >&2
        exit 1
    fi
    uv run --env-file .env python manage.py migrate --noinput
    for name in "${services[@]}"; do
        start_service "${name}"
    done
    echo "Sistem aktif di http://127.0.0.1:8000"
}

stop_all() {
    local index
    for ((index=${#services[@]}-1; index>=0; index--)); do
        stop_service "${services[index]}"
    done
    if docker container inspect "${MINIO_CONTAINER}" >/dev/null 2>&1 \
        && [[ "$(docker inspect -f '{{.State.Running}}' "${MINIO_CONTAINER}")" == "true" ]]; then
        docker stop "${MINIO_CONTAINER}" >/dev/null
        echo "MinIO berhenti."
    else
        echo "MinIO sudah berhenti."
    fi
    echo "PostgreSQL dan Redis global tetap aktif."
}

show_status() {
    local name
    local pid
    for name in "${services[@]}"; do
        if pid="$(service_pid "${name}")"; then
            echo "${name}: aktif (PID ${pid})"
        elif pid="$(unmanaged_service_pid "${name}")"; then
            echo "${name}: aktif di luar Makefile (PID ${pid})"
        else
            echo "${name}: berhenti"
        fi
    done
    if docker container inspect "${MINIO_CONTAINER}" >/dev/null 2>&1; then
        echo "minio: $(docker inspect -f '{{.State.Status}}' "${MINIO_CONTAINER}")"
    else
        echo "minio: belum dibuat"
    fi
    pg_isready >/dev/null 2>&1 \
        && echo "postgresql: aktif" || echo "postgresql: berhenti"
    redis-cli ping 2>/dev/null | grep -qx PONG \
        && echo "redis: aktif" || echo "redis: berhenti"
}

show_logs() {
    local files=("${LOG_DIR}"/*.log)
    [[ -e "${files[0]}" ]] || {
        echo "Belum ada log. Jalankan make start terlebih dahulu." >&2
        exit 1
    }
    tail -n 100 -f "${files[@]}"
}

case "${1:-}" in
    start) start_all ;;
    stop) stop_all ;;
    restart) stop_all; start_all ;;
    status) show_status ;;
    logs) show_logs ;;
    *)
        echo "Gunakan: $0 {start|stop|restart|status|logs}" >&2
        exit 2
        ;;
esac
