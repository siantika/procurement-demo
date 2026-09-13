"""Seed akun demo canonical secara idempotent."""

import os
import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.choices import AccountAuditAction, UserRole
from apps.audit.writer import write_audit_event
from apps.catalog.models import Product, Supplier
from apps.catalog.services import create_product, create_supplier
from apps.sourcing.choices import ResultSourceType, ResultStatus
from apps.sourcing.models import ProcurementResult, SupplierOffer
from apps.sourcing.policies import calculate_net_purchase_price
from apps.sourcing.result_services import (
    create_manual_result,
    validate_result,
)
from apps.sourcing.services import create_supplier_offer
from apps.tender.models import TenderRequest
from apps.tender.services import create_tender, get_current_tender_revision

User = get_user_model()

DEMO_USERS = (
    {
        "username": "demo-admin",
        "email": "admin@example.test",
        "full_name": "Demo Admin",
        "role": UserRole.ADMIN,
        "password_env": "DEMO_ADMIN_PASSWORD",
    },
    {
        "username": "demo-staff",
        "email": "staff@example.test",
        "full_name": "Demo Procurement Staff",
        "role": UserRole.PROCUREMENT_STAFF,
        "password_env": "DEMO_STAFF_PASSWORD",
    },
    {
        "username": "demo-manager",
        "email": "manager@example.test",
        "full_name": "Demo Manager",
        "role": UserRole.MANAGER,
        "password_env": "DEMO_MANAGER_PASSWORD",
    },
)


