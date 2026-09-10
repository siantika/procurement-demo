# Technical Design

## Medical Procurement Bid Optimizer

> Status: Baseline implementasi demo MVP  
> Target: Django modular monolith, PostgreSQL, Celery, Redis, dan MinIO  
> Terakhir diperbarui: 11 September 2026

---

## 1. Tujuan

Dokumen ini menerjemahkan Product Overview, Business Rules, Use Cases, Domain Model, System Architecture, dan Data Model menjadi rancangan implementasi yang dapat langsung diikuti oleh developer.

Dokumen ini menetapkan:

- struktur source code dan dependency antarmodul;
- batas tanggung jawab view, form, application service, domain policy, model, task, dan adapter;
- kontrak command serta query utama;
- route HTTP untuk server-rendered UI;
- transaction boundary, concurrency, idempotency, snapshot, dan audit;
- implementasi kalkulasi procurement, pricing, optimizer, approval, signature, dan finalization;
- strategi error handling, observability, security, dan automated test.

Dokumen ini tidak mengubah kebutuhan bisnis. Jika detail di dokumen ini bertentangan dengan sumber yang lebih tinggi, urutan prioritas pada bagian 2 berlaku.

---

## 2. Sumber dan Prioritas Keputusan

Implementasi mengikuti sumber berikut:

1. `02-business-rules.md` untuk formula, invariant, authorization, dan lifecycle;
2. `03-use-cases.md` untuk actor, precondition, flow, dan outcome;
3. `05-system-architecture.md` untuk bentuk sistem, transaction, asynchronous processing, security, dan deployment;
4. `06-data-model.md` serta Django migrations untuk schema, constraint, index, snapshot, dan retention;
5. `04-domain-model.md` untuk aggregate, entity, value object, dan domain service;
6. `01-product-overview.md` untuk tujuan produk dan batas MVP.

Setelah implementation dimulai, Django migration adalah schema database executable. `schema.dbml` tetap digunakan sebagai visualisasi dan harus diperbarui ketika migration mengubah desain data.

Keputusan implementasi baru dalam dokumen ini adalah:

- struktur package internal setiap Django app;
- kontrak service, command, query, dan error;
- route dan pola HTTP server-rendered;
- versi awal policy kalkulasi dan algoritma;
- pola test dan quality gate.

Perubahan yang memengaruhi business rule, lifecycle, ownership data, atau deployment topology harus dimulai dengan pembaruan dokumen sumber terkait, bukan hanya perubahan kode.

---

## 3. Target Runtime dan Konfigurasi

### 3.1 Runtime Components

| Komponen | Target | Fungsi |
|---|---|---|
| Python | Versi yang didukung release Django yang dipilih | Runtime web dan worker |
| Django | 6.x | Web framework, auth, form, ORM, migration, admin |
| PostgreSQL | Release supported/stable | Source of truth bisnis |
| Celery | Release compatible dengan Django/Python | Background task |
| Redis | Release supported/stable | Celery broker; bukan source of truth |
| MinIO | Release pinned pada deployment | Private object storage |
| PDF renderer | HTML/CSS-to-PDF library yang dipin | Render template A4 tanpa remote resource |

Seluruh dependency production harus dipin menggunakan lock file. Upgrade dependency dilakukan melalui pull request tersendiri dan wajib menjalankan unit, integration, migration, dan security checks.

### 3.2 Environment

Settings dipisahkan secara eksplisit:

```text
config/settings/
  __init__.py
  base.py
  local.py
  test.py
  demo.py
```

Konfigurasi dibaca dari environment. Nilai minimum:

```text
DJANGO_SETTINGS_MODULE
DJANGO_SECRET_KEY
DJANGO_DEBUG
DJANGO_ALLOWED_HOSTS
DJANGO_CSRF_TRUSTED_ORIGINS
DATABASE_URL
CELERY_BROKER_URL
MINIO_ENDPOINT
MINIO_ACCESS_KEY
MINIO_SECRET_KEY
MINIO_BUCKET
MINIO_SECURE
APP_BASE_URL
APP_TIME_ZONE=Asia/Jakarta
OPTIMIZER_MAX_ITEMS=100
OPTIMIZER_MAX_OFFERS_PER_ITEM=50
OPTIMIZER_MAX_RESULTS=20
OPTIMIZER_SOFT_TIME_LIMIT_SECONDS=240
OPTIMIZER_HARD_TIME_LIMIT_SECONDS=300
```

Secret, password demo, signed URL, dan credential storage tidak memiliki fallback yang aman untuk production dan tidak boleh disimpan di repository.

### 3.3 Time, Locale, dan Currency

- Waktu disimpan sebagai UTC dengan `USE_TZ=True`.
- Waktu ditampilkan dalam `Asia/Jakarta` untuk demo.
- Timestamp bisnis selalu berasal dari server melalui satu injected clock; browser time tidak dipercaya.
- Mata uang MVP selalu `IDR` dan tetap disimpan eksplisit.
- Nilai uang, quantity, dan percentage diterima sebagai `Decimal`; `float` dilarang pada domain policy dan snapshot.
- Format Rupiah hanya berada di presentation layer dan tidak digunakan kembali sebagai input kalkulasi.

---

## 4. Struktur Source Code

### 4.1 Target Layout

```text
apps/
  accounts/
  catalog/
  tender/
  sourcing/
  optimization/
  bids/
  approval/
  signatures/
  documents/
  notifications/
  audit/
  dashboard/
  core/
    domain/
    infrastructure/
    management/commands/
config/
  settings/
  urls.py
  celery.py
templates/
static/
tests/
docs/
```

Setiap business app menggunakan struktur berikut hanya bila file tersebut dibutuhkan:

```text
apps/<module>/
  models.py
  choices.py
  commands.py
  services.py
  policies.py
  selectors.py
  forms.py
  views.py
  urls.py
  tasks.py
  admin.py
  exceptions.py
  migrations/
  tests/
```

Tidak dibuat layer repository generik di atas Django ORM. Query write berada di application service pemilik aggregate; query read yang reusable berada di `selectors.py`.

