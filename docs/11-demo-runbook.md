# Demo Runbook

## Medical Procurement Bid Optimizer

> Status: Dokumentasi implementasi saat ini<br>
> Terakhir diperbarui: 15 September 2026

## 1. Lingkungan dan komponen

Runbook menggunakan command yang sudah ada. Compose demo menjalankan PostgreSQL, Redis, MinIO/bucket init, Django web, optimization worker, document worker, dan Celery beat. Nginx HTTPS disiapkan di host melalui konfigurasi contoh; bukan container Compose. Monitoring eksternal tidak diperlukan oleh command ini dan belum disediakan repository.

Operasi lokal menggunakan `.env` serta `scripts/dev-services.sh`; operasi Compose menggunakan `ENV_FILE` default `.env.vps`. Jangan mencampur hostname layanan Compose (`postgres`, `redis`, `minio`) dengan endpoint lokal host.

## 2. Setup development host

```bash
uv sync --frozen
cp .env.example .env
```

Isi connection/credential serta tiga DEMO password pada `.env`. PostgreSQL dan Redis harus sudah aktif di host; database local/test serta role akses disiapkan operator. `make start` memeriksa dependency host, membuat/menjalankan container `procurement-minio`, memastikan bucket, menjalankan migration, kemudian memulai web/workers/beat.

```bash
make start
make status
uv run --env-file .env python manage.py seed_demo
```

Web lokal: `http://127.0.0.1:8000`. Log/PID/scheduler file berada di `.run/`. `make stop` menghentikan process yang dikelolanya dan container MinIO lokal; PostgreSQL/Redis host tetap berjalan. `make start` tidak otomatis menjalankan seed.

Untuk smoke/reset pada local settings, command tetap memerlukan `APP_ENV=demo`. Label ini harus sengaja dikonfigurasi untuk dataset demo; `.env.example` tidak mengaktifkannya secara default.

## 3. Setup Compose HTTP lokal

```bash
cp .env.demo.example .env.demo
```

Isi seluruh placeholder/credential/password. Example ini menonaktifkan secure cookies/redirect agar demo HTTP loopback dapat berjalan; gunakan example VPS untuk deployment HTTPS.

```bash
make docker-start ENV_FILE=.env.demo
make docker-status ENV_FILE=.env.demo
make docker-seed ENV_FILE=.env.demo
make docker-smoke ENV_FILE=.env.demo
```

Seluruh target `docker-*` menerima `ENV_FILE`; gunakan file yang sama pada start, status, seed, reset, smoke, backup, dan stop.

## 4. Setup VPS HTTPS

```bash
cp .env.vps.example .env.vps
chmod 600 .env.vps
```

Isi domain, secret, database URL, broker/cache, MinIO, dan tiga DEMO password. `MINIO_ROOT_USER/PASSWORD` harus sesuai `MINIO_ACCESS_KEY/SECRET_KEY` pada konfigurasi demo ini. Contoh memakai TLS di Nginx dan `MINIO_SECURE=false` untuk koneksi MinIO internal Compose.

```bash
make docker-preflight-vps
make docker-start
make docker-status
make docker-seed
```

`docker-start` menjalankan Compose config preflight, bukan otomatis VPS security preflight. Jalankan `docker-preflight-vps` terpisah untuk VPS: script memeriksa required values, placeholder, APP_ENV/settings, HTTPS base/origins, secure flags, panjang secret/password, loopback bind, HSTS, dan permission file.

Sesuaikan `deploy/nginx-procurement.conf.example` dengan domain dan `WEB_HOST_PORT` (example VPS 8002). Konfigurasi awal HTTP mendukung certificate issuance; terbitkan TLS dan aktifkan HTTPS redirect sebelum akses publik. `config.settings.demo` mempercayai forwarded HTTPS header dari proxy; web harus tetap dibatasi loopback sesuai example.

Web container otomatis migrate dan collectstatic sebelum Gunicorn. `minio-init` membuat bucket, tanpa mengaktifkan object versioning. Dockerfile memasang dependency renderer/font, dan worker/scheduler menunggu health web. Stack tidak menyediakan backup/restore otomatis atau high availability.

## 5. Verifikasi release

Automated checks pada test environment dijelaskan dalam [09 — Test Plan](09-demo-test-plan.md). Pada container demo:

```bash
docker compose --env-file .env.vps exec web python manage.py check --deploy
docker compose --env-file .env.vps exec web python manage.py showmigrations
docker compose --env-file .env.vps exec web python manage.py makemigrations --check --dry-run
make docker-smoke
```

`make docker-smoke` menjalankan tiga service flow dan membuat record baru pada setiap pengulangan. Seed telah menyediakan manual VALID A60+B40 sebagai alternatif, tanpa selection atau PDF otomatis.

Endpoint:

- `/health/live/`: process liveness.
- `/health/ready/`: PostgreSQL connection dan migration readiness saja.
- `/metrics/`: HTTP in-process metrics, DB row count per job status, dan umur PENDING tertua.

Periksa Redis/MinIO/worker/scheduler secara terpisah melalui status/log dan smoke. Health web sukses tidak membuktikan semua dependency tersebut sehat. Tidak ada operational dashboard atau Telegram alert yang otomatis berjalan.

## 6. Seed dan reset

