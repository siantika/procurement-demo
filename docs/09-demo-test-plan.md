# Demo Test Plan

## Medical Procurement Bid Optimizer

> Status: Test baseline demo MVP  
> Acuan: `02-business-rules.md`, `03-use-cases.md`, dan `07-technical-design.md`  
> Terakhir diperbarui: 11 September 2026

---

## 1. Tujuan

Test plan memastikan demo tidak hanya tampak berjalan, tetapi menjaga empat risiko utama:

1. angka procurement dan Bid benar;
2. role serta lifecycle tidak dapat dilewati;
3. histori tidak berubah setelah master data berubah;
4. background retry/concurrency tidak membuat data ganda atau status palsu.

Test plan ini bukan certification atau production performance test.

---

## 2. Lingkungan Test

| Environment | Kegunaan |
|---|---|
| Unit | Domain policy tanpa network/database bila memungkinkan |
| Integration | PostgreSQL, Django service/model, transaction, constraint |
| Worker integration | PostgreSQL + Redis/Celery test worker |
| Storage integration | MinIO test bucket privat |
| End-to-end | Build/image yang sama dengan demo |

Test yang bergantung pada row lock, partial unique index, JSONB, dan concurrency wajib memakai PostgreSQL. Test bucket MinIO dipisahkan dari bucket demo dan dibersihkan berdasarkan test-run prefix.

---

## 3. Test Data Utama

Golden dataset:

```text
Requested quantity: 100 unit

Supplier A
  base price:       7,000,000.0000
  discount:                   10%
  available:              60.000
  net price:       6,300,000.0000
  allocation cost: 378,000,000.00

Supplier B
  base price:       7,500,000.0000
  discount:                    5%
  available:             100.000
  net price:       7,125,000.0000
  allocation:               40.000
  allocation cost: 285,000,000.00

Total purchase:      663,000,000.00
Target margin:                 15%
Total bid value:     780,000,000.00
Gross profit:        117,000,000.00
HPS:                 800,000,000.00
Maximum margin:              17.1250%
Feasible:                       yes
```

Factory/fixture memakai Decimal string, UUID stabil hanya ketika test memerlukannya, dan server-controlled time.

---

## 4. Automated Test Suites

### 4.1 Calculation dan Validation

| ID | Test | Expected result |
|---|---|---|
| CAL-001 | Discount 10% dari Rp7.000.000 | Net Rp6.300.000 |
| CAL-002 | Allocation A60 + B40 | Total Rp663.000.000 |
| CAL-003 | Target margin 15% | Bid Rp780.000.000 dan profit Rp117.000.000 |
| CAL-004 | Bid sama dengan HPS | Feasible |
| CAL-005 | Bid satu sen di atas HPS | Tidak feasible |
| CAL-006 | Purchase lebih besar dari HPS | Margin non-negatif tidak feasible |
| CAL-007 | Margin 0% | Bid sama dengan purchase |
| CAL-008 | Margin >=100% atau negatif | Ditolak |
| CAL-009 | Boundary `ROUND_HALF_UP` | Sesuai `idr-half-up-v1` |
| CAL-010 | MANUAL/OPTIMIZER/CUSTOMIZED allocation sama | Nilai tersimpan identik |
| VAL-001 | Allocation tepat memenuhi quantity | VALID |
| VAL-002 | Allocation kurang/lebih | Ditolak |
| VAL-003 | Product offer berbeda | Ditolak |
| VAL-004 | Offer inactive/expired/belum valid | Ditolak |
| VAL-005 | Allocation melewati available quantity | Ditolak |
| VAL-006 | Offer digunakan Bid lain | Tetap eligible; bukan stok global |

### 4.2 Authorization

| ID | Actor dan action | Expected result |
|---|---|---|
| AUTH-001 | Anonymous membuka business page | Redirect login |
| AUTH-002 | Staff mengubah Product/Supplier | 403 |
| AUTH-003 | Admin membuat Tender/Offer | 403 |
| AUTH-004 | Manager submit Bid | 403 |
| AUTH-005 | Staff approve/reject | 403 |
| AUTH-006 | Manager bukan approver melakukan sign | 403 |
| AUTH-007 | Manager memicu finalization | 403 |
| AUTH-008 | Admin/anonymous download PDF | 403/redirect atau 404 sesuai visibility policy |
| AUTH-009 | Mutation tanpa CSRF | Ditolak |
| AUTH-010 | Inactive user login | Ditolak |

### 4.3 Lifecycle

| ID | Scenario | Expected result |
|---|---|---|
| LIFE-001 | DRAFT result divalidasi lengkap | Menjadi VALID |
| LIFE-002 | Edit VALID result | Ditolak |
| LIFE-003 | Submit Bid tanpa selected result | Ditolak |
| LIFE-004 | DRAFT -> WAITING_APPROVAL | Submission snapshot/hash tersimpan |
| LIFE-005 | Approve/reject selain WAITING_APPROVAL | Ditolak |
| LIFE-006 | Reject tanpa reason | Ditolak |
| LIFE-007 | Revisi REJECTED | Revision DRAFT baru; history tetap |
| LIFE-008 | Sign selain APPROVED | Ditolak |
| LIFE-009 | Finalize selain SIGNED | Ditolak |
| LIFE-010 | PDF render gagal | Bid tetap SIGNED |
| LIFE-011 | PDF tersimpan dan diverifikasi | Bid menjadi FINALIZED |

### 4.4 Optimizer dan Background Job

