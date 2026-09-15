# Technical Design

## Medical Procurement Bid Optimizer

> Status: Dokumentasi implementasi saat ini<br>
> Terakhir diperbarui: 15 September 2026

## 1. Sumber implementasi

Kode pada `apps/`, `config/`, dan migration merupakan acuan. Nama fungsi di bawah adalah API service aktual, yang menerima keyword arguments seperti `actor` dan `correlation_id`; belum ada shared CommandContext, generic idempotency key, atau service response envelope.

## 2. Layer dan entrypoint

| Layer | Lokasi dan peran |
|---|---|
| URL/view | `config/urls.py`, `apps/*/urls.py`, `views.py`: session/role guard, input HTTP, render/redirect |
| Form | `apps/*/forms.py`, `apps/core/forms.py`: field validation dan hidden expected version |
| Service | `services.py`, `sourcing/result_services.py`: transaksi, locking/version, mutation, snapshot, audit, notification |
| Pure policy | sourcing eligibility/validator/calculator, Bid calculator, optimizer engine |
| Model | `models.py`: fields, relation, constraint, immutability guard |
| Task | optimization/documents `tasks.py`: claim, execution, completion/failure, reconciliation |
| Adapter | `documents/storage.py`: private MinIO; `renderers.py`: WeasyPrint HTML/CSS v1 |
| Shared utility | `core/domain/canonical_json.py`, `core/formatting.py`, `core/exceptions.py` |

UI menggunakan semantic template dan CSS lokal; tidak ada SPA, Django REST Framework, public API, atau frontend dependency tambahan. Routes status JSON hanya mendukung polling job.

## 3. Application service API aktual

| Modul | Fungsi |
|---|---|
| accounts | `create_user`, `change_user_role`, `deactivate_user`, `save_user_from_admin` |
| catalog | `create_product`, `update_product`, `deactivate_product`, `reactivate_product`, `create_supplier`, `update_supplier`, `deactivate_supplier` |
| tender | `create_tender`, `revise_tender`, `get_current_tender_revision` |
| sourcing Offer | `create_supplier_offer`, `correct_unused_offer`, `supersede_supplier_offer`, `deactivate_supplier_offer` |
| sourcing Result | `create_manual_result`, `update_draft_result`, `validate_result`, `customize_result`, `select_result` |
| optimization | `request_optimization`, `retry_optimization`, `claim_optimization_run`, `calculate_run_outcome`, `complete_optimization_run`, `fail_optimization_run` |
| bids | `create_bid_proposal`, `set_target_margin`, `submit_bid`, `revise_rejected_bid` |
| approval | `approve_bid`, `reject_bid` |
| signatures | `sign_bid` |
| documents | `request_finalization`, `claim_generation_job`, `release_generation_job_for_retry`, `complete_generation_job`, `fail_generation_job`, `get_authorized_document` |
| notifications | `create_notification`, `mark_notification_read` |
| audit | `write_audit_event` |

Approval/signature/document services melakukan transition Bid revision langsung dalam transaksi masing-masing, memakai guard model Bid. Tidak ada lifecycle gateway terpisah yang dipanggil ketiga modul tersebut.

## 4. Authorization, concurrency, dan errors

`accounts/policies.py` menyediakan `require_active_user`, `require_valid_role`, `require_role`, dan role helpers. Service memastikan actor berwenang; views memakai guard juga. Relasi model menggunakan `settings.AUTH_USER_MODEL`, sementara kode akun mengambil model melalui `get_user_model()`.

Row lock menggunakan `select_for_update()` dalam `transaction.atomic()`. `expected_version` diterapkan pada edit master/Offer/Tender/result/Bid dan keputusan/signing terkait. Unique constraints menangani race selection sequence, active optimization, keputusan/signature, document version, dan notification.

Exception domain aktual adalah `ConcurrencyConflict` dan `InvalidTransition`, keduanya turunan Django ValidationError. View memetakan exception menurut alur: beberapa mengembalikan 409, beberapa merender form 400/409, dan beberapa menampilkan Django message lalu redirect. PermissionDenied menghasilkan 403. Tidak ada generic IdempotencyConflict atau uniform API error schema.

## 5. Kalkulasi canonical

Implementasi `calc-v1` menggunakan Decimal dengan local context precision 38 untuk aritmetika terkait:

