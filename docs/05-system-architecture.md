# System Architecture

## Medical Procurement Bid Optimizer

> Status: Target architecture MVP<br>
> Terakhir diperbarui: 9 September 2026

---

## 1. Tujuan

Dokumen ini menerjemahkan Product Overview, Business Rules, Use Cases, dan Domain Model menjadi arsitektur teknis untuk MVP **Medical Procurement Bid Optimizer**.

Dokumen ini menetapkan batas sistem, pembagian komponen dan dependency, ownership data, pola transaksi dan background processing, historical snapshot, audit trail, security, observability, resilience, deployment, serta keputusan arsitektur.

---

## 2. Sumber dan Prioritas Keputusan

Arsitektur ini diturunkan dari:

1. 01-product-overview.md — tujuan, pengguna, scope, dan product requirements;
2. 02-business-rules.md — formula, invariant, lifecycle, dan authorization;
3. 03-use-cases.md — actor, precondition, flow, dan postcondition;
4. 04-domain-model.md — domain area, aggregate, service, dan domain event.

Jika terdapat perbedaan antardokumen, baseline implementasi mengikuti aturan yang paling rinci pada dokumen 02–04 dan konfliknya dicatat pada **Open Questions**.

---

## 3. Architecture Goals

### 3.1 Correctness

- Tender Request tetap menjadi source of truth dan tidak dapat diubah oleh optimizer, result editor, atau Bid Proposal.
- Result MANUAL, OPTIMIZER, dan CUSTOMIZED menggunakan validator, calculation policy, precision, dan rounding policy yang sama.
- Seluruh transition status divalidasi di server dan tidak dapat dilompati.
- Formula harga beli, bid value, gross profit, actual margin, dan HPS feasibility hanya memiliki satu implementasi canonical.

### 3.2 Historical Integrity

- Perubahan Product, Supplier, dan Supplier Offer tidak mengubah Optimization Run, Procurement Result, submission, signature, atau Final Document historis.
- Selection, submission, decision, signature, dan finalization dapat ditelusuri ke actor, revision, timestamp, serta snapshot sumber.
- Dokumen final bersifat versioned, private, dan memiliki checksum SHA-256.

### 3.3 Reliability dan Security

- Optimization dan PDF generation tidak menahan HTTP request.
- Kegagalan publikasi background job dapat dideteksi dan dipulihkan melalui status job serta reconciliation.
- Redelivery, retry, double-click, dan concurrent request tidak menghasilkan transition atau notification ganda.
- Authentication, role, object-level authorization, dan status guard diberlakukan di server.
- Signature image dan PDF tidak tersedia melalui public URL permanen.

### 3.4 Simplicity for MVP

- Sistem menggunakan modular monolith agar transaction boundary dan deployment sederhana.
- PostgreSQL menjadi source of truth.
- Redis hanya menjadi broker/cache teknis, bukan penyimpan fakta bisnis.

---

## 4. System Context

Source PlantUML: [system-context.puml](images/system-context.puml).

~~~mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#ffffff"}}}%%
flowchart LR
    Admin[Admin]
    Staff[Procurement Staff]
    Manager[Manager]
    App[Medical Procurement Bid Optimizer]
    Institution[Instansi / Portal Tender]
    Supplier[Supplier]

    Admin -->|Kelola Product dan Supplier| App
    Staff -->|Catat tender/offer, susun result dan proposal| App
    Manager -->|Review, approve/reject, sign| App
    App -->|Bid Proposal PDF melalui user berizin| Staff
    Supplier -. Informasi offer dicatat manual .-> Staff
    Institution -. Dokumen tender masuk secara eksternal .-> Staff
    Staff -. Pengajuan PDF di luar sistem .-> Institution
~~~

Supplier dan instansi adalah pihak eksternal tanpa integrasi langsung pada MVP. Sistem tidak menangani supplier onboarding, negosiasi, submission ke portal, procurement contract, purchasing, inventory, shipping, invoicing, payment, accounting, atau ERP.

---

## 5. Architecture Overview

### 5.1 Style dan Container

Target MVP adalah **Django modular monolith**. Proses web dan worker menggunakan codebase serta database yang sama.

