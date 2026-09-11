"""Test dasar untuk model User pada modul accounts.

Jalankan file ini setelah setiap perubahan kecil. Setelah semua model test
lulus, tambahkan test form pada class terpisah.
"""

import uuid

from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from .admin import AccountUserAdmin
from .choices import UserRole
from .forms import (
    AdminUserChangeForm,
    AdminUserCreationForm,
    LoginForm,
)

User = get_user_model()


class UserModelTests(TestCase):
    """Memeriksa kontrak paling dasar dari custom User."""

    @classmethod
    def setUpTestData(cls):
        """Buat data yang dapat dipakai oleh semua test di class."""

        cls.raw_password = "StrongPassword123!"
        cls.user = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            password=cls.raw_password,
            full_name="Procurement Staff",
            role=UserRole.PROCUREMENT_STAFF,
        )

    def test_new_user_has_uuid_primary_key(self):
        # Arrange dan Act sudah dilakukan oleh setUpTestData.

        # Assert: id yang dibuat model harus berupa object UUID.
        self.assertIsInstance(self.user.pk, uuid.UUID)

    def test_username_must_be_unique(self):
        # Arrange: self.user sudah memakai username "staff".

        # Act dan Assert: database harus menolak username yang sama.
        # transaction.atomic diperlukan agar IntegrityError tidak merusak
        # transaction utama milik TestCase.
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                username="staff",
                email="different@example.com",
                password="AnotherStrongPassword123!",
                full_name="Different User",
                role=UserRole.MANAGER,
            )

    def test_email_must_be_unique(self):
        # Arrange: self.user sudah memakai email "staff@example.com".

        # Act dan Assert: gunakan username berbeda tetapi email sama.
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                username="different-user",
                email="staff@example.com",
                password="AnotherStrongPassword123!",
                full_name="Different User",
                role=UserRole.MANAGER,
            )

    def test_role_rejects_unknown_value_during_validation(self):
        # Arrange: masukkan role di luar UserRole.
        self.user.role = "UNKNOWN_ROLE"

        # Act dan Assert: choices diperiksa ketika full_clean dipanggil.
        with self.assertRaises(ValidationError) as error:
            self.user.full_clean()

        self.assertIn("role", error.exception.message_dict)

    def test_create_user_hashes_password(self):
        # Arrange dan Act dilakukan oleh create_user di setUpTestData.

        # Assert: database bukan plaintext, tetapi password tetap cocok
        # ketika diperiksa melalui password hasher Django.
        self.assertNotEqual(self.user.password, self.raw_password)
        self.assertTrue(self.user.check_password(self.raw_password))


