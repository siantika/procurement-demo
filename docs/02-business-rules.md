# Business Rules

## Medical Procurement Bid Optimizer

> Status: Dokumentasi implementasi saat ini<br>
> Terakhir diperbarui: 15 September 2026

## 1. Cakupan dan enforcement

Aturan berikut merangkum perilaku service, policy, model, dan constraint yang tersedia. Angka dihitung dengan Decimal; mutation bisnis memakai transaksi dan audit. Nama fungsi aktual dijelaskan pada [Technical Design](07-technical-design.md).

## 2. Access dan master data

| ID | Aturan yang berlaku |
|---|---|
| BR-ACCESS-001 | Actor bisnis harus authenticated, aktif, mempunyai role valid, serta lolos role guard server-side. Superuser tidak otomatis mempunyai akses role lain. |
| BR-ACCESS-002 | Admin mengelola dan membaca halaman Product/Supplier serta akun Django Admin. |
| BR-ACCESS-003 | Hanya Staff mengelola Offer/Tender/Result/Optimization serta membuat, memberi harga, submit, revise, dan finalize Bid. |
| BR-ACCESS-004 | Hanya Manager approve/reject. Signing dibatasi lagi kepada Manager yang menyetujui revision tersebut. |
| BR-MASTER-001 | Product/Supplier inactive ditolak untuk Offer baru dan Product inactive ditolak untuk Tender revision baru. |
| BR-MASTER-002 | UI menggunakan deactivation, tanpa hard-delete master. Relasi historis ke master menggunakan PROTECT. |
| BR-MASTER-003 | Snapshot historis mempertahankan nama, harga, dan konteks transaksi saat dibuat. |
| BR-MASTER-004 | Product dapat diaktifkan kembali oleh Admin. Supplier belum mempunyai endpoint reactivation. |

Akses detail Bid/job/PDF tersedia bagi Staff dan Manager aktif berdasarkan role; belum ada pembatasan ownership atau tenant untuk objek tersebut. Notifikasi selalu dibatasi kepada recipient sendiri.

## 3. Tender Request

- Root menyimpan `internal_code`, `current_revision_number`, dan `version`.
- Pembuatan Tender/revision memerlukan sedikitnya satu item, line number unik dan positif, Product aktif, requested quantity positif, serta unit.
- Instansi, title, description, reference number, HPS, dan kebutuhan disimpan pada revision; tidak ada master Institution.
- HPS opsional. Jika diisi nilainya harus positif; currency hanya IDR.
- Revision dan item immutable setelah dibuat. Perubahan resmi menghasilkan revision baru; revisi setelah revision pertama wajib alasan dan memeriksa `expected_version`.
- Result/optimizer tidak mengubah kebutuhan Tender. Result dan Bid lama tetap menunjuk revision asal.
- Item menyimpan specification dan description; tidak ada `target_unit_price` atau pencocokan spesifikasi otomatis.

Enforcement: `apps/tender/services.py` dan `models.py`.

## 4. Supplier Offer

- Satu Offer terkait satu Supplier dan satu Product; identity tersebut tidak dapat diganti melalui correction atau supersede.
- Harga dasar positif; diskon 0–100%; harga net dihitung server dengan empat desimal. Diskon 100% dapat dicatat, tetapi Offer berharga net nol tidak eligible.
- `available_quantity` opsional; jika diisi harus positif. Kosong berarti tanpa batas kapasitas pada kalkulasi result ini, bukan stok terverifikasi.
- `valid_from` dan `valid_until` opsional dan inklusif. Jika keduanya diisi, akhir tidak boleh sebelum awal.
- Eligibility memerlukan Offer, Product, dan Supplier aktif; Product cocok; currency IDR; harga net positif; kapasitas positif/kosong; dan tanggal evaluasi dalam masa berlaku.
- Correction hanya untuk Offer tanpa allocation, tanpa referensi optimization snapshot, dan tanpa successor. Koreksi memeriksa version dan menghitung ulang harga net.
- Supersede membuat Offer baru yang menunjuk Offer lama, menonaktifkan Offer lama, dan mempertahankan histori. Satu Offer hanya boleh mempunyai satu successor.
- Deactivation tidak mengubah harga/snapshot transaksi lama.

Enforcement: `apps/sourcing/services.py`, `policies.py`, dan `selectors.py`.

## 5. Procurement Result

