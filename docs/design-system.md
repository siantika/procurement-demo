# Procurement UI Design System

> Status: Token/komponen implementasi dan aturan perubahan UI<br>
> Terakhir diperbarui: 15 September 2026

Dokumen ini adalah acuan visual untuk seluruh halaman Procurement ERP.
Gunakan aturan ini sebelum membuat atau mengubah template dan CSS.

## Arah visual

Antarmuka harus terasa sederhana, tenang, profesional, dan dapat dipercaya.
Konteks produk adalah procurement medis, sehingga kejelasan informasi lebih
penting daripada dekorasi.

Prinsip utama:

- gunakan ruang kosong yang cukup;
- tampilkan hierarki informasi yang jelas;
- hindari animasi dan dekorasi berlebihan;
- gunakan komponen yang sudah ada sebelum membuat variasi baru;
- pertahankan tampilan yang baik pada desktop dan perangkat mobile.

## Sumber implementasi

Token dan komponen CSS utama berada di:

```text
apps/accounts/static/css/app.css
```

Template dasar berada di:

```text
templates/base.html
```

Jangan menduplikasi nilai dari kedua file tersebut ke template halaman.

## Warna

Gunakan CSS custom properties yang sudah didefinisikan pada `:root`.

| Token | Nilai | Penggunaan |
| --- | --- | --- |
| `--bg` | `#f4f7f6` | Latar halaman |
| `--surface` | `#ffffff` | Card dan panel |
| `--surface-soft` | `#edf7f4` | Aksen lembut |
| `--text` | `#18302b` | Teks utama |
| `--muted` | `#667873` | Teks sekunder |
| `--border` | `#dbe5e2` | Border komponen |
| `--primary` | `#147d6c` | Aksi dan identitas utama |
| `--primary-dark` | `#0d6356` | Hover dan aksen kuat |
| `--danger` | `#a53b3b` | Error dan status berbahaya |
| `--danger-bg` | `#fff1f1` | Latar pesan error |
| `--shadow` | `0 18px 50px rgba(25, 59, 51, 0.08)` | Bayangan card/toast |
| `--radius` | `18px` | Radius card |

Jangan menambahkan warna hard-coded baru apabila token yang ada sudah dapat
mewakili kebutuhan tersebut. Tambahkan token baru hanya jika warna mempunyai
fungsi semantik yang berbeda.

## Tipografi

Gunakan system font stack dari stylesheet utama. Jangan menambahkan font dari
CDN tanpa persetujuan karena aplikasi harus tetap cepat dan dapat digunakan
tanpa ketergantungan eksternal.

Aturan hierarki:

- satu `h1` untuk judul utama setiap halaman;
- `h2` untuk judul card atau bagian utama;
- `.eyebrow` untuk konteks singkat di atas judul;
- gunakan warna `--muted` untuk deskripsi sekunder;
- hindari teks kapital penuh selain label pendek.

## Layout

Konten utama memakai `.page-shell` dengan lebar maksimum `1120px`.

- Gunakan `.page-heading` untuk judul halaman.
- Gunakan CSS Grid untuk kumpulan card.
- Gunakan jarak yang konsisten dengan komponen yang sudah tersedia.
- Hindari width dan spacing inline pada template.
- Layout harus tetap terbaca pada lebar layar `320px`.

## Komponen

### Card

Gunakan `.card` sebagai fondasi panel. Tambahkan class khusus hanya untuk
perbedaan layout, bukan untuk mendefinisikan ulang warna dan border dasar.

```html
<section class="card feature-card">
    ...
</section>
```

### Tombol

Gunakan `.button` sebagai class dasar dan `.button-primary` untuk aksi utama.
Satu area form sebaiknya hanya memiliki satu aksi utama yang dominan.

```html
<button class="button button-primary" type="submit">
    Simpan
</button>
```

### Form

Gunakan partial `templates/components/form_fields.html` untuk field yang
dipakai ulang. `apps/core/forms.py` menyediakan payload hidden
`expected_version` untuk mutation yang memerlukan version check.
Formset Tender memakai `templates/components/tender_item_fields.html`
dan JavaScript lokal untuk tambah/hapus item.

