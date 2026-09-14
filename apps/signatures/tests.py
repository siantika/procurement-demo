import uuid
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from apps.accounts.choices import UserRole
from apps.approval.services import approve_bid
from apps.audit.models import AuditEvent
from apps.bids.choices import BidStatus
from apps.bids.tests import BidFixtureMixin
from apps.documents.storage import StoredObject

from .models import Signature
from .services import sign_bid

User = get_user_model()


class SignatureServiceTests(BidFixtureMixin, TestCase):
    def approved_bid(self):
        _proposal, revision = self.submitted_bid()
        approve_bid(
            actor=self.manager,
            revision_id=revision.pk,
            expected_version=revision.version,
            correlation_id=self.correlation_id(),
        )
        revision.refresh_from_db()
        return revision

    def test_approving_manager_can_sign_without_image(self):
        revision = self.approved_bid()

        signature = sign_bid(
            actor=self.manager,
            revision_id=revision.pk,
            expected_version=revision.version,
            correlation_id=self.correlation_id(),
        )

        revision.refresh_from_db()
        self.assertEqual(revision.status, BidStatus.SIGNED)
        self.assertEqual(signature.signed_by, self.manager)
        self.assertEqual(
            signature.signed_snapshot_hash, revision.submission_hash
        )
        self.assertIsNone(signature.image_object_key)
        self.assertTrue(
            AuditEvent.objects.filter(action="BID_SIGNED").exists()
        )

    def test_other_manager_cannot_sign(self):
        revision = self.approved_bid()
        other = User.objects.create_user(
            username="other-manager",
            email="other-manager@example.test",
            password="StrongPassword123!",
            full_name="Other Manager",
            role=UserRole.MANAGER,
        )

        with self.assertRaises(PermissionDenied):
            sign_bid(
                actor=other,
                revision_id=revision.pk,
                expected_version=revision.version,
                correlation_id=str(uuid.uuid4()),
            )

        revision.refresh_from_db()
        self.assertEqual(revision.status, BidStatus.APPROVED)
        self.assertFalse(Signature.objects.exists())

    def test_staff_cannot_sign(self):
        revision = self.approved_bid()
        with self.assertRaises(PermissionDenied):
            sign_bid(
                actor=self.staff,
                revision_id=revision.pk,
                expected_version=revision.version,
                correlation_id=self.correlation_id(),
            )

    def test_signature_is_immutable(self):
        revision = self.approved_bid()
        signature = sign_bid(
            actor=self.manager,
            revision_id=revision.pk,
            expected_version=revision.version,
            correlation_id=self.correlation_id(),
        )

        signature.signer_name = "Changed"
        with self.assertRaises(ValidationError):
            signature.save()
        with self.assertRaises(ValidationError):
            Signature.objects.filter(pk=signature.pk).update(
                signer_name="Changed"
            )

    def test_optional_png_is_validated_and_stored_privately(self):
        revision = self.approved_bid()
        image_buffer = BytesIO()
        Image.new("RGB", (400, 160), "white").save(
            image_buffer, format="PNG"
        )
        upload = SimpleUploadedFile(
            "signature.png",
            image_buffer.getvalue(),
            content_type="image/png",
        )
        stored = StoredObject(
            object_key=f"signatures/{revision.pk}/image.png",
            version_id="signature-v1",
            content_type="image/png",
            size=len(image_buffer.getvalue()),
        )
        with patch(
            "apps.signatures.services.store_private_object",
            return_value=stored,
        ):
            signature = sign_bid(
                actor=self.manager,
                revision_id=revision.pk,
                expected_version=revision.version,
                signature_image=upload,
                correlation_id=self.correlation_id(),
            )

        self.assertEqual(signature.image_object_key, stored.object_key)
        self.assertEqual(signature.image_mime_type, "image/png")
        self.assertEqual(len(signature.image_sha256), 64)


class SignatureViewTests(SignatureServiceTests):
    def test_approver_can_sign_from_ui(self):
        revision = self.approved_bid()
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse(
                "signatures:sign", kwargs={"revision_id": revision.pk}
            ),
            {
                "expected_version": revision.version,
                "confirmation": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        revision.refresh_from_db()
        self.assertEqual(revision.status, BidStatus.SIGNED)

    def test_other_manager_get_is_forbidden(self):
        revision = self.approved_bid()
        other = User.objects.create_user(
            username="view-other-manager",
            email="view-other-manager@example.test",
            password="StrongPassword123!",
            full_name="Other Manager",
            role=UserRole.MANAGER,
        )
        self.client.force_login(other)

        response = self.client.get(
            reverse(
                "signatures:sign", kwargs={"revision_id": revision.pk}
            )
        )

        self.assertEqual(response.status_code, 403)
