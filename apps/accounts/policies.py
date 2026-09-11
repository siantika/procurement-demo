"""Authorization policy untuk modul accounts.

KERJAKAN SETELAH login/logout berhasil.

Policy menjawab apakah actor boleh melakukan tindakan. Ia tidak menerima
``HttpRequest`` dan tidak merender response.

TODO:
1. Import ``PermissionDenied`` dan ``UserRole``.
2. Buat ``require_active_user(user)``:
   - user harus authenticated;
   - user harus active;
   - jika gagal, raise ``PermissionDenied``.
3. Buat ``require_role(user, expected_role)``.
4. Buat helper ``require_admin``, ``require_procurement_staff``, dan
   ``require_manager`` di atas ``require_role``.
5. Tulis test untuk role benar, role salah, anonymous, dan inactive user.

PENTING:
Menyembunyikan menu di template bukan authorization. View boleh melakukan
pengecekan awal, tetapi write service tetap wajib memanggil policy ini.
"""
