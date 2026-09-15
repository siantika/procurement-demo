# Data Model

## Medical Procurement Bid Optimizer

> Status: Schema model Django saat ini<br>
> Terakhir diperbarui: 15 September 2026

## 1. Sumber dan cakupan

Inventaris berikut dicocokkan dengan metadata 23 model konkret pada `apps/*/models.py`. Migration merupakan schema executable. [DBML](schema.dbml) merepresentasikan tabel/kolom/relasi yang sama; tabel bawaan Django untuk session, admin log, auth permission/group, content type, migration history, dan tabel M2M User tidak dirinci dalam kedua inventaris ini. Field konkret yang diwariskan dari AbstractUser tetap dicatat.

PostgreSQL menyimpan fakta bisnis, revision, snapshot JSONB, audit, notification, dan status job. Redis menyimpan broker/cache, bukan status bisnis canonical. MinIO menyimpan binary PDF/signature, sementara metadata/object key/hash ada di PostgreSQL. `apps/core` tidak mempunyai tabel idempotency atau model tersendiri.

## 2. Konvensi

- UUID menjadi primary key model aplikasi, kecuali `DocumentNumberSequence` yang memakai integer tahun.
- Tipe di tabel adalah tipe PostgreSQL hasil field model. `null` adalah nullable DB; field `blank` form dan empty string bukan sinonim null.
- Default dan timestamp otomatis yang dicatat adalah perilaku **Django**, bukan klaim SQL server default.
- Currency model terkait dibatasi IDR. Uang umumnya decimal(20,2), harga decimal(20,4), persentase decimal(7,4), quantity decimal(18,3).
- FK dicatat dengan kebijakan `on_delete` Django. PROTECT/CASCADE adalah perilaku ORM deletion; bukan klaim semua database FK mempunyai SQL ON DELETE yang sama.
- Indeks FK/PK/field unique otomatis tersedia selain indeks eksplisit yang dirinci. CheckConstraint/UniqueConstraint berikut berasal dari model; invariant lintas row/status/actor tetap memerlukan service.

## 3. Inventaris tabel

| Model | Tabel | Source |
|---|---|---|
| `accounts.User` | `accounts_user` | `apps/accounts/models.py` |
| `catalog.Product` | `catalog_product` | `apps/catalog/models.py` |
| `catalog.Supplier` | `catalog_supplier` | `apps/catalog/models.py` |
| `sourcing.SupplierOffer` | `sourcing_supplier_offer` | `apps/sourcing/models.py` |
| `sourcing.ProcurementResult` | `sourcing_procurement_result` | `apps/sourcing/models.py` |
| `sourcing.ProcurementResultItem` | `sourcing_procurement_result_item` | `apps/sourcing/models.py` |
| `sourcing.SupplierAllocation` | `sourcing_supplier_allocation` | `apps/sourcing/models.py` |
| `sourcing.ProcurementResultSelection` | `sourcing_procurement_result_selection` | `apps/sourcing/models.py` |
| `tender.TenderRequest` | `tender_tender_request` | `apps/tender/models.py` |
| `tender.TenderRequestRevision` | `tender_tender_request_revision` | `apps/tender/models.py` |
| `tender.TenderRequestItem` | `tender_tender_request_item` | `apps/tender/models.py` |
| `optimization.OptimizationRun` | `optimization_optimization_run` | `apps/optimization/models.py` |
| `optimization.OptimizationCandidateRejection` | `optimization_candidate_rejection` | `apps/optimization/models.py` |
| `bids.BidProposal` | `bids_bid_proposal` | `apps/bids/models.py` |
| `bids.BidProposalRevision` | `bids_bid_proposal_revision` | `apps/bids/models.py` |
| `bids.BidProposalItem` | `bids_bid_proposal_item` | `apps/bids/models.py` |
| `approval.ApprovalDecision` | `approval_approval_decision` | `apps/approval/models.py` |
| `signatures.Signature` | `signatures_signature` | `apps/signatures/models.py` |
| `documents.DocumentNumberSequence` | `documents_number_sequence` | `apps/documents/models.py` |
| `documents.DocumentGenerationJob` | `documents_generation_job` | `apps/documents/models.py` |
| `documents.FinalDocument` | `documents_final_document` | `apps/documents/models.py` |
| `notifications.Notification` | `notifications_notification` | `apps/notifications/models.py` |
| `audit.AuditEvent` | `audit_audit_event` | `apps/audit/models.py` |

## 4. Kolom, constraint, dan indeks

### `accounts_user` — User

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `password` | `varchar(128)` | Tidak | — | — |
| `last_login` | `timestamptz` | Ya | — | — |
| `is_superuser` | `boolean` | Tidak | — | Django default: False |
| `username` | `varchar(150)` | Tidak | unique | — |
| `first_name` | `varchar(150)` | Tidak | — | — |
| `last_name` | `varchar(150)` | Tidak | — | — |
| `is_staff` | `boolean` | Tidak | — | Django default: False |
| `is_active` | `boolean` | Tidak | — | Django default: True |
| `date_joined` | `timestamptz` | Tidak | — | Django default: django.utils.timezone.now |
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `email` | `varchar(254)` | Tidak | unique | — |
| `full_name` | `varchar(255)` | Tidak | — | — |
| `role` | `varchar(32)` | Tidak | — | choices: ADMIN, PROCUREMENT_STAFF, MANAGER |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |
| `updated_at` | `timestamptz` | Tidak | — | Django auto_now |

Constraint eksplisit:

- `accounts_user_role_valid`: `CONSTRAINT "accounts_user_role_valid" CHECK ("role" IN ('ADMIN', 'PROCUREMENT_STAFF', 'MANAGER'))`.
- `accounts_user_staff_requires_admin_role`: `CONSTRAINT "accounts_user_staff_requires_admin_role" CHECK ((NOT "is_staff" OR "role" = 'ADMIN'))`.
- `accounts_user_username_ci_unique`: `CREATE UNIQUE INDEX "accounts_user_username_ci_unique" ON "accounts_user" ((LOWER("username")))`.
- `accounts_user_email_ci_unique`: `CREATE UNIQUE INDEX "accounts_user_email_ci_unique" ON "accounts_user" ((LOWER("email")))`.

