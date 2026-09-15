# Demo Scenario

## Medical Procurement Bid Optimizer

> Durasi target: 12–15 menit
> Skenario: Optimasi pengadaan Infusion Pump sampai Final PDF
> Terakhir diperbarui: 15 September 2026

---

## 1. Pesan Utama

Demo harus menunjukkan bahwa sistem:

- mempertahankan kebutuhan Tender sebagai source of truth;
- membandingkan kombinasi Supplier Offer secara transparan;
- memisahkan procurement cost dari bid pricing;
- mempertahankan keputusan manusia melalui selection dan approval;
- menghasilkan Bid Proposal final yang versioned dan dapat diaudit.

Jangan menghabiskan waktu pada CRUD yang berulang. Fokus pada keputusan bisnis dan jejak datanya.

---

## 2. Persona

| Persona | Peran dalam demo |
|---|---|
| Procurement Staff | Menyiapkan Offer/Tender, memilih result, membuat dan submit Bid, lalu finalize |
| Manager | Review, approve, dan sign |
| Admin | Ditunjukkan singkat hanya bila perlu menjelaskan master data |

Akun seed adalah `demo-staff`, `demo-manager`, dan `demo-admin`. Password wajib dari environment seed dan tidak dimasukkan ke dokumen atau slide.

---

## 3. Data Cerita

Sebuah rumah sakit membutuhkan 100 unit Infusion Pump dengan HPS Rp800.000.000.

| Supplier | Kapasitas | Harga dasar | Diskon | Harga net |
|---|---:|---:|---:|---:|
| Supplier A | 60 | Rp7.000.000 | 10% | Rp6.300.000 |
| Supplier B | 100 | Rp7.500.000 | 5% | Rp7.125.000 |
| Supplier C | 100 | Rp7.200.000 | 0% | Rp7.200.000 |

Expected recommendation:

```text
Supplier A: 60 x Rp6.300.000 = Rp378.000.000
Supplier B: 40 x Rp7.125.000 = Rp285.000.000
Total procurement             = Rp663.000.000
```

Dengan target margin 15%:

```text
Total Bid     = Rp663.000.000 / 0,85 = Rp780.000.000
Gross Profit  = Rp117.000.000
HPS           = Rp800.000.000
Status        = Feasible
```

---

## 4. Pre-Demo State

Sebelum audiens hadir:

- seluruh service sehat;
- Product, Supplier, Offer, Tender, dan manual VALID result canonical sudah di-seed; seed tidak membuat optimizer run, Bid, atau PDF;
- belum ada active OptimizationRun untuk Tender demo;
- browser Staff berada di halaman login atau dashboard;
- browser/profile terpisah untuk Manager sudah siap tetapi belum login;
- queue kosong;
- satu PDF cadangan dari build yang sama tersedia privat;
- zoom browser dan resolusi proyektor sudah diuji.

Master data boleh sudah tersedia agar waktu digunakan untuk alur bernilai tinggi. Presenter cukup membuka detail Offer dan Tender untuk membuktikan input.

---

## 5. Primary Demo Flow

Durasi per langkah berikut adalah perkiraan. Jika seluruh langkah memakai batas atas, total dapat melebihi 15 menit; ringkas review input dan riwayat sesuai waktu presentasi.

### Step 1 — Login sebagai Procurement Staff

Durasi: 1 menit.

Action:

1. Login sebagai Staff.
2. Tunjukkan dashboard dan menu yang tersedia.
3. Jelaskan bahwa Product/Supplier administration tidak tersedia untuk Staff.

Expected:

- login berhasil;
- navigation hanya memuat capability Staff;
- tidak ada credential terlihat pada layar.

Talking point: authorization diperiksa kembali di server, bukan hanya menyembunyikan menu.

### Step 2 — Tinjau Supplier Offer dan Tender

Durasi: 2 menit.

Action:

1. Buka daftar Offer dan tunjukkan Product Infusion Pump dari informasi Offer. Halaman katalog Product hanya untuk Admin.
2. Buka tiga Supplier Offer dan tunjukkan harga net/ketersediaan.
3. Buka Tender dan tunjukkan quantity 100 serta HPS Rp800 juta.

Expected:

- net price A Rp6,3 juta dan B Rp7,125 juta;
- requirement Tender tidak berubah saat optimasi;
- revision dan timestamp sumber terlihat.

Talking point: available quantity adalah batas per result, bukan pengurangan stok global.

### Step 3 — Jalankan Optimizer

Durasi: 2 menit.

Action:

1. Klik Run Optimization.
2. Tunjukkan status PENDING/RUNNING.
3. Tunggu sampai COMPLETED.
4. Buka daftar ranked result.

Expected:

- hanya satu active run;
- run menyimpan waktu, actor, algorithm version, dan input hash;
- rank 1 adalah Supplier A 60 + Supplier B 40;
- total purchase Rp663 juta;
- alternatif, jika tersedia, berada di bawah rank 1 dengan biaya tidak lebih rendah.

Talking point: optimizer memberi rekomendasi sourcing; ia tidak memilih hasil atau menetapkan harga Bid.

### Step 4 — Pilih Result

Durasi: 1 menit.

Action:

1. Bandingkan rank 1 dengan alternatif.
2. Pilih rank 1.
3. Tunjukkan selected result pada detail Result/Tender. Audit selection disimpan di model, tanpa halaman audit terpisah.

Expected:

- selection dilakukan eksplisit oleh Staff;
- hanya result VALID dari Tender yang sama dapat dipilih;
- result optimizer tetap immutable.

### Step 5 — Buat dan Price Bid Proposal

Durasi: 2 menit.

Action:

1. Buat Bid dari selected result.
2. Masukkan target margin 15%.
3. Tinjau purchase, total Bid, gross profit, actual margin, dan HPS.
4. Submit untuk approval.

Expected:

- purchase Rp663 juta;
- Bid Rp780 juta;
- gross profit Rp117 juta;
- actual margin 15%;
- status HPS feasible;
- Bid berubah DRAFT menjadi WAITING_APPROVAL;
- submission snapshot/hash tercatat.

Talking point: harga penawaran dihitung setelah sourcing dipilih; formula dan rounding memiliki version.

### Step 6 — Manager Approve dan Sign

Durasi: 2 menit.

Action:

1. Pindah ke browser/profile Manager.
2. Buka approval queue dan review proposal.
3. Approve proposal.
4. Sign proposal yang sama.

Expected:

- queue menampilkan WAITING_APPROVAL dan APPROVED/SIGNED/FINALIZED yang disetujui Manager tersebut;
- approval mengubah status menjadi APPROVED;
- hanya approving Manager dapat sign;
- signature mengubah status menjadi SIGNED;
- actor, timestamp, dan submission hash dapat ditelusuri.

Talking point: approval dan signature adalah keputusan manusia yang append-only.

### Step 7 — Finalize dan Download PDF

Durasi: 2–3 menit.

Action:

1. Kembali ke Staff.
2. Refresh proposal dan klik Finalize.
3. Tunjukkan job PENDING/RUNNING sementara Bid tetap SIGNED.
4. Tunggu job COMPLETED dan status FINALIZED.
5. Download serta buka PDF.

Expected:

- PDF berisi nomor/revision, instansi, item, pricing, approval, signer, validity, dan document version;
- Bid hanya FINALIZED setelah PDF tersimpan dan terverifikasi;
- checksum dan version tersedia pada detail document;
- download berhasil untuk Staff/Manager berizin.

Talking point: PDF lama tetap tersedia; tombol "Buat versi PDF baru" pada FINALIZED menghasilkan job, nomor, version, dan object baru. Jika regeneration gagal, Bid tetap FINALIZED dan versi lama tetap dapat diunduh.

