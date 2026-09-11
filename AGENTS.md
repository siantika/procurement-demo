# Repository Instructions

Instruksi ini berlaku untuk seluruh repository.

## Sebelum mengubah frontend

1. Baca `docs/design-system.md` sampai selesai.
2. Periksa `templates/base.html` dan stylesheet utama di
   `apps/accounts/static/css/app.css`.
3. Gunakan komponen dan token yang sudah ada sebelum membuat pola baru.
4. Pertahankan karakter visual yang sederhana, tenang, dan profesional.

## Aturan template dan CSS

- Jangan menambahkan inline CSS ke template.
- Jangan menduplikasi style yang sudah tersedia.
- Gunakan semantic HTML dan struktur heading yang benar.
- Setiap input harus mempunyai label dan error yang aksesibel.
- Semua halaman harus responsif sampai lebar layar 320px.
- Jangan menambahkan library UI, font CDN, atau JavaScript dependency tanpa
  permintaan atau persetujuan pengguna.
- Jika komponen dipakai oleh beberapa halaman, buat partial di
  `templates/components/`.

## Aturan Django dan keamanan

- Gunakan komponen authentication bawaan Django.
- Logout hanya boleh melalui request `POST` dengan CSRF token.
- Jangan menampilkan password, hash, permission internal, atau data sensitif.
- Authorization wajib ditegakkan pada server, bukan hanya melalui navigasi.
- Gunakan `get_user_model()` pada form, view, service, dan test.
- Gunakan `settings.AUTH_USER_MODEL` untuk relasi field pada model.
- Jangan membuat migration jika schema model tidak berubah.

## Batas perubahan

- Pertahankan perubahan pengguna yang tidak berkaitan dengan tugas.
- Jangan merombak desain global untuk kebutuhan satu halaman tanpa alasan.
- Jangan mengubah token desain yang ada tanpa menjelaskan dampaknya.
- Jangan menambahkan fitur atau data bisnis yang tidak diminta.

## Verifikasi

Setelah mengubah Python, template, atau alur autentikasi, jalankan pemeriksaan
yang relevan:

```bash
uv run ruff check <file-yang-diubah>
uv run python manage.py check --settings=config.settings.test
uv run python manage.py test apps.accounts.tests \
    --settings=config.settings.test
```

Untuk perubahan visual, periksa minimal:

- halaman login dalam keadaan normal dan error;
- dashboard sebagai user terautentikasi;
- halaman profile dengan nama atau email panjang;
- layout desktop dan mobile;
- navigasi keyboard dan focus state.

## Referensi utama

- Arsitektur dan keputusan teknis: `docs/07-technical-design.md`.
- Rencana implementasi: `docs/08-demo-implementation-plan.md`.
- Aturan visual: `docs/design-system.md`.