### `catalog_product` — Product

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `code` | `varchar(50)` | Tidak | unique | — |
| `name` | `varchar(255)` | Tidak | — | — |
| `description` | `text` | Tidak | — | — |
| `default_unit` | `varchar(32)` | Tidak | — | — |
| `is_active` | `boolean` | Tidak | — | Django default: True |
| `version` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada; Django default: 1 |
| `created_by_id` | `uuid` | Tidak | — | FK accounts_user.id; PROTECT |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |
| `updated_at` | `timestamptz` | Tidak | — | Django auto_now |

Constraint eksplisit:

- `catalog_product_code_ci_unique`: `CREATE UNIQUE INDEX "catalog_product_code_ci_unique" ON "catalog_product" ((LOWER("code")))`.
- `catalog_product_version_positive`: `CONSTRAINT "catalog_product_version_positive" CHECK ("version" > 0)`.

Indeks eksplisit:

- `catalog_pro_is_acti_d8c282_idx`: `is_active, name`.

### `catalog_supplier` — Supplier

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `code` | `varchar(50)` | Tidak | unique | — |
| `name` | `varchar(255)` | Tidak | — | — |
| `contact_name` | `varchar(255)` | Tidak | — | — |
| `email` | `varchar(254)` | Tidak | — | — |
| `phone` | `varchar(50)` | Tidak | — | — |
| `address` | `text` | Tidak | — | — |
| `is_active` | `boolean` | Tidak | — | Django default: True |
| `version` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada; Django default: 1 |
| `created_by_id` | `uuid` | Tidak | — | FK accounts_user.id; PROTECT |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |
| `updated_at` | `timestamptz` | Tidak | — | Django auto_now |

Constraint eksplisit:

- `catalog_supplier_code_ci_unique`: `CREATE UNIQUE INDEX "catalog_supplier_code_ci_unique" ON "catalog_supplier" ((LOWER("code")))`.
- `catalog_supplier_version_positive`: `CONSTRAINT "catalog_supplier_version_positive" CHECK ("version" > 0)`.

Indeks eksplisit:

- `catalog_sup_is_acti_50209d_idx`: `is_active, name`.

### `sourcing_supplier_offer` — SupplierOffer

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `supplier_id` | `uuid` | Tidak | — | FK catalog_supplier.id; PROTECT |
| `product_id` | `uuid` | Tidak | — | FK catalog_product.id; PROTECT |
| `supersedes_offer_id` | `uuid` | Ya | unique | FK sourcing_supplier_offer.id; PROTECT |
| `supplier_reference` | `varchar(100)` | Tidak | — | — |
| `base_unit_price` | `decimal(20, 4)` | Tidak | — | — |
| `discount_percent` | `decimal(7, 4)` | Tidak | — | Django default: 0 |
| `net_purchase_price` | `decimal(20, 4)` | Tidak | — | — |
| `currency` | `varchar(3)` | Tidak | — | Django default: 'IDR' |
| `available_quantity` | `decimal(18, 3)` | Ya | — | — |
| `valid_from` | `date` | Ya | — | — |
| `valid_until` | `date` | Ya | — | — |
| `is_active` | `boolean` | Tidak | — | Django default: True |
| `calculation_version` | `varchar(32)` | Tidak | — | — |
| `version` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada; Django default: 1 |
| `created_by_id` | `uuid` | Tidak | — | FK accounts_user.id; PROTECT |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |
| `updated_at` | `timestamptz` | Tidak | — | Django auto_now |

Constraint eksplisit:

- `sourcing_offer_base_price_positive`: `CONSTRAINT "sourcing_offer_base_price_positive" CHECK ("base_unit_price" > 0)`.
- `sourcing_offer_discount_bounded`: `CONSTRAINT "sourcing_offer_discount_bounded" CHECK (("discount_percent" >= 0 AND "discount_percent" <= 100))`.
- `sourcing_offer_net_price_nonnegative`: `CONSTRAINT "sourcing_offer_net_price_nonnegative" CHECK ("net_purchase_price" >= 0)`.
- `sourcing_offer_quantity_positive`: `CONSTRAINT "sourcing_offer_quantity_positive" CHECK (("available_quantity" IS NULL OR "available_quantity" > 0))`.
- `sourcing_offer_currency_idr`: `CONSTRAINT "sourcing_offer_currency_idr" CHECK ("currency" = 'IDR')`.
- `sourcing_offer_valid_date_order`: `CONSTRAINT "sourcing_offer_valid_date_order" CHECK (("valid_from" IS NULL OR "valid_until" IS NULL OR "valid_until" >= ("valid_from")))`.
- `sourcing_offer_version_positive`: `CONSTRAINT "sourcing_offer_version_positive" CHECK ("version" > 0)`.

Indeks eksplisit:

- `sourcing_su_product_9d45a6_idx`: `product, is_active, valid_until`.
- `sourcing_su_supplie_31b84d_idx`: `supplier, product, created_at`.

### `sourcing_procurement_result` — ProcurementResult

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `tender_revision_id` | `uuid` | Tidak | — | FK tender_tender_request_revision.id; PROTECT |
| `source_type` | `varchar(20)` | Tidak | — | choices: MANUAL, OPTIMIZER, CUSTOMIZED |
| `status` | `varchar(20)` | Tidak | — | choices: DRAFT, VALID; Django default: ResultStatus.DRAFT |
| `optimization_run_id` | `uuid` | Ya | — | FK optimization_optimization_run.id; PROTECT |
| `source_result_id` | `uuid` | Ya | — | FK sourcing_procurement_result.id; PROTECT |
| `rank` | `integer` | Ya | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `total_purchase` | `decimal(20, 2)` | Ya | — | — |
| `currency` | `varchar(3)` | Tidak | — | Django default: 'IDR' |
| `calculation_version` | `varchar(32)` | Tidak | — | — |
| `snapshot_schema_version` | `integer` | Ya | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `result_snapshot` | `jsonb` | Ya | — | — |
| `result_hash` | `varchar(64)` | Ya | — | — |
| `validated_at` | `timestamptz` | Ya | — | — |
| `created_by_id` | `uuid` | Tidak | — | FK accounts_user.id; PROTECT |
| `version` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada; Django default: 1 |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |
| `updated_at` | `timestamptz` | Tidak | — | Django auto_now |