class Command(BaseCommand):
    help = "Create or verify canonical accounts and procurement data."

    def handle(self, *args, **options):
        passwords = self._load_passwords()
        correlation_id = str(uuid.uuid4())

        with transaction.atomic():
            for definition in DEMO_USERS:
                self._seed_user(
                    definition=definition,
                    password=passwords[definition["password_env"]],
                    correlation_id=correlation_id,
                )
            self._seed_business_data(correlation_id=correlation_id)

        self.stdout.write(
            self.style.SUCCESS("Data demo berhasil dibuat/diverifikasi.")
        )

    def _seed_business_data(self, *, correlation_id):
        admin = User.objects.get(username="demo-admin")
        staff = User.objects.get(username="demo-staff")
        product = Product.objects.filter(code__iexact="PUMP-001").first()
        if product is None:
            product = create_product(
                actor=admin,
                code="PUMP-001",
                name="Infusion Pump",
                description="Pompa infus untuk kebutuhan rumah sakit.",
                default_unit="unit",
                correlation_id=correlation_id,
            )
        self._verify(
            product,
            name="Infusion Pump",
            default_unit="unit",
            is_active=True,
        )

        suppliers = self._seed_suppliers(
            admin=admin,
            correlation_id=correlation_id,
        )
        offers = self._seed_offers(
            staff=staff,
            product=product,
            suppliers=suppliers,
            correlation_id=correlation_id,
        )
        revision = self._seed_tender(
            staff=staff,
            product=product,
            correlation_id=correlation_id,
        )
        self._seed_manual_result(
            staff=staff,
            revision=revision,
            offers=offers,
            correlation_id=correlation_id,
        )

    def _seed_suppliers(self, *, admin, correlation_id):
        suppliers = {}
        for code, name in (
            ("SUP-A", "Supplier A"),
            ("SUP-B", "Supplier B"),
            ("SUP-C", "Supplier C"),
        ):
            supplier = Supplier.objects.filter(code__iexact=code).first()
            if supplier is None:
                supplier = create_supplier(
                    actor=admin,
                    code=code,
                    name=name,
                    contact_name="",
                    email="",
                    phone="",
                    address="",
                    correlation_id=correlation_id,
                )
            self._verify(supplier, name=name, is_active=True)
            suppliers[code] = supplier
        return suppliers

    def _seed_offers(
        self,
        *,
        staff,
        product,
        suppliers,
        correlation_id,
    ):
        definitions = (
            ("DEMO-OFFER-A", "SUP-A", "7000000", "10", "60"),
            ("DEMO-OFFER-B", "SUP-B", "7500000", "5", "100"),
            ("DEMO-OFFER-C", "SUP-C", "7200000", "0", "100"),
        )
        offers = {}
        for (
            reference,
            supplier_code,
            price,
            discount,
            quantity,
        ) in definitions:
            offer = SupplierOffer.objects.filter(
                supplier=suppliers[supplier_code],
                product=product,
                supplier_reference=reference,
            ).first()
            if offer is None:
                offer = create_supplier_offer(
                    actor=staff,
                    supplier_id=suppliers[supplier_code].pk,
                    product_id=product.pk,
                    supplier_reference=reference,
                    base_unit_price=Decimal(price),
                    discount_percent=Decimal(discount),
                    available_quantity=Decimal(quantity),
                    valid_from=date(2026, 1, 1),
                    valid_until=date(2030, 12, 31),
                    correlation_id=correlation_id,
                )
            self._verify(
                offer,
                supplier=suppliers[supplier_code],
                product=product,
                base_unit_price=Decimal(price),
                discount_percent=Decimal(discount),
                net_purchase_price=calculate_net_purchase_price(
                    price, discount
                ),
                available_quantity=Decimal(quantity),
                valid_from=date(2026, 1, 1),
                valid_until=date(2030, 12, 31),
                is_active=True,
            )
            offers[supplier_code] = offer
        return offers

    def _seed_tender(self, *, staff, product, correlation_id):
        tender = TenderRequest.objects.filter(
            internal_code__iexact="DEMO-TENDER-001"
        ).first()
        if tender is None:
            tender = create_tender(
                actor=staff,
                internal_code="DEMO-TENDER-001",
                tender_reference_number="RS-DEMO-2026-001",
                institution_name="Rumah Sakit Demo",
                institution_address="Jakarta",
                title="Pengadaan 100 Unit Infusion Pump",
                description="Golden scenario untuk demo portfolio.",
                total_hps=Decimal("800000000.00"),
                items=[
                    {
                        "line_number": 1,
                        "product_id": product.pk,
                        "requested_quantity": Decimal("100.000"),
                        "unit": "unit",
                        "specification": "Medical grade",
                        "description": "",
                    }
                ],
                correlation_id=correlation_id,
            )
        revision = get_current_tender_revision(tender.pk)
        self._verify(
            revision,
            institution_name="Rumah Sakit Demo",
            total_hps=Decimal("800000000.00"),
        )
        item = revision.items.get(line_number=1)
        self._verify(
            item,
            product=product,
            requested_quantity=Decimal("100.000"),
            unit="unit",
        )
        return revision

    def _seed_manual_result(
        self, *, staff, revision, offers, correlation_id
    ):
        result = ProcurementResult.objects.filter(
            tender_revision=revision,
            source_type=ResultSourceType.MANUAL,
            created_by=staff,
        ).first()
        if result is None:
            tender_item = revision.items.get(line_number=1)
            result = create_manual_result(
                actor=staff,
                tender_revision_id=revision.pk,
                allocations=[
                    {
                        "tender_item_id": tender_item.pk,
                        "line_number": 1,
                        "supplier_offer_id": offers["SUP-A"].pk,
                        "allocated_quantity": Decimal("60.000"),
                    },
                    {
                        "tender_item_id": tender_item.pk,
                        "line_number": 2,
                        "supplier_offer_id": offers["SUP-B"].pk,
                        "allocated_quantity": Decimal("40.000"),
                    },
                ],
                correlation_id=correlation_id,
            )
            result = validate_result(
                actor=staff,
                result_id=result.pk,
                expected_version=result.version,
                correlation_id=correlation_id,
            )
        self._verify(
            result,
            status=ResultStatus.VALID,
            total_purchase=Decimal("663000000.00"),
            calculation_version="calc-v1",
        )

    @staticmethod
    def _verify(instance, **expected):
        mismatches = [
            name
            for name, value in expected.items()
            if getattr(instance, name) != value
        ]
        if mismatches:
            fields = ", ".join(mismatches)
            raise CommandError(
                f"Data demo {instance} berbeda pada field: {fields}."
            )

    @staticmethod
    def _load_passwords():
        names = [item["password_env"] for item in DEMO_USERS]
        missing = [name for name in names if not os.environ.get(name)]
        if missing:
            joined_names = ", ".join(missing)
            raise CommandError(
                f"Environment password wajib diisi: {joined_names}"
            )
        return {name: os.environ[name] for name in names}

    def _seed_user(self, *, definition, password, correlation_id):
        user = User.objects.filter(
            username__iexact=definition["username"]
        ).first()
        created = user is None

        if created:
            candidate = User(
                username=definition["username"],
                email=definition["email"],
                full_name=definition["full_name"],
                role=definition["role"],
            )
            validate_password(password, user=candidate)
            user = User.objects.create_user(
                username=definition["username"],
                email=definition["email"],
                password=password,
                full_name=definition["full_name"],
                role=definition["role"],
            )
            changed_fields = []
        else:
            changed_fields = self._update_user(
                user=user,
                definition=definition,
                password=password,
            )

        if not created and not changed_fields:
            return

        write_audit_event(
            actor=None,
            entity_type="User",
            entity_id=user.pk,
            action=(
                AccountAuditAction.USER_CREATED
                if created
                else AccountAuditAction.USER_UPDATED
            ),
            correlation_id=correlation_id,
            to_status=user.role if created else None,
            metadata={
                "source": "seed_demo",
                "changed_fields": changed_fields,
            },
        )

    @staticmethod
    def _update_user(*, user, definition, password):
        changed_fields = []
        for field_name in ("email", "full_name", "role"):
            expected_value = definition[field_name]
            if getattr(user, field_name) != expected_value:
                setattr(user, field_name, expected_value)
                changed_fields.append(field_name)

        if not user.is_active:
            user.is_active = True
            changed_fields.append("is_active")
        if not user.check_password(password):
            validate_password(password, user=user)
            user.set_password(password)
            changed_fields.append("password")

        if changed_fields:
            user.full_clean()
            user.save()
        return changed_fields
