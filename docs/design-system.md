# Regulatory Ledger Design System

> Produk: Medical Procurement Bid Optimizer<br>
> Status: Aturan visual implementasi<br>
> Terakhir diperbarui: 16 September 2026

## 1. Arah visual

Antarmuka menggunakan bahasa visual **Regulatory Ledger**: formal, presisi,
dan dapat diaudit. Referensinya adalah lembar kendali dokumen, register tender,
sertifikat, dan berkas keputusan—bukan dashboard SaaS modern.

Trust dan traceability harus terlihat pada struktur halaman. Revision,
snapshot, actor, timestamp, version, serta hash bukan metadata sekunder;
semuanya merupakan bukti kendali yang perlu mudah ditemukan dan dibandingkan.

Prinsip utama:

1. tampilkan informasi seperti record resmi, bukan kumpulan widget dekoratif;
2. gunakan garis, urutan, label, dan tipografi untuk membangun hierarki;
3. pertahankan data historis sebagai elemen visual yang jelas;
4. bedakan aksi operasional dari keputusan yang tidak dapat dibatalkan;
5. jangan memakai dekorasi yang tidak menjelaskan status atau struktur.

## 2. Fondasi token

Token canonical berada di `apps/accounts/static/css/app.css`.

| Token | Nilai | Fungsi |
| --- | --- | --- |
| `--paper` | `#F7F5F0` | Latar halaman dan bidang dokumen |
| `--surface` | `#FFFFFF` | Panel, tabel, dan form |
| `--border` | `#D8D4C8` | Hairline border dan pemisah record |
| `--primary` | `#1C3D3A` | Navigasi, heading, tombol utama |
| `--accent` | `#B8860B` | Approval, signing, dan aksi kritis |
| `--danger` | `#8B2E2E` | Rejection, failure, dan destructive action |
| `--ink` | `#172321` | Teks utama |
| `--muted` | `#66645D` | Teks pendukung |

Ketentuan:

- tidak ada `box-shadow` pada komponen apa pun;
- radius hanya `2px`, `3px`, atau maksimal `4px`;
- surface menggunakan putih dengan border `1px`;
- warna baru hanya boleh ditambahkan jika memiliki fungsi semantik baru;
- opacity tidak boleh menjadi satu-satunya pembeda status.

## 3. Tipografi

Tidak ada font CDN. Seluruh halaman harus tetap berfungsi tanpa koneksi
eksternal.

- Heading: Georgia, Cambria, `Times New Roman`, serif.
- Body dan label: system sans-serif.
- ID tender, nomor proposal, version, hash, checksum, dan diagnostic reference:
  `ui-monospace`, SFMono-Regular, Consolas, monospace.
- Angka finansial dan kuantitas: `font-variant-numeric: tabular-nums`.

Hierarki:

- hanya satu `h1` per halaman;
- `h1` terasa seperti judul dokumen, bukan hero marketing;
- `h2` menandai bagian record;
- `.eyebrow` menjadi klasifikasi dokumen singkat;
- label form dan header tabel menggunakan sans-serif, ukuran kecil, dan huruf
  kapital dengan tracking terukur;
- jangan membuat heading, label, dan data tabel berukuran hampir sama.

## 4. Shell aplikasi

`templates/base.html` adalah shell canonical.

- Header memakai bidang hijau tua tanpa blur atau shadow.
- Identitas produk berbentuk wordmark dan tanda `MP`, bukan app icon rounded.
- Label `INTERNAL / CONTROLLED RECORD` menegaskan klasifikasi sistem.
- Navigasi mengikuti role dan tetap mempertahankan logout `POST` dengan CSRF.
- Navigasi memakai ikon garis lokal bersama label teks; ikon tidak pernah menjadi
  satu-satunya petunjuk fungsi.
- Lebar konten maksimum `1180px`; pada layar sempit navigasi boleh wrap.

## 5. Surface dan layout

`.card` adalah lembar record putih dengan hairline border. Card tidak memiliki
shadow. Radius maksimum `4px`.

Perbedaan hierarki dibuat dengan:

- ketebalan atau posisi border;
- label klasifikasi;
- nomor urut;
- kepadatan ruang;
- warna semantik yang sudah ditetapkan.

Jangan membedakan card hanya dengan radius dan shadow.

## 6. Dashboard register

Dashboard adalah indeks modul, bukan galeri tile.

- `.module-grid` menggunakan counter urut `01`, `02`, `03`, dan seterusnya;
- setiap fitur mempunyai ikon garis spesifik di dalam label nomor register;
- modul utama memakai rule hijau tua;
- modul yang memerlukan tindakan memakai accent emas dan label jumlah;
- modul tenang tetap datar dengan hairline border;
- hover hanya memperkuat border atau underline, tanpa gerakan naik.

Nomor urut hanya dipakai bila urutannya benar-benar bermakna dalam alur kerja
atau register.

Ikon mengikuti grid `24 × 24`, memakai stroke `currentColor`, sudut tegas, dan
tanpa bidang berbayang. Ikon bersifat pendamping: nama fitur tetap ditulis sebagai
teks. Jangan menggunakan emoji, ikon berwarna acak, atau library/CDN eksternal.

## 7. Status workflow

Status selalu menggunakan kombinasi **ikon + warna + label teks eksplisit**.
Gunakan `.status-badge` dan class dari filter `status_class`.