- Sumber `MANUAL`, `OPTIMIZER`, atau `CUSTOMIZED`; status hanya `DRAFT` dan `VALID`.
- Manual DRAFT dapat belum memenuhi kebutuhan. Alokasi yang disimpan harus positif, memakai Offer eligible dengan Product sesuai, serta mempunyai line/Offer unik per item.
- Agar VALID, semua Tender item harus tersedia, tanpa item tambahan; snapshot item sesuai kebutuhan; total alokasi per item tepat sama dengan requested quantity; dan harga net snapshot sesuai formula canonical.
- Kapasitas Offer dijumlahkan atas seluruh item dalam satu result, termasuk ketika Product berulang. Total tersebut tidak boleh melewati kapasitas Offer.
- Kapasitas reusable pada result/Bid lain. Optimization sampai finalization tidak mengurangi atau mereservasi quantity secara global.
- Validasi manual/customized memeriksa eligibility Offer live pada tanggal server saat validasi, sedangkan nilai biaya memakai snapshot allocation. Offer yang dinonaktifkan setelah DRAFT tidak lolos validasi.
- Validasi sukses menyimpan total, snapshot schema v1, SHA-256, dan waktu validasi. Result VALID serta children tidak dapat diedit melalui jalur model yang dijaga.
- Customization hanya dari VALID dan membuat DRAFT baru beserta `source_result`. Source tidak ditimpa. Validasi ulang tetap diperlukan.
- Selection hanya menerima VALID. Selection history append-only dengan nomor meningkat per Tender; memilih result yang sedang terpilih mengembalikan selection yang sama.
- Service selection dapat mencatat result revision lama. Create/revise/submit Bid memeriksa lagi bahwa selection berasal dari **Tender revision terbaru**. Tidak ada pointer `selected_result` pada root Tender.

Enforcement: `apps/sourcing/result_services.py`, `validators.py`, `calculations.py`, dan `models.py`.

## 6. Kalkulasi procurement dan Bid

```text
net_purchase_price = base_unit_price × (1 − discount_percent / 100)
allocation_purchase = round_money(allocated_quantity × net_purchase_price)
item_purchase_total = sum(allocation_purchase)
total_purchase = sum(item_purchase_total)

raw_unit_purchase = item_purchase_total / requested_quantity
bid_unit_price = round_price(raw_unit_purchase / (1 − target_margin_percent / 100))
item_bid_total = round_money(requested_quantity × bid_unit_price)
total_bid_value = sum(item_bid_total)
gross_profit = total_bid_value − total_purchase
actual_margin_percent = gross_profit / total_bid_value × 100
```

Harga/unit dan persentase memakai empat desimal; uang memakai dua desimal; quantity disimpan tiga desimal. Pembulatan harga, persentase, dan uang memakai `ROUND_HALF_UP`. `normalize_quantity()` menggunakan Decimal quantize tanpa override rounding. Version kalkulasi `calc-v1`; rounding policy uang `idr-half-up-v1`.

Target margin dinormalisasi menjadi empat desimal, lalu harus `0 <= margin < 100`. Pricing dihitung per item dengan pembulatan bid unit price sebelum item total; formula total purchase dibagi denominator hanya ilustrasi sebelum pembulatan, bukan pengganti kalkulasi per item.

Jika HPS tersedia:

```text
max_margin_percent = (HPS − total_purchase) / HPS × 100
is_hps_feasible = total_bid_value <= HPS
```

Jika HPS kosong, `max_margin_percent` dan `is_hps_feasible` bernilai null; kondisi ini tidak menghalangi submission. Pricing di atas HPS dapat disimpan pada DRAFT agar dapat ditinjau, tetapi tidak dapat disubmit.

## 7. Optimization

- Hanya Staff meminta run atas Tender revision terbaru. Satu run PENDING/RUNNING per root Tender, ditegakkan dengan transaksi dan partial unique constraint.
- Input dibekukan saat request: kebutuhan dan eligible Offer berikut nilai harga, kapasitas, master status, tanggal evaluasi, serta hash.
- Worker mengevaluasi snapshot, tanpa mengganti input dengan harga/status Offer live.
- `greedy-bounded-v1` mengalokasikan Offer berurutan menurut harga net, supplier code, dan Offer ID; alternatif berasal dari skip-vector exploration terbatas.
- Kandidat diurutkan menurut total purchase, jumlah supplier berbeda, lalu candidate identifier. Ranking berlaku untuk kandidat yang ditemukan dan lolos shared validator; tidak menjamin enumerasi seluruh solusi atau minimum jumlah supplier secara global.
- Default: 100 item, 50 eligible Offer per item, maksimal 20 result, exploration limit 2.000, soft limit 240 detik, hard limit 300 detik. Worker Compose concurrency 2.
- Nol kandidat valid berarti COMPLETED dengan result count 0, bukan status NO_SOLUTION atau technical failure.
- Kegagalan teknis/soft timeout menjadi FAILED dengan pesan aman dan diagnostic reference. Retry oleh Staff membuat run baru atas input terbaru dan `retry_of_run_id`; run gagal tidak ditimpa.
- Reconciliation memublikasikan ulang PENDING yang berumur minimal 60 detik. Saat ini tidak mengambil alih run optimization RUNNING yang stale.