`seed_demo` wajib tiga password env dan tidak mencetak/generate password. User canonical dibuat/diverifikasi/diperbarui; business data diverifikasi dan mismatch ditolak. Offer canonical berlaku 2026–2030. Command seed sendiri tidak membatasi APP_ENV; operator harus memilih target dengan benar.

Reset/smoke memerlukan `APP_ENV=demo`. Reset memerlukan token tepat:

```bash
make docker-reset
make docker-seed
```

Reset menargetkan user `demo-admin/staff/manager`, Product `PUMP-001`, suppliers `SUP-A..C`, offers `DEMO-OFFER-A..C`, Tender `DEMO-TENDER-001`, serta workflow turunannya. Notifikasi recipient demo dan audit actor/entity demo juga dihapus. Penghapusan DB dilakukan langsung untuk melewati immutable guards pada command khusus ini, lalu object signature/PDF yang tercatat dibersihkan.

Migration history, document-number sequence tahunan, data unrelated, dan object yang tidak tercatat pada dataset tersebut tidak direset. Reset bukan scanner orphan. Bila DB sudah terhapus tetapi object cleanup gagal, command mengembalikan error; periksa MinIO dan object tersisa sebelum rehearsal berikutnya. Jangan reset saat worker masih memproses dataset demo.

## 7. Backup dan restore

```bash
make docker-backup
```

Script hanya menerima environment file dengan `APP_ENV=demo`. Output `backups/demo-<UTC>/` berisi `postgres.dump` (pg_dump custom format), `minio/` (mirror current objects seluruh bucket), `release-commit.txt`, dan `migrations.txt`.

Backup belum otomatis terenkripsi, dikirim off-host, atau mengambil seluruh riwayat object versions. DB dump dan object mirror berjalan berurutan, tanpa coordinated snapshot/freeze; jadwalkan saat mutation/jobs berhenti jika membutuhkan pasangan data stabil. Operator menyalin/enkripsi artefak sesuai kebutuhan. Tidak ada restore script/Make target; restore PostgreSQL dan MinIO harus diuji di environment terisolasi, dengan release/migrations yang sesuai.

Verifikasi restore: DB ready, FinalDocument/signature object ada, size/SHA-256 sesuai, authorized download berhasil, dan tidak ada job stale/duplikasi. `smoke_demo` dapat dipakai untuk mengecek alur baru setelah restore.

## 8. Troubleshooting

| Gejala | Perilaku kode dan tindakan operator |
|---|---|
| Web not ready | Periksa PostgreSQL/migration/settings serta log web |
| Login gagal | Periksa active account, username/password, cache, secure cookies/proxy; rate limit lima failure dalam window 300 detik |
| Optimization PENDING lama | Pulihkan Redis/optimization worker/scheduler; reconciliation republish PENDING setelah grace 60 detik |
| Optimization RUNNING stale | Belum ada takeover otomatis. Periksa worker/status dan gunakan prepared result atau dataset demo baru setelah diagnosis; jangan menganggap republish PENDING menyelesaikan kasus ini |
| Optimization FAILED | Lihat safe code/diagnostic reference; Staff retry membuat run baru atas input terbaru |
| COMPLETED result count 0 | Periksa eligibility/quantity; sediakan Offer yang dapat memenuhi kebutuhan atau manual result valid |
| PDF PENDING lama | Periksa document queue/worker/scheduler; reconciliation republish |
| PDF RUNNING stale | Reconciliation memeriksa uploaded object setelah 120 detik default; complete object valid atau release/republish |
| PDF FAILED | Task normal maksimal tiga attempt; pulihkan renderer/storage lalu Staff meminta dokumen lagi untuk job/version baru |
| Regeneration PDF gagal | Bid tetap FINALIZED dan versi PDF lama tetap dapat diunduh |
| PDF object hilang/corrupt | Download ditolak integrity/storage guard; pulihkan pasangan backup yang sesuai |
| 403 | Periksa role/session; hanya approving Manager boleh sign; Admin tidak boleh download bisnis |

Read-only checks:

```bash
make docker-status
docker compose --env-file .env.vps logs --tail=200 web worker-optimization worker-documents scheduler
docker compose --env-file .env.vps exec web python manage.py showmigrations
```

Jangan mengubah state Bid atau checksum secara manual untuk menyatakan job sukses. Gunakan fallback yang memang telah diverifikasi saat rehearsal.

## 9. Persiapan presentasi dan shutdown

1. Catat commit/image/migration dan jalankan checks serta smoke pada target demo.
2. Bila perlu reset setelah smoke, hentikan aktivitas dataset, reset/seed ulang, lalu siapkan prepared run/PDF melalui workflow biasa.
3. Gunakan browser Staff dan Manager terpisah; uji proyektor, keyboard, desktop/mobile, dan PDF.
4. Ikuti [10 — Demo Scenario](10-demo-scenario.md). Halaman audit timeline belum tersedia; gunakan revision/job/history metadata yang ada.
5. Backup data yang diperlukan sebelum/selepas presentasi; catat outcome dan masalah aktual.

```bash
make docker-logs
make docker-stop
```

Compose down mempertahankan named data volumes. Rollback image harus kompatibel dengan migration/snapshot saat ini; restore pasangan DB/storage di target terisolasi bila schema tidak kompatibel. Tidak ada deployment rollback automation checked-in.
