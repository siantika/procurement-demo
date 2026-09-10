# Demo Implementation Plan

## Medical Procurement Bid Optimizer

> Status: Rencana eksekusi demo MVP  
> Acuan teknis: `07-technical-design.md`  
> Terakhir diperbarui: 11 September 2026

---

## 1. Tujuan Demo

Demo harus membuktikan bahwa aplikasi dapat menjalankan satu alur pengadaan internal secara utuh:

```text
Supplier Offer dan Tender
  -> Procurement Result
  -> Optimization dan Selection
  -> Bid Pricing
  -> Approval dan Signature
  -> Final PDF
```

Keberhasilan demo dinilai dari correctness alur, kejelasan informasi, pembatasan role, dan kemampuan menghasilkan dokumen final yang dapat ditelusuri. Demo bukan bukti kesiapan production atau integrasi dengan portal tender eksternal.

---

## 2. Kondisi Awal Repository

Pada saat rencana ini dibuat, repository baru memiliki kerangka Django, login/profile/dashboard dasar, dan dokumentasi desain. Database masih menggunakan SQLite dan business module belum diimplementasikan penuh.

Konsekuensinya, pekerjaan dimulai dari foundation PostgreSQL dan custom User sebelum membangun fitur bisnis. File cache Python bukan source code dan tidak digunakan sebagai baseline implementasi.

---

## 3. Scope Prioritas

### 3.1 P0 — Wajib Berfungsi

- login dan role Admin, Procurement Staff, Manager;
- Product dan Supplier;
- Supplier Offer beserta discount, validity, dan available quantity;
- Tender Request dengan item dan optional HPS;
- manual Procurement Result dan validation;
- OptimizationRun asynchronous dengan hasil terurut;
- customization dan selection terhadap result valid;
- Bid Proposal, target margin, HPS feasibility, dan submission;
- Manager approve/reject serta approving Manager melakukan signature;
- Procurement Staff memicu finalization;
- PDF dibuat asynchronous, disimpan privat, dan dapat diunduh user berizin;
- audit trail dan notification untuk event utama;
- seed/reset data demo yang idempotent dan aman.

### 3.2 P1 — Dikerjakan Jika P0 Stabil

- filter dan pencarian list yang lebih lengkap;
- pagination untuk dataset besar;
- tampilan perbandingan result yang lebih kaya;
- signature image; signature metadata tanpa gambar tetap valid untuk demo;
- dashboard metrics tambahan;
- regeneration PDF melalui UI;
- operational dashboard Grafana lengkap.

### 3.3 Ditunda

- self-registration, SSO, MFA, dan multi-tenancy;
- API publik atau SPA;
- import spreadsheet;
- integrasi supplier/rumah sakit/portal tender;
- reservation stock global;
- procurement contract, inventory, shipment, invoice, dan payment;
- multi-currency;
- high availability dan production SLA.

---

## 4. Prinsip Eksekusi

- Implementasikan vertical slice yang dapat diuji, bukan seluruh model sekaligus tanpa flow.
- Business write hanya melalui application service.
- Kalkulasi MANUAL, OPTIMIZER, dan CUSTOMIZED memakai policy yang sama.
- Setiap state transition memiliki authorization, transaction, audit, dan test.
- PostgreSQL digunakan sejak integration test pertama; SQLite hanya boleh untuk eksperimen lokal yang tidak menguji constraint/concurrency.
- Background status berasal dari PostgreSQL, bukan Celery result backend.
- P1 tidak boleh menghambat stabilisasi P0.

---

## 5. Milestone Implementasi

### M0 — Foundation

Deliverable:

- settings `local`, `test`, dan `demo`;
- dependency lock dan environment example tanpa secret;
- PostgreSQL connection;
- custom UUID User dan role;
- base layout, login/logout, role-aware navigation;
- core Decimal, clock, correlation ID, audit, dan idempotency primitives;
- CI awal dan health endpoint.