## 8. Bid, approval, dan revision

- Bid dibuat dari current selection VALID pada Tender revision terbaru, dengan result hash valid. Root dan revision Bid terpisah.
- Hanya current DRAFT dapat diberi margin atau disubmit. Service memeriksa expected version untuk edit/submit.
- Submission memeriksa selection masih sama, hash/snapshot result cocok, pricing/item dihitung ulang dengan benar, target margin tersedia, dan HPS tidak dilampaui.
- Submission membekukan snapshot/hash, submitter, dan waktu serta mengubah status menjadi WAITING_APPROVAL. Material data dan item sesudah submission immutable; status tetap dapat maju melalui workflow.
- Current WAITING_APPROVAL hanya dapat diputuskan sekali oleh Manager; decision terkait OneToOne ke Bid revision.
- Reject wajib alasan nonkosong setelah trim. Approve menyimpan reason null.
- Revision baru hanya tersedia setelah current revision REJECTED. Revision lama tetap REJECTED; DRAFT baru memakai current selection terbaru dan harus diberi margin kembali.
- Tidak ada edit material atau revision action untuk APPROVED/SIGNED/FINALIZED. Staff dapat membuat Bid baru jika membutuhkan penawaran berbeda.

## 9. Signature dan Final Document

- Signing hanya dari APPROVED oleh Manager yang tercatat pada approval, dengan version dan submission hash valid. Satu signature per revision/decision.
- Gambar signature opsional, diunggah pada setiap signing; tidak ada reusable signature profile. PNG/JPEG diverifikasi dengan Pillow, maksimum 1 MiB, lebar 200–2000 px dan tinggi 80–1000 px.
- Signature menyimpan signer name, actor, waktu, signed submission hash, dan metadata gambar privat bila digunakan; status menjadi SIGNED.
- Staff meminta finalization pada SIGNED atau regeneration pada FINALIZED. Service memeriksa kesesuaian approval, signature, submission hash, serta flag HPS frozen; tidak mengambil HPS/Offer dari Tender/master terbaru.
- Request ganda ketika job aktif mengembalikan job yang sama. Request setelah job terminal membuat document version baru dan nomor baru, termasuk setelah kegagalan.
- PDF dibuat dari frozen finalization snapshot, template v1, A4, masa berlaku 30 hari dari tanggal capture snapshot. Gambar signature dimuat privat dan diverifikasi sebelum disertakan.
- Sebelum FINALIZED, worker menyimpan serta memeriksa PDF magic header, MIME type, size, SHA-256, input hash, dan object key. Batas ukuran PDF 10 MiB.
- Pada finalization pertama, Bid tetap SIGNED selama rendering/gagal. Pada regeneration, Bid tetap FINALIZED dan versi lama tetap tersedia bila job baru gagal.
- PDF dapat diunduh Staff/Manager aktif melalui Django; size/hash/header diperiksa lagi saat download. Admin tidak mempunyai akses download bisnis.
- Document version adalah versi aplikasi. Compose/adapter tidak otomatis mengaktifkan bucket versioning MinIO. Object PDF memakai key terpisah per job/version.

## 10. Notification dan audit

| Event | Recipient |
|---|---|
| BID_WAITING_APPROVAL | Semua Manager aktif |
| OPTIMIZATION_COMPLETED / OPTIMIZATION_FAILED | Requester run |
| BID_APPROVED / BID_REJECTED / BID_SIGNED | Submitter Bid |
| DOCUMENT_COMPLETED / DOCUMENT_FAILED | Requester document job |

Keputusan approve/reject menandai seluruh notifikasi waiting approval terkait revision tersebut sebagai dibaca. Recipient dapat membaca dan menandai notifikasinya sendiri melalui POST; operasi berulang tidak mengubah timestamp baca pertama. Toast muncul dari notifikasi unread pada render halaman, bukan push/WebSocket.

Mutation bisnis menulis AuditEvent dalam transaksi yang sama. Actor name dibekukan; actor null untuk sistem. Model menolak update/delete audit. Perlindungan ini merupakan guard aplikasi; tidak ada database trigger/privilege khusus yang mengubahnya menjadi jaminan terhadap SQL langsung. Reset demo merupakan command khusus yang menggunakan penghapusan langsung terbatas.

Duplicate handling bersifat per operasi: unique decision/signature, active job reuse, task claim, selection reuse, serta unique `(recipient, source_event_id, type)`. Tidak ada tabel `core_idempotency_record`, `IdempotencyConflict`, atau kontrak generic HTTP idempotency key saat ini.