### 4.2 Responsibility per Layer

| Layer | Boleh melakukan | Tidak boleh melakukan |
|---|---|---|
| View | Parse HTTP, panggil form/service, pilih response, set message | Menulis model langsung, menghitung harga, menentukan transition |
| Form | Normalisasi input, validasi field dan error yang ramah user | Menentukan authorization final atau melakukan write lintas aggregate |
| Application service | Authorization, transaction, lock, invariant, write, snapshot, audit, task scheduling | Bergantung pada template atau request HTTP |
| Domain policy | Kalkulasi dan keputusan deterministic dari explicit input | Query database, membaca request, mengirim task, mengakses storage |
| Selector | Query read teroptimasi dan object visibility | Mengubah state |
| Model | Struktur data, local invariant, constraint, helper kecil | Mengorkestrasi use case lintas aggregate |
| Task | Claim job, panggil service/engine, mapping retry | Menduplikasi business rule |
| Adapter | Integrasi queue, storage, renderer, clock | Menentukan business transition |

### 4.3 Dependency Direction

```text
views/forms/tasks
       |
       v
application services -----> selectors / Django ORM
       |
       v
domain policies ----------> value objects
       |
       v
infrastructure ports <----- concrete adapters
```

Aturan dependency:

- `optimization` boleh memakai contract/policy dari `tender` dan `sourcing`;
- `bids` boleh membaca snapshot tender dan result yang dipilih;
- `approval`, `signatures`, dan `documents` memanggil lifecycle service milik `bids`;
- `notifications` dan `audit` menerima fakta bisnis, bukan memutuskan outcome sumber;
- `dashboard` hanya memakai selectors;
- import melingkar antarmodul dilarang;
- task menerima identifier sederhana, bukan serialized Django model.

---

## 5. Shared Technical Contracts

### 5.1 Command Object

Setiap write use case menerima immutable command object. Contoh:

```python
@dataclass(frozen=True)
class SubmitBidCommand:
    bid_revision_id: UUID
    expected_version: int
    idempotency_key: str
    actor_id: UUID
    correlation_id: str
```

Command membawa seluruh konteks yang diperlukan service dan tidak membawa `HttpRequest`.

### 5.2 Result Object

Service mengembalikan result minimal:

```python
@dataclass(frozen=True)
class CommandResult:
    entity_id: UUID
    version: int | None = None
    status: str | None = None
    created: bool = False
```

Service tidak mengembalikan response HTTP, template, atau message framework object.

### 5.3 Domain Errors

| Error | Makna | HTTP outcome |
|---|---|---|
| `AuthenticationRequired` | Session tidak valid | Redirect login / 401 untuk endpoint machine |
| `PermissionDenied` | Actor tidak memiliki capability/object permission | 403 |
| `EntityNotFound` | Entity tidak ada atau sengaja disamarkan karena object visibility | 404 |
| `ValidationError` | Input atau invariant bisnis tidak valid | Form error / 422 untuk JSON |
| `InvalidTransition` | Status asal tidak mengizinkan command | 409 |
| `ConcurrencyConflict` | `expected_version` stale atau lock conflict | 409 |
| `IdempotencyConflict` | Key yang sama dipakai dengan payload berbeda | 409 |
| `DependencyUnavailable` | Queue/storage/renderer sementara tidak tersedia | 503 atau status job FAILED |

Unexpected exception tidak ditampilkan ke user. UI menerima safe message dan `diagnostic_reference`; detail exception hanya masuk structured log.

### 5.4 Correlation ID

Middleware menerima header correlation ID yang valid atau membuat UUID baru. Nilai diteruskan ke command, audit event, task header, dan structured log, lalu dikembalikan pada response. Panjang dan karakter dibatasi agar aman untuk log.

---

## 6. Authentication dan Authorization

### 6.1 User Model

- Custom `accounts.User` dengan UUID primary key harus dibuat sebelum migration bisnis pertama.
- `AUTH_USER_MODEL` tidak boleh diubah setelah tabel bisnis bergantung padanya.
- Role disimpan sebagai `TextChoices`: `ADMIN`, `PROCUREMENT_STAFF`, atau `MANAGER`.
- `is_superuser` tidak menggantikan role dalam audit; tindakan superuser tetap mencatat actor sebenarnya.
- User administration dilakukan melalui Django Admin oleh Admin.

### 6.2 Enforcement

Setiap write service memanggil policy authorization walaupun view sudah memakai decorator/mixin. Pengecekan mencakup:

1. account aktif;
2. capability berdasarkan role;
3. visibility/relationship object;
4. status entity;
5. aturan khusus, misalnya signer harus sama dengan approving Manager.

Role matrix canonical:

| Operation | Admin | Procurement Staff | Manager |
|---|:---:|:---:|:---:|
| User, Product, Supplier administration | Ya | Tidak | Tidak |
| Supplier Offer dan Tender | Tidak | Ya | Tidak |
| Result, optimizer, selection, Bid draft/pricing/submission | Tidak | Ya | Tidak |
| Approve/reject | Tidak | Tidak | Ya |
| Sign approved revision | Tidak | Tidak | Approver yang sama |
| Finalize | Tidak | Ya | Tidak |
| Download final PDF | Tidak | Ya | Ya |

### 6.3 Session Security

- Seluruh state-changing route menggunakan `POST` dan CSRF protection.
- Cookie production menggunakan `Secure`, `HttpOnly`, dan `SameSite=Lax` kecuali ada alasan yang terdokumentasi.
- Login di-rate-limit berdasarkan kombinasi identity dan source address tanpa menyimpan credential.
- Logout menggunakan `POST`.
- Redirect target dari query string harus lolos allowed-host validation.

---

## 7. Model dan Persistence Implementation

### 7.1 Base Conventions