Constraint eksplisit:

- `sourcing_result_version_positive`: `CONSTRAINT "sourcing_result_version_positive" CHECK ("version" > 0)`.
- `sourcing_result_currency_idr`: `CONSTRAINT "sourcing_result_currency_idr" CHECK ("currency" = 'IDR')`.
- `sourcing_result_rank_positive`: `CONSTRAINT "sourcing_result_rank_positive" CHECK (("rank" IS NULL OR "rank" > 0))`.
- `sourcing_result_total_positive`: `CONSTRAINT "sourcing_result_total_positive" CHECK (("total_purchase" IS NULL OR "total_purchase" > 0))`.
- `sourcing_result_schema_positive`: `CONSTRAINT "sourcing_result_schema_positive" CHECK (("snapshot_schema_version" IS NULL OR "snapshot_schema_version" > 0))`.
- `sourcing_result_source_lineage_valid`: `CONSTRAINT "sourcing_result_source_lineage_valid" CHECK ((("optimization_run_id" IS NULL AND "rank" IS NULL AND "source_result_id" IS NULL AND "source_type" = 'MANUAL') OR ("optimization_run_id" IS NULL AND "rank" IS NULL AND "source_result_id" IS NOT NULL AND "source_type" = 'CUSTOMIZED') OR ("optimization_run_id" IS NOT NULL AND "rank" IS NOT NULL AND "source_result_id" IS NULL AND "source_type" = 'OPTIMIZER')))`.
- `sourcing_result_source_not_self`: `CONSTRAINT "sourcing_result_source_not_self" CHECK (("source_result_id" IS NULL OR NOT ("source_result_id" = ("id") AND "source_result_id" IS NOT NULL)))`.
- `sourcing_result_state_payload_valid`: `CONSTRAINT "sourcing_result_state_payload_valid" CHECK ((("result_hash" IS NULL AND "result_snapshot" IS NULL AND "snapshot_schema_version" IS NULL AND "status" = 'DRAFT' AND "total_purchase" IS NULL AND "validated_at" IS NULL) OR ("result_hash" IS NOT NULL AND "result_snapshot" IS NOT NULL AND "snapshot_schema_version" IS NOT NULL AND "status" = 'VALID' AND "total_purchase" IS NOT NULL AND "validated_at" IS NOT NULL)))`.
- `sourcing_result_run_rank_unique`: `CREATE UNIQUE INDEX "sourcing_result_run_rank_unique" ON "sourcing_procurement_result" ("optimization_run_id", "rank") WHERE "optimization_run_id" IS NOT NULL`.

Indeks eksplisit:

- `src_result_tender_status_idx`: `tender_revision, status, total_purchase`.
- `src_result_run_rank_idx`: `optimization_run_id, rank`.

### `sourcing_procurement_result_item` — ProcurementResultItem

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `procurement_result_id` | `uuid` | Tidak | — | FK sourcing_procurement_result.id; CASCADE |
| `tender_request_item_id` | `uuid` | Tidak | — | FK tender_tender_request_item.id; PROTECT |
| `line_number` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `requested_quantity_snapshot` | `decimal(18, 3)` | Tidak | — | — |
| `unit_snapshot` | `varchar(32)` | Tidak | — | — |
| `item_purchase_total` | `decimal(20, 2)` | Ya | — | — |
| `currency` | `varchar(3)` | Tidak | — | Django default: 'IDR' |
| `product_snapshot` | `jsonb` | Tidak | — | — |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |
| `updated_at` | `timestamptz` | Tidak | — | Django auto_now |

Constraint eksplisit:

- `sourcing_result_item_tender_unique`: `CONSTRAINT "sourcing_result_item_tender_unique" UNIQUE ("procurement_result_id", "tender_request_item_id")`.
- `sourcing_result_item_line_unique`: `CONSTRAINT "sourcing_result_item_line_unique" UNIQUE ("procurement_result_id", "line_number")`.
- `sourcing_result_item_line_positive`: `CONSTRAINT "sourcing_result_item_line_positive" CHECK ("line_number" > 0)`.
- `sourcing_result_item_quantity_positive`: `CONSTRAINT "sourcing_result_item_quantity_positive" CHECK ("requested_quantity_snapshot" > 0)`.
- `sourcing_result_item_total_positive`: `CONSTRAINT "sourcing_result_item_total_positive" CHECK (("item_purchase_total" IS NULL OR "item_purchase_total" > 0))`.
- `sourcing_result_item_currency_idr`: `CONSTRAINT "sourcing_result_item_currency_idr" CHECK ("currency" = 'IDR')`.

### `sourcing_supplier_allocation` — SupplierAllocation

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `procurement_result_item_id` | `uuid` | Tidak | — | FK sourcing_procurement_result_item.id; CASCADE |
| `supplier_offer_id` | `uuid` | Tidak | — | FK sourcing_supplier_offer.id; PROTECT |
| `line_number` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `allocated_quantity` | `decimal(18, 3)` | Tidak | — | — |
| `base_unit_price_snapshot` | `decimal(20, 4)` | Tidak | — | — |
| `discount_percent_snapshot` | `decimal(7, 4)` | Tidak | — | — |
| `net_purchase_price_snapshot` | `decimal(20, 4)` | Tidak | — | — |
| `allocation_purchase` | `decimal(20, 2)` | Tidak | — | — |
| `currency` | `varchar(3)` | Tidak | — | Django default: 'IDR' |
| `supplier_snapshot` | `jsonb` | Tidak | — | — |
| `offer_snapshot` | `jsonb` | Tidak | — | — |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |
| `updated_at` | `timestamptz` | Tidak | — | Django auto_now |

