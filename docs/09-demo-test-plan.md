# Demo Test Plan

## Medical Procurement Bid Optimizer

> Status: Dokumentasi implementasi saat ini<br>
> Terakhir diperbarui: 15 September 2026

## 1. Cakupan verifikasi

Dokumen ini memetakan suite yang benar-benar tersedia dan pemeriksaan manual yang perlu dilakukan operator. Nama test merupakan bukti cakupan, bukan pernyataan bahwa seluruh acceptance scenario lama telah diotomatisasi.

## 2. Lingkungan

- Python 3.12, dependency terkunci dalam `uv.lock`, dan PostgreSQL.
- `config.settings.test` memakai `TEST_DATABASE_URL`, default `postgresql:///procurement_test`. Django membuat database test tersendiri; role PostgreSQL perlu hak membuat database tersebut.
- Celery test memakai eager execution serta memory broker/result backend.
- Test service/task memakai patch/mock publish atau storage sesuai fixture; suite renderer menghasilkan PDF nyata tetapi tidak mewajibkan MinIO live untuk semua test.
- Race tests memakai TransactionTestCase dan koneksi/thread PostgreSQL. SQLite tidak didukung oleh database URL parser.

## 3. Suite yang tersedia

| File/suite | Perilaku yang diperiksa |
|---|---|
| `apps.accounts.tests` | UUID/identity/role/constraint, forms admin, password validation, session/CSRF/logout POST, login rate limit, role navigation, admin access |
| `apps.accounts.test_services` | Mutation akun, authorization, dan audit |
| `apps.accounts.test_seed_demo` | Password env wajib, tiga akun tanpa mencetak password, canonical business data, dan seed berulang tanpa duplikasi data/audit |
| `apps.accounts.test_reset_demo` | APP_ENV/token guard, reset canonical namespace berulang, dan preservation akun unrelated |
| `apps.accounts.test_smoke_demo` | Guard environment/runs dan orchestration jumlah rehearsal; bukan live worker E2E dalam unit suite |
| `apps.catalog.tests` | Normalisasi/unique code, create/update/version/audit, inactive/reactivate Product, access dan views |
| `apps.tender.tests` | Item/Product/HPS/revision validation, snapshots, immutability, stale version, dynamic formset/multiple items, views |
| `apps.sourcing.tests` | Harga net, discount 100% ineligible, date/master eligibility, Offer correction/supersede/identity/version, views |
| `apps.sourcing.test_results` | Allocation rounding/quantity/product/capacity, validation, live inactive Offer, corrupt price snapshot, VALID immutability, customization, selection/selection race, historic display |
| `apps.optimization.test_engine` | Golden candidate, capacity shortage rejection, supplier-count tie break, dan candidate identifier independen dari urutan allocation |
| `apps.optimization.test_benchmark` | Dataset sintetis seeded, determinisme checksum, shared validation, schema report, dan guard supported workload |
| `apps.optimization.tests` | Frozen input setelah deactivation, penolakan run aktif kedua, ranked result persistence, duplicate delivery, failed/retry run, notifications, role dan status/detail views |
| `apps.bids.tests` | Golden margin/HPS pricing, selected-result requirement, create/price/submit/version, material immutability, rejection/revision, waiting/decision notifications, views |
| `apps.approval.tests` | Decision immutability dan concurrent decision race menghasilkan satu row |
| `apps.signatures.tests` | Approving Manager sign tanpa gambar, role/Manager lain ditolak, signature immutability, PNG private storage, dan signing page/confirmation flow |
| `apps.documents.tests` | SIGNED sampai completion valid, active job reuse, failure, checksum/object verification, regeneration version/number, PDF renderer/signature embedding, stale uploaded-job recovery, download authorization/security headers |
| `apps.notifications.tests` | Event deduplication, recipient-only read, unread/read toast |
| `apps.audit.tests` | Actor snapshot, system actor, correlation validation, append-only guard, actor PROTECT/revision constraint |
| `apps.core.tests` | Canonical JSON/hash dan format Rupiah/quantity/decimal |
| `config.tests` | PostgreSQL/env parsing, correlation middleware, health/metrics/JSON log formatting |

Kasus input-limit/timeout optimizer, PENDING publish recovery, repeated-product optimizer, invalid-image matrix, reset storage cleanup failure, dan document-task retry/backoff belum mempunyai test khusus dalam suite saat ini. Jangan menganggap seluruh behavior service otomatis tercakup.

Suite saat ini berisi 248 test. Benchmark waktu tidak menjadi assertion unit
test karena hasil bergantung pada mesin dan beban host.

Tidak ada generic idempotency-key replay/conflict test karena fiturnya tidak ada. Tidak ada signature-profile replacement test, general orphan scanner test, atau Grafana/Telegram E2E. Rehearsal layanan nyata tetap terpisah dari test eager/mocked.