~~~mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#ffffff"}}}%%
flowchart TB
    Browser[Browser]
    Web[Django Web Application]
    Worker[Celery Workers]
    DB[(PostgreSQL)]
    Broker[(Redis Broker)]
    Storage[(Private Object Storage)]

    Browser -->|HTTPS| Web
    Web --> DB
    Web --> Storage
    Web --> Broker
    Broker --> Worker
    Worker --> DB
    Worker --> Storage
~~~

| Container | Tanggung jawab | Source of truth? |
|---|---|---|
| Browser | Server-rendered UI, form submission, status polling, authorized download | Tidak |
| Django Web | Authentication, authorization, synchronous use case, query/read model, task dispatch | Tidak |
| Celery Workers | Optimization, notification side effect, dan PDF generation | Tidak |
| PostgreSQL | Business data, snapshots, revision, audit, idempotency, dan job status | Ya |
| Redis | Celery broker dan data teknis berumur pendek | Tidak |
| Private Object Storage | Signature image dan immutable/versioned Final Document | Binary object saja; metadata canonical di PostgreSQL |

### 5.2 Request dan Dependency Direction

~~~text
HTTP
 -> URL Router
 -> View / Form
 -> Application Service
 -> Domain Policy / Calculator / Validator
 -> Django ORM / Task Queue / Storage Adapter
~~~

- View menangani HTTP dan representasi response.
- Application service mengorkestrasi authorization, transaction, locking, transition, snapshot, audit, dan task dispatch.
- Domain policy menangani invariant dan kalkulasi reusable tanpa dependency ke HTTP, queue, atau storage.
- Task background memanggil application service yang sama, bukan menduplikasi business rule.
- UI bukan enforcement point utama untuk permission atau business rule.

---

## 6. Application Components

Nama berikut adalah **batas logis target**. Satu Django app fisik boleh menampung beberapa komponen pada tahap awal, tetapi ownership dan dependency tetap dijaga.

| Komponen | Tanggung jawab | Data yang dimiliki |
|---|---|---|
| accounts | Authentication, account status, role, permission | User, role/group |
| catalog | Product dan Supplier lifecycle | Product, Supplier |
| tender | Pencatatan dan revision kebutuhan | TenderRequest aggregate |
| sourcing | Supplier Offer, manual/customized result, validation, cost, selection | SupplierOffer, ProcurementResult, selection history |
| optimization | Input snapshot, candidate, ranking, execution, retry | OptimizationRun |
| bids | Proposal revision, pricing, HPS, lifecycle | BidProposal aggregate |
| approval | Submission history dan keputusan Manager | ApprovalDecision |
| signatures | Signing policy dan signature metadata/file | Signature |
| documents | Finalization, rendering, versioning, storage, checksum | FinalDocument dan generation job |
| notifications | In-app notification dan read state | Notification |
| audit | Append-only business audit trail | AuditEvent |
| dashboard | Role-based projection | Read model; bukan source of truth |

Canonical policy yang dipakai web dan worker:

- SupplierOfferEligibilityPolicy;
- ProcurementResultValidator;
- ProcurementCostCalculator;
- MoneyRoundingPolicy;
- BidPricingCalculator;
- HpsFeasibilityPolicy;
- BidStatusTransitionPolicy;
- BidFinalizationPolicy.

Optimizer hanya membentuk kandidat; setiap kandidat tetap melewati validator dan calculator yang sama dengan result manual/customized.

Dependency rules:

- optimization bergantung pada kontrak tender dan policy sourcing, bukan sebaliknya;
- bids membaca snapshot Tender Request dan selected result; sourcing tidak bergantung pada bid pricing;
- approval, signatures, dan documents mengubah lifecycle melalui service/policy milik bids;
- notifications dan audit bereaksi terhadap fakta bisnis, tetapi tidak menentukan keberhasilan event sumber;
- dashboard tidak mengubah aggregate secara langsung;
- core domain tidak bergantung pada dashboard, template, Celery, atau SDK storage.

---

## 7. Data Architecture

### 7.1 Ownership dan Consistency Boundary

PostgreSQL adalah source of truth untuk status dan metadata bisnis. Setiap write dilakukan melalui application service pemilik aggregate.