Constraint eksplisit:

- `sourcing_allocation_line_unique`: `CONSTRAINT "sourcing_allocation_line_unique" UNIQUE ("procurement_result_item_id", "line_number")`.
- `sourcing_allocation_offer_unique`: `CONSTRAINT "sourcing_allocation_offer_unique" UNIQUE ("procurement_result_item_id", "supplier_offer_id")`.
- `sourcing_allocation_line_positive`: `CONSTRAINT "sourcing_allocation_line_positive" CHECK ("line_number" > 0)`.
- `sourcing_allocation_quantity_positive`: `CONSTRAINT "sourcing_allocation_quantity_positive" CHECK ("allocated_quantity" > 0)`.
- `sourcing_allocation_base_price_positive`: `CONSTRAINT "sourcing_allocation_base_price_positive" CHECK ("base_unit_price_snapshot" > 0)`.
- `sourcing_allocation_discount_bounded`: `CONSTRAINT "sourcing_allocation_discount_bounded" CHECK (("discount_percent_snapshot" >= 0 AND "discount_percent_snapshot" <= 100))`.
- `sourcing_allocation_net_price_positive`: `CONSTRAINT "sourcing_allocation_net_price_positive" CHECK ("net_purchase_price_snapshot" > 0)`.
- `sourcing_allocation_purchase_positive`: `CONSTRAINT "sourcing_allocation_purchase_positive" CHECK ("allocation_purchase" > 0)`.
- `sourcing_allocation_currency_idr`: `CONSTRAINT "sourcing_allocation_currency_idr" CHECK ("currency" = 'IDR')`.

### `sourcing_procurement_result_selection` — ProcurementResultSelection

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `tender_request_id` | `uuid` | Tidak | — | FK tender_tender_request.id; PROTECT |
| `tender_revision_id` | `uuid` | Tidak | — | FK tender_tender_request_revision.id; PROTECT |
| `procurement_result_id` | `uuid` | Tidak | — | FK sourcing_procurement_result.id; PROTECT |
| `selection_number` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `selected_by_id` | `uuid` | Tidak | — | FK accounts_user.id; PROTECT |
| `selected_at` | `timestamptz` | Tidak | — | Django auto_now_add |

Constraint eksplisit:

- `sourcing_selection_number_unique`: `CONSTRAINT "sourcing_selection_number_unique" UNIQUE ("tender_request_id", "selection_number")`.
- `sourcing_selection_number_positive`: `CONSTRAINT "sourcing_selection_number_positive" CHECK ("selection_number" > 0)`.

Indeks eksplisit:

- `sourcing_selection_current_idx`: `tender_request, -selection_number`.

### `tender_tender_request` — TenderRequest

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `internal_code` | `varchar(50)` | Tidak | unique | — |
| `current_revision_number` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada; Django default: 1 |
| `version` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada; Django default: 1 |
| `created_by_id` | `uuid` | Tidak | — | FK accounts_user.id; PROTECT |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |
| `updated_at` | `timestamptz` | Tidak | — | Django auto_now |

Constraint eksplisit:

- `tender_current_revision_positive`: `CONSTRAINT "tender_current_revision_positive" CHECK ("current_revision_number" > 0)`.
- `tender_version_positive`: `CONSTRAINT "tender_version_positive" CHECK ("version" > 0)`.

Indeks eksplisit:

- `tender_tend_created_a078ba_idx`: `created_at`.

### `tender_tender_request_revision` — TenderRequestRevision

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `tender_request_id` | `uuid` | Tidak | — | FK tender_tender_request.id; CASCADE |
| `revision_number` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `tender_reference_number` | `varchar(100)` | Tidak | — | — |
| `institution_name` | `varchar(255)` | Tidak | — | — |
| `institution_address` | `text` | Tidak | — | — |
| `title` | `varchar(255)` | Tidak | — | — |
| `description` | `text` | Tidak | — | — |
| `currency` | `varchar(3)` | Tidak | — | Django default: 'IDR' |
| `total_hps` | `decimal(20, 2)` | Ya | — | — |
| `revision_reason` | `text` | Tidak | — | — |
| `content_hash` | `varchar(64)` | Tidak | — | — |
| `created_by_id` | `uuid` | Tidak | — | FK accounts_user.id; PROTECT |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |

Constraint eksplisit:

- `tender_revision_number_unique`: `CONSTRAINT "tender_revision_number_unique" UNIQUE ("tender_request_id", "revision_number")`.
- `tender_revision_number_positive`: `CONSTRAINT "tender_revision_number_positive" CHECK ("revision_number" > 0)`.
- `tender_revision_hps_positive`: `CONSTRAINT "tender_revision_hps_positive" CHECK (("total_hps" IS NULL OR "total_hps" > 0))`.
- `tender_revision_currency_idr`: `CONSTRAINT "tender_revision_currency_idr" CHECK ("currency" = 'IDR')`.

### `tender_tender_request_item` — TenderRequestItem

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `tender_revision_id` | `uuid` | Tidak | — | FK tender_tender_request_revision.id; CASCADE |
| `line_number` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `product_id` | `uuid` | Tidak | — | FK catalog_product.id; PROTECT |
| `product_snapshot` | `jsonb` | Tidak | — | — |
| `requested_quantity` | `decimal(18, 3)` | Tidak | — | — |
| `unit` | `varchar(32)` | Tidak | — | — |
| `specification` | `text` | Tidak | — | — |
| `description` | `text` | Tidak | — | — |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |

Constraint eksplisit:

- `tender_item_line_unique`: `CONSTRAINT "tender_item_line_unique" UNIQUE ("tender_revision_id", "line_number")`.
- `tender_item_line_positive`: `CONSTRAINT "tender_item_line_positive" CHECK ("line_number" > 0)`.
- `tender_item_quantity_positive`: `CONSTRAINT "tender_item_quantity_positive" CHECK ("requested_quantity" > 0)`.

