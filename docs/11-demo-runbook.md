# Demo Runbook

## Medical Procurement Bid Optimizer

> Status: Prosedur operasi demo MVP  
> Lingkungan: Single VPS Docker Compose, best-effort  
> Terakhir diperbarui: 11 September 2026

---

## 1. Tujuan dan Batas

Runbook ini digunakan untuk menyiapkan, memverifikasi, menjalankan, memulihkan, dan menutup lingkungan demo. Ini bukan runbook production dan tidak menetapkan SLA/RPO/RTO.

Command di bawah adalah kontrak target implementasi. Jika wrapper seperti `make` atau script deployment belum tersedia, command tersebut harus dibuat pada milestone M6 sebelum rehearsal final.

---

## 2. Komponen

| Service | Wajib | Persisten |
|---|:---:|:---:|
| Reverse proxy/HTTPS | Ya untuk VPS | Konfigurasi |
| Django web | Ya | Tidak |
| Scheduler/reconciliation | Ya | Tidak |
| Optimization worker | Ya | Tidak |
| Document worker | Ya | Tidak |
| PostgreSQL | Ya | Ya |
| Redis broker | Ya | Tidak canonical |
| MinIO private storage | Ya | Ya |
| OTel/Prometheus/Grafana | Direkomendasikan | Metrics sesuai retention demo |

Hanya reverse proxy membuka port publik. PostgreSQL, Redis, dan MinIO berada pada private Compose network.

---

## 3. Required Inputs

Operator harus memiliki:

- release commit/tag dan image version yang akan didemokan;
- file environment pada VPS dengan permission minimum;
- credential Admin, Staff, dan Manager melalui kanal aman;
- akses SSH/VPS dan akses backup sesuai kewenangan;
- domain/TLS yang valid bila memakai VPS;
- salinan runbook dan demo scenario;
- waktu maintenance di luar sesi demo.

Jangan menempelkan secret ke chat, ticket publik, screenshot, shell history, atau dokumen ini.

---

## 4. Environment Safety

Sebelum migration, reset, restore, atau seed:

1. verifikasi hostname dan environment label;
2. pastikan `APP_ENV=demo`;
3. pastikan database dan bucket menunjuk target demo;
4. pastikan tidak ada production endpoint/credential;
5. catat release dan backup terakhir.

`reset_demo_data` wajib menolak berjalan bila environment bukan demo dan mewajibkan token konfirmasi eksplisit `DEMO_ONLY`. Reset tidak dijalankan saat audiens menggunakan aplikasi.

---

## 5. Initial Setup atau Release

### 5.1 Preflight Source

```bash
git status --short
docker compose config --quiet
docker compose build
```

Working tree untuk release harus diketahui. Jangan membuang perubahan lokal secara destruktif. Image yang diuji harus sama dengan image yang dijalankan saat demo.

### 5.2 Start Infrastructure

```bash
docker compose up -d postgres redis minio
docker compose ps
```

Tunggu health check service, lalu jalankan migration dari image web:

```bash
docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run
```

### 5.3 Seed

Target command:

```bash
docker compose run --rm web python manage.py seed_demo
```

Command harus idempotent dan menghasilkan/memverifikasi golden dataset pada `08-demo-implementation-plan.md`. Password berasal dari environment atau output one-time yang tidak masuk log permanen.

### 5.4 Start Application

```bash
docker compose up -d web scheduler worker-optimization worker-documents
docker compose ps
```

Jika observability dipakai:

```bash
docker compose up -d otel-collector prometheus grafana
```

---

## 6. Release Verification

### 6.1 Automated Checks

Pada CI atau environment test yang sesuai:

```bash
python manage.py test
python manage.py check --deploy --settings=config.settings.demo
```

Jangan menjalankan destructive test suite terhadap database demo yang berisi rehearsal record.

### 6.2 Health

Verifikasi:

- `/health/live/` sukses;
- `/health/ready/` sukses;
- web dapat membaca PostgreSQL;
- kedua worker memiliki heartbeat dan mengonsumsi queue yang benar;
- scheduler aktif;
- MinIO bucket privat dapat ditulis/dibaca aplikasi;
- disk masih memiliki ruang yang memadai;
- waktu server tersinkronisasi.

### 6.3 Functional Smoke Test

1. Login sebagai Staff.
2. Buka Tender canonical.
3. Jalankan optimizer smoke atau lihat run terbaru dari build sama.
4. Pastikan rank 1 Rp663 juta.
5. Buat Bid margin 15% dan pastikan Rp780 juta/feasible.
6. Approve/sign menggunakan Manager.
7. Finalize dan download PDF.
8. Verifikasi PDF dapat dibuka dan checksum metadata tersedia.

Setelah smoke test, reset ke pre-demo state atau gunakan dataset khusus rehearsal yang jelas.

---

## 7. Demo-Day Timeline

### T-24 Jam

- freeze release candidate;
- jalankan seluruh `09-demo-test-plan.md`;
- buat backup PostgreSQL dan MinIO;
- rehearsal primary flow dan fallback;
- cek TLS, disk, memory, dan alert;
- siapkan PDF/run cadangan dari release yang sama.

### T-60 Menit

- verifikasi VPS dan network;
- cek `docker compose ps`;
- cek worker heartbeat, queue depth, oldest PENDING job;
- cek MinIO dan PostgreSQL;
- reset/seed data demo jika diperlukan;
- buka browser profile Staff dan Manager secara terpisah.

### T-15 Menit

- hentikan perubahan/deployment;
- pastikan tidak ada active run/job yang tidak diharapkan;
- cek zoom/proyektor;
- tutup tab admin, console, log, dan terminal sensitif;
- pastikan presenter mengikuti `10-demo-scenario.md`.

### Setelah Demo