| Consistency boundary | Aggregate root | Data yang diubah atomik |
|---|---|---|
| Kebutuhan tender | TenderRequest | TenderRequestItem dan revision metadata |
| Alternatif sourcing | ProcurementResult | ProcurementResultItem dan SupplierAllocation |
| Eksekusi optimizer | OptimizationRun | Input snapshot, rank/result reference, outcome |
| Proposal komersial | BidProposal | BidProposalItem, pricing, revision, status |
| Keputusan submission | ApprovalDecision | Submitted snapshot/reference dan decision |
| Dokumen final | FinalDocument | Version, object key, checksum, snapshot reference |

Aggregate tidak harus dimuat sebagai satu object besar untuk read path, tetapi invariant pada write path divalidasi dalam transaction boundary yang sesuai.

### 7.2 Historical Snapshot

Snapshot bukan pengganti foreign key. Reference dipakai untuk navigasi data asal, sedangkan snapshot dipakai untuk rekonstruksi historis.

| Tahap | Snapshot minimum |
|---|---|
| Tender revision | Institution text, metadata, HPS, seluruh item, dan seluruh atribut Product yang direferensikan |
| Optimization Run | Tender revision/input dan seluruh atribut Supplier Offer, Product, serta Supplier yang eligible |
| Procurement Result | Requirement, allocation, seluruh atribut Product/Supplier/Offer yang digunakan, harga, dan hasil kalkulasi |
| Bid submission revision | Tender, selected result, pricing input/output, HPS feasibility, schema/calculation version |
| Signature | Proposal revision, approved snapshot hash, signer identity/name, server time, private file reference |
| Final Document | Frozen content, template/document version, private object key, MIME type, size, SHA-256 |

Setiap snapshot memiliki schema version. Nilai uang menggunakan decimal dan currency MVP adalah IDR. Snapshot yang di-hash menggunakan serialization canonical.

### 7.3 Mutability Policy

- Product dan Supplier historis tidak di-hard-delete; gunakan inactive state.
- Supplier Offer yang belum digunakan dapat dikoreksi oleh Procurement Staff dengan audit trail.
- Perubahan informasi komersial Supplier Offer yang telah digunakan membuat offer baru; offer lama dipertahankan dan dapat dibuat inactive/expired.
- Tender yang sudah digunakan pada submission direvisi melalui revision baru.
- Procurement Result DRAFT dapat diedit. Setelah VALID, result immutable; perubahan membuat CUSTOMIZED result baru.
- Karena VALID sudah immutable, persistent state LOCKED tidak diperlukan untuk correctness. Submission tetap membekukan reference dan snapshot.
- Proposal REJECTED direvisi sebagai revision DRAFT baru; submission/decision lama tidak ditimpa.
- Satu submitted revision memiliki satu terminal decision: approve atau reject.
- Final Document menggunakan object key baru per version dan tidak overwrite file historis.

### 7.4 Decimal dan Constraints

- Semua kalkulasi memakai fixed-precision decimal, bukan binary floating point.
- Intermediate precision dan rounding mode dimiliki satu MoneyRoundingPolicy.
- Actual margin dihitung ulang dari nilai final setelah rounding.
- Nilai final disimpan bersama calculation policy/version.

Data Model minimal menyediakan constraint untuk:

- positive quantity dan price;
- discount 0..100 dan target margin 0 <= margin < 100;
- satu active Optimization Run (PENDING/RUNNING) per Tender Request;
- satu item result per pasangan Procurement Result dan Tender Request Item;
- unique notification berdasarkan recipient, source event, dan type;
- unique idempotency key dalam scope operation/actor;
- unique revision/version identity untuk submission dan Final Document.

Invariant lintas row seperti complete fulfillment, product matching, HPS feasibility, dan legal transition ditegakkan service dalam transaction serta concurrency test.

### 7.5 Audit, Domain Event, dan Log

- **AuditEvent** adalah fakta bisnis append-only berisi actor, entity, action, transition, timestamp, dan reason/note.
- **Task Message** adalah pesan teknis idempotent untuk memicu background processing.
- **Operational Log** adalah telemetry diagnosis dengan retention tersendiri.

AuditEvent ditulis dalam transaksi bisnis yang sama. Update/delete audit history ditolak melalui application policy dan, pada production, database privilege atau trigger append-only.

---

## 8. Transaction dan Concurrency

### 8.1 Transaction Boundaries

Operasi berikut dilakukan atomik:

- membuat Optimization Run, input snapshot, dan audit;
- claim PENDING menjadi RUNNING;
- menyimpan result, rank, run outcome, audit, dan notification;
- memilih Procurement Result dan mencatat selection;
- membuat submission revision/snapshot dan DRAFT menjadi WAITING_APPROVAL;
- approve/reject beserta decision dan audit;
- signing beserta validasi approved snapshot;
- menyimpan FinalDocument dan mengubah SIGNED menjadi FINALIZED setelah file tersedia.

### 8.2 Concurrency Control

- Transition memakai conditional update atau SELECT FOR UPDATE pada aggregate root.
- Revision/version number mendeteksi stale form dan concurrent edit.
- Partial unique constraint mencegah dua active Optimization Run untuk tender yang sama.
- Duplicate transition mengembalikan outcome aman atau conflict tanpa membuat event kedua.
- Selection dan submission memvalidasi ulang result/tender relationship di dalam transaction.

---

## 9. Asynchronous Processing

### 9.1 Pekerjaan Background

Pekerjaan asynchronous:

- optimization;
- Bid Proposal PDF rendering/finalization;
- notification side effect jika tidak dibuat inline.

Read/review, manual validation, pricing, submission, decision, dan signing tetap synchronous selama memenuhi target performa MVP.

Task dipublikasikan langsung ke Redis/Celery melalui callback setelah transaction commit. Run/job yang tertinggal dalam status PENDING dideteksi oleh reconciliation dan dapat dipublikasikan ulang. Worker tetap idempotent karena delivery broker bersifat at-least-once.

### 9.2 Optimization Run

~~~text
PENDING -> RUNNING -> COMPLETED
                   -> FAILED
~~~

- Input snapshot dibuat sebelum task dipublikasikan.
- Worker membaca snapshot run, bukan current Supplier Offer.
- Sukses dengan nol kandidat valid adalah COMPLETED dengan result count 0, bukan failure teknis.
- Exception teknis menghasilkan FAILED dengan safe error dan diagnostic reference.
- Business retry selalu membuat run baru; delivery retry tidak membuat run baru.
- Completion/failure notification memakai source event ID agar tidak duplikat.

### 9.3 PDF Generation dan Finalization

PDF generation berjalan di background. Technical DocumentGenerationJob boleh memiliki PENDING, RUNNING, COMPLETED, atau FAILED, tetapi status teknis ini tidak ditambahkan ke lifecycle Bid Proposal.

- Bid Proposal tetap SIGNED selama rendering.
- Worker hanya memakai frozen finalization input.
- Renderer tidak boleh mengambil arbitrary remote resource.
- File ditulis ke object key unik, lalu checksum dan metadata diverifikasi.
- Transaction akhir menyimpan FinalDocument dan mengubah SIGNED menjadi FINALIZED.
- Jika rendering, storage, atau DB finalization gagal, proposal tidak menjadi FINALIZED.
- Orphan file dibersihkan reconciliation/lifecycle policy setelah grace period.
- Delivery retry idempotent; regeneration yang diminta membuat document version baru.

### 9.4 Queue Isolation

Gunakan queue logis terpisah:

- optimization untuk pekerjaan CPU/DB intensive;
- documents untuk PDF;
- default untuk notification ringan.

Concurrency, timeout, dan retry diatur per queue agar optimization tidak menyebabkan starvation pada finalization.

---

## 10. Key Runtime Flows

### 10.1 Manual atau Customized Result

~~~mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#ffffff"}}}%%
sequenceDiagram
    actor Staff as Procurement Staff
    participant Web as Django Web
    participant Service as Sourcing Service
    participant Policy as Shared Validator/Calculator
    participant DB as PostgreSQL

    Staff->>Web: Simpan result/allocation
    Web->>Service: Command + actor + expected version
    Service->>Policy: Validate offer, product, quantity
    Policy-->>Service: Outcome + Decimal cost
    Service->>DB: Transaction: aggregate + snapshot + audit
    Service-->>Web: DRAFT atau VALID
~~~

Customization membuat result baru dengan source result reference; source tidak di-update.

### 10.2 Optimization