Acceptance criteria:

- migration dapat dijalankan pada database kosong;
- tiga role dapat login dan melihat menu yang sesuai;
- state-changing request memiliki CSRF protection;
- test foundation berjalan di PostgreSQL;
- deployment setting tidak memiliki hard-coded secret atau `DEBUG=True`.

### M1 — Catalog, Offer, dan Tender

Deliverable:

- Product dan Supplier lifecycle;
- Supplier Offer dengan canonical net purchase price;
- Tender root, immutable revision, items, Product snapshot, dan HPS;
- list/detail/create/update sesuai authorization;
- audit untuk seluruh mutation.

Acceptance criteria:

- Admin hanya dapat mengelola Product/Supplier;
- Staff hanya dapat mengelola Offer/Tender;
- inactive master tidak dapat dipakai untuk transaksi baru;
- offer menghasilkan net price yang benar;
- revisi Tender tidak mengubah revision lama.

### M2 — Procurement Result

Deliverable:

- DRAFT result, item, dan supplier allocation;
- shared eligibility policy, validator, dan cost calculator;
- transition DRAFT menjadi VALID dan immutable;
- CUSTOMIZED result baru dari source valid;
- append-only selection history.

Acceptance criteria:

- setiap Tender item dipenuhi tepat sejumlah requested quantity;
- product/offer mismatch ditolak;
- available quantity tidak boleh dilampaui per result;
- total purchase sama pada jalur MANUAL dan CUSTOMIZED untuk allocation sama;
- VALID result tidak dapat diedit;
- hanya result dari Tender revision yang sama dapat dipilih.

### M3 — Optimizer dan Notification

Deliverable:

- OptimizationRun snapshot dan lifecycle;
- queue `optimization`, worker, timeout, retry classification, dan reconciliation;
- `greedy-bounded-v1` dengan deterministic ranking;
- persistence maksimal 20 result valid;
- notification selesai/gagal.

Acceptance criteria:

- hanya satu run PENDING/RUNNING per Tender;
- worker hanya membaca frozen input snapshot;
- hasil pertama meminimalkan total purchase untuk model v1;
- redelivery tidak menggandakan result atau notification;
- nol kandidat valid menghasilkan COMPLETED dengan `result_count=0`;
- kegagalan teknis menampilkan safe error dan diagnostic reference.

### M4 — Bid, Pricing, dan Approval

Deliverable:

- Bid root/revision dan item pricing;
- target margin, actual margin, gross profit, dan HPS feasibility;
- submission snapshot/hash;
- Manager approval/rejection;
- revision baru setelah rejection;
- notification rejection.

Acceptance criteria:

- Bid hanya memakai selected VALID result dari Tender yang sama;
- total pricing sesuai `calc-v1`;
- proposal di atas HPS tidak dapat disubmit;
- hanya DRAFT dapat disubmit;
- hanya Manager dapat membuat keputusan;
- reject wajib memiliki reason;
- concurrent approve/reject menghasilkan tepat satu decision.

### M5 — Signature dan Final Document

Deliverable:

- signature metadata dan optional private image;
- signing policy untuk approving Manager;
- GenerationJob dan queue `documents`;
- template PDF v1, MinIO adapter, checksum, dan versioning;
- authorized PDF download;
- orphan/PENDING reconciliation.

Acceptance criteria:

- Manager lain tidak dapat menandatangani approval;
- Bid tetap SIGNED ketika rendering belum selesai atau gagal;
- FINALIZED hanya setelah object PDF terverifikasi;
- duplicate delivery tidak membuat FinalDocument ganda;
- file lama tidak ditimpa saat regeneration;
- Admin atau anonymous user tidak dapat mengunduh PDF.

### M6 — Demo Hardening

Deliverable:

- seed dan reset command khusus environment demo;
- end-to-end automated smoke test;
- responsive error/empty/loading state;
- structured log dan metrics minimum;
- Docker Compose demo dan backup procedure;
- rehearsal menggunakan `10-demo-scenario.md` dan `11-demo-runbook.md`.

