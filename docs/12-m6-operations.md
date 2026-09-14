# M6 Demo Operations

Dokumen ini melengkapi `11-demo-runbook.md` dengan command yang sudah
diimplementasikan.

## Menyiapkan environment

Salin `.env.demo.example` menjadi `.env.demo`, lalu ganti seluruh nilai
`replace-with-*`. Nilai `MINIO_ACCESS_KEY` harus sama dengan
`MINIO_ROOT_USER`; nilai `MINIO_SECRET_KEY` harus sama dengan
`MINIO_ROOT_PASSWORD`. File `.env.demo` tidak boleh di-commit.

Validasi konfigurasi sebelum menyalakan container:

```bash
DEMO_ENV_FILE=.env.demo docker compose config --quiet
```

Semua target `docker-*` menerima override yang sama, misalnya
`make docker-status DEMO_ENV_FILE=.env.demo.staging`.

## Menjalankan stack

```bash
make docker-start
make docker-status
make docker-seed
```

Endpoint minimum:

- `GET /health/live/` untuk liveness process;
- `GET /health/ready/` untuk database dan migration readiness;
- `GET /metrics/` untuk metrik HTTP dan background job tanpa label UUID.

## Rehearsal

Jalankan primary scenario tiga kali melalui worker dan private storage:

```bash
make docker-smoke
```

Smoke harus menghasilkan purchase `Rp663.000.000`, Bid `Rp780.000.000`,
dan PDF yang lolos verifikasi checksum.

## Reset aman

Reset hanya berjalan bila `APP_ENV=demo` dan confirmation token tepat.
Command hanya menghapus namespace canonical `demo-*`, `PUMP-001`,
`SUP-A..C`, `DEMO-OFFER-*`, dan `DEMO-TENDER-001` beserta turunannya.

```bash
make docker-reset
make docker-seed
```

PostgreSQL migration history dan object di luar dataset demo tidak dihapus.

## Backup

```bash
make docker-backup
```

Artefak berada di `backups/demo-<UTC>/` dan berisi dump PostgreSQL,
salinan object MinIO, commit release, dan migration state. Direktori backup
tidak di-commit. Salin dan enkripsi artefak di media terpisah sesuai
kebijakan operator.

Restore wajib dilakukan pada environment terisolasi. Verifikasi migration,
jalankan `/health/ready/`, cocokkan checksum FinalDocument, lalu jalankan
`smoke_demo` sebelum target dianggap pulih.

## Shutdown dan troubleshooting

```bash
make docker-logs
make docker-stop
```

Jika job tertahan, periksa worker sesuai queue dan biarkan reconciliation
memublikasikan ulang record PENDING. Bid tetap `SIGNED` ketika rendering PDF
gagal; jangan mengubah status secara manual.