### `optimization_optimization_run` — OptimizationRun

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `tender_request_id` | `uuid` | Tidak | — | FK tender_tender_request.id; PROTECT |
| `tender_revision_id` | `uuid` | Tidak | — | FK tender_tender_request_revision.id; PROTECT |
| `retry_of_run_id` | `uuid` | Ya | — | FK optimization_optimization_run.id; PROTECT |
| `status` | `varchar(20)` | Tidak | — | choices: PENDING, RUNNING, COMPLETED, FAILED; Django default: OptimizationStatus.PENDING |
| `algorithm_version` | `varchar(32)` | Tidak | — | — |
| `snapshot_schema_version` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `input_snapshot` | `jsonb` | Tidak | — | — |
| `input_hash` | `varchar(64)` | Tidak | — | — |
| `result_count` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada; Django default: 0 |
| `safe_error_code` | `varchar(64)` | Ya | — | — |
| `safe_error_message` | `text` | Ya | — | — |
| `diagnostic_reference` | `varchar(100)` | Ya | — | — |
| `requested_by_id` | `uuid` | Tidak | — | FK accounts_user.id; PROTECT |
| `started_at` | `timestamptz` | Ya | — | — |
| `completed_at` | `timestamptz` | Ya | — | — |
| `version` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada; Django default: 1 |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |

Constraint eksplisit:

- `optimization_one_active_run_per_tender`: `CREATE UNIQUE INDEX "optimization_one_active_run_per_tender" ON "optimization_optimization_run" ("tender_request_id") WHERE "status" IN ('PENDING', 'RUNNING')`.
- `optimization_snapshot_schema_positive`: `CONSTRAINT "optimization_snapshot_schema_positive" CHECK ("snapshot_schema_version" > 0)`.
- `optimization_run_version_positive`: `CONSTRAINT "optimization_run_version_positive" CHECK ("version" > 0)`.
- `optimization_run_state_payload_valid`: `CONSTRAINT "optimization_run_state_payload_valid" CHECK ((("completed_at" IS NULL AND "diagnostic_reference" IS NULL AND "result_count" = 0 AND "safe_error_code" IS NULL AND "safe_error_message" IS NULL AND "started_at" IS NULL AND "status" = 'PENDING') OR ("completed_at" IS NULL AND "diagnostic_reference" IS NULL AND "result_count" = 0 AND "safe_error_code" IS NULL AND "safe_error_message" IS NULL AND "started_at" IS NOT NULL AND "status" = 'RUNNING') OR ("completed_at" IS NOT NULL AND "diagnostic_reference" IS NULL AND "safe_error_code" IS NULL AND "safe_error_message" IS NULL AND "started_at" IS NOT NULL AND "status" = 'COMPLETED') OR ("completed_at" IS NOT NULL AND "diagnostic_reference" IS NOT NULL AND "result_count" = 0 AND "safe_error_code" IS NOT NULL AND "safe_error_message" IS NOT NULL AND "started_at" IS NOT NULL AND "status" = 'FAILED')))`.

Indeks eksplisit:

- `opt_run_tender_created_idx`: `tender_request, -created_at`.
- `opt_run_status_created_idx`: `status, created_at`.

### `optimization_candidate_rejection` — OptimizationCandidateRejection

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `optimization_run_id` | `uuid` | Tidak | — | FK optimization_optimization_run.id; CASCADE |
| `candidate_identifier` | `varchar(128)` | Tidak | — | — |
| `reason_code` | `varchar(64)` | Tidak | — | — |
| `safe_detail` | `jsonb` | Tidak | — | Django default: builtins.dict |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |

Constraint eksplisit:

- `optimization_rejection_candidate_unique`: `CONSTRAINT "optimization_rejection_candidate_unique" UNIQUE ("optimization_run_id", "candidate_identifier")`.

### `bids_bid_proposal` — BidProposal

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `proposal_number` | `varchar(50)` | Tidak | unique | — |
| `tender_request_id` | `uuid` | Tidak | — | FK tender_tender_request.id; PROTECT |
| `current_revision_number` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada; Django default: 1 |
| `version` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada; Django default: 1 |
| `created_by_id` | `uuid` | Tidak | — | FK accounts_user.id; PROTECT |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |
| `updated_at` | `timestamptz` | Tidak | — | Django auto_now |

Constraint eksplisit:

- `bid_current_revision_positive`: `CONSTRAINT "bid_current_revision_positive" CHECK ("current_revision_number" > 0)`.
- `bid_root_version_positive`: `CONSTRAINT "bid_root_version_positive" CHECK ("version" > 0)`.

Indeks eksplisit:

- `bid_tender_created_idx`: `tender_request, -created_at`.

### `bids_bid_proposal_revision` — BidProposalRevision

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `bid_proposal_id` | `uuid` | Tidak | — | FK bids_bid_proposal.id; CASCADE |
| `revision_number` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `tender_revision_id` | `uuid` | Tidak | — | FK tender_tender_request_revision.id; PROTECT |
| `selected_result_id` | `uuid` | Tidak | — | FK sourcing_procurement_result.id; PROTECT |
| `status` | `varchar(24)` | Tidak | — | choices: DRAFT, WAITING_APPROVAL, APPROVED, REJECTED, SIGNED, FINALIZED; Django default: BidStatus.DRAFT |
| `target_margin_percent` | `decimal(7, 4)` | Ya | — | — |
| `total_purchase` | `decimal(20, 2)` | Ya | — | — |
| `total_bid_value` | `decimal(20, 2)` | Ya | — | — |
| `gross_profit` | `decimal(20, 2)` | Ya | — | — |
| `actual_margin_percent` | `decimal(7, 4)` | Ya | — | — |
| `max_margin_percent` | `decimal(7, 4)` | Ya | — | — |
| `is_hps_feasible` | `boolean` | Ya | — | — |
| `currency` | `varchar(3)` | Tidak | — | Django default: 'IDR' |
| `calculation_version` | `varchar(32)` | Tidak | — | — |
| `snapshot_schema_version` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `selected_result_snapshot` | `jsonb` | Tidak | — | — |
| `submission_snapshot` | `jsonb` | Ya | — | — |
| `submission_hash` | `varchar(64)` | Ya | — | — |
| `submitted_by_id` | `uuid` | Ya | — | FK accounts_user.id; PROTECT |
| `submitted_at` | `timestamptz` | Ya | — | — |
| `created_by_id` | `uuid` | Tidak | — | FK accounts_user.id; PROTECT |
| `version` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada; Django default: 1 |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |
| `updated_at` | `timestamptz` | Tidak | — | Django auto_now |