- catat outcome dan incident;
- simpan audit/screenshot yang memang diizinkan;
- backup bila data demo perlu dipertahankan;
- revoke credential sementara;
- matikan environment bila tidak perlu aktif.

---

## 8. Reset Demo Data

Target command:

```bash
docker compose run --rm web python manage.py reset_demo_data --confirm DEMO_ONLY
docker compose run --rm web python manage.py seed_demo
```

Reset command harus:

- memverifikasi `APP_ENV=demo`;
- hanya menargetkan dataset demo berdasarkan stable seed namespace;
- tidak memakai broad filesystem/database deletion;
- tidak menghapus migration history;
- tidak menghapus object di luar prefix demo;
- menulis ringkasan jumlah row/object yang dihapus;
- dapat dilanjutkan dengan seed idempotent.

Jika command belum diimplementasikan, jangan menggantinya dengan SQL ad hoc saat demo. Gunakan restore database/bucket demo yang sudah diuji.

---

## 9. Backup dan Restore

### 9.1 Backup

Backup yang perlu dipasangkan:

- PostgreSQL dump;
- MinIO objects/version metadata untuk prefix demo;
- release/image version dan migration state.

Backup harus terenkripsi, disimpan di luar VPS bila perlu bertahan dari kehilangan host, dan tidak mencatat secret di filename/log.

### 9.2 Restore Verification

Restore dianggap berhasil bila:

- migration state cocok dengan image;
- user dan Tender canonical tersedia;
- FinalDocument row menunjuk object yang tersedia;
- size dan SHA-256 cocok;
- PDF dapat diunduh melalui authorization check;
- tidak ada job stale yang langsung membuat duplicate outcome.

Restore selalu direhearsal pada target terisolasi sebelum dianggap sebagai fallback demo.

---

## 10. Troubleshooting

| Gejala | Pemeriksaan | Tindakan aman |
|---|---|---|
| Web tidak ready | PostgreSQL health, migration, settings | Pulihkan dependency; restart web setelah penyebab jelas |
| Login gagal semua user | DB, account active, cookie/TLS, clock | Verifikasi account dan session config; jangan reset password massal |
| Optimization PENDING lama | Redis, optimization worker, queue, scheduler | Pastikan worker sehat; biarkan reconciliation republish |
| Optimization FAILED | safe code dan diagnostic reference | Perbaiki input atau dependency; business retry membuat run baru |
| Result count 0 | eligible offer/capacity/validity | Gunakan manual valid result atau koreksi data melalui UI |
| PDF PENDING lama | document worker dan queue | Pulihkan worker; reconciliation republish |
| PDF FAILED | renderer, asset, MinIO, disk | Retry transient; Bid harus tetap SIGNED |
| PDF row ada, object hilang | MinIO/object metadata/checksum | Treat as integrity failure; gunakan backup, jangan tandai sukses manual |
| 403 pada action benar | role, actor, status, object relationship | Koreksi session/data; jangan bypass permission |
| Angka berbeda | calculation/algorithm version dan seed | Hentikan primary demo jika correctness belum dapat dijelaskan |
| Disk hampir penuh | volume PostgreSQL/MinIO/log | Hentikan job baru; lakukan cleanup hanya terhadap target terverifikasi |

### Useful Read-Only Checks

```bash
docker compose ps
docker compose logs --tail=200 web
docker compose logs --tail=200 worker-optimization
docker compose logs --tail=200 worker-documents
docker compose exec web python manage.py showmigrations
```

Jangan menampilkan log ke audiens. Periksa dan redaksi output sebelum membagikannya karena log dapat membawa identifier bisnis.

---

## 11. Incident Decision

| Kondisi | Keputusan |
|---|---|
| Angka, permission, atau historical integrity salah | Stop demo flow; gunakan penjelasan/fallback yang sudah diverifikasi |
| Worker transient gagal tetapi record aman | Tunjukkan failure handling lalu gunakan prepared record |
| PDF tidak dapat diverifikasi | Jangan menyatakan proposal FINALIZED |
| Credential/secret diduga terekspos | Hentikan screen sharing terkait, rotate credential, catat incident |
| Data tidak dikenal atau environment salah | Jangan reset/migrate; identifikasi target terlebih dahulu |

---

## 12. Rollback Release

Rollback hanya dilakukan ke image yang kompatibel dengan migration saat ini. Jangan menjalankan reverse migration secara spontan pada demo environment yang berisi data.

Urutan aman:

1. hentikan mutation/background worker bila diperlukan;
2. catat image dan migration state;
3. verifikasi compatibility release sebelumnya;
4. deploy image sebelumnya;
5. jalankan health dan functional smoke check;
6. lanjutkan hanya jika snapshot/document compatibility terbukti.

Jika schema tidak backward compatible, gunakan restore pasangan PostgreSQL/MinIO yang dibuat sebelum release pada environment terisolasi.

---

## 13. Ready-to-Demo Checklist

- [ ] Release/image dan commit tercatat.
- [ ] Migration tidak tertunda.
- [ ] Seluruh P0 automated test lulus.
- [ ] Web, scheduler, workers, PostgreSQL, Redis, dan MinIO sehat.
- [ ] Golden dataset menghasilkan Rp663 juta dan Bid Rp780 juta.
- [ ] Staff dan Manager login melalui browser profile terpisah.
- [ ] Optimizer dan PDF smoke test berhasil.
- [ ] Queue tidak memiliki stale job.
- [ ] Backup terbaru tersedia dan restore pernah diuji.
- [ ] Prepared run/PDF fallback berasal dari release dan data yang sama.
- [ ] Tidak ada secret pada tab, terminal, slide, atau dokumen yang ditampilkan.
- [ ] Presenter sudah rehearsal primary flow.

