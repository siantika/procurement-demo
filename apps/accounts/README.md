# Accounts learning path

Modul ini dikerjakan sebagai satu vertical slice kecil. Jangan mengerjakan
semua TODO sekaligus.

## Status

- custom User, form, login/logout/profile, dan dashboard selesai;
- Django Admin dan authorization policy selesai;
- account services sudah transactional dan menulis AuditEvent;
- `seed_demo` sudah membuat tiga akun dan dataset bisnis canonical secara
  idempotent;
- perluasan service bisnis berikutnya dilakukan di app pemilik aggregate.

## Urutan pengerjaan

1. Selesaikan `forms.py` dan buat test form.
2. Selesaikan login/logout/profile pada `views.py`.
3. Petakan view pada `urls.py`, lalu include dari `config/urls.py`.
4. Sesuaikan template login/profile dan uji session melalui browser.
5. Selesaikan `admin.py` dan buat tiga user role melalui Django Admin.
6. Implementasikan `policies.py` beserta test 403.
7. Implementasikan `services.py` setelah primitive audit tersedia.

Seluruh langkah accounts di atas sudah diterapkan. Daftar tetap dipertahankan
sebagai urutan referensi untuk pengembangan atau onboarding berikutnya.

## Checkpoint commands

Gunakan prefix environment proyek pada setiap perintah:

```bash
uv run --env-file .env python manage.py check
uv run --env-file .env python manage.py makemigrations --check
uv run --env-file .env python manage.py test apps.accounts
uv run --env-file .env python manage.py runserver
```

Setelah menambah atau mengubah model:

```bash
uv run --env-file .env python manage.py makemigrations accounts
uv run --env-file .env python manage.py migrate
```

Jangan membuat migration baru hanya karena mengubah form, view, URL, template,
admin, policy, atau service. Migration hanya dibutuhkan ketika schema model
berubah.

## Definition of done dasar

- `manage.py check` bersih;
- tidak ada migration yang belum dibuat/diterapkan;
- user aktif dapat login;
- user inactive ditolak;
- logout hanya melalui POST;
- password tidak pernah tersimpan plaintext;
- role salah ditolak server dengan 403;
- tiga role melihat navigasi yang sesuai.
