# Use Cases

## Medical Procurement Bid Optimizer

> Status: Dokumentasi implementasi saat ini<br>
> Terakhir diperbarui: 15 September 2026

## 1. Aktor dan navigasi

Admin menggunakan menu Produk/Supplier, serta Django Admin untuk akun. Staff menggunakan Offer, Tender, Result, Bid, dan tautan Optimization dari dashboard/Tender. Manager menggunakan Approval. Semua pengguna mempunyai dashboard, Notifikasi, Profil, dan logout POST.

Diagram aktor tersedia dalam bentuk [Mermaid](images/use-cases.mmd). Matriks berikut mencatat endpoint yang benar-benar tersedia; `<id>` merupakan UUID.

## 2. Use case yang tersedia

| ID | Aktor | Alur dan halaman utama |
|---|---|---|
| UC-001 | Semua pengguna | GET/POST `/accounts/login/`; GET profil; logout POST `/accounts/logout/` |
| UC-002 | Admin | List/detail/create/edit/deactivate Product; POST reactivate Product melalui `/catalog/products/` |
| UC-003 | Admin | List/detail/create/edit/deactivate Supplier melalui `/catalog/suppliers/` |
| UC-004 | Staff | List/detail/create/correct/supersede/deactivate melalui `/sourcing/offers/` |
| UC-005 | Staff | List/detail/create dan revise Tender melalui `/tenders/` |
| UC-006 | Staff | Pilih Tender revision pada `/sourcing/results/new/`, simpan manual DRAFT, edit allocation, POST validate |
| UC-007 | Staff | POST `/optimization/tenders/<id>/runs/`, lihat detail/status run, retry FAILED |
| UC-008 | Staff | List/detail result; filter result berdasarkan `?tender=<id>`; review ranked result dari run |
| UC-009 | Staff | POST `/sourcing/results/<id>/customize/`, edit DRAFT baru, validasi ulang |
| UC-010 | Staff | POST `/sourcing/results/<id>/select/` untuk result VALID |
| UC-011 | Staff | POST `/bids/tenders/<id>/create/` berdasarkan current selection |
| UC-012 | Staff | GET/POST `/bids/<id>/pricing/` untuk target margin pada current DRAFT |
| UC-013 | Staff | POST `/bids/<id>/submit/` dengan expected version |
| UC-014 | Manager | Review Bid dari `/approval/`, POST `/approval/<revision_id>/approve/` |
| UC-015 | Manager | GET reject form, POST `/approval/<revision_id>/reject/submit/` dengan alasan |
| UC-016 | Staff | POST `/bids/<id>/revise/` pada REJECTED; beri margin dan submit revision baru |
| UC-017 | Approving Manager | GET/POST `/signatures/<revision_id>/sign/`, gambar signature opsional |
| UC-018 | Staff | POST `/documents/bids/<revision_id>/finalize/`, termasuk membuat versi PDF baru pada FINALIZED |
| UC-019 | Staff/Manager | GET `/documents/<document_id>/download/` setelah FinalDocument tersedia |

Admin dapat mengelola akun melalui `/admin/accounts/user/`, tanpa self-registration atau invitation flow. Profil sendiri hanya menampilkan informasi account.

## 3. Sourcing manual dan customization

1. Staff memilih Tender revision dan memasukkan allocation positif dari Offer eligible.
2. Simpan DRAFT. DRAFT belum harus memenuhi seluruh quantity.
3. Perbaiki allocation melalui halaman edit, lalu pilih validasi.
4. Server memeriksa semua kebutuhan tepat terpenuhi, Product sesuai, harga canonical, eligibility live, dan total kapasitas Offer dalam result.
5. Jika gagal, perbaiki DRAFT; jika sukses, result menjadi VALID dan detail memakai historical snapshot.
6. Pilih result secara eksplisit. Untuk mengubah VALID, gunakan customization yang membuat DRAFT baru dengan lineage ke sumber.

Halaman list dan detail memungkinkan review alternatif, tanpa halaman perbandingan berdampingan yang terpisah. Manager mereview rincian pada Bid; halaman Result hanya Staff.

## 4. Optimization