Constraint eksplisit:

- `bid_revision_number_unique`: `CONSTRAINT "bid_revision_number_unique" UNIQUE ("bid_proposal_id", "revision_number")`.
- `bid_revision_number_positive`: `CONSTRAINT "bid_revision_number_positive" CHECK ("revision_number" > 0)`.
- `bid_revision_version_positive`: `CONSTRAINT "bid_revision_version_positive" CHECK ("version" > 0)`.
- `bid_revision_schema_positive`: `CONSTRAINT "bid_revision_schema_positive" CHECK ("snapshot_schema_version" > 0)`.
- `bid_revision_currency_idr`: `CONSTRAINT "bid_revision_currency_idr" CHECK ("currency" = 'IDR')`.
- `bid_revision_margin_bounded`: `CONSTRAINT "bid_revision_margin_bounded" CHECK (("target_margin_percent" IS NULL OR ("target_margin_percent" >= 0 AND "target_margin_percent" < 100)))`.
- `bid_revision_purchase_positive`: `CONSTRAINT "bid_revision_purchase_positive" CHECK (("total_purchase" IS NULL OR "total_purchase" > 0))`.
- `bid_revision_value_positive`: `CONSTRAINT "bid_revision_value_positive" CHECK (("total_bid_value" IS NULL OR "total_bid_value" > 0))`.
- `bid_revision_profit_nonnegative`: `CONSTRAINT "bid_revision_profit_nonnegative" CHECK (("gross_profit" IS NULL OR "gross_profit" >= 0))`.
- `bid_revision_pricing_payload_valid`: `CONSTRAINT "bid_revision_pricing_payload_valid" CHECK ((("actual_margin_percent" IS NULL AND "gross_profit" IS NULL AND "is_hps_feasible" IS NULL AND "max_margin_percent" IS NULL AND "target_margin_percent" IS NULL AND "total_bid_value" IS NULL) OR ("actual_margin_percent" IS NOT NULL AND "gross_profit" IS NOT NULL AND "target_margin_percent" IS NOT NULL AND "total_bid_value" IS NOT NULL AND "total_purchase" IS NOT NULL)))`.
- `bid_revision_submission_payload_valid`: `CONSTRAINT "bid_revision_submission_payload_valid" CHECK ((("status" = 'DRAFT' AND "submission_hash" IS NULL AND "submission_snapshot" IS NULL AND "submitted_at" IS NULL AND "submitted_by_id" IS NULL) OR ("actual_margin_percent" IS NOT NULL AND "gross_profit" IS NOT NULL AND "status" IN ('WAITING_APPROVAL', 'APPROVED', 'REJECTED', 'SIGNED', 'FINALIZED') AND "submission_hash" IS NOT NULL AND "submission_snapshot" IS NOT NULL AND "submitted_at" IS NOT NULL AND "submitted_by_id" IS NOT NULL AND "target_margin_percent" IS NOT NULL AND "total_bid_value" IS NOT NULL AND "total_purchase" IS NOT NULL)))`.

Indeks eksplisit:

- `bid_revision_status_idx`: `status, -updated_at`.

### `bids_bid_proposal_item` — BidProposalItem

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `bid_revision_id` | `uuid` | Tidak | — | FK bids_bid_proposal_revision.id; CASCADE |
| `tender_request_item_id` | `uuid` | Tidak | — | FK tender_tender_request_item.id; PROTECT |
| `line_number` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `product_snapshot` | `jsonb` | Tidak | — | — |
| `requested_quantity` | `decimal(18, 3)` | Tidak | — | — |
| `unit` | `varchar(32)` | Tidak | — | — |
| `item_purchase_total` | `decimal(20, 2)` | Tidak | — | — |
| `unit_purchase_cost` | `decimal(20, 4)` | Tidak | — | — |
| `bid_unit_price` | `decimal(20, 4)` | Tidak | — | — |
| `item_bid_total` | `decimal(20, 2)` | Tidak | — | — |
| `currency` | `varchar(3)` | Tidak | — | Django default: 'IDR' |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |

Constraint eksplisit:

- `bid_item_tender_unique`: `CONSTRAINT "bid_item_tender_unique" UNIQUE ("bid_revision_id", "tender_request_item_id")`.
- `bid_item_line_unique`: `CONSTRAINT "bid_item_line_unique" UNIQUE ("bid_revision_id", "line_number")`.
- `bid_item_line_positive`: `CONSTRAINT "bid_item_line_positive" CHECK ("line_number" > 0)`.
- `bid_item_quantity_positive`: `CONSTRAINT "bid_item_quantity_positive" CHECK ("requested_quantity" > 0)`.
- `bid_item_purchase_positive`: `CONSTRAINT "bid_item_purchase_positive" CHECK ("item_purchase_total" > 0)`.
- `bid_item_unit_purchase_positive`: `CONSTRAINT "bid_item_unit_purchase_positive" CHECK ("unit_purchase_cost" > 0)`.
- `bid_item_unit_price_positive`: `CONSTRAINT "bid_item_unit_price_positive" CHECK ("bid_unit_price" > 0)`.
- `bid_item_total_positive`: `CONSTRAINT "bid_item_total_positive" CHECK ("item_bid_total" > 0)`.
- `bid_item_currency_idr`: `CONSTRAINT "bid_item_currency_idr" CHECK ("currency" = 'IDR')`.