- Semua identity bisnis menggunakan UUID v4.
- Nama tabel eksplisit mengikuti `06-data-model.md`.
- Controlled value menggunakan `TextChoices` dan `CheckConstraint`.
- `created_at` memakai `auto_now_add` atau server-side default yang konsisten; `updated_at` hanya untuk mutable row.
- Foreign key lintas aggregate memakai `PROTECT`; `CASCADE` hanya untuk child yang tidak bermakna tanpa aggregate root.
- Default manager tidak menyembunyikan row historis. Selector aktif harus eksplisit.
- Hard delete untuk historical business entity tidak diekspos melalui application service.

### 7.2 Database Constraints

Migration wajib mengimplementasikan constraint pada Data Model, terutama:

- case-insensitive uniqueness untuk username, email, product code, dan supplier code;
- positive price/quantity dan bounded percentage;
- unique line number per revision/result;
- satu active OptimizationRun per Tender Request melalui partial unique constraint;
- satu result item per pasangan result dan tender item;
- unique `(optimization_run_id, rank)`;
- unique decision dan signature per Bid revision;
- unique document version per Bid revision;
- unique notification `(recipient_id, source_event_id, type)`;
- unique idempotency `(actor_id, operation, idempotency_key)`.

Constraint database adalah pertahanan terakhir. Application service tetap menghasilkan error bisnis yang dapat dipahami sebelum constraint dilanggar. `IntegrityError` akibat race diterjemahkan menjadi `ConcurrencyConflict` atau outcome idempotent.

### 7.3 Immutable Rows

Tender revision, VALID Procurement Result beserta child, ApprovalDecision, Signature, FinalDocument, dan AuditEvent bersifat immutable setelah transaction pembuatannya selesai.

Immutability ditegakkan melalui:

- tidak menyediakan update/delete service;
- admin read-only atau tidak diregistrasikan;
- model guard untuk perubahan melalui application path;
- database trigger/privilege append-only pada deployment production bila dibutuhkan;
- automated test yang mencoba mutation dan deletion.

Query historis tidak boleh join ke current master untuk mengganti nilai snapshot. Foreign key digunakan untuk lineage, sedangkan tampilan historis menggunakan snapshot.

### 7.4 Migration Order

Urutan implementasi migration:

1. accounts;
2. catalog;
3. tender dan Supplier Offer;
4. optimization dan Procurement Result;
5. Bid Proposal;
6. approval dan signatures;
7. documents;
8. notifications, audit, dan idempotency;
9. partial/functional index dan append-only hardening.

Migration data harus deterministic, dapat diobservasi, dan tidak mengambil data dari network.

---

## 8. Snapshot, Canonical Serialization, dan Audit

### 8.1 Snapshot Builder

Snapshot dibuat oleh dedicated builder per schema:

```text
TenderRevisionSnapshotBuilder
OptimizationInputSnapshotBuilder
ProcurementResultSnapshotBuilder
BidSubmissionSnapshotBuilder
FinalizationSnapshotBuilder
```

Builder menerima explicit data yang sudah dibaca di dalam transaction. Builder tidak melakukan hidden query setelah snapshot mulai dibentuk.

### 8.2 Canonical JSON

Utility `core.domain.canonical_json` menerapkan:

- UTF-8;
- object key lexicographic;
- compact separators;
- UUID lowercase string;
- timestamp ISO-8601 UTC dengan suffix `Z`;
- Decimal sebagai string dengan scale canonical;
- array sesuai explicit `line_number`;
- null dipertahankan bila field bagian dari schema;
- SHA-256 hex lowercase.

`captured_at` berada dalam snapshot yang disimpan. Hash harus selalu dihitung dari representasi canonical yang sama dan tidak dari output pretty-printed.

### 8.3 Audit Writer

Setiap state-changing service menulis `AuditEvent` dalam database transaction yang sama dengan business change. Metadata hanya berisi identifier atau konteks kecil; full snapshot, token, private URL, atau signature binary tidak disalin ke audit.

Audit action minimum:

```text
PRODUCT_CREATED, PRODUCT_UPDATED, PRODUCT_DEACTIVATED
SUPPLIER_CREATED, SUPPLIER_UPDATED, SUPPLIER_DEACTIVATED
OFFER_CREATED, OFFER_CORRECTED, OFFER_SUPERSEDED, OFFER_DEACTIVATED
TENDER_CREATED, TENDER_REVISED
RESULT_CREATED, RESULT_VALIDATED, RESULT_CUSTOMIZED, RESULT_SELECTED
OPTIMIZATION_REQUESTED, OPTIMIZATION_STARTED
OPTIMIZATION_COMPLETED, OPTIMIZATION_FAILED
BID_CREATED, BID_PRICED, BID_SUBMITTED, BID_APPROVED, BID_REJECTED
BID_REVISION_CREATED, BID_SIGNED
DOCUMENT_GENERATION_REQUESTED, DOCUMENT_FINALIZED, DOCUMENT_GENERATION_FAILED
```

---

## 9. Application Service Design

### 9.1 Catalog

| Service | Tanggung jawab |
|---|---|
| `create_product(command)` | Validasi Admin, unique code, create, audit |
| `update_product(command)` | Lock row, expected version, update mutable field, audit |
| `deactivate_product(command)` | Lock, inactive tanpa merusak histori, audit |
| `create_supplier(command)` | Validasi Admin, create, audit |
| `update_supplier(command)` | Lock, expected version, update, audit |
| `deactivate_supplier(command)` | Lock, inactive, audit |

Product/Supplier inactive tetap dapat tampil pada histori, tetapi tidak muncul sebagai pilihan transaksi baru.

### 9.2 Supplier Offer

| Service | Tanggung jawab |
|---|---|
| `create_supplier_offer(command)` | Validasi Staff, Product/Supplier aktif, kalkulasi net price, create, audit |
| `correct_unused_offer(command)` | Hanya offer yang belum memiliki reference historis, expected version, recalculate, audit |
| `supersede_supplier_offer(command)` | Buat offer baru dan hubungkan `supersedes_offer_id`; offer lama tetap ada |
| `deactivate_supplier_offer(command)` | Mencegah penggunaan baru tanpa mengubah result lama |

Eligibility menerima `as_of_date`, product, currency, active state, validity period, positive net price, dan quantity yang dibutuhkan. `available_quantity=NULL` berarti tidak ada batas quantity per result. Quantity tidak dikurangi setelah digunakan oleh Bid lain.