1. Staff membuka Tender terbaru dan menekan aksi optimization.
2. Server menolak jika Tender masih mempunyai active run atau batas input dilampaui; selain itu snapshot dibekukan dan run dibuat PENDING.
3. Halaman detail run menampilkan status, actor, version algoritma, input hash, timestamps, ranked results, dan reason code candidate rejection.
4. JavaScript memanggil endpoint status; halaman diperbarui setelah run terminal.
5. COMPLETED dapat mempunyai nol result. Staff memeriksa kapasitas/eligibility atau menyusun result manual; tidak ada solusi otomatis bila input tidak dapat dipenuhi.
6. FAILED menyediakan pesan aman, diagnostic reference, dan tombol retry. Retry menghasilkan run baru menggunakan input terbaru, bukan melanjutkan snapshot lama.

## 5. Bid dan Manager decision

1. Staff memilih VALID result, lalu membuat Bid DRAFT dari Tender.
2. Tetapkan target margin; halaman menampilkan purchase, bid value, gross profit, actual margin, dan HPS feasibility.
3. Staff submit. Server menolak jika selection/revision berubah atau pricing/hash/HPS tidak valid.
4. Semua Manager aktif memperoleh waiting approval notification.
5. `/approval/` menampilkan WAITING_APPROVAL serta APPROVED/SIGNED/FINALIZED yang disetujui oleh Manager tersebut, agar pekerjaan dapat diteruskan setelah approval.
6. Manager membuka detail Bid dan approve atau reject dengan reason. Keputusan tunggal menjadi immutable, dan waiting notifications semua Manager untuk revision itu ditandai read.
7. Submitter menerima notifikasi keputusan. Setelah reject, Staff membuat revision DRAFT baru dari current selection, menetapkan margin kembali, dan submit ulang.

Staff dan Manager dapat membuka detail Bid/revision; daftar `/bids/` khusus Staff. Revision history tersedia pada detail Bid. Tidak ada halaman timeline AuditEvent tersendiri.

## 6. Signing, finalization, dan regeneration

1. Manager yang menyetujui membuka halaman signing pada APPROVED.
2. Konfirmasi signing; opsional upload gambar PNG/JPEG. Server memeriksa approver, expected version, dan submission hash.
3. Status menjadi SIGNED dan submitter menerima notifikasi.
4. Staff menekan **Buat dokumen final**. Job aktif ditampilkan pada detail Bid dan `/documents/jobs/<id>/`.
5. Worker render/upload/verify; pada finalization pertama status Bid tetap SIGNED sampai sukses.
6. Job COMPLETED menghasilkan FINALIZED. Staff/Manager dapat membuka detail job serta download PDF dengan integrity check.
7. Pada FINALIZED, Staff dapat menekan **Buat versi PDF baru**. Job/version/nomor baru dibuat dan file lama tetap tersedia.
8. Setelah kegagalan terminal, Staff meminta pembuatan dokumen kembali; tidak ada endpoint document retry terpisah. Regeneration yang gagal tidak membatalkan FinalDocument lama.

## 7. Notifikasi dan exception umum

- `/notifications/` menampilkan recipient sendiri; POST `<id>/read/` menandai read.
- Toast unread mempunyai tautan ke run, Bid revision, atau job. Menutup toast hanya menyembunyikan tampilan, bukan menandai notifikasi read di database.
- Anonymous diarahkan ke login pada business page. Role salah mendapat 403 dari server.
- Form invalid ditampilkan kembali atau ditangani dengan message/redirect sesuai view.
- Version stale dan illegal transition pada sejumlah mutation mengembalikan 409; view lain menggunakan message dan redirect. Tidak ada format error API seragam.
- Download gagal jika status/integritas/storage tidak valid; tidak ada public MinIO URL atau presigned-download flow.

## 8. Traceability

UC-001 merealisasikan PRD-001; UC-002–004 PRD-002; UC-005 PRD-003; UC-006 PRD-004; UC-007 PRD-005; UC-008–010 PRD-006; UC-011–013 PRD-008; UC-014–016 PRD-009; UC-017 PRD-010; UC-018–019 PRD-011. Notifikasi PRD-007 dan snapshot/audit PRD-012 mendukung workflow terkait.

Detail enforcement terdapat pada [Business Rules](02-business-rules.md), dan perintah operasional terdapat pada [Demo Runbook](11-demo-runbook.md).