| ID | Scenario | Expected result |
|---|---|---|
| JOB-001 | Golden dataset | Rank 1 total Rp663.000.000 |
| JOB-002 | Tie total cost | Supplier count lalu candidate ID menentukan urutan |
| JOB-003 | Capacity tidak cukup | COMPLETED, result count 0 |
| JOB-004 | Snapshot dibuat lalu Offer berubah | Run tetap memakai nilai snapshot |
| JOB-005 | Task OptimizationRun dikirim dua kali | Result/notification tidak ganda |
| JOB-006 | Exception teknis | FAILED + safe error + diagnostic reference |
| JOB-007 | Publish hilang setelah commit | Reconciliation publish ulang PENDING |
| JOB-008 | PDF task dikirim dua kali | Satu FinalDocument per job/version |
| JOB-009 | Upload sukses, DB commit gagal | Orphan terdeteksi reconciliation |
| JOB-010 | Nol candidate | Tidak diklasifikasikan sebagai technical failure |

### 4.5 Concurrency dan Idempotency

| ID | Race | Expected result |
|---|---|---|
| CON-001 | Dua run dibuat untuk Tender yang sama | Satu active run |
| CON-002 | Dua edit memakai expected version sama | Satu berhasil, satu 409 |
| CON-003 | Approve dan reject concurrent | Tepat satu decision |
| CON-004 | Dua selection concurrent | Sequence unik dan current selection jelas |
| CON-005 | Dua request finalization | Version/job tidak ganda |
| CON-006 | Idempotency key sama, payload sama | Outcome awal dikembalikan |
| CON-007 | Idempotency key sama, payload berbeda | 409 conflict |

### 4.6 Historical Integrity

| ID | Perubahan setelah transaksi | Expected result |
|---|---|---|
| HIST-001 | Rename Product/Supplier | Result/Bid lama tetap menampilkan snapshot lama |
| HIST-002 | Supersede Offer | Cost result lama tidak berubah |
| HIST-003 | Revisi Tender | Submission lama tetap memakai revision lama |
| HIST-004 | Ganti signature profile | Signature historis tidak berubah |
| HIST-005 | Regenerate PDF | Version/object key baru; file lama tetap ada |
| HIST-006 | Mutation AuditEvent melalui service/admin | Tidak tersedia atau ditolak |
| HIST-007 | Canonical content yang sama | Hash sama |
| HIST-008 | Perubahan material | Hash berbeda |

---

## 5. End-to-End Tests

### E2E-001 — Primary Success Flow

1. Admin membuat Product dan Supplier.
2. Staff membuat tiga Supplier Offer.
3. Staff membuat Tender 100 Infusion Pump dengan HPS Rp800 juta.
4. Staff menjalankan optimizer dan menunggu COMPLETED.
5. Rank 1 menunjukkan A60 + B40 dan total Rp663 juta.
6. Staff memilih result dan membuat Bid.
7. Staff menetapkan margin 15%; Bid menjadi Rp780 juta dan feasible.
8. Staff submit.
9. Manager approve dan sign.
10. Staff finalize dan menunggu job COMPLETED.
11. Staff dan Manager dapat download PDF; actor lain tidak.

Expected: seluruh status, angka, snapshot, hash, notification, audit, dan PDF sesuai.

### E2E-002 — Rejection and Revision

1. Staff submit Bid valid.
2. Manager reject dengan reason.
3. Submitter menerima satu notification.
4. Staff membuat revision DRAFT baru dan mengubah margin.
5. Revision lama, decision, reason, dan hash tetap tersedia.
6. Revision baru dapat disubmit ulang.

### E2E-003 — HPS Failure

1. Pilih result purchase Rp663 juta.
2. Tetapkan margin di atas 17,125% sehingga total Bid melewati HPS.
3. UI menampilkan tidak feasible.
4. Submission ditolak server-side walaupun request POST dibuat langsung.

---

## 6. Manual Demo Readiness Checks

Automated test tidak menggantikan pemeriksaan berikut:

- layout terbaca pada laptop/proyektor target;
- angka Rupiah dan status mudah dikenali;
- loading/polling optimizer dan PDF jelas;
- validation error tampil dekat input yang salah;
- session pergantian Staff/Manager tidak tertukar;
- PDF A4 tidak terpotong dan nama file aman;
- halaman error tidak menampilkan stack trace;
- data seed cocok dengan script presentasi.

---

## 7. Eksekusi

Perintah baseline setelah test suite tersedia:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py check --deploy --settings=config.settings.demo
```

Integration suite dijalankan dengan PostgreSQL/Redis/MinIO test services yang terisolasi. Perintah final dapat dibungkus Makefile atau Compose, tetapi wrapper harus mengembalikan non-zero exit code ketika test gagal.

---

## 8. Defect Severity

| Severity | Contoh | Keputusan demo |
|---|---|---|
| Blocker | Login gagal, angka salah, final PDF tidak ada, data corrupt | Demo tidak boleh dilanjutkan |
| High | Permission bypass, illegal transition, duplicate decision/document | Demo tidak boleh dilanjutkan |
| Medium | Error message buruk, filter/list bermasalah dengan workaround | Perbaiki atau dokumentasikan workaround |
| Low | Cosmetic spacing atau copy minor | Boleh ditunda jika tidak mengganggu cerita |

---

## 9. Exit Criteria

Build lulus test plan bila:

- seluruh test CAL, AUTH, LIFE, JOB, CON, dan HIST wajib lulus;
- E2E-001 lulus tiga kali berturut-turut dari data reset;
- E2E-002 dan E2E-003 minimal lulus sekali pada release candidate;
- tidak ada Blocker atau High defect terbuka;
- PDF golden case memiliki angka dan metadata yang benar;
- test report mencatat commit/image version, migration state, waktu, dan executor.

