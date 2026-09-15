# Panduan Dokumentasi

## Medical Procurement Bid Optimizer

> Status: Dokumentasi implementasi saat ini<br>
> Terakhir diperbarui: 15 September 2026

Dokumentasi ini menjelaskan fitur dan perilaku yang tersedia dalam repository saat ini. Kode aplikasi, konfigurasi, dan migration menjadi sumber pemeriksaan; dokumentasi mengikuti implementasi, bukan daftar fitur yang harus dibangun.

| Dokumen | Isi |
|---|---|
| [01 — Product Overview](01-product-overview.md) | Fitur, pengguna, dan batas produk |
| [02 — Business Rules](02-business-rules.md) | Aturan yang ditegakkan oleh kode saat ini |
| [03 — Use Cases](03-use-cases.md) | Alur pengguna dan akses halaman |
| [04 — Domain Model](04-domain-model.md) | Konsep, relasi, lifecycle, dan snapshot |
| [05 — System Architecture](05-system-architecture.md) | Komponen runtime dan deployment yang tersedia |
| [06 — Data Model](06-data-model.md) | Tabel, kolom, constraint, dan indeks model Django |
| [07 — Technical Design](07-technical-design.md) | Service, kalkulasi, job, dan keamanan |
| [08 — Demo Implementation Plan](08-demo-implementation-plan.md) | Pemetaan milestone ke implementasi yang sudah ada |
| [09 — Demo Test Plan](09-demo-test-plan.md) | Suite yang tersedia dan cara verifikasi |
| [10 — Demo Scenario](10-demo-scenario.md) | Skenario presentasi sesuai UI saat ini |
| [11 — Demo Runbook](11-demo-runbook.md) | Setup, operasi, recovery, dan backup |
| [12 — M6 Operations](12-m6-operations.md) | Ringkasan perintah operasional |
| [Design System](design-system.md) | Token, komponen UI, dan aturan perubahan frontend |
| [DBML](schema.dbml) | Representasi 23 tabel aplikasi dari model Django |

## Sumber pemeriksaan

- `apps/*/models.py`, `choices.py`, dan `migrations/`: schema serta controlled values.
- `apps/*/services.py`, `apps/sourcing/result_services.py`, policy, dan calculator: aturan bisnis.
- `apps/*/urls.py`, `views.py`, serta `templates/`: akses dan alur pengguna.
- `config/settings/`, `compose.yaml`, `Makefile`, `Dockerfile`, dan `scripts/`: konfigurasi serta operasi.
- `apps/*/test*.py` dan `config/tests/`: cakupan automated test yang tersedia.

Tanggal pembaruan menunjukkan audit dokumentasi, bukan bukti deployment atau kelulusan rehearsal di VPS. Lihat dokumen 09 untuk membedakan automated test dari pemeriksaan manual dan integrasi layanan nyata.