## 4. Golden data

```text
Tender: 100 Infusion Pump, HPS Rp800.000.000
Offer A: net Rp6.300.000 × 60 = Rp378.000.000
Offer B: net Rp7.125.000 × 40 = Rp285.000.000
Purchase: Rp663.000.000
Margin: 15%
Bid: Rp780.000.000
Gross profit: Rp117.000.000
Actual margin: 15%
Max margin HPS: 17,125%
```

Harga Bid production dihitung per item/unit dengan canonical rounding; golden case ini menghasilkan nilai total tepat.

## 5. Perintah verifikasi

Dari root repository, dengan PostgreSQL test dapat diakses:

```bash
uv sync --frozen
uv run ruff check .
uv run python manage.py check --settings=config.settings.test
uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test
uv run python manage.py test --settings=config.settings.test
```

Untuk perubahan authentication/template, pemeriksaan minimum repository:

```bash
uv run python manage.py test apps.accounts.tests --settings=config.settings.test
```

Jika membutuhkan `TEST_DATABASE_URL` dari `.env`, gunakan `uv run --env-file .env` dan tetap sertakan `--settings=config.settings.test`. Target `make check` memuat `.env` dan mengikuti settings di sana; perintah eksplisit di atas memilih settings test secara pasti.

Deployment check memakai environment demo yang sudah diisi:

```bash
uv run --env-file .env.vps python manage.py check --deploy --settings=config.settings.demo
```

Check ini memeriksa settings Django; bukan pengganti HTTPS, database, queue, dan storage rehearsal pada stack target. Jika hostname layanan Compose tidak dapat dijangkau host, jalankan pemeriksaan runtime dari container.

## 6. Benchmark optimizer

Benchmark engine-only menggunakan dataset sintetis deterministik dan tidak
membaca database atau broker:

```bash
uv run python manage.py benchmark_optimizer \
    --items 100 \
    --offers-per-item 50 \
    --seed 42 \
    --warmups 2 \
    --runs 10
```

Gunakan `--format json` untuk artefak machine-readable. Report mencatat versi
algoritma/runtime, commit dan status working tree, parameter workload, durasi
per run, median, p95, standard deviation, coefficient of variation, peak
alokasi Python, jumlah skip-vector yang dieksplorasi, kandidat ditemukan dan
ditolak, jumlah result, checksum, serta status shared validation.

Durasi hanya mengukur engine. Shared validation dijalankan setelah timer.
Pengukuran memori memakai `tracemalloc` dalam run terpisah dan dilabeli sebagai
peak Python allocation, bukan total process RSS. Batas command mengikuti
supported workload aplikasi: maksimal 100 item dan 50 Offer per item.

## 7. Rehearsal layanan nyata

Pada Compose demo yang sudah sehat dan di-seed:

```bash
make docker-smoke
```

Target menjalankan `smoke_demo --runs 3`: optimization, select, Bid margin 15%, submit, approve, sign tanpa gambar, finalization, dan authorized download. Setiap pengulangan menambah record baru tanpa reset otomatis. Command menunggu status DB, maksimum default 90 detik untuk optimization dan 90 detik untuk document job.

Periksa juga melalui UI:

1. Login dengan browser Staff/Manager terpisah; lihat role navigation.
2. Optimization rank 1 A60+B40, purchase Rp663 juta; pilih result secara eksplisit.
3. Margin 15% menghasilkan Bid Rp780 juta; margin 18% tersimpan sebagai DRAFT infeasible dan submission ditolak.
4. Manager reject dengan reason; Staff menerima notifikasi dan membuat revision baru dengan margin kembali.
5. Approving Manager sign, termasuk uji gambar opsional; Manager lain ditolak.
6. Staff finalize; lihat polling, download PDF dan versi berikutnya dari UI.
7. Pulihkan broker/worker yang berhenti dan periksa PENDING reconciliation. Untuk optimization RUNNING stale, jangan mengasumsikan recovery otomatis.
8. Periksa regeneration gagal tetap mempertahankan PDF final lama; uji restore backup di environment terisolasi.

## 8. Pemeriksaan visual/manual

- Login normal/error, dashboard authenticated, profil dengan nama/email panjang.
- Desktop/mobile sampai 320px, keyboard navigation dan visible focus.
- Form label/error, empty/loading/error states, angka Rupiah, long hash/name wrapping.
- PDF A4, pricing, nomor/revision/version, signer, validity, dan signature image bila dipakai.
- Permission salah ditolak server dan response tidak membocorkan detail sensitif.

Pemeriksaan manual ini belum diotomatisasi sebagai browser test dalam repository. Catat commit/image, migration state, waktu, executor, hasil, serta defect. Masalah angka, authorization, histori, atau integrity PDF perlu diselesaikan sebelum memakai build untuk demo.