~~~mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#ffffff"}}}%%
sequenceDiagram
    actor Staff as Procurement Staff
    participant Web as Django Web
    participant DB as PostgreSQL
    participant Queue as Redis/Celery
    participant Worker as Optimization Worker

    Staff->>Web: Run optimizer
    Web->>DB: PENDING run + snapshot
    DB-->>Web: Commit run ID
    Web->>Queue: Publish task setelah commit
    Queue->>Worker: Deliver
    Worker->>DB: Claim PENDING menjadi RUNNING
    Worker->>Worker: Build, validate, calculate, rank
    Worker->>DB: Results + ranks + COMPLETED + event
    Worker->>DB: Idempotent notification
~~~

### 10.3 Submission dan Decision

~~~mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#ffffff"}}}%%
sequenceDiagram
    actor Staff as Procurement Staff
    actor Manager
    participant Web as Django Web
    participant Bid as Bid Service
    participant DB as PostgreSQL

    Staff->>Web: Submit proposal
    Web->>Bid: Submit command
    Bid->>DB: Lock dan validate DRAFT
    Bid->>Bid: Revalidate result, pricing, HPS
    Bid->>DB: Snapshot + WAITING_APPROVAL + audit
    Manager->>Web: Approve atau reject
    Web->>Bid: Decision command
    Bid->>DB: Lock dan validate WAITING_APPROVAL
    Bid->>DB: Decision + status + audit
~~~

Rejection menghasilkan notification idempotent. Revision sesudah rejection mempertahankan seluruh history lama.

### 10.4 Signing dan Finalization

~~~mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#ffffff"}}}%%
sequenceDiagram
    actor Manager
    actor User as User Berizin
    participant Web as Django Web
    participant DB as PostgreSQL
    participant Queue as Background Queue
    participant Worker as Document Worker
    participant Storage as Private Storage

    Manager->>Web: Sign approved revision
    Web->>DB: Validate approving manager + snapshot hash
    Web->>DB: Signature + SIGNED + audit
    User->>Web: Finalize
    Web->>DB: Validate SIGNED + generation job
    Web->>Queue: Publish task setelah commit
    Queue->>Worker: Generate immutable PDF
    Worker->>Storage: Store unique object
    Worker->>DB: FinalDocument + checksum + FINALIZED + audit
~~~

Download memeriksa authentication, role, object permission, FINALIZED status, dan document version sebelum streaming file atau memberi signed URL berumur sangat singkat.

---

## 11. Security Architecture

### 11.1 Identity dan Session

- Gunakan Django authentication dan session-based login untuk web MVP.
- Account inactive tidak dapat membuat session baru.
- Cookie production menggunakan Secure, HttpOnly, dan SameSite yang sesuai.
- CSRF protection wajib untuk seluruh state-changing request.
- TLS berakhir pada reverse proxy/load balancer tepercaya.

### 11.2 Authorization

Baseline role matrix berdasarkan Business Rules dan Use Cases:

| Capability | Admin | Procurement Staff | Manager |
|---|:---:|:---:|:---:|
| Kelola Product/Supplier | Ya | Tidak | Tidak |
| Catat dan kelola Supplier Offer | Tidak | Ya | Tidak |
| Catat Tender Request | Tidak | Ya | Tidak |
| Susun/run/customize/select result | Tidak | Ya | Tidak |
| Buat, price, submit Bid Proposal | Tidak | Ya | Tidak |
| Approve/reject | Tidak | Tidak | Ya |
| Sign | Tidak | Tidak | Approving Manager saja |
| Finalize | Tidak | Ya| Sesuai keputusan terbuka |
| Download PDF|  Tidak | Ya | Ya |

Authorization diperiksa sebagai role/capability permission sekaligus object/state permission, termasuk organization scope, tender relationship, approving manager, dan proposal status.

### 11.3 Sensitive Data dan File

- Secret berasal dari environment/secret manager dan tidak masuk repository.
- Signature dan Final Document berada di private storage dengan encryption at rest.
- Upload signature dibatasi tipe, ukuran, resolusi, dan magic-byte; nama user tidak menjadi object key.
- PDF renderer memakai local/allowlisted assets serta memblokir arbitrary URL/file access untuk mencegah SSRF dan file disclosure.
- Signed URL, jika digunakan, berumur sangat singkat dan tidak ditulis ke log.
- Backup mengikuti encryption dan access-control policy yang sama.

### 11.4 Application Hardening