### 9.3 Tender

| Service | Tanggung jawab |
|---|---|
| `create_tender(command)` | Buat root, revision 1, items, product snapshots, hash, audit |
| `revise_tender(command)` | Lock root, expected version, buat revision immutable baru, audit |
| `get_current_tender_revision(tender_id)` | Ambil revision berdasarkan root pointer secara konsisten |

Setiap create/revise memvalidasi minimal satu item, unique `line_number`, quantity positif, Product aktif untuk revision baru, currency IDR, dan `total_hps > 0` bila diisi.

Revisi tender tidak mengubah Bid lama. Draft berbasis revision lama tidak dapat disubmit sebelum explicit rebase menjadi Bid revision baru.

### 9.4 Procurement Result

| Service | Tanggung jawab |
|---|---|
| `create_manual_result(command)` | Buat DRAFT lengkap untuk satu tender revision |
| `update_draft_result(command)` | Lock DRAFT, expected version, replace/edit child secara atomik |
| `validate_result(command)` | Revalidate seluruh aggregate, hitung cost, freeze snapshot, ubah VALID |
| `customize_result(command)` | Salin VALID source menjadi CUSTOMIZED DRAFT baru |
| `select_result(command)` | Lock Tender, validasi VALID + revision, append selection, audit |

Tidak ada service `update_valid_result`. Optimizer menggunakan internal create-valid service yang tetap memanggil validator dan calculator canonical.

### 9.5 Optimization

| Service | Tanggung jawab |
|---|---|
| `request_optimization(command)` | Lock Tender, build snapshot, enforce limit/active run, create PENDING, schedule publish, audit |
| `claim_optimization_run(run_id)` | Conditional PENDING → RUNNING, timestamp/version, audit |
| `complete_optimization_run(command)` | Persist VALID results/ranks + COMPLETED + notification atomik |
| `fail_optimization_run(command)` | Persist safe error + FAILED + notification atomik |
| `retry_optimization(command)` | Buat run baru dengan `retry_of_run_id` |

### 9.6 Bid Proposal

| Service | Tanggung jawab |
|---|---|
| `create_bid(command)` | Validasi latest selection, buat Bid root/revision DRAFT dan frozen result snapshot |
| `set_target_margin(command)` | Lock DRAFT, expected version, calculate item/total pricing dan HPS feasibility |
| `submit_bid(command)` | Lock DRAFT, revalidate latest tender revision/result/pricing/HPS, freeze submission, WAITING_APPROVAL |
| `revise_rejected_bid(command)` | Lock root, salin context ke revision DRAFT baru, preserve history |
| `approve_bid(command)` | Lock WAITING_APPROVAL, append decision, APPROVED |
| `reject_bid(command)` | Lock WAITING_APPROVAL, require reason, append decision, REJECTED + notification |
| `sign_bid(command)` | Lock APPROVED, verify same approver/hash, append Signature, SIGNED |
| `request_finalization(command)` | Lock SIGNED, freeze render input, create generation job, schedule publish |

### 9.7 Documents dan Notifications

| Service | Tanggung jawab |
|---|---|
| `claim_generation_job(job_id)` | Conditional PENDING → RUNNING |
| `complete_generation_job(command)` | Verify object, create FinalDocument, COMPLETED, Bid FINALIZED, audit atomik |
| `fail_generation_job(command)` | FAILED + safe error; Bid tetap SIGNED |
| `create_notification_from_event(command)` | Insert idempotent dari source event |
| `mark_notification_read(command)` | Hanya recipient, set `read_at` sekali |

---

## 10. HTTP dan Server-Rendered UI

### 10.1 General Pattern

- GET bersifat read-only dan boleh di-refresh.
- State change hanya melalui POST.
- POST sukses mengikuti Post/Redirect/Get.
- Form membawa hidden `expected_version` dan idempotency key untuk operation berisiko duplicate.
- Mutation URL menyatakan action secara eksplisit.
- List menggunakan pagination berbasis cursor atau stable ordered page sesuai query; default 25 dan maksimum 100 row.
- Search dibatasi panjangnya dan memakai indexed field bila tersedia.

### 10.2 Route Catalog

| Method | Route name / path | Role | Use case |
|---|---|---|---|
| GET/POST | `accounts:login` — `/accounts/login/` | Public | UC-001 |
| POST | `accounts:logout` — `/accounts/logout/` | Authenticated | UC-001 |
| GET | `dashboard` — `/` | Authenticated | Role dashboard |
| GET/POST | `catalog:product-list/create` | Admin | UC-002 |
| GET/POST | `catalog:product-update/deactivate` | Admin | UC-002 |
| GET/POST | `catalog:supplier-list/create` | Admin | UC-003 |
| GET/POST | `catalog:supplier-update/deactivate` | Admin | UC-003 |
| GET/POST | `sourcing:offer-list/create` | Staff | UC-004 |
| GET/POST | `sourcing:offer-update/supersede/deactivate` | Staff | UC-004 |
| GET/POST | `tender:list/create/detail/revise` | Staff | UC-005 |
| GET/POST | `sourcing:result-create/result-edit` | Staff | UC-006 |
| POST | `optimization:run-create` | Staff | UC-007 |
| GET | `optimization:run-detail` | Staff | UC-007/008 |
| GET | `sourcing:result-list/result-detail` | Staff | UC-008 |
| POST | `sourcing:result-customize` | Staff | UC-009 |
| POST | `sourcing:result-select` | Staff | UC-010 |
| POST | `bids:create` | Staff | UC-011 |
| GET/POST | `bids:detail/price` | Staff | UC-011/012 |
| POST | `bids:submit` | Staff | UC-013 |
| GET | `approval:queue/detail` | Manager | UC-014/015 |
| POST | `approval:approve` | Manager | UC-014 |
| POST | `approval:reject` | Manager | UC-015 |
| POST | `bids:revise` | Staff | UC-016 |
| GET/POST | `signatures:sign` | Approving Manager | UC-017 |
| POST | `documents:finalize` | Staff | UC-018 |
| GET | `documents:job-status` | Authorized Staff/Manager | UC-018 |
| GET | `documents:download` | Authorized Staff/Manager | UC-019 |
| GET/POST | `notifications:list/mark-read` | Recipient | Notifications |