- `sourcing/policies.py`: base dikurangi diskon, net price quantize `0.0001`, HALF_UP.
- `sourcing/calculations.py`: quantity quantize `0.001`; allocation amount quantity × net price quantize `0.01`, HALF_UP; item/result menjumlahkan amount allocation yang sudah dibulatkan.
- `bids/calculations.py`: margin quantize `0.0001`, validasi 0–<100; biaya per unit dihitung dari item purchase/quantity; bid unit price quantize `0.0001`, HALF_UP; item total quantity × bid unit price quantize `0.01`, HALF_UP; total Bid menjumlahkan item total.
- Gross profit dihitung dari total Bid dikurangi purchase; actual margin memakai total Bid setelah pembulatan; maksimum margin HPS dan feasibility memakai HPS snapshot.

Tidak ada direct unit-price override, tax calculation, shipping cost, atau FX conversion. Gunakan [Business Rules](02-business-rules.md) untuk formula dan [Demo Scenario](10-demo-scenario.md) untuk golden values.

## 6. Snapshot dan hashing

Snapshot builders tersedia di tender service, sourcing/optimization/bids/documents `snapshots.py`. Version saat ini 1. Topologi JSON berbeda menurut snapshot type, bukan satu envelope generik yang seragam:

- optimization: `schema_version`, `snapshot_type=optimization_input`, `captured_at`, `evaluation_date`, `source`, `data` berisi requirements/eligible_offers;
- result: Tender context dan data item/allocation frozen;
- submission: selected result context, pricing/item, serta submitter;
- finalization: `source`, `document`, `tender`, `pricing`, `approval`, dan `signature`.

`canonical_dumps()` menormalisasi nilai serta mengurutkan object keys; `canonical_hash()` menghitung SHA-256 atas JSON canonical. Array order tetap material. Harga/quantity snapshot direpresentasikan sebagai string desimal, timestamp sebagai representasi ISO dari builder. Snapshot hashes diperiksa pada titik workflow terkait.

Manual/customized validation membaca status/kapasitas Offer live pada tanggal server; optimizer membaca flags/tanggal/harga input frozen. Bid submission memvalidasi ulang pricing dari result snapshot dan current selection; finalization memeriksa flag HPS/submission frozen, bukan membaca ulang HPS Tender terbaru.

## 7. Optimization execution

`optimization/engine.py` mengekspor `optimize()`/`run_optimizer`; `strategies/greedy_bounded_v1.py` menyediakan wrapper `run()`. Input/output adalah frozen dataclasses pada `contracts.py`.

Engine mengurutkan Offer menurut harga, supplier code, Offer ID dan memelihara remaining capacity lintas item. Skip-vector dalam heap mengeksplorasi alternatif sampai limit, callback stop, atau antrian habis. Candidate ID adalah SHA-256 dari allocation yang diurutkan. Hasil diurutkan menurut purchase, distinct supplier count, identifier lalu dipotong maksimal result count. Kandidat dipersist sebagai VALID setelah shared validator memverifikasi snapshot input.

| Setting | Default |
|---|---:|
| OPTIMIZER_MAX_ITEMS | 100 |
| OPTIMIZER_MAX_OFFERS_PER_ITEM | 50 |
| OPTIMIZER_MAX_RESULTS | 20 |
| OPTIMIZER_EXPLORATION_LIMIT | 2.000 |
| OPTIMIZER_SOFT_TIME_LIMIT_SECONDS | 240 |
| OPTIMIZER_HARD_TIME_LIMIT_SECONDS | 300 |
| OPTIMIZER_RECONCILIATION_GRACE_SECONDS | 60 |

Batas ini berasal dari `settings/base.py`; tidak semua mempunyai parser environment override. Worker mengevaluasi callback stop mendekati soft limit; pencarian terbatas dapat selesai dengan kandidat yang sudah ditemukan. SoftTimeLimitExceeded/exception menjadi FAILED. Tidak ada automatic Celery retry loop optimizer; Staff retry membuat run baru dari input terbaru. Reconciliation hanya republish PENDING, maksimum 100 row per eksekusi, tanpa stale RUNNING takeover.

## 8. Document execution, retry, dan regeneration

`request_finalization()` menerima SIGNED/FINALIZED yang mempunyai approval/signature/hash valid. Active PENDING/RUNNING job dikembalikan kembali. Job baru menggunakan `max(document_version seluruh job) + 1`, nomor dari `DocumentNumberSequence` yang dikunci per tahun, dan frozen finalization snapshot.

Proposal number berbeda dari document number:

```text
proposal_number: BID-{YYYY}-{8 karakter hex UUID uppercase}
document_number: BID/{YYYY}/{sequence:06d}/R{revision:02d}
PDF object key:  documents/{bid_revision_id}/{revision_number}/{document_version}/{job_id}.pdf
signature key:   signatures/{bid_revision_id}/{UUID}.png atau .jpg
```

Regeneration membuat nomor sequence baru, bukan menggunakan kembali nomor sebelumnya. Counter tahunan tidak direset oleh reset dataset demo.

Task claim meningkatkan attempt count dan version, render `templates/documents/pdf_v1.html` memakai stylesheet lokal A4, lalu upload ke MinIO. Signature image privat diperiksa metadata MIME/size/hash, versi object jika tersedia, dan format gambar Pillow sebelum menjadi data URI. PDF diperiksa header `%PDF-` dan maksimum 10 MiB. Completion memeriksa object, hash input, key, dan status Bid sebelum menyimpan FinalDocument serta mengubah SIGNED menjadi FINALIZED.

Default soft/hard document task limit 50/60 detik. Kegagalan ditangani maksimum tiga attempt pada jalur task: retry setelah attempt 1 dan 2 memakai delay 10 dan 30 detik. Walau tuple kode memuat 90, attempt ketiga menjadi FAILED; tidak ada retry delay 90 atau jitter pada jalur tersebut. Reconciliation stale dapat memublikasikan ulang job di luar loop attempt ini.

Beat menjalankan reconciliation setiap 60 detik. PENDING berumur minimal 60 detik direpublish; RUNNING stale setelah hard limit + grace (120 detik) diperiksa pada key deterministik. Object valid dapat di-complete; kegagalan pemeriksaan melepas claim dan republish. Ini recovery job yang dikenal, bukan pemindaian/pembersihan orphan bucket secara menyeluruh.

Pada finalization pertama, kegagalan mempertahankan SIGNED. Pada regeneration, FINALIZED dan PDF lama tetap tersedia. Request baru setelah terminal failure menghasilkan job/version baru. Unique generation-job output dan version constraints mencegah completion ganda.

## 9. Storage dan download

Adapter MinIO `storage.py` menyediakan store/stat/read/remove dan bucket creation jika belum ada. Tidak ada public policy atau bucket-versioning activation yang dipasang adapter/Compose. `object_version_id` dapat null; version aplikasi tetap disimpan dan PDF baru memakai key baru. Stat/read saat ini membaca object key tanpa parameter version ID.

`get_authorized_document()` memeriksa active valid Staff/Manager, status FINALIZED, size/SHA-256/header, lalu view mengirim binary melalui Django dengan private cache/security headers. Tidak ada presigned URL flow. Gambar signature diunggah per signing, tanpa profile reuse atau direct-download endpoint.

## 10. Authentication, UI, dan observability

- Django LoginView/AuthenticationForm dan LogoutView POST; CSRF middleware aktif.
- Login rate limit default lima kegagalan per kombinasi username yang dinormalisasi dan REMOTE_ADDR selama window 300 detik. Key di-hash; login sukses menghapus failures key.
- Profile read-only, dashboard module links, navigation sesuai role, generic authentication error.
- Partial form merender label dan error dekat field; perilaku atribut aksesibilitas input mengikuti widget/form Django. Tender formset menggunakan JavaScript lokal untuk dynamic items; status optimization/document memakai polling.
- Notification dibuat langsung oleh service bisnis; unique recipient/event/type dan read timestamp menjaga duplicate/read behavior. Toast dari render unread, tanpa realtime push.
- Audit writer membekukan actor name dan memvalidasi correlation ID. JSON operational logs terpisah dari AuditEvent.
- Correlation middleware menerima header `X-Correlation-ID` dengan 1–100 karakter `[A-Za-z0-9._-]`, atau membuat UUID baru bila header tidak aman, lalu memasangnya pada response. Audit writer memeriksa correlation ID nonkosong dan maksimal 100 karakter.
- Health ready mencakup DB/migrations saja. HTTP metrics adalah in-process counters, bukan histogram/percentile atau agregasi multiprocess; job metrics membaca jumlah row/status dari DB.

## 11. Verifikasi

Suite saat ini mencakup kalkulasi, access, lifecycle, snapshots, sejumlah race PostgreSQL, task redelivery/reconciliation, signature/PDF, dan commands demo. Test setting eager Celery serta storage mocks tidak membuktikan kondisi Redis/MinIO/VPS nyata. Detail cakupan dan perintah terdapat pada [Demo Test Plan](09-demo-test-plan.md).