### Step 8 — Tinjau Riwayat dan Metadata

Durasi: 1 menit.

Action:

1. Buka detail Bid, riwayat revision, dan daftar generation job.
2. Tunjukkan status, submission hash, Manager decision, signature, serta nomor/version/checksum PDF.
3. Jelaskan bahwa AuditEvent disimpan oleh sistem; belum ada halaman timeline audit tersendiri.

Expected:

- riwayat revision/job, actor keputusan/signing, timestamp, dan status dapat dilihat pada halaman yang tersedia;
- snapshot historis tetap terpisah dari master current.

Penutup: sistem membantu mencari procurement cost efisien tanpa mengambil alih keputusan Staff dan Manager.

---

## 6. Optional Branches

Gunakan hanya jika ada waktu atau audiens bertanya.

### HPS Tidak Feasible

Gunakan Bid DRAFT tersendiri sebelum submission. Masukkan margin 18% agar Bid melebihi HPS; UI menandai tidak feasible dan server menolak submission. Bid yang sudah disubmit/finalized tidak dapat diubah margin-nya.

### Rejection dan Revision

Gunakan Bid WAITING_APPROVAL tersendiri. Manager reject dengan alasan. Staff menerima notification lalu membuat revision DRAFT baru dari current selection, menetapkan margin kembali, dan submit; submission lama tetap ada.

### Permission Proof

Buka mutation URL dengan role yang salah dan tunjukkan 403/404 tanpa detail sensitif.

### Historical Integrity

Dengan session Admin terpisah, ubah nama Product current lalu buka Bid/PDF lama. Snapshot lama tetap menampilkan nilai saat transaksi. Lakukan setelah primary flow karena seed memverifikasi nama Product canonical dan menolak mismatch.

---

## 7. Presenter Guardrails

- Jangan mengubah seed angka ketika demo sedang berjalan.
- Jangan membuka Django Admin, MinIO Console, terminal berisi environment, atau operational log yang mungkin sensitif di depan audiens.
- Jangan menjanjikan submission portal, stock reservation, atau production SLA; ketiganya di luar scope.
- Jangan menyebut ranked result sebagai enumerasi seluruh solusi atau optimum global untuk semua variasi input. Engine menggunakan bounded deterministic exploration; ranking berlaku pada kandidat yang ditemukan. Golden case rank 1 adalah A60+B40.
- Jika background job memerlukan waktu, jelaskan frozen snapshot dan asynchronous processing; jangan klik action berulang kali.

---

## 8. Fallback

| Gangguan | Respons presenter |
|---|---|
| Optimizer masih berjalan | Tunjukkan run pre-generated dari snapshot/data yang sama |
| Optimizer gagal | Tunjukkan safe error lalu gunakan manual VALID result canonical |
| Manager session bermasalah | Login ulang pada browser profile terpisah |
| PDF generation gagal | Jelaskan Bid tetap SIGNED; buka FinalDocument cadangan dari build yang sama |
| Internet eksternal gagal | Demo tetap berjalan pada endpoint lokal/VPS; tidak bergantung resource remote |
| Proyektor lambat | Gunakan zoom/layout yang sudah dipreflight dan hindari membuka dashboard berat |

Fallback tidak boleh memalsukan status. Presenter menyatakan dengan jelas bila memakai record yang dibuat saat rehearsal.

---

## 9. Success Criteria

Demo berhasil bila audiens dapat melihat:

- kebutuhan Tender 100 unit tidak berubah;
- optimizer merekomendasikan A60 + B40 dengan total Rp663 juta;
- Staff secara eksplisit memilih result;
- margin 15% menghasilkan Bid Rp780 juta dan feasible terhadap HPS;
- Manager approve dan sign;
- Staff menghasilkan serta mengunduh PDF final;
- seluruh keputusan memiliki actor, status, timestamp, snapshot/hash, dan audit trail.