- Seluruh input dan transition divalidasi server-side.
- Django escaping tetap aktif; rich text yang diizinkan disanitasi.
- Terapkan HSTS setelah HTTPS stabil, Content Security Policy, frame protection, dan MIME sniffing protection.
- Login dan endpoint mahal seperti optimization diberi rate limit.
- Dependency scanning, Django deployment checks, dan secret scanning dijalankan di CI.

---

## 12. Observability dan Auditability

Setiap HTTP request memiliki correlation ID yang diteruskan ke task. Run/job/entity ID digunakan untuk menelusuri alur tanpa menulis snapshot penuh ke log.

Structured log minimal memuat:

~~~text
timestamp, level, service/process, environment
correlation_id, actor_id, entity_type/entity_id
operation, from_status/to_status
duration_ms, outcome, safe_error_code
~~~

Credential, token, signature binary, private URL, full proposal snapshot, dan stack trace untuk end user tidak dicatat.

Metrics minimum:

- HTTP count, latency, error rate, permission denial;
- DB saturation, slow query, lock wait, transaction failure;
- pending job count dan oldest pending age;
- queue depth, oldest task age, retry/dead task per queue;
- optimization duration, result count, completed/failed rate;
- document generation duration/failure dan storage error;
- duplicate-prevention count;
- login failure dan suspicious download.

Health checks:

- **Liveness** memeriksa process;
- **Readiness web** memeriksa dependency minimum, terutama database;
- **Worker health** memeriksa heartbeat dan queue consumption;
- deep Redis/storage check dipisahkan agar gangguan nonkritis tidak selalu mengeluarkan web dari load balancer.

Audit trail bisnis tidak bergantung pada retention operational log.

---

## 13. Failure Handling dan Resilience

| Failure | Perilaku | Recovery |
|---|---|---|
| Duplicate HTTP command | Expected version/idempotency mencegah duplicate transition | Outcome lama atau 409 Conflict |
| DB commit gagal | Tidak ada status, audit, atau job parsial | Retry bila aman |
| Web mati setelah commit sebelum task terbit | Run/job tetap PENDING | Reconciliation memublikasikan ulang |
| Redis tidak tersedia | Run/job tetap PENDING | Alert dan publish ulang setelah pulih |
| Optimization redelivery | Worker melihat claim/outcome lama | No-op atau resume idempotent |
| Optimization exception | Run FAILED dengan safe error | User membuat run baru |
| Nol kandidat valid | Run COMPLETED dengan nol result | Perbaiki offer/manual result atau run baru |
| Notification redelivery | Unique source event menolak duplicate | No-op |
| PDF/storage gagal | Proposal tetap SIGNED, job FAILED | Retry idempotent |
| File ada, DB commit gagal | File menjadi orphan | Reconciliation cleanup setelah grace period |
| Concurrent approve/reject | Lock/conditional transition memenangkan satu | Request lain conflict |
| Master berubah saat proses | Snapshot/frozen version tetap dipakai | Histori tidak berubah |

Retry otomatis hanya untuk error transient, memakai exponential backoff dan batas percobaan. Business validation failure tidak di-retry. Setelah batas retry, task masuk failure/dead-letter handling dan menghasilkan alert.

PostgreSQL menggunakan automated backup dan point-in-time recovery bila tersedia. Object storage menggunakan versioning/immutability. Restore drill harus memverifikasi reference object dan checksum. Target RPO/RTO serta retention masih perlu diputuskan.

---

## 14. Deployment Architecture

~~~mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#ffffff"}}}%%
flowchart TB
    User[User Browser]
    Edge[HTTPS Load Balancer / Reverse Proxy]
    Web1[Django Web]
    Web2[Django Web optional]
    OptWorker[Optimization Worker]
    DocWorker[Document Worker]
    PG[(Managed PostgreSQL)]
    Redis[(Managed Redis)]
    Object[(Private Object Storage)]
    Monitor[Logs / Metrics / Alerts]

    User --> Edge
    Edge --> Web1
    Edge --> Web2
    Web1 --> PG
    Web2 --> PG
    Web1 --> Redis
    Web2 --> Redis
    Redis --> OptWorker
    Redis --> DocWorker
    OptWorker --> PG
    DocWorker --> PG
    DocWorker --> Object
    Web1 --> Object
    Web2 --> Object
    Web1 -. telemetry .-> Monitor
    OptWorker -. telemetry .-> Monitor
    DocWorker -. telemetry .-> Monitor