### `approval_approval_decision` — ApprovalDecision

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `bid_revision_id` | `uuid` | Tidak | unique | FK bids_bid_proposal_revision.id; PROTECT |
| `decision` | `varchar(16)` | Tidak | — | choices: APPROVED, REJECTED |
| `reason` | `text` | Ya | — | — |
| `submission_hash` | `varchar(64)` | Tidak | — | — |
| `decided_by_id` | `uuid` | Tidak | — | FK accounts_user.id; PROTECT |
| `decided_at` | `timestamptz` | Tidak | — | Django default: django.utils.timezone.now |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |

Constraint eksplisit:

- `approval_decision_reason_valid`: `CONSTRAINT "approval_decision_reason_valid" CHECK ((("decision" = 'APPROVED' AND "reason" IS NULL) OR ("decision" = 'REJECTED' AND "reason" IS NOT NULL AND NOT ("reason" = '' AND "reason" IS NOT NULL))))`.

Indeks eksplisit:

- `approval_manager_decided_idx`: `decided_by, -decided_at`.

### `signatures_signature` — Signature

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `bid_revision_id` | `uuid` | Tidak | unique | FK bids_bid_proposal_revision.id; PROTECT |
| `approval_decision_id` | `uuid` | Tidak | unique | FK approval_approval_decision.id; PROTECT |
| `signed_by_id` | `uuid` | Tidak | — | FK accounts_user.id; PROTECT |
| `signer_name` | `varchar(255)` | Tidak | — | — |
| `signed_snapshot_hash` | `varchar(64)` | Tidak | — | — |
| `image_object_key` | `varchar(512)` | Ya | unique | — |
| `image_version_id` | `varchar(255)` | Ya | — | — |
| `image_mime_type` | `varchar(100)` | Ya | — | — |
| `image_size_bytes` | `bigint` | Ya | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `image_sha256` | `varchar(64)` | Ya | — | — |
| `signed_at` | `timestamptz` | Tidak | — | Django default: django.utils.timezone.now |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |

Constraint eksplisit:

- `signature_image_metadata_valid`: `CONSTRAINT "signature_image_metadata_valid" CHECK ((("image_mime_type" IS NULL AND "image_object_key" IS NULL AND "image_sha256" IS NULL AND "image_size_bytes" IS NULL AND "image_version_id" IS NULL) OR ("image_mime_type" IN ('image/png', 'image/jpeg') AND "image_object_key" IS NOT NULL AND "image_sha256" IS NOT NULL AND "image_size_bytes" > 0 AND "image_size_bytes" <= 1048576)))`.

### `documents_number_sequence` — DocumentNumberSequence

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `year` | `integer` | Tidak | PK | nonnegative integer (field type); positive checks terpisah jika ada |
| `next_number` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada; Django default: 1 |

### `documents_generation_job` — DocumentGenerationJob

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `bid_revision_id` | `uuid` | Tidak | — | FK bids_bid_proposal_revision.id; PROTECT |
| `status` | `varchar(20)` | Tidak | — | choices: PENDING, RUNNING, COMPLETED, FAILED; Django default: GenerationJobStatus.PENDING |
| `document_version` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `template_version` | `varchar(32)` | Tidak | — | Django default: '1' |
| `snapshot_schema_version` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `input_snapshot` | `jsonb` | Tidak | — | — |
| `input_hash` | `varchar(64)` | Tidak | — | — |
| `attempt_count` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada; Django default: 0 |
| `safe_error_code` | `varchar(64)` | Ya | — | — |
| `safe_error_message` | `text` | Ya | — | — |
| `diagnostic_reference` | `varchar(100)` | Ya | — | — |
| `requested_by_id` | `uuid` | Tidak | — | FK accounts_user.id; PROTECT |
| `started_at` | `timestamptz` | Ya | — | — |
| `completed_at` | `timestamptz` | Ya | — | — |
| `version` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada; Django default: 1 |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |

Constraint eksplisit:

- `document_job_version_unique`: `CONSTRAINT "document_job_version_unique" UNIQUE ("bid_revision_id", "document_version")`.
- `document_job_version_positive`: `CONSTRAINT "document_job_version_positive" CHECK ("document_version" > 0)`.
- `document_job_schema_positive`: `CONSTRAINT "document_job_schema_positive" CHECK ("snapshot_schema_version" > 0)`.
- `document_job_row_version_positive`: `CONSTRAINT "document_job_row_version_positive" CHECK ("version" > 0)`.
- `document_job_terminal_payload_valid`: `CONSTRAINT "document_job_terminal_payload_valid" CHECK ((("completed_at" IS NULL AND "status" IN ('PENDING', 'RUNNING')) OR ("completed_at" IS NOT NULL AND "safe_error_code" IS NULL AND "status" = 'COMPLETED') OR ("completed_at" IS NOT NULL AND "safe_error_code" IS NOT NULL AND "status" = 'FAILED')))`.

Indeks eksplisit:

- `document_job_status_idx`: `status, created_at`.
- `document_job_revision_idx`: `bid_revision, -document_version`.

### `documents_final_document` — FinalDocument

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `generation_job_id` | `uuid` | Tidak | unique | FK documents_generation_job.id; PROTECT |
| `bid_revision_id` | `uuid` | Tidak | — | FK bids_bid_proposal_revision.id; PROTECT |
| `document_version` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `document_number` | `varchar(100)` | Tidak | — | — |
| `template_version` | `varchar(32)` | Tidak | — | — |
| `object_key` | `varchar(512)` | Tidak | unique | — |
| `object_version_id` | `varchar(255)` | Ya | — | — |
| `mime_type` | `varchar(100)` | Tidak | — | Django default: 'application/pdf' |
| `size_bytes` | `bigint` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `sha256` | `varchar(64)` | Tidak | — | — |
| `snapshot_schema_version` | `integer` | Tidak | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `content_snapshot` | `jsonb` | Tidak | — | — |
| `finalized_by_id` | `uuid` | Tidak | — | FK accounts_user.id; PROTECT |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |

Constraint eksplisit:

- `final_document_version_unique`: `CONSTRAINT "final_document_version_unique" UNIQUE ("bid_revision_id", "document_version")`.
- `final_document_version_positive`: `CONSTRAINT "final_document_version_positive" CHECK ("document_version" > 0)`.
- `final_document_size_positive`: `CONSTRAINT "final_document_size_positive" CHECK ("size_bytes" > 0)`.
- `final_document_schema_positive`: `CONSTRAINT "final_document_schema_positive" CHECK ("snapshot_schema_version" > 0)`.
- `final_document_pdf_mime`: `CONSTRAINT "final_document_pdf_mime" CHECK ("mime_type" = 'application/pdf')`.

Indeks eksplisit:

- `final_document_revision_idx`: `bid_revision, -document_version`.

### `notifications_notification` — Notification

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `recipient_id` | `uuid` | Tidak | — | FK accounts_user.id; PROTECT |
| `type` | `varchar(40)` | Tidak | — | choices: BID_WAITING_APPROVAL, OPTIMIZATION_COMPLETED, OPTIMIZATION_FAILED, BID_APPROVED, BID_REJECTED, BID_SIGNED, DOCUMENT_COMPLETED, DOCUMENT_FAILED |
| `source_event_id` | `uuid` | Tidak | — | — |
| `source_entity_type` | `varchar(64)` | Tidak | — | — |
| `source_entity_id` | `uuid` | Tidak | — | — |
| `title` | `varchar(255)` | Tidak | — | — |
| `message` | `text` | Tidak | — | — |
| `read_at` | `timestamptz` | Ya | — | — |
| `created_at` | `timestamptz` | Tidak | — | Django auto_now_add |

Constraint eksplisit:

- `notification_event_recipient_unique`: `CONSTRAINT "notification_event_recipient_unique" UNIQUE ("recipient_id", "source_event_id", "type")`.

Indeks eksplisit:

- `notif_recipient_read_idx`: `recipient, read_at, -created_at`.

### `audit_audit_event` — AuditEvent

| Kolom | Tipe | Null | PK/unique | Catatan model |
|---|---|---|---|---|
| `id` | `uuid` | Tidak | PK | Django default: uuid.uuid4 |
| `actor_id` | `uuid` | Ya | — | FK accounts_user.id; PROTECT |
| `actor_name` | `varchar(255)` | Tidak | — | — |
| `entity_type` | `varchar(64)` | Tidak | — | — |
| `entity_id` | `uuid` | Tidak | — | — |
| `entity_revision` | `integer` | Ya | — | nonnegative integer (field type); positive checks terpisah jika ada |
| `action` | `varchar(64)` | Tidak | — | — |
| `from_status` | `varchar(32)` | Ya | — | — |
| `to_status` | `varchar(32)` | Ya | — | — |
| `reason` | `text` | Ya | — | — |
| `metadata` | `jsonb` | Tidak | — | Django default: builtins.dict |
| `correlation_id` | `varchar(100)` | Tidak | — | — |
| `occurred_at` | `timestamptz` | Tidak | — | Django auto_now_add |

Constraint eksplisit:

- `audit_event_revision_positive`: `CONSTRAINT "audit_event_revision_positive" CHECK (("entity_revision" IS NULL OR "entity_revision" > 0))`.

Indeks eksplisit:

- `audit_entity_timeline_idx`: `entity_type, entity_id, -occurred_at`.
- `audit_actor_timeline_idx`: `actor, -occurred_at`.

## 5. Invariant di atas schema

- Result VALID dan children, Tender revision/item, decision, signature, final document, selection, serta audit mempunyai guard mutation model/queryset terkait. Tidak ada trigger SQL append-only umum.
- Service result menjumlahkan Offer capacity lintas item dan memeriksa quantity tepat. Currency/Product/snapshot/actor consistency lintas row tidak cukup ditegakkan oleh FK saja.
- Partial unique `optimization_one_active_run_per_tender` berlaku per root Tender untuk PENDING/RUNNING. Lihat nama/SQL aktual dalam inventaris model di atas.
- Document job tidak mempunyai partial unique active-job constraint. Service mengunci Bid revision dan menggunakan kembali active job; `(bid_revision, document_version)` tetap unique.
- OneToOne decision/signature dan unique FinalDocument generation-job/version melindungi duplicate outcome. Tidak ada generic HTTP idempotency record.
- Current selection adalah row dengan selection number terbesar per Tender. Create/revise/submit Bid memerlukan selection dari Tender revision terbaru.

## 6. Snapshot, file, dan lifecycle

Tender content, optimization input, VALID result, submission, serta finalization snapshot/hash dicapture pada titik masing-masing. Schema JSON v1 mempunyai topologi spesifik per snapshot type; lihat builder `apps/sourcing/snapshots.py`, `apps/optimization/snapshots.py`, `apps/bids/snapshots.py`, dan `apps/documents/snapshots.py`.

File PDF memakai `documents/{bid_revision_id}/{revision_number}/{document_version}/{job_id}.pdf`; signature image memakai `signatures/{bid_revision_id}/{UUID}.{ext}`. Object version ID opsional; bucket versioning tidak diaktifkan otomatis oleh adapter/Compose. Version dokumen aplikasi berasal dari job sequence, bukan hanya version storage.

SIGNED menjadi FINALIZED setelah PDF disimpan dan diverifikasi; regeneration menghasilkan job/version/nomor baru dengan Bid tetap FINALIZED. DocumentNumberSequence menyimpan counter tahunan, tanpa relasi FK ke FinalDocument; reset canonical dataset tidak menghapus counter ini.

## 7. Migration dan data demo

Jalankan migration dependency graph Django melalui `manage.py migrate`; jangan mengasumsikan urutan manual antar modul. `makemigrations --check --dry-run --settings=config.settings.test` memeriksa model/migration drift tanpa membuat migration.

Command aktual `seed_demo` membuat/verifikasi akun, master, Offer, Tender, serta manual VALID result canonical. `reset_demo_data --confirm DEMO_ONLY` dan `smoke_demo --runs 1..3` memerlukan APP_ENV demo. Reset menggunakan penghapusan langsung dataset canonical, mempertahankan migration history dan document-number sequence. Lihat dokumen 08 dan 11 untuk data/prosedur lengkap.