Route detail memakai UUID dan selalu memfilter object visibility sebelum memuat template. Internal database exception tidak boleh mengungkap keberadaan object yang tidak boleh dilihat actor.

### 10.3 Response untuk Background Operation

Setelah optimizer/finalization diminta, POST me-redirect ke detail run/job. Halaman melakukan polling ringan ke route status yang mengembalikan fragment HTML atau JSON minimal:

```json
{
  "status": "PENDING",
  "terminal": false,
  "safe_message": null,
  "updated_at": "2026-09-11T03:00:00Z"
}
```

Polling memakai backoff, berhenti pada terminal state, dan tidak menentukan transition. Kehilangan koneksi browser tidak membatalkan job.

### 10.4 Download

Download service memvalidasi session, role, Bid relationship/status, FinalDocument version, dan object metadata. Baseline demo melakukan streaming melalui Django dengan:

- `Content-Type: application/pdf`;
- `Content-Disposition: attachment` dengan filename aman;
- `X-Content-Type-Options: nosniff`;
- `Cache-Control: private, no-store`;
- audit atau access log tanpa private object URL.

---

## 11. Calculation Policies

### 11.1 Numeric Context

Policy version awal:

```text
calculation_version = "calc-v1"
rounding_policy_version = "idr-half-up-v1"
```

Aturan implementasi:

- gunakan `decimal.localcontext()` dengan precision minimal 38 digit;
- `ROUND_HALF_UP` adalah mode rounding v1;
- quantity disimpan 3 decimal;
- percentage dan unit/intermediate price disimpan 4 decimal;
- allocation/item/total final disimpan 2 decimal;
- quantize hanya pada boundary yang ditetapkan policy, bukan setelah setiap operator;
- actual margin dihitung kembali dari final `gross_profit` dan `total_bid_value`.

Perubahan mode atau titik rounding harus menaikkan `calculation_version`; data historis tidak dihitung ulang.

### 11.2 Procurement Cost

```text
net_purchase_price
  = base_unit_price - (base_unit_price * discount_percent / 100)

allocation_purchase
  = round_money(allocated_quantity * net_purchase_price)

item_purchase_total
  = sum(allocation_purchase per item)

total_purchase
  = sum(item_purchase_total per result)
```

`SupplierOffer.net_purchase_price` dihitung saat offer dibuat atau disupersede. Validator tetap menghitung ulang dan membandingkan dengan snapshot untuk mendeteksi data korup atau version mismatch.

### 11.3 Bid Pricing

```text
target_margin_rate = target_margin_percent / 100
unit_purchase_cost = item_purchase_total / requested_quantity
bid_unit_price     = unit_purchase_cost / (1 - target_margin_rate)
item_bid_total     = round_money(requested_quantity * bid_unit_price)
total_bid_value    = sum(item_bid_total)
gross_profit       = total_bid_value - total_purchase
actual_margin      = (gross_profit / total_bid_value) * 100
```

`bid_unit_price` disimpan dengan 4 decimal, sedangkan `item_bid_total`, total, dan gross profit dengan 2 decimal. Proposal invalid jika `total_bid_value <= 0`.

### 11.4 HPS

```text
is_hps_feasible = total_hps is null or total_bid_value <= total_hps
max_margin_percent = ((total_hps - total_purchase) / total_hps) * 100
```

`max_margin_percent` null bila HPS tidak tersedia. Jika `total_purchase > total_hps`, tidak ada margin non-negatif yang feasible. Submission dan finalization menolak proposal tidak feasible.

---

## 12. Procurement Result Validation

`ProcurementResultValidator` menerima tender revision snapshot, result candidate, offer snapshots, dan evaluation date. Validasi dijalankan dengan urutan stabil dan menghasilkan machine-readable violations.

Untuk setiap result:

1. tender revision/result relationship sama;
2. terdapat tepat satu result item untuk setiap tender item;
3. tidak ada result item tambahan;
4. product pada setiap offer sama dengan product tender item;
5. Supplier, Product, dan Offer eligible pada evaluation date/snapshot;
6. setiap allocated quantity positif;
7. total allocation per item tepat sama dengan requested quantity;
8. allocation dari satu offer tidak melewati `available_quantity` jika tersedia;
9. currency seluruh nilai adalah IDR;
10. cost dihitung menggunakan policy canonical;
11. snapshot, hash, dan calculation version lengkap sebelum status VALID.

Perbandingan quantity menggunakan Decimal dengan scale 3 dan harus exact setelah normalisasi. Validator tidak menggunakan epsilon floating point.

Violation code minimum:

```text
MISSING_TENDER_ITEM
EXTRA_TENDER_ITEM
PRODUCT_MISMATCH
OFFER_INACTIVE
OFFER_NOT_YET_VALID
OFFER_EXPIRED
NON_POSITIVE_NET_PRICE
ALLOCATION_NON_POSITIVE
ALLOCATION_EXCEEDS_OFFER_LIMIT
QUANTITY_NOT_FULFILLED
CURRENCY_MISMATCH
CALCULATION_MISMATCH
```

---

## 13. Optimizer Design

### 13.1 Objective dan Assumptions

Optimizer v1 meminimalkan `total_purchase`. Model MVP memiliki karakter berikut:

- requirement antar-item independen;
- offer hanya memenuhi product yang sama;
- satu item boleh dialokasikan ke beberapa supplier;
- `available_quantity` adalah batas per result, bukan reservasi global;
- tidak ada minimum order, shipping cost, supplier-wide capacity, fixed cost, atau cross-item discount;
- optimizer tidak menentukan bid price atau target margin.

Dengan assumptions tersebut, kandidat termurah dapat dihitung per item dengan mengurutkan eligible offer berdasarkan net price dan mengisi quantity secara greedy. Kandidat pertama adalah optimum untuk model v1.