Acceptance criteria:

- fresh setup sampai seed dapat diulang tanpa data ganda;
- primary scenario berhasil tiga kali berturut-turut;
- reset lalu demo ulang menghasilkan outcome yang sama;
- recovery Redis/worker dan PDF failure sudah direhearsal;
- tidak ada P0 defect terbuka.

---

## 6. Critical Path

```text
Custom User/PostgreSQL
  -> Catalog/Offer/Tender
  -> Result Validator/Calculator
  -> Optimizer
  -> Bid Pricing
  -> Approval/Signature
  -> PDF/MinIO
  -> End-to-End Rehearsal
```

Pekerjaan UI dapat berjalan setelah service contract pada slice terkait stabil. PDF tidak perlu menunggu dashboard metrics P1. Signature image dapat ditunda tanpa menghambat signature metadata dan finalization.

---

## 7. Data Demo Canonical

Seed minimum menggunakan identifier stabil agar idempotent:

| Data | Nilai utama |
|---|---|
| Users | 1 Admin, 1 Procurement Staff, 1 Manager |
| Product | Infusion Pump, unit |
| Supplier A | 60 unit, base Rp7.000.000, discount 10%, net Rp6.300.000 |
| Supplier B | 100 unit, base Rp7.500.000, discount 5%, net Rp7.125.000 |
| Supplier C | 100 unit, net Rp7.200.000 |
| Tender | 100 Infusion Pump, HPS Rp800.000.000 |
| Cheapest result | A 60 + B 40 = Rp663.000.000 |
| Target margin | 15% |
| Expected bid | Rp780.000.000 |
| Expected profit | Rp117.000.000 |
| HPS status | Feasible; maksimum margin 17,125% |

Password tidak ditulis di repository atau dokumen. Seed membaca environment atau menghasilkan password untuk disampaikan melalui kanal aman.

---

## 8. Work Item Completion Rule

Satu work item baru selesai bila:

- code dan migration tersedia;
- authorization server-side diterapkan;
- success dan failure path memiliki automated test;
- audit dibuat untuk mutation bisnis;
- error message aman dan dapat ditindaklanjuti;
- query utama tidak memiliki N+1 yang jelas;
- dokumentasi terkait diperbarui jika kontrak berubah.

---

## 9. Risiko dan Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Custom User terlambat dibuat | Migration bisnis sulit diubah | Selesaikan pada M0 sebelum model lain |
| Kalkulasi berbeda antarflow | Angka demo tidak dipercaya | Satu policy + golden calculation tests |
| Worker/Redis gagal saat demo | Optimizer/PDF tertahan | Reconciliation, health check, rehearsal, prepared finalized record |
| MinIO atau renderer gagal | PDF tidak tersedia | Preflight storage/render, retry, fallback PDF yang telah dihasilkan |
| Scope UI melebar | P0 tidak selesai | Freeze P0 dan pindahkan enhancement ke P1 |
| Concurrency hanya diuji di SQLite | Race tidak terdeteksi | Integration test wajib PostgreSQL |
| Data seed berubah | Script demo tidak reproducible | Stable key, idempotent seed, expected totals tetap |
| Secret masuk repository/log | Insiden keamanan | Environment-only secret dan secret scan |

---

## 10. Exit Criteria Demo Build

Build siap masuk rehearsal bila:

- M0 sampai M5 memenuhi acceptance criteria;
- seluruh test wajib pada `09-demo-test-plan.md` lulus;
- primary end-to-end scenario menghasilkan angka canonical dan PDF;
- role yang salah menerima 403/404 pada mutation/download;
- tidak ada migration tertunda;
- queue, database, dan storage health check lulus;
- seed/reset dan backup procedure telah dicoba;
- versi image, schema, algorithm, calculation, dan PDF template tercatat.

