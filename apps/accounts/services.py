"""Application service untuk perubahan state account.

KERJAKAN SETELAH policies selesai dan setelah primitive audit tersedia.

Target operasi dari docs:
- create_user(...)
- change_user_role(...)
- deactivate_user(...)

Untuk setiap write service, ikuti urutan berikut:
1. Terima data eksplisit dan actor; jangan menerima ``HttpRequest``.
2. Panggil authorization policy.
3. Buka ``transaction.atomic()``.
4. Validasi invariant bisnis.
5. Simpan perubahan dengan User manager/ORM.
6. Buat audit event dalam transaction yang sama.
7. Kembalikan hasil minimal, bukan ``HttpResponse``.

TODO PENTING UNTUK PASSWORD:
Gunakan ``User.objects.create_user(...)`` atau ``user.set_password(...)``.
Jangan pernah memakai ``User.objects.create(password=raw_password)`` karena
nilai tersebut akan tersimpan sebagai plaintext dan tidak dapat digunakan
untuk login.

Event audit yang kelak dibuat:
- USER_CREATED
- USER_ROLE_CHANGED
- USER_DEACTIVATED
"""