Gunakan `.stack-form` dan `.field-group`. Setiap input wajib memiliki label.
Error harus tampil dekat dengan field dan dapat dipahami tanpa mengandalkan
warna saja.

```html
<form method="post" class="stack-form" novalidate>
    {% csrf_token %}
    <div class="field-group">
        {{ form.name.label_tag }}
        {{ form.name }}
        {% for error in form.name.errors %}
            <p class="field-error">{{ error }}</p>
        {% endfor %}
    </div>
</form>
```

### Tabel, detail, dan pesan

- `.table-card`, `.table-wrap`, dan `.data-table` untuk tabel dengan horizontal scroll pada layar sempit.
- `.detail-card` dan `.detail-grid` untuk pasangan label/nilai.
- `.form-actions` dan `.button-secondary` untuk kelompok aksi sekunder.
- `.alert-success` untuk pesan sukses dan `.status-alert` untuk status proses; level pesan lain memakai fondasi `.alert` saat ini.
- `.toast-region` dan `.toast` untuk maksimal tiga notifikasi unread pada render halaman; tombol close menyimpan dismissal di sessionStorage, tanpa mengubah read state database.
- `.hash-value` untuk tipografi monospace hash; `.detail-grid dd` memberi `overflow-wrap: anywhere` pada nilai detail panjang.

### Status

Gunakan `.status-badge` untuk role atau status singkat. Jangan menggunakan
badge sebagai pengganti penjelasan untuk status yang kompleks.

### Alert

Gunakan `.alert` dengan `role="alert"` untuk error pada level form atau
halaman. Pesan autentikasi harus tetap generik dan tidak boleh mengungkapkan
apakah sebuah username terdaftar.

## Navigasi dan keamanan

- Navigasi utama tetap berada di `templates/base.html`.
- Tampilkan menu sesuai status `user.is_authenticated` dan role: Admin Produk/Supplier, Staff Offer/Tender/Result/Bid, Manager Approval. Optimization juga tersedia melalui dashboard Staff.
- Logout wajib menggunakan form `POST` dan `{% csrf_token %}`.
- Jangan mengganti logout dengan link `GET`.
- Jangan menampilkan password, permission internal, atau data sensitif.
- Jangan mengandalkan penyembunyian tombol sebagai authorization server.

## Bahasa dan isi

Gunakan Bahasa Indonesia yang ringkas dan konsisten untuk antarmuka pengguna.
Nama teknis seperti username dapat dipertahankan jika lebih mudah dipahami.

- Gunakan "Masuk", bukan campuran "Login" dan "Sign in".
- Gunakan "Keluar" untuk logout.
- Gunakan "Profil" untuk profile.
- Judul tombol harus menjelaskan tindakan yang akan terjadi.

## PDF

Dokumen PDF memakai template `templates/documents/pdf_v1.html` dan stylesheet
`apps/documents/static/documents/css/pdf_v1.css`, terpisah dari layout web.
Template v1 adalah A4 dengan margin 20mm, Noto Sans/DejaVu Sans fallback,
dan gambar signature opsional. Dockerfile memasang font Noto; halaman web
tetap memakai system font stack tanpa font CDN.

## Accessibility

Setiap perubahan harus memenuhi aturan minimum berikut:

- struktur heading berurutan;
- input mempunyai label yang terhubung;
- elemen interaktif dapat digunakan dengan keyboard;
- focus state tetap terlihat;
- warna teks mempunyai kontras yang cukup;
- elemen dekoratif menggunakan `aria-hidden="true"`;
- landmark seperti `header`, `nav`, dan `main` dipertahankan.

## Definition of done frontend

Sebelum perubahan dianggap selesai:

1. Gunakan komponen dan token yang sudah ada.
2. Periksa tampilan desktop dan mobile.
3. Pastikan tidak ada inline CSS baru.
4. Jalankan Django system check.
5. Jalankan test yang berkaitan dengan halaman.
6. Pastikan alur CSRF, authentication, dan authorization tetap aman.

Perintah verifikasi utama:

```bash
uv run python manage.py check --settings=config.settings.test
uv run python manage.py test apps.accounts.tests \
    --settings=config.settings.test
```