### 13.2 Deterministic Ordering

Eligible offer per item diurutkan berdasarkan:

1. `net_purchase_price` ascending;
2. supplier code ascending;
3. offer UUID ascending.

Candidate global diurutkan berdasarkan:

1. `total_purchase` ascending;
2. jumlah distinct supplier ascending;
3. canonical candidate identifier ascending.

Candidate identifier adalah SHA-256 dari ordered tuple `(tender_item_id, offer_id, allocated_quantity)`.

### 13.3 Candidate Generation

Engine v1 menjalankan langkah berikut:

1. Parse dan validate input snapshot schema/version.
2. Kelompokkan offer eligible berdasarkan product.
3. Untuk setiap tender item, bangun cheapest feasible allocation dengan greedy fill.
4. Jika total eligible capacity tidak cukup, simpan rejection reason dan hasil run dapat menjadi nol kandidat.
5. Gabungkan cheapest allocation semua item menjadi base candidate.
6. Bentuk alternative seed dengan mengecualikan satu offer yang digunakan atau menaikkan posisi awal offer pada satu item, lalu greedy-fill ulang item tersebut.
7. Masukkan kombinasi alternative ke min-heap berdasarkan deterministic ordering.
8. Pop kandidat, deduplicate berdasarkan candidate identifier, lalu validasi dan hitung menggunakan canonical validator/calculator.
9. Ekspansi alternative berikutnya dilakukan sampai 20 result valid, ruang kandidat habis, exploration limit tercapai, atau soft time limit mendekat.
10. Persist hanya result valid dan ranking final dalam satu completion transaction.

Kandidat pertama optimal dalam model v1. Kandidat alternatif adalah rekomendasi terbaik yang ditemukan oleh bounded deterministic exploration, bukan klaim enumerasi seluruh kombinasi global. Jika kebutuhan berikutnya memperkenalkan fixed supplier cost atau constraint lintas item, algorithm version harus berubah dan linear/integer programming perlu dievaluasi.

### 13.4 Limits dan Cancellation

- Maksimum 100 tender item.
- Maksimum 50 eligible offer per item.
- Maksimum 20 kandidat disimpan.
- Maksimum dua optimization task berjalan bersamaan.
- Soft timeout 240 detik; hard timeout 300 detik.
- Engine memeriksa remaining time pada boundary ekspansi candidate.
- Hard timeout diperlakukan sebagai technical failure dengan safe error code.

`algorithm_version = "greedy-bounded-v1"`. Snapshot input dan hasil menyimpan version ini agar run dapat direproduksi.

### 13.5 Worker Flow

```text
task(run_id, correlation_id)
  -> conditional claim PENDING -> RUNNING
  -> read only OptimizationRun.input_snapshot
  -> optimizer engine
  -> shared validator/calculator
  -> complete service or fail service
```

Redelivery terhadap COMPLETED/FAILED adalah no-op. Redelivery terhadap RUNNING tidak mengambil alih tanpa reconciliation decision. Business retry membuat run baru.

---

## 14. Bid Lifecycle dan Concurrency

### 14.1 State Machine

```text
DRAFT -> WAITING_APPROVAL -> APPROVED -> SIGNED -> FINALIZED
                         \-> REJECTED -> new DRAFT revision
```

Tidak ada transition mundur pada revision yang sama. Revisi setelah rejection membuat row revision baru dan menaikkan `current_revision_number`.

### 14.2 Submit

Dalam satu `transaction.atomic()`:

1. lock Bid root dan current Bid revision;
2. cocokkan `expected_version`;
3. pastikan status DRAFT;
4. pastikan Bid memakai current/explicitly accepted Tender revision;
5. validasi selected result masih VALID dan berasal dari Tender revision yang sama;
6. hitung ulang pricing dan HPS feasibility;
7. buat submission snapshot dan hash;
8. isi submitter/time;
9. transition ke WAITING_APPROVAL dan increment version;
10. tulis audit event.

### 14.3 Approve atau Reject

Service melakukan row lock terhadap revision WAITING_APPROVAL. Unique decision constraint memastikan hanya satu keputusan menang ketika dua request concurrent.

- approve memerlukan submission hash yang masih cocok;
- reject mewajibkan reason setelah trim;
- decision bersifat append-only;
- duplicate command dengan idempotency key yang sama mengembalikan outcome pertama;
- command berbeda setelah decision selesai menghasilkan 409.

### 14.4 Sign

Signing memvalidasi:

- revision APPROVED;
- ApprovalDecision adalah APPROVED;
- actor adalah `decided_by` yang sama;
- `submission_hash == approval.submission_hash`;
- belum ada Signature;
- metadata image lengkap dan file lolos validation bila digunakan.

Signature profile current hanya menjadi input. Signature row menyimpan nama, hash, dan object metadata historis tersendiri.

---

## 15. Final Document Design

### 15.1 Request Finalization

Procurement Staff memicu finalization. Dalam transaction:

1. lock Bid revision SIGNED;
2. revalidate HPS, approval, signature, dan frozen hashes;
3. alokasikan `document_version` berikutnya secara concurrency-safe;
4. alokasikan nomor `BID/{YYYY}/{sequence:06d}/R{revision:02d}`;
5. buat immutable finalization snapshot dan input hash;
6. buat GenerationJob PENDING;
7. tulis audit event;
8. `transaction.on_commit()` memublikasikan job ke queue `documents`.

Bid tetap SIGNED sampai worker berhasil.

### 15.2 Rendering

- Template path dan asset dipilih dari `template_version`, tidak dari input user.
- Template v1 adalah HTML/CSS A4 dengan Noto Sans yang dipaketkan.
- Renderer memblokir HTTP(S), arbitrary `file://`, dan path di luar asset allowlist.
- User content di-escape; tidak ada raw HTML dari field bisnis.
- PDF memuat nomor/revision, instansi, tender, validity 30 hari, item, quantity, unit price, total, approval, signer, dan document version.
- Render dilakukan pada temporary directory dengan size/time limit.

### 15.3 Storage dan Completion

Object key tidak mengandung PII:

```text
documents/{bid_uuid}/{revision_number}/{document_version}/{job_uuid}.pdf
```

Worker:

1. render PDF;
2. hitung SHA-256 dan size;
3. upload ke object key unik;
4. lakukan HEAD/read verification;
5. dalam transaction, lock job/revision;
6. create FinalDocument, set job COMPLETED, set Bid FINALIZED, dan audit;
7. jika transaction gagal setelah upload, biarkan object menjadi orphan untuk reconciliation.

Kegagalan render/upload membuat job FAILED dan Bid tetap SIGNED. Technical retry maksimum tiga attempt menggunakan backoff 10, 30, dan 90 detik dengan jitter. Regeneration membuat version baru dan tidak overwrite file lama.

---

## 16. Task Publication dan Reconciliation

### 16.1 Celery Queues

| Queue | Task | Karakteristik |
|---|---|---|
| `optimization` | Run optimizer | CPU/DB intensive, concurrency maksimum 2 |
| `documents` | Render/finalize PDF | Memory dan I/O sensitive |
| `default` | Notification/reconciliation ringan | Latency rendah |

Task memakai `acks_late` hanya bersama idempotent claim/outcome logic. Result backend Celery bukan source of truth; UI membaca status PostgreSQL.

### 16.2 Publish Gap

Run/job PENDING disimpan sebelum publish. Publish dijalankan dalam `transaction.on_commit()`. Jika publish gagal, record tetap PENDING dan exception dicatat tanpa menghapus record.

Scheduler tiap satu menit mencari PENDING yang lebih tua dari grace period satu menit lalu publish ulang. Duplicate delivery aman karena conditional claim.

### 16.3 Stale RUNNING

Reconciliation mendeteksi RUNNING yang melebihi timeout, tetapi tidak langsung menjalankan ulang jika outcome eksternal belum dapat dibuktikan. Untuk document job, adapter memeriksa object key dan metadata sebelum menentukan retry/cleanup. Semua recovery menghasilkan audit/operational log yang sesuai.

---

## 17. Query dan Performance Design

### 17.1 Selectors

Selector utama:

```text
catalog.list_active_products
catalog.list_active_suppliers
sourcing.list_eligible_offers
tender.get_tender_detail
sourcing.list_results_for_tender
sourcing.get_result_detail
optimization.get_run_detail
bids.list_staff_bids
approval.list_waiting_approval
bids.get_bid_detail
notifications.list_for_recipient
documents.get_authorized_document
```

Selector detail memakai `select_related` untuk single-valued relation dan `Prefetch` untuk child terurut. Template tidak boleh memicu query per row secara tidak terkendali.

### 17.2 Pagination dan Stable Ordering

- Tender/Bid/run/audit list diurutkan `created_at DESC, id DESC`.
- Product/Supplier list diurutkan normalized name/code lalu id.
- Result diurutkan `total_purchase ASC, id ASC`.
- Approval queue diurutkan `submitted_at ASC, id ASC`.
- Semua list memiliki deterministic tie-break.

### 17.3 Performance Targets Demo

Target awal, diverifikasi dengan seed data representatif:

- p95 GET list/detail synchronous di bawah 500 ms pada VPS demo;
- p95 POST biasa di bawah 1 detik, tidak termasuk background work;
- tidak ada N+1 pada route utama;
- optimizer dan PDF tetap berada dalam timeout yang ditetapkan;
- query plan index utama diperiksa pada dataset demo.

Target ini adalah fitness target demo, bukan SLA.

---

## 18. Security Implementation

### 18.1 Input dan Output

- Gunakan Django Form untuk whitelist field; jangan memakai `fields = "__all__"` pada business form.
- Batasi panjang text, jumlah inline item, dan jumlah allocation di server.
- Escape output template secara default.
- File signature hanya PNG/JPEG, maksimum 1 MiB, resolusi 200x80 sampai 2000x1000, dan divalidasi berdasarkan magic byte serta decode aktual.
- Nama upload tidak digunakan sebagai object key.
- CSV/spreadsheet import, rich text, dan arbitrary URL tidak termasuk MVP.

### 18.2 Headers dan Deployment Check

Production/demo HTTPS mengaktifkan secure cookie, HSTS setelah TLS stabil, frame protection, MIME sniffing protection, Referrer Policy, dan Content Security Policy yang sesuai dengan asset lokal. CI menjalankan `manage.py check --deploy` menggunakan safe deployment settings.

### 18.3 Sensitive Logging

Log tidak boleh berisi:

- password/session/CSRF token;
- MinIO credential atau signed URL;
- signature binary;
- full submission/finalization snapshot;
- arbitrary request body;
- stack trace pada response user.

---

## 19. Observability

### 19.1 Structured Logging

Field minimum:

```text
timestamp, level, process, environment
correlation_id, actor_id, entity_type, entity_id
operation, from_status, to_status
duration_ms, outcome, safe_error_code
```

Web, scheduler, dan worker menggunakan format yang sama. `diagnostic_reference` menghubungkan safe error di database/UI dengan operational log.

### 19.2 Metrics

Minimum metrics:

- HTTP request count/latency/error/permission denial;
- DB query latency, lock wait, transaction failure;
- queue depth dan oldest task age per queue;
- oldest PENDING run/job;
- optimization duration/result count/completed/failed;
- document duration/failure/storage error;
- duplicate/idempotency prevention;
- login failure dan unauthorized download attempt.

Metric tidak memakai user ID atau entity UUID sebagai high-cardinality label.

### 19.3 Health Endpoints

- `/health/live/`: process hidup, tanpa deep dependency check;
- `/health/ready/`: database dapat menerima query ringan dan migration state sesuai;
- worker health: Celery heartbeat/queue consumption;
- Redis dan MinIO deep checks dipantau terpisah.

Health endpoint tidak mengungkap version detail, credential, hostname internal, atau stack trace.

---

## 20. Testing Strategy

### 20.1 Test Pyramid

