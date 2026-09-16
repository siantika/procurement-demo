# M6 Demo Operations

> Status: Command yang tersedia saat ini<br>
> Terakhir diperbarui: 15 September 2026

Dokumen ini melengkapi `11-demo-runbook.md` dengan command yang sudah
diimplementasikan.

## Menyiapkan environment

Untuk VPS, salin `.env.vps.example` menjadi `.env.vps`, lalu ganti seluruh
nilai `replace-with-*`. Nilai `MINIO_ACCESS_KEY` harus sama dengan
`MINIO_ROOT_USER`; nilai `MINIO_SECRET_KEY` harus sama dengan
`MINIO_ROOT_PASSWORD`. File `.env.vps` tidak boleh di-commit.

Validasi konfigurasi sebelum menyalakan container:

```bash
docker compose --env-file .env.vps config --quiet
```

Semua target `docker-*` memakai `.env` secara default untuk operasi lokal.
Pada VPS, berikan `ENV_FILE=.env.vps` pada setiap target. Target juga menerima
file environment lain, misalnya
`make docker-status ENV_FILE=.env.vps.staging`.

Untuk VPS publik, gunakan `.env.vps.example` sebagai sumber `.env.vps`,
isi domain dan seluruh secret, lalu batasi permission-nya. Preflight VPS
menolak placeholder, endpoint non-HTTPS, secure cookie yang mati, dan file
environment yang dapat dibaca user lain.

```bash
chmod 600 .env.vps
make docker-preflight-vps ENV_FILE=.env.vps
```

Port loopback web dapat dipindahkan bila `8000` sudah dipakai aplikasi lain
dengan `WEB_HOST_PORT`. Contoh VPS memakai `127.0.0.1:8002`, sehingga hanya
reverse proxy yang dapat mengakses Gunicorn. Salin dan sesuaikan
`deploy/nginx-procurement.conf.example`, terbitkan sertifikat TLS, lalu uji
konfigurasi Nginx sebelum reload. Template sengaja dimulai sebagai HTTP agar
Certbot dapat melakukan validasi pertama; jalankan `certbot --nginx --redirect`
segera setelah virtual host aktif agar seluruh request dialihkan ke HTTPS.

## Menjalankan stack

```bash
make docker-start ENV_FILE=.env.vps
make docker-status ENV_FILE=.env.vps
make docker-seed ENV_FILE=.env.vps
```

Endpoint minimum:

- `GET /health/live/` untuk liveness process;
- `GET /health/ready/` untuk database dan migration readiness saja; Redis, MinIO, dan worker harus diperiksa terpisah;
- `GET /metrics/` untuk metrik HTTP in-process dan jumlah row/status job serta umur PENDING tanpa label UUID; belum ada Grafana/Telegram stack.

## Rehearsal

Jalankan primary scenario tiga kali melalui worker dan private storage:

```bash
make docker-smoke ENV_FILE=.env.vps
```

Setiap pengulangan smoke membuat run/Bid/dokumen baru tanpa reset otomatis.
Smoke harus menghasilkan purchase `Rp663.000.000`, Bid `Rp780.000.000`,
dan PDF yang lolos verifikasi checksum.

## Reset aman

Reset hanya berjalan bila `APP_ENV=demo` dan confirmation token tepat.
Command menargetkan akun `demo-admin`, `demo-staff`, `demo-manager`,
Product `PUMP-001`, Supplier `SUP-A..C`, Offer `DEMO-OFFER-A..C`,
dan `DEMO-TENDER-001` beserta workflow turunannya.

```bash
make docker-reset ENV_FILE=.env.vps
make docker-seed ENV_FILE=.env.vps
```

PostgreSQL migration history, document-number sequence tahunan, dan object di luar dataset demo tidak dihapus. Notifikasi recipient demo dan audit actor/entity demo ikut direset. Reset bukan pembersih orphan bucket umum.

## Backup

```bash
make docker-backup ENV_FILE=.env.vps
```

Artefak berada di `backups/demo-<UTC>/` dan berisi dump PostgreSQL,
mirror current objects seluruh bucket MinIO, commit release, dan migration state.
Script tidak membekukan mutation/job, mengenkripsi, mengirim off-host,
atau menyalin seluruh riwayat object versions secara otomatis. Direktori backup
tidak di-commit. Salin dan enkripsi artefak di media terpisah sesuai
kebijakan operator.

Restore wajib dilakukan pada environment terisolasi. Verifikasi migration,
jalankan `/health/ready/`, cocokkan checksum FinalDocument, lalu jalankan
`smoke_demo` sebelum target dianggap pulih.

## Shutdown dan troubleshooting

```bash
make docker-logs ENV_FILE=.env.vps
make docker-stop ENV_FILE=.env.vps
```

Jika job tertahan, periksa worker sesuai queue dan biarkan reconciliation
memublikasikan ulang record PENDING. Optimization RUNNING stale belum
dipulihkan otomatis; document RUNNING stale diperiksa melalui object key
setelah hard timeout + grace. Pada finalization pertama Bid tetap `SIGNED`
ketika rendering gagal. Pada regeneration Bid tetap `FINALIZED` dan PDF
lama tersedia; jangan mengubah status secara manual. Staff dapat meminta
pembuatan dokumen lagi setelah job terminal untuk job/version baru.

Untuk Compose HTTP lokal gunakan `.env` yang berasal dari `.env.example`, lalu
jalankan target `docker-*` tanpa override. `compose.local.yaml` mengganti
endpoint host dengan hostname service Compose, sehingga file yang sama juga
dapat digunakan oleh development host melalui `make start`. Prosedur lengkap ada di
[Demo Runbook](11-demo-runbook.md).
