# Demo Implementation Plan — Status Implementasi

## Medical Procurement Bid Optimizer

> Status: Dokumentasi implementasi saat ini<br>
> Terakhir diperbarui: 15 September 2026

## 1. Tujuan dan status dokumen

Dokumen ini memetakan milestone demo ke kode yang sudah tersedia. Ini bukan backlog yang mengharuskan fitur tambahan. Foundation dan business modules telah diimplementasikan; local/test/demo menggunakan PostgreSQL, bukan SQLite.

```text
Catalog/Offer/Tender -> Result manual atau optimization -> Selection
  -> Bid pricing/submission -> Manager approval/signature -> Final PDF
```

## 2. Pemetaan milestone

| Milestone | Implementasi yang tersedia | Bukti kode |
|---|---|---|
| M0 — Foundation | Python 3.12/Django 6, PostgreSQL, UUID User, tiga role, login/logout/profile/dashboard, audit, correlation ID, environment settings, health | `config/`, `apps/accounts/`, `apps/audit/`, `apps/core/` |
| M1 — Catalog/Offer/Tender | Product/Supplier lifecycle, Product reactivation, Offer price/discount/validity/capacity/correction/supersede, immutable Tender revision/item | `apps/catalog/`, `apps/sourcing/services.py`, `apps/tender/` |
| M2 — Result | Manual DRAFT/editor, shared validator/calculator, VALID snapshot/immutability, customization, selection sequence | `apps/sourcing/result_services.py`, `validators.py`, `calculations.py` |
| M3 — Optimization/Notification | Snapshot run, greedy bounded ranking, task claim, completion/failure/retry run, PENDING reconciliation, notifications/toasts | `apps/optimization/`, `apps/notifications/` |
| M4 — Bid/Approval | Selected result, margin/HPS/pricing, submission hash, single decision, rejection revision, waiting/decision notifications | `apps/bids/`, `apps/approval/` |
| M5 — Signature/Document | Metadata dan gambar signature opsional, private PDF worker, nomor/versi/checksum, authorized download, regeneration UI, stale document recovery | `apps/signatures/`, `apps/documents/` |
| M6 — Operations | Seed/reset/smoke commands, JSON logs/metrics, Compose/Dockerfile, local process helper, VPS preflight/Nginx example, backup script | `apps/accounts/management/commands/`, `Makefile`, `scripts/`, `deploy/` |

Tersedianya kode tidak sama dengan klaim semua acceptance test/rehearsal telah lulus. Status eksekusi dicatat operator melalui dokumen 09–11.

## 3. Batas yang masih berlaku

| Area | Kondisi saat ini |
|---|---|
| Optimizer | Bounded greedy search, maksimal 20 hasil default; tidak mengevaluasi semua solusi |
| Recovery optimization | Republish PENDING; RUNNING stale belum dipulihkan otomatis |
| Recovery document | Memeriksa object untuk stale job yang dikenal; belum ada general orphan scanner |
| Idempotency | Guard per operasi; tidak ada shared HTTP idempotency record/key |
| User interface | Form/list/detail dan filter Tender pada result; belum ada pagination/pencarian umum atau halaman comparison/timeline audit terpisah |
| Signature | Gambar sudah tersedia pada signing; belum ada reusable signature profile |
| Monitoring | Health/metrics/log tersedia; belum ada OTel/Prometheus/Grafana/Telegram stack |
| Storage | Document version/key terpisah; MinIO bucket versioning tidak otomatis aktif |
| Delivery | Compose serta Nginx/preflight example tersedia; tidak ada workflow CI/CD checked-in |
| Backup | Dump DB dan mirror object current lokal; enkripsi/off-host copy/restore belum otomatis |

Tidak ada tambahan scope business seperti stok, kontrak, payment, multi-tenancy, atau portal integration.

## 4. Data demo canonical

`seed_demo` membuat atau memverifikasi:

| Data | Nilai |
|---|---|
| Akun | `demo-admin`, `demo-staff`, `demo-manager` |
| Product | `PUMP-001`, Infusion Pump, unit |
| Suppliers | `SUP-A`, `SUP-B`, `SUP-C` |
| Offer A | `DEMO-OFFER-A`, base Rp7 juta, diskon 10%, net Rp6,3 juta, 60 unit |
| Offer B | `DEMO-OFFER-B`, base Rp7,5 juta, diskon 5%, net Rp7,125 juta, 100 unit |
| Offer C | `DEMO-OFFER-C`, base/net Rp7,2 juta, diskon 0%, 100 unit |
| Validity Offer | 1 Januari 2026–31 Desember 2030 |
| Tender | `DEMO-TENDER-001`, Rumah Sakit Demo, 100 unit, HPS Rp800 juta |
| Manual result | VALID, A60 + B40, total purchase Rp663 juta |
| Margin skenario | 15% → Bid Rp780 juta, gross profit Rp117 juta; max HPS margin 17,125% |

Seed tidak otomatis memilih result, menjalankan optimizer, membuat Bid, approval, signature, atau PDF. Password ketiga akun wajib berasal dari `DEMO_ADMIN_PASSWORD`, `DEMO_STAFF_PASSWORD`, `DEMO_MANAGER_PASSWORD`; command tidak menghasilkan/mencetak password. Seed memperbarui akun canonical bila perlu, tetapi menolak business data yang menyimpang dari nilai yang diperiksa.

## 5. Verifikasi demo

Gunakan automated suite pada [09 — Test Plan](09-demo-test-plan.md), alur UI pada [10 — Scenario](10-demo-scenario.md), dan command aktual pada [11 — Runbook](11-demo-runbook.md). `smoke_demo --runs 3` menjalankan service flow tiga kali, membuat record baru pada setiap pengulangan tanpa reset otomatis, dan memverifikasi purchase/Bid/PDF download integrity.