| Jenis | Fokus |
|---|---|
| Unit | Decimal policies, validator, transitions, optimizer ordering, snapshot/hash |
| Model | Constraint, choices, delete policy, immutable behavior |
| Service integration | Transaction, lock, audit pairing, version conflict, idempotency |
| View | Authentication, role, CSRF, form errors, PRG, object visibility |
| Task | Claim, redelivery, retry classification, completion/failure |
| Storage/PDF | Upload verification, checksum, private access, deterministic content |
| End-to-end | Primary scenario UC-001 sampai UC-019 |

### 20.2 Required Calculation Tests

- net price dengan discount 0, pecahan, dan 100 persen;
- multi-supplier allocation;
- quantity dengan tiga decimal;
- rounding boundary setengah;
- actual margin setelah final rounding;
- HPS absent, exactly equal, exceeded, dan purchase di atas HPS;
- hasil MANUAL, OPTIMIZER, dan CUSTOMIZED identik untuk input allocation yang sama.

### 20.3 Required Concurrency Tests

- dua request optimizer pada Tender yang sama hanya membuat satu active run;
- dua selection concurrent menghasilkan sequence valid tanpa lost update;
- stale form gagal melalui expected version;
- approve dan reject concurrent hanya menghasilkan satu decision;
- dua finalization request tidak mendapat version/nomor document yang sama;
- task redelivery tidak menggandakan result, notification, atau FinalDocument.

Test concurrency memakai PostgreSQL, bukan SQLite, karena row lock, partial unique constraint, dan isolation behavior berbeda.

### 20.4 Historical Integrity Tests

- perubahan Product/Supplier/Offer tidak mengubah snapshot result/Bid/PDF lama;
- revisi Tender tidak mengubah Bid lama;
- VALID result tidak dapat diedit;
- decision/signature/audit/final document tidak dapat diubah melalui application path;
- regeneration menghasilkan object key dan document version baru;
- hash berubah untuk perubahan material dan stabil untuk canonical content yang sama.

### 20.5 CI Quality Gate

Pipeline minimum:

1. formatting dan lint;
2. static/type check pada domain/application code;
3. unit dan PostgreSQL integration test;
4. migration consistency check;
5. template/system check;
6. dependency dan secret scan;
7. build image reproducible;
8. smoke test dari image hasil build.

---

## 21. Delivery Sequence

Implementasi disarankan mengikuti vertical slice berikut:

1. foundation: settings, custom User, role policy, PostgreSQL, base template, audit/idempotency primitives;
2. Catalog: Product dan Supplier;
3. Supplier Offer dan canonical cost policy;
4. Tender root/revision/item dan snapshot;
5. manual Procurement Result, validation, customization, dan selection;
6. OptimizationRun, Celery worker, deterministic optimizer, dan notification;
7. Bid creation, pricing, HPS, submission, dan revision;
8. approval/rejection dan notification;
9. signature dan private image storage;
10. PDF generation, finalization, authorized download, dan reconciliation;
11. observability, deployment hardening, benchmark, dan end-to-end demo data.

Setiap slice harus mencakup migration, model, service, UI, authorization, audit, dan test yang relevan. Jangan menunda seluruh invariant atau security test ke milestone terakhir.

---

## 22. Traceability

### 22.1 Use Case ke Service

| Use Case | Service utama |
|---|---|
| UC-001 | Django authentication + account policy |
| UC-002 | Catalog product services |
| UC-003 | Catalog supplier services |
| UC-004 | Supplier Offer services |
| UC-005 | Tender create/revise services |
| UC-006 | Manual result services |
| UC-007 | Optimization request/worker services |
| UC-008 | Result selectors |
| UC-009 | `customize_result` |
| UC-010 | `select_result` |
| UC-011 | `create_bid` |
| UC-012 | `set_target_margin` |
| UC-013 | `submit_bid` |
| UC-014 | `approve_bid` |
| UC-015 | `reject_bid` |
| UC-016 | `revise_rejected_bid` |
| UC-017 | `sign_bid` |
| UC-018 | `request_finalization` + document worker |
| UC-019 | authorized document selector/download service |

### 22.2 Invariant ke Enforcement Point

| Invariant | Enforcement utama | Pertahanan tambahan |
|---|---|---|
| Preserve Tender Requirement | immutable Tender revision/snapshot | hash dan historical test |
| Complete Fulfillment | ProcurementResultValidator | quantity/unique DB constraints |
| Product Matching | Validator | FK lineage dan snapshot |
| Human-Controlled Selection | `select_result` service | append-only selection history |
| Pricing Separation | BidPricingCalculator | module dependency test |
| HPS Feasibility | HpsFeasibilityPolicy saat price/submit/finalize | stored result dan tests |
| Controlled Approval | Bid transition service | unique ApprovalDecision |
| Controlled Signature | signature policy | unique Signature + approver FK |
| Controlled Finalization | request/worker completion service | unique job/document version |
| Historical Integrity | immutable revision/snapshot policy | PROTECT, hashes, tests |

---

## 23. Definition of Done

Technical implementation MVP dianggap sesuai dokumen ini jika:

- seluruh UC-001 sampai UC-019 memiliki route, authorization, service, dan automated test;
- schema migration sesuai `06-data-model.md` dan tidak memiliki pending model change;
- kalkulasi Decimal menghasilkan output konsisten untuk MANUAL, OPTIMIZER, dan CUSTOMIZED;
- lifecycle ilegal ditolak di server;
- concurrency dan idempotency test lulus menggunakan PostgreSQL;
- snapshot/hash mempertahankan histori setelah master data berubah;
- optimizer dan document job pulih dari lost publish/redelivery tanpa duplikasi;
- proposal tidak menjadi FINALIZED sebelum PDF tersimpan dan terverifikasi;
- seluruh file privat hanya dapat diakses melalui authorization check;
- deployment check, security scan, health check, dan smoke test lulus;
- end-to-end scenario dari Tender sampai authorized PDF download dapat didemonstrasikan.

---

Dokumen ini adalah baseline implementasi. Detail class atau nama fungsi boleh disesuaikan selama ownership, kontrak, invariant, transaction boundary, dan traceability yang ditetapkan tetap dipertahankan.
