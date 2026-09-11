"""Konfigurasi pengelolaan User melalui Django Admin.

KERJAKAN SETELAH ketiga form pada ``forms.py`` selesai.

TODO:
1. Import ``admin`` dan ``UserAdmin``.
2. Import custom ``User`` serta dua admin form.
3. Buat class yang mewarisi ``UserAdmin`` dan register custom User.
4. Set ``add_form`` ke ``AdminUserCreationForm``.
5. Set ``form`` ke ``AdminUserChangeForm``.
6. Tambahkan full_name dan role ke ``fieldsets`` serta ``add_fieldsets``.
7. Tampilkan username, email, full_name, role, dan is_active di
   ``list_display``.
8. Tambahkan filter role dan is_active.

CHECKPOINT:
- Buat superuser, buka ``/admin/``, lalu buat satu user untuk setiap role.
- Pastikan password hasil pembuatan dapat dipakai login.
- Pastikan hanya role ADMIN yang nantinya diberi akses admin/is_staff.

Jangan register User sebelum ``AdminUserCreationForm`` dan
``AdminUserChangeForm`` menunjuk ke custom model; form bawaan awalnya
menunjuk ke User bawaan Django.
"""