~~~

### 14.1 Environment dan Release

- Pisahkan local, CI/test, staging, dan production.
- Production data tidak disalin ke non-production tanpa anonymization dan authorization.
- Web dan worker dibangun dari artifact/commit yang sama, dengan command dan resource limit berbeda.
- Migration dijalankan satu kali sebagai release step terkontrol.
- Schema change memakai expand/migrate/contract bila rolling deployment diperlukan.
- Template PDF, font, dan asset dipaketkan/versioned agar output reproducible.

### 14.2 Scaling

- Web dapat ditambah horizontal dan tidak bergantung pada local disk.
- Optimization worker diskalakan berdasar queue age/resource usage tanpa melampaui kapasitas DB.
- Document worker diskalakan terpisah.
- Local filesystem container tidak digunakan untuk file permanen.

---

## 15. Architecture Decisions

| ID | Keputusan | Status | Alasan dan konsekuensi |
|---|---|---|---|
| ADR-001 | Django modular monolith | Accepted | Transaction lintas domain sederhana; module boundary dijaga di review/test. |
| ADR-002 | PostgreSQL sebagai source of truth | Accepted | ACID, constraint, row lock, partial index, Decimal; Redis tidak canonical. |
| ADR-003 | Celery + Redis | Accepted | Optimization/PDF background; task wajib idempotent karena at-least-once delivery. |
| ADR-004 | Shared validator/calculator | Accepted | Semua source type memakai policy identik. |
| ADR-005 | Versioned snapshot plus entity reference | Accepted | Histori stabil dan sumber tetap dapat ditelusuri. |
| ADR-006 | VALID result immutable | Accepted | Customization membuat result baru; persistent LOCKED tidak diperlukan. |
| ADR-007 | Satu decision per submitted revision | Accepted | Approve/reject tidak ambigu; resubmission membuat revision baru. |
| ADR-008 | Async PDF; FINALIZED setelah artefak berhasil | Accepted | Tidak ada status final tanpa file final. |
| ADR-009 | Private, versioned object dan SHA-256 | Accepted | Confidentiality, integrity, dan non-overwrite history. |
| ADR-010 | IDR-only MVP | Accepted | Mengikuti Domain Model; Money tetap eksplisit. |
| ADR-011 | Institution sebagai value/snapshot Tender | Accepted | Master Institution belum diperlukan. |
| ADR-012 | Append-only audit, bukan event sourcing | Accepted | Traceability tanpa kompleksitas event-sourced state. |
| ADR-013 | Server-rendered Django UI | Proposed | Selaras dengan codebase awal; API dapat memakai service yang sama kelak. |

---

## 16. Constraints dan Assumptions

- Aplikasi adalah alat penyusunan penawaran internal, bukan purchasing atau inventory.
- Supplier Offer dicatat user; tidak ada real-time supplier API atau stock reservation.
- available_quantity adalah batas pada snapshot/result, bukan reservasi global. Dua alternatif boleh memakai availability yang sama karena belum menjadi purchase order.
- Optimizer MVP hanya meminimalkan total_purchase; gross profit bukan objective optimizer.
- Tie-break deterministic: total purchase, jumlah supplier, lalu stable candidate identifier.
- HPS optional, tetapi bila tersedia divalidasi ulang saat submission dan finalization.
- Electronic signature MVP bukan cryptographic digital signature tersertifikasi.
- Notification hanya in-app.
- Final Document tidak dikirim otomatis ke instansi/portal.
- Waktu event berasal dari server, disimpan UTC, dan ditampilkan sesuai timezone.
- Baseline deployment melayani satu perusahaan kecuali Data Model menetapkan tenancy.

---

## 17. Open Questions

Keputusan berikut diperlukan sebelum authorization, capacity, dan production readiness difinalisasi:

1. Siapa yang boleh memicu finalization: Procurement Staff, approving Manager, keduanya, atau role khusus?
2. Apakah instalasi pasti single-company, atau perlu organization/tenant boundary sejak MVP?
3. Berapa maksimum tender item, eligible offer per item, kandidat tersimpan, durasi optimization, dan concurrent run?
4. Berapa target availability, p95 latency, RPO, RTO, backup, audit, dan document retention?
5. Provider PostgreSQL, Redis, object storage, secret manager, hosting, dan observability apa yang dipilih?
6. Apakah user management cukup melalui Django Admin, atau perlu invitation, password reset, MFA, dan/atau SSO?
7. Apa format dan batas signature image serta kebijakan penggantian signature profile?
8. Apa template legal, font, nomor dokumen, metadata wajib, dan aturan versioning PDF?
9. Bagaimana revision Tender Request setelah Bid Proposal dibuat memengaruhi draft dan submission lama?

---

## 18. Traceability

### 18.1 Product Requirements ke Arsitektur

| Requirement | Realisasi arsitektur |
|---|---|
| PRD-001 | accounts, session security, role/object authorization, server-side guard |
| PRD-002 | catalog/sourcing, inactive policy, snapshot history |
| PRD-003 | tender aggregate dan revision/snapshot |
| PRD-004 | sourcing, shared validator dan cost calculator |
| PRD-005 | optimization, Celery/Redis, input snapshot, deterministic ranking |
| PRD-006 | Immutable result lineage, read model, selection history |
| PRD-007 | Idempotent in-app notification dengan unique source-event constraint |
| PRD-008 | bids, shared pricing/HPS policy, submission snapshot |
| PRD-009 | approval, conditional transition, append-only decision/audit |
| PRD-010 | signatures, approving-manager guard, snapshot hash, private file |
| PRD-011 | documents worker, private versioned PDF, SHA-256, authorized download |
| PRD-012 | Versioned snapshot, audit, immutable result/submission/document |

### 18.2 Business Rules ke Enforcement Point

| Rule area | Enforcement utama | Defense tambahan |
|---|---|---|
| BR-ACCESS-* | Permission/application service | Endpoint guard dan tests |
| BR-MASTER-*, BR-OFFER-* | Catalog/sourcing policy | FK, check, inactive policy |
| BR-REQ-* | Tender aggregate/service | Revision dan snapshot |
| BR-RESULT-* | ProcurementResultValidator | Transaction dan constraints |
| BR-CALC-*, BR-MONEY-* | Canonical Decimal calculators | Golden test, calculation version |
| BR-OPT-* | Optimization service/worker | Partial unique index, snapshot, idempotency |
| BR-BID-*, BR-HPS-* | BidPricingCalculator/HpsFeasibilityPolicy | Submit/finalize revalidation |
| BR-NOTIF-* | Notification consumer | Unique source-event constraint |
| BR-APP-* | Transition policy/approval service | Row lock, revision, append-only decision |
| BR-SIGN-* | Signature service | Approver/revision/hash constraint |
| BR-FINAL-* | BidFinalizationPolicy/document worker | Private immutable storage, checksum |

### 18.3 Use Cases ke Runtime Flow

| Use Cases | Arsitektur/flow |
|---|---|
| UC-001–005 | Synchronous accounts, catalog, sourcing, dan tender service |
| UC-006, UC-009 | Manual/customized result dengan shared policy |
| UC-007 | Asynchronous optimization |
| UC-008, UC-010 | Result read model dan transactional selection |
| UC-011–013, UC-016 | Bid draft, pricing, revision, submission |
| UC-014–015 | Transactional approval/rejection |
| UC-017 | Signing terhadap approved snapshot |
| UC-018 | Asynchronous finalization/document |
| UC-019 | Authorized private document download |

---

## 19. Architecture Fitness Checks

Arsitektur tetap sesuai jika automated test dan operational checks membuktikan:

- manual, optimizer, dan customized result menghasilkan nilai identik untuk allocation yang sama;
- tidak ada valid result dengan quantity mismatch, product mismatch, atau offer ineligible;
- concurrent request tidak membuat dua active Optimization Run untuk tender yang sama;
- concurrent approve/reject hanya menghasilkan satu decision;
- perubahan master/offer setelah snapshot tidak mengubah output historis;
- task redelivery tidak menggandakan result, decision, notification, atau Final Document;
- Bid Proposal tidak melompati WAITING_APPROVAL, APPROVED, atau SIGNED;
- proposal tidak FINALIZED sebelum PDF/checksum tersimpan;
- user tanpa object permission tidak dapat melihat snapshot, signature, atau PDF;
- restore database/storage dapat memverifikasi Final Document melalui checksum.