| State | Class | Tanda | Arti |
| --- | --- | --- | --- |
| Draft | `.status-draft` | `○` | Belum dikunci |
| Submitted/Review/Pending | `.status-review` | `→` | Sedang menunggu atau diproses |
| Approved/Valid/Completed | `.status-approved` | `✓` | Lolos keputusan atau validasi |
| Rejected/Failed | `.status-rejected` | `×` | Ditolak atau gagal |
| Signed | `.status-signed` | `§` | Signature tercatat |
| Finalized | `.status-finalized` | `■` | Artefak final tersedia |

Badge berbentuk label persegi, bukan pill. Jangan mengandalkan warna saja.
Role menggunakan `.role-badge`; version menggunakan `.version-badge` monospace.

## 8. Revision, snapshot, dan integrity

Traceability adalah pembeda produk dan harus hadir secara visual:

- `.version-timeline` menampilkan seluruh revision dengan node, actor, alasan,
  timestamp, dan revision aktif;
- `.version-badge` menampilkan nomor revision di dekat identitas record;
- `.workflow-track` memakai urutan nyata `01–05` untuk Draft, Review,
  Approved, Signed, dan Final;
- `.integrity-panel` menampilkan jenis hash, penjelasan snapshot, dan nilai hash;
- `.hash-value` wajib monospace serta dapat wrap tanpa memotong isi.

Hash tidak boleh menjadi link samar atau disembunyikan di bagian footer.

## 9. Tabel ledger

Gunakan `.table-card`, `.table-wrap`, dan `.data-table`.

- kolom teks rata kiri;
- kolom harga, kapasitas, quantity, rank, version, dan total memakai
  `.numeric-cell`, rata kanan, dan `tabular-nums`;
- header tabel mempunyai rule atas/bawah yang tegas;
- baris dipisahkan hairline border;
- hover tidak boleh mengubah layout;
- tabel tetap dapat digeser horizontal pada layar sempit.

## 10. Form dan tombol

Form memakai `.stack-form` dan `.field-group`.

- setiap input mempunyai label yang terhubung;
- field berbentuk persegi dengan radius maksimal `3px`;
- focus state terlihat melalui outline;
- error muncul dekat field dan menggunakan teks, bukan warna saja;
- satu area form hanya mempunyai satu aksi utama dominan.

Tombol:

- `.button-primary`: aksi operasional utama berwarna hijau tua;
- `.button-secondary`: aksi netral dengan border;
- `.button-danger`: rejection atau destructive action;
- tombol utama di dalam `.irreversible-action`: accent emas karena merupakan
  keputusan kritis.

## 11. Keputusan permanen

Approval dan signing bukan submit form biasa.

- gunakan `.irreversible-action` dengan border emas;
- sertakan penjelasan bahwa keputusan masuk audit trail;
- tampilkan revision dan snapshot yang sedang diputuskan;
- penolakan memakai `.irreversible-action-danger` serta alasan wajib;
- confirmation checkbox harus tetap mempunyai label.

## 12. Empty state dan pesan

`.empty-state` harus ditulis dari perspektif pekerjaan procurement.

Contoh:

- Tender kosong: kebutuhan instansi belum dicatat;
- Result kosong: belum ada alternatif sourcing;
- Bid kosong: belum ada result valid yang dipilih;
- Approval kosong: antrean keputusan sudah bersih.

Hindari “No data found” atau “Belum ada data” tanpa arahan langkah berikutnya.

Alert menggunakan border dan label eksplisit. Toast menggunakan panel datar
dengan rule status; tidak memakai shadow.

## 13. Responsivitas dan aksesibilitas

- layout harus terbaca sampai lebar `320px`;
- navigation dapat wrap tanpa menabrak label lain;
- action group menjadi vertikal pada layar kecil;
- detail grid berubah menjadi satu kolom;
- workflow sequence tetap terbaca sebagai urutan;
- focus state harus terlihat untuk link, button, dan field;
- elemen dekoratif menggunakan `aria-hidden="true"`;
- landmark `header`, `nav`, dan `main` wajib dipertahankan;
- pesan error memakai `role="alert"` bila memerlukan perhatian langsung.

## 14. PDF

PDF tetap menggunakan `templates/documents/pdf_v1.html` dan
`apps/documents/static/documents/css/pdf_v1.css`. Web design system tidak boleh
disalin otomatis ke PDF karena PDF mempunyai kebutuhan A4 dan renderer sendiri.

## 15. Definition of done

1. Tidak ada box-shadow, gradient, blur, atau radius lebih dari `4px`.
2. Warna mengikuti token Regulatory Ledger.
3. Status memakai ikon, warna, dan label teks.
4. Revision/snapshot/hash terlihat pada detail yang relevan.
5. Angka tabel rata kanan dengan tabular numerals.
6. Tampilan diperiksa pada desktop, mobile, dan lebar `320px`.
7. Login normal/error, dashboard, profile panjang, Tender, dan Bid diperiksa.
8. Tidak ada inline CSS atau dependency frontend baru.
9. Django system check dan test terkait lulus.

```bash
uv run ruff check <file-yang-diubah>
uv run python manage.py check --settings=config.settings.test
uv run python manage.py test apps.accounts.tests \
    --settings=config.settings.test
```