class LoginFormTests(TestCase):
    """Memeriksa autentikasi melalui form bawaan Django."""

    @classmethod
    def setUpTestData(cls):
        cls.raw_password = "StrongPassword123!"
        cls.user = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            password=cls.raw_password,
            full_name="Procurement Staff",
            role=UserRole.PROCUREMENT_STAFF,
        )

    def login_data(self, **overrides):
        data = {
            "username": self.user.username,
            "password": self.raw_password,
        }
        data.update(overrides)
        return data

    def test_accepts_valid_credentials(self):
        form = LoginForm(data=self.login_data())
        self.assertTrue(form.is_valid())
        self.assertEqual(form.get_user(), self.user)

    def test_rejects_unknown_username(self):
        form = LoginForm(data=self.login_data(username="unknown-user"))
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

    def test_rejects_wrong_password(self):
        form = LoginForm(
            data=self.login_data(password="WrongPassword123!")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

    def test_rejects_inactive_user(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        form = LoginForm(data=self.login_data())
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)


class AdminUserCreationFormTests(TestCase):
    """Memeriksa pembuatan custom User dan password-nya."""

    @classmethod
    def setUpTestData(cls):
        cls.existing_user = User.objects.create_user(
            username="existing",
            email="existing@example.com",
            password="ExistingPassword123!",
            full_name="Existing User",
            role=UserRole.MANAGER,
        )

    def valid_data(self, **overrides):
        password = "StrongPassword123!"
        data = {
            "username": "new-staff",
            "email": "new-staff@example.com",
            "password1": password,
            "password2": password,
            "full_name": "New Procurement Staff",
            "role": UserRole.PROCUREMENT_STAFF,
        }
        data.update(overrides)
        return data

    def test_accepts_valid_data(self):
        form = AdminUserCreationForm(data=self.valid_data())
        self.assertTrue(form.is_valid())

    def test_saves_custom_user_and_hashes_password(self):
        data = self.valid_data()
        form = AdminUserCreationForm(data=data)
        self.assertTrue(form.is_valid(), form.errors.as_json())

        user = form.save()

        self.assertIsInstance(user, User)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        self.assertEqual(user.username, data["username"])
        self.assertEqual(user.email, data["email"])
        self.assertEqual(user.full_name, data["full_name"])
        self.assertEqual(user.role, data["role"])
        self.assertNotEqual(user.password, data["password1"])
        self.assertTrue(user.check_password(data["password1"]))

    def test_rejects_mismatched_passwords(self):
        form = AdminUserCreationForm(
            data=self.valid_data(password2="DifferentPassword123!")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_rejects_weak_password(self):
        form = AdminUserCreationForm(
            data=self.valid_data(
                password1="password",
                password2="password",
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_rejects_duplicate_username(self):
        form = AdminUserCreationForm(
            data=self.valid_data(username=self.existing_user.username)
        )
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)

    def test_rejects_duplicate_email(self):
        form = AdminUserCreationForm(
            data=self.valid_data(email=self.existing_user.email)
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_rejects_unknown_role(self):
        form = AdminUserCreationForm(
            data=self.valid_data(role="UNKNOWN_ROLE")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors)

    def test_rejects_each_missing_required_field(self):
        required_fields = (
            "username",
            "email",
            "full_name",
            "role",
            "password1",
            "password2",
        )
        for field_name in required_fields:
            with self.subTest(field_name=field_name):
                form = AdminUserCreationForm(
                    data=self.valid_data(**{field_name: ""})
                )
                self.assertFalse(form.is_valid())
                self.assertIn(field_name, form.errors)

    def test_commit_false_does_not_write_to_database(self):
        data = self.valid_data()
        form = AdminUserCreationForm(data=data)
        self.assertTrue(form.is_valid(), form.errors.as_json())

        user = form.save(commit=False)

        self.assertFalse(User.objects.filter(pk=user.pk).exists())
        self.assertTrue(user.check_password(data["password1"]))

        user.save()
        self.assertTrue(User.objects.filter(pk=user.pk).exists())


class AdminUserChangeFormTests(TestCase):
    """Memeriksa perubahan user tanpa mengubah UUID atau password."""

    @classmethod
    def setUpTestData(cls):
        cls.raw_password = "StrongPassword123!"
        cls.user = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password=cls.raw_password,
            full_name="Original Manager",
            role=UserRole.MANAGER,
        )

    def change_data(self, **overrides):
        data = {
            "username": self.user.username,
            "email": self.user.email,
            "full_name": "Updated Manager",
            "role": UserRole.ADMIN,
            "is_active": False,
        }
        data.update(overrides)
        return data

    def test_exposes_only_supported_fields(self):
        form = AdminUserChangeForm(instance=self.user)
        self.assertEqual(
            tuple(form.fields),
            (
                "username",
                "password",
                "email",
                "full_name",
                "role",
                "is_active",
            ),
        )
        self.assertNotIn("id", form.fields)

    def test_updates_user_without_changing_id_or_password(self):
        original_id = self.user.pk
        original_password = self.user.password
        form = AdminUserChangeForm(
            data=self.change_data(),
            instance=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())

        user = form.save()

        self.assertEqual(user.pk, original_id)
        self.assertEqual(user.password, original_password)
        self.assertTrue(user.check_password(self.raw_password))
        self.assertEqual(user.full_name, "Updated Manager")
        self.assertEqual(user.role, UserRole.ADMIN)
        self.assertFalse(user.is_active)

    def test_rejects_unknown_role(self):
        form = AdminUserChangeForm(
            data=self.change_data(role="UNKNOWN_ROLE"),
            instance=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors)


class AccountViewTests(TestCase):
    """Memeriksa kontrak HTTP dan session untuk account views."""

    @classmethod
    def setUpTestData(cls):
        cls.raw_password = "StrongPassword123!"
        cls.user = User.objects.create_user(
            username="view-user",
            email="view-user@example.com",
            password=cls.raw_password,
            full_name="View User",
            role=UserRole.PROCUREMENT_STAFF,
        )

    def login_data(self, **overrides):
        data = {
            "username": self.user.username,
            "password": self.raw_password,
        }
        data.update(overrides)
        return data

    def test_login_page_uses_account_login_template(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")
        self.assertIsInstance(response.context["form"], LoginForm)

    def test_valid_login_creates_session_and_redirects(self):
        response = self.client.post(
            reverse("accounts:login"),
            data=self.login_data(),
        )

        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(
            self.client.session["_auth_user_id"],
            str(self.user.pk),
        )

    def test_login_honors_safe_next_url(self):
        profile_url = reverse("accounts:profile")
        response = self.client.post(
            reverse("accounts:login"),
            data={**self.login_data(), "next": profile_url},
        )

        self.assertRedirects(response, profile_url)

    def test_invalid_login_does_not_create_session(self):
        response = self.client.post(
            reverse("accounts:login"),
            data=self.login_data(password="WrongPassword123!"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Username atau password salah.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_authenticated_user_is_redirected_from_login(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:login"))

        self.assertRedirects(response, reverse("dashboard"))

    def test_anonymous_user_is_redirected_from_profile(self):
        profile_url = reverse("accounts:profile")

        response = self.client.get(profile_url)

        login_url = reverse("accounts:login")
        self.assertRedirects(
            response,
            f"{login_url}?next={profile_url}",
        )

    def test_authenticated_user_can_open_profile(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/profile.html")
        self.assertEqual(response.context["user"], self.user)

    def test_post_logout_clears_session_and_redirects(self):
        self.client.force_login(self.user)
        self.assertIn("_auth_user_id", self.client.session)

        response = self.client.post(reverse("accounts:logout"))

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_get_logout_is_not_allowed(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:logout"))

        self.assertEqual(response.status_code, 405)
        self.assertIn("POST", response.headers["Allow"])

    def test_login_post_without_csrf_is_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)

        response = csrf_client.post(
            reverse("accounts:login"),
            data=self.login_data(),
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("_auth_user_id", csrf_client.session)

    def test_logout_post_without_csrf_is_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.post(reverse("accounts:logout"))

        self.assertEqual(response.status_code, 403)
        self.assertIn("_auth_user_id", csrf_client.session)


class AccountUserAdminTests(TestCase):
    """Memeriksa konfigurasi dan authorization Django Admin."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="root-admin",
            email="root@example.com",
            password="StrongPassword123!",
            full_name="Root Admin",
            role=UserRole.ADMIN,
        )
        cls.admin_user = User.objects.create_user(
            username="business-admin",
            email="admin@example.com",
            password="StrongPassword123!",
            full_name="Business Admin",
            role=UserRole.ADMIN,
            is_staff=True,
        )
        cls.manager = User.objects.create_user(
            username="manager-admin-test",
            email="manager-admin@example.com",
            password="StrongPassword123!",
            full_name="Manager Admin Test",
            role=UserRole.MANAGER,
            is_staff=True,
        )

    def setUp(self):
        self.user_admin = django_admin.site._registry[User]
        self.request_factory = RequestFactory()

    def request_for(self, user):
        request = self.request_factory.get("/admin/accounts/user/")
        request.user = user
        return request

    def test_custom_user_is_registered_with_expected_forms(self):
        self.assertIsInstance(self.user_admin, AccountUserAdmin)
        self.assertIs(
            self.user_admin.add_form,
            AdminUserCreationForm,
        )
        self.assertIs(
            self.user_admin.form,
            AdminUserChangeForm,
        )

    def test_list_configuration_exposes_business_fields(self):
        self.assertEqual(
            self.user_admin.list_display,
            (
                "username",
                "email",
                "full_name",
                "role",
                "is_active",
            ),
        )
        self.assertEqual(
            self.user_admin.list_filter,
            ("role", "is_active"),
        )

    def test_superuser_can_open_user_admin_pages(self):
        self.client.force_login(self.superuser)
        urls = (
            reverse("admin:accounts_user_changelist"),
            reverse("admin:accounts_user_add"),
            reverse(
                "admin:accounts_user_change",
                args=[self.admin_user.pk],
            ),
        )

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_admin_role_can_open_user_changelist(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse("admin:accounts_user_changelist")
        )

        self.assertEqual(response.status_code, 200)

    def test_non_admin_role_cannot_open_user_changelist(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("admin:accounts_user_changelist")
        )

        self.assertEqual(response.status_code, 403)

    def test_only_admin_role_receives_model_permissions(self):
        admin_request = self.request_for(self.admin_user)
        manager_request = self.request_for(self.manager)

        self.assertTrue(
            self.user_admin.has_module_permission(admin_request)
        )
        self.assertTrue(self.user_admin.has_add_permission(admin_request))
        self.assertTrue(
            self.user_admin.has_change_permission(admin_request)
        )
        self.assertTrue(self.user_admin.has_view_permission(admin_request))

        self.assertFalse(
            self.user_admin.has_module_permission(manager_request)
        )
        self.assertFalse(
            self.user_admin.has_add_permission(manager_request)
        )
        self.assertFalse(
            self.user_admin.has_change_permission(manager_request)
        )
        self.assertFalse(
            self.user_admin.has_view_permission(manager_request)
        )

    def test_hard_delete_is_disabled(self):
        request = self.request_for(self.superuser)

        self.assertFalse(
            self.user_admin.has_delete_permission(request, self.manager)
        )

    def test_save_model_synchronizes_is_staff_with_role(self):
        request = self.request_for(self.superuser)
        user = User(
            username="new-admin",
            email="new-admin@example.com",
            full_name="New Admin",
            role=UserRole.ADMIN,
        )
        user.set_password("StrongPassword123!")

        self.user_admin.save_model(request, user, form=None, change=False)
        self.assertTrue(user.is_staff)

        user.role = UserRole.MANAGER
        self.user_admin.save_model(request, user, form=None, change=True)
        self.assertFalse(user.is_staff)
