# System Architecture

## Medical Procurement Bid Optimizer

> Status: Target architecture demo MVP<br>
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

Jika terdapat perbedaan antardokumen, baseline implementasi mengikuti aturan yang paling rinci pada dokumen 02–04 dan konfliknya dicatat pada **Decision Register** di bagian 17.

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
    Storage[(MinIO Private Object Storage)]

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
| MinIO Object Storage | Signature image dan immutable/versioned Final Document pada private bucket | Binary object saja; metadata canonical di PostgreSQL |

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
- Satu Tender hanya boleh memiliki satu active run. Deployment membatasi maksimum dua optimization task bersamaan.
- Satu run menerima maksimum 100 Tender Request Item dan 50 eligible Supplier Offer per item serta hanya menyimpan 20 kandidat terbaik.
- Soft timeout adalah 4 menit dan hard timeout 5 menit. Seluruh limit merupakan konfigurasi deployment dan divalidasi sebelum task dibuat.
- Worker membaca snapshot run, bukan current Supplier Offer.
- Sukses dengan nol kandidat valid adalah COMPLETED dengan result count 0, bukan failure teknis.
- Exception teknis menghasilkan FAILED dengan safe error dan diagnostic reference.
- Business retry selalu membuat run baru; delivery retry tidak membuat run baru.
- Completion/failure notification memakai source event ID agar tidak duplikat.

### 9.3 PDF Generation dan Finalization

PDF generation berjalan di background. Technical DocumentGenerationJob boleh memiliki PENDING, RUNNING, COMPLETED, atau FAILED, tetapi status teknis ini tidak ditambahkan ke lifecycle Bid Proposal.

- Bid Proposal tetap SIGNED selama rendering.
- Worker hanya memakai frozen finalization input.
- Renderer memakai template HTML/CSS A4 `template_version=1` dan font Noto Sans yang dipaketkan; remote font/resource tidak diizinkan.
- Nomor dokumen mengikuti `BID/{YYYY}/{sequence:06d}/R{revision:02d}` dan masa berlaku penawaran demo adalah 30 hari kalender.
- PDF memuat nomor/revision, instansi dan tender, tanggal, masa berlaku, item/quantity/unit price/total, approval, signer, dan document version.
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
    participant Storage as MinIO Private Storage

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
| Finalize | Tidak | Ya | Tidak |
| Download PDF | Tidak | Ya | Ya |

Authorization diperiksa sebagai role/capability permission sekaligus object/state permission, termasuk tender relationship, approving manager, dan proposal status.

### 11.3 Sensitive Data dan File

- Secret berasal dari environment/secret manager dan tidak masuk repository.
- Signature dan Final Document berada di private storage dengan encryption at rest.
- Signature image bersifat opsional. Jika digunakan, upload hanya menerima PNG/JPEG yang lolos magic-byte validation, maksimum 1 MiB, dan dimensi 200×80 sampai 2000×1000 px; nama user tidak menjadi object key.
- Penggantian signature profile hanya berlaku untuk signing berikutnya. Signature historis tetap menunjuk private MinIO object/snapshot yang dibekukan saat signing.
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

Telemetry demo menggunakan OpenTelemetry Collector untuk menerima metrics aplikasi, Prometheus sebagai metrics backend, dan Grafana untuk dashboard serta rule evaluation. Grafana mengirim operational alert ke Telegram. Log cukup berupa structured log yang dibaca melalui `docker compose logs`; centralized log dan distributed trace backend tidak dipasang pada demo. Telegram tidak digunakan untuk notification bisnis kepada Admin, Procurement Staff, atau Manager.

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

MinIO menggunakan private bucket dan object versioning. Demo tidak memiliki RPO/RTO atau retention formal. Jika data demo perlu dipertahankan, backup PostgreSQL dan MinIO disalin ke lokasi di luar VPS karena volume pada host yang sama tidak melindungi dari kehilangan VPS; recovery diverifikasi dengan mencocokkan object reference dan checksum.

---

## 14. Deployment Architecture

~~~mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#ffffff"}}}%%
flowchart TB
    User[User Browser]
    Offsite[(Off-host Backup)]
    Telegram[Telegram Alert Receiver]

    subgraph VPS[Hostinger VPS Jakarta - One Docker Compose Deployment]
        Edge[HTTPS Reverse Proxy]
        Web[Django Web]
        Scheduler[Scheduler / Reconciliation]
        OptWorker[Optimization Worker]
        DocWorker[Document Worker]
        PG[(PostgreSQL Volume)]
        Redis[(Redis Broker)]
        MinIO[(MinIO Volume)]
        OTel[OpenTelemetry Collector]
        Prometheus[(Prometheus Metrics)]
        Grafana[Grafana Dashboard / Alerting]

        Edge --> Web
        Web --> PG
        Web --> Redis
        Web --> MinIO
        Scheduler --> PG
        Scheduler --> Redis
        Redis --> OptWorker
        Redis --> DocWorker
        OptWorker --> PG
        DocWorker --> PG
        DocWorker --> MinIO
        Web -. metrics .-> OTel
        Scheduler -. metrics .-> OTel
        OptWorker -. metrics .-> OTel
        DocWorker -. metrics .-> OTel
        OTel --> Prometheus
        Prometheus --> Grafana
    end

    User --> Edge
    PG -. encrypted backup .-> Offsite
    MinIO -. encrypted backup .-> Offsite
    Grafana -->|Operational alert| Telegram
~~~

Deployment ini ditujukan untuk demo MVP pada satu Hostinger VPS di Jakarta. Tidak ada SLA atau maintenance window formal. Downtime saat deployment, restart, patching manual, atau pemulihan dapat diterima selama dijadwalkan di luar sesi demo.

### 14.1 Environment dan Release

- Pisahkan local, CI/test, dan demo sebagai Compose project/environment yang berbeda; demo tidak berbagi volume atau credential dengan environment lain.
- Gunakan data sintetis atau data yang telah dianonimkan pada environment demo.
- Satu `compose.yaml` mendefinisikan reverse proxy, Django web, scheduler/reconciliation, optimization worker, document worker, PostgreSQL, Redis, MinIO, OpenTelemetry Collector, Prometheus, dan Grafana sebagai container terpisah dalam satu deployment.
- Web, scheduler, dan worker menggunakan image/commit aplikasi yang sama, tetapi command, health check, restart policy, dan resource limit berbeda.
- PostgreSQL dan MinIO memakai persistent volume terpisah. Redis tidak menyimpan fakta bisnis canonical dan boleh dipulihkan dari status job PostgreSQL.
- Hanya reverse proxy yang membuka port publik. PostgreSQL, Redis, dan MinIO hanya dapat diakses melalui private Compose network; MinIO Console tidak diekspos ke internet.
- Migration dijalankan satu kali sebagai release step terkontrol.
- Image menggunakan tag/digest immutable; deployment demo tidak memakai bind mount source code atau tag `latest`.
- Template PDF, font, dan asset dipaketkan/versioned agar output reproducible.
- Jika data demo perlu dipertahankan, backup terenkripsi PostgreSQL dan MinIO disalin keluar dari VPS dan diuji melalui restore sederhana.
- Tidak ada maintenance window atau patch schedule formal untuk demo. Upgrade dilakukan manual di luar sesi demo dan dicatat secara ringkas.
- Prometheus menyimpan metrics, Grafana menyediakan dashboard/rule evaluation dan mengirim alert ke Telegram, sedangkan log demo dibaca melalui `docker compose logs`. Loki dan trace backend seperti Tempo tidak digunakan pada demo.

### 14.2 Scaling

- Scaling MVP dilakukan secara vertikal pada VPS atau dengan menambah replica container worker di Compose selama kapasitas CPU, memory, disk I/O, dan PostgreSQL masih mencukupi.
- Optimization worker dan document worker tetap berupa service terpisah agar concurrency serta resource limit dapat diatur berbeda.
- Application container tidak menyimpan file permanen pada writable layer. Data permanen hanya berada pada volume PostgreSQL/MinIO dan, jika diaktifkan, backup off-host.
- Satu VPS adalah single point of failure dan bukan high availability. Multi-host deployment, database managed, atau distributed object storage memerlukan keputusan arsitektur baru.

---

## 15. Architecture Decisions

Bagian ini mencatat keputusan yang paling memengaruhi bentuk sistem. Setiap keputusan menyebutkan alternatif yang dipertimbangkan, solusi yang dipilih, alasan, serta konsekuensi yang harus diterima atau dimitigasi.

### 15.1 Ringkasan Keputusan

| ID | Area keputusan | Alternatif utama | Solusi yang dipilih | Status |
|---|---|---|---|---|
| ADR-001 | Bentuk aplikasi | Microservices; monolith tanpa batas modul; modular monolith | Django modular monolith | Accepted |
| ADR-002 | Penyimpanan data canonical | Beberapa database per modul; document database; PostgreSQL tunggal | PostgreSQL dalam Compose sebagai source of truth | Accepted |
| ADR-003 | Pekerjaan berat dan pengiriman task | Synchronous HTTP; Celery dengan Transactional Outbox; Celery direct publish | Celery + Redis dalam Compose, publish setelah commit, dan reconciliation | Accepted |
| ADR-004 | Implementasi business rule | Rule terpisah per flow; rule di model/view; shared domain policy | Shared validator dan calculator | Accepted |
| ADR-005 | Histori data | Membaca master terkini; snapshot saja; event sourcing; reference + snapshot | Versioned snapshot plus entity reference | Accepted |
| ADR-006 | Perubahan result | Result VALID tetap editable; state LOCKED; immutable result | Result VALID immutable; perubahan membuat CUSTOMIZED result baru | Accepted |
| ADR-007 | Approval | Decision dapat ditimpa; banyak decision pada revision sama; satu terminal decision | Satu terminal decision per submitted revision | Accepted |
| ADR-008 | Pembuatan dokumen | PDF synchronous; status final sebelum file; PDF asynchronous | PDF asynchronous; FINALIZED hanya setelah file berhasil | Accepted |
| ADR-009 | Penyimpanan dokumen | Database binary; public storage; external object storage; self-hosted MinIO | Private MinIO, versioning, dan SHA-256 | Accepted |
| ADR-010 | Mata uang MVP | Multi-currency sejak awal; IDR implisit; IDR eksplisit | IDR-only dengan tipe Money/Decimal yang eksplisit | Accepted |
| ADR-011 | Data instansi | Master Institution; integrasi portal; value/snapshot pada Tender | Institution sebagai value dan snapshot Tender | Accepted |
| ADR-012 | Audit | Operational log saja; event sourcing; append-only audit | Append-only AuditEvent, bukan event sourcing | Accepted |
| ADR-013 | Antarmuka web | SPA + API; server-rendered UI; desktop application | Server-rendered Django UI | Accepted |
| ADR-014 | Semantik availability Supplier Offer | Global reservation; pengurangan saat optimization; reusable per Bid | `available_quantity` reusable sebagai batas kelayakan per Bid | Accepted |
| ADR-015 | Topologi deployment | Managed services terpisah; Kubernetes; satu Docker Compose deployment | Seluruh subsystem pada satu Hostinger VPS Jakarta dengan Docker Compose | Accepted |

### 15.2 ADR-001 — Django Modular Monolith

**Masalah.** MVP memiliki beberapa area bisnis—tender, sourcing, optimization, bid, approval, signature, dan document—yang saling berhubungan dan sering membutuhkan konsistensi dalam satu transaksi.

**Alternatif.** Microservices memberi deployment dan scaling independen, tetapi menambah distributed transaction, network failure, contract versioning, dan observability lintas service. Monolith tanpa batas modul lebih cepat dibuat, tetapi mudah menghasilkan dependency yang tidak terkontrol.

**Keputusan.** Gunakan satu codebase dan satu unit deployment Django dengan batas modul logis yang jelas. Setiap aggregate hanya diubah melalui application service pemiliknya, sementara dependency antarmodul mengikuti aturan pada bagian 6.

**Konsekuensi.** Transaction boundary, testing, dan deployment MVP lebih sederhana. Sebagai gantinya, boundary modul harus dijaga melalui struktur package, review, dan test dependency. Worker dapat diskalakan terpisah walaupun memakai codebase yang sama. Pemisahan menjadi service baru dipertimbangkan jika data produksi menunjukkan kebutuhan scaling atau ownership yang berbeda.

### 15.3 ADR-002 — PostgreSQL sebagai Source of Truth

**Masalah.** Sistem membutuhkan status workflow, nilai uang presisi, constraint, audit, snapshot, dan concurrency control yang konsisten.

**Alternatif.** Database terpisah per modul meningkatkan isolasi tetapi mempersulit transaksi lintas domain. Document database memudahkan penyimpanan snapshot, tetapi kurang sesuai untuk constraint relasional dan workflow yang dominan. Redis cepat, tetapi tidak digunakan sebagai penyimpan fakta bisnis permanen.

**Keputusan.** Seluruh status dan metadata bisnis canonical disimpan di PostgreSQL yang berjalan sebagai service Docker Compose dengan persistent volume. Snapshot dapat memakai JSON terstruktur/versioned bila sesuai, sedangkan relasi dan constraint utama tetap relational. Redis hanya berfungsi sebagai broker dan penyimpan data teknis sementara.

**Konsekuensi.** Sistem memperoleh ACID transaction, row lock, partial unique index, dan Decimal yang kuat. PostgreSQL menjadi dependency kritis dan potensi bottleneck bersama, sehingga query, index, connection pool, backup, dan kapasitasnya harus dipantau. Karena PostgreSQL berada pada VPS yang sama, kerusakan host memengaruhi aplikasi dan database sekaligus; backup off-host direkomendasikan jika data demo perlu dipertahankan dan menjadi wajib sebelum deployment production.

### 15.4 ADR-003 — Celery + Redis dengan Direct Publish

**Masalah.** Optimization dan PDF generation dapat memakan waktu lama sehingga tidak boleh menahan HTTP request.

**Alternatif.** Menjalankannya synchronously menyederhanakan infrastruktur, tetapi berisiko timeout dan pengalaman pengguna yang buruk. Transactional Outbox memberi jaminan publikasi lebih kuat setelah database commit, tetapi membutuhkan tabel outbox, dispatcher, cleanup, dan operasional tambahan. Direct publish paling sederhana, tetapi ada celah jika proses web mati setelah commit dan sebelum task berhasil dikirim.

**Keputusan.** Redis berjalan sebagai service internal Docker Compose. Simpan Optimization Run atau DocumentGenerationJob berstatus PENDING dalam transaction, lalu publish task langsung ke Celery melalui callback setelah commit. Proses reconciliation mencari job PENDING yang melewati batas waktu dan memublikasikannya ulang. Worker melakukan claim secara atomik dan harus idempotent terhadap redelivery.

**Konsekuensi.** Infrastruktur MVP lebih sederhana karena tidak memiliki layanan Redis eksternal atau Outbox Dispatcher. Redis pada satu VPS bukan high availability dan datanya boleh hilang; job PENDING di PostgreSQL menjadi dasar recovery. Risiko lost publish dimitigasi, bukan dihilangkan secara atomik, melalui metric oldest pending age, alert, dan reconciliation. Transactional Outbox perlu dievaluasi kembali jika volume, target availability, atau toleransi keterlambatan job menjadi lebih ketat.

### 15.5 ADR-004 — Shared Validator dan Calculator

**Masalah.** Result MANUAL, OPTIMIZER, dan CUSTOMIZED harus menghasilkan validasi dan angka yang sama untuk input serta allocation yang sama.

**Alternatif.** Masing-masing flow dapat memiliki implementasi sendiri, tetapi formula dan rounding mudah berbeda seiring perubahan. Menaruh rule di view atau task juga mengikat domain pada delivery mechanism dan menyulitkan reuse.

**Keputusan.** Eligibility policy, result validator, cost calculator, bid pricing calculator, HPS policy, precision, dan rounding ditempatkan pada shared domain policy yang dipanggil oleh web maupun worker.

**Konsekuensi.** Rule memiliki satu implementasi canonical dan dapat diuji tanpa HTTP, database, atau Celery. Policy harus dijaga tetap deterministic dan tidak mengambil current mutable data secara tersembunyi; seluruh input yang dibutuhkan harus diberikan secara eksplisit.

### 15.6 ADR-005 — Versioned Snapshot plus Entity Reference

**Masalah.** Perubahan Product, Supplier, Offer, atau Tender tidak boleh mengubah arti result, approval, signature, dan dokumen lama.

**Alternatif.** Membaca record master terkini lebih hemat storage tetapi merusak histori. Snapshot saja menjaga histori, tetapi menyulitkan navigasi dan penelusuran sumber. Event sourcing dapat merekonstruksi seluruh state, tetapi kompleksitasnya tidak sebanding dengan kebutuhan MVP.

**Keputusan.** Simpan foreign key/reference untuk lineage dan snapshot versioned untuk nilai historis. Snapshot menggunakan schema version dan canonical serialization ketika perlu di-hash.

**Konsekuensi.** Histori dapat direkonstruksi secara stabil tanpa kehilangan hubungan ke data asal. Biaya storage dan kebutuhan migrasi/reader untuk versi snapshot lama meningkat. Snapshot harus dibuat pada boundary yang telah ditetapkan dan tidak boleh berisi data current yang dibaca ulang saat rendering historis.

### 15.7 ADR-006 dan ADR-007 — Immutability Result dan Decision

**Masalah.** Pengeditan atau penimpaan data setelah validasi/approval dapat menghilangkan bukti mengenai apa yang sebenarnya direview dan disetujui.

**Alternatif.** Result VALID dan decision dapat terus diedit dengan audit perubahan, atau ditahan menggunakan status LOCKED tambahan. Keduanya menambah state dan tetap berisiko membuat referensi historis ambigu.

**Keputusan.** Procurement Result menjadi immutable setelah VALID; perubahan menghasilkan CUSTOMIZED result baru dengan reference ke sumber. Setiap submitted proposal revision hanya boleh memiliki satu terminal decision, yaitu APPROVED atau REJECTED. Proposal yang ditolak diperbaiki sebagai revision DRAFT baru.

**Konsekuensi.** Lineage review jelas dan state LOCKED permanen tidak dibutuhkan. Jumlah revision/result akan bertambah, sehingga UI harus menampilkan versi aktif, sumber customization, dan history secara jelas. Unique constraint dan conditional transition mencegah dua keputusan akibat request bersamaan.

### 15.8 ADR-008 dan ADR-009 — Final Document Asynchronous dan Private

**Masalah.** PDF adalah artefak legal/historis yang pembuatannya dapat gagal atau lambat dan isinya tidak boleh berubah setelah final.

**Alternatif.** Rendering synchronous lebih sederhana tetapi rentan timeout. Menetapkan status FINALIZED sebelum upload selesai dapat menghasilkan status final tanpa dokumen. Menyimpan binary di database memusatkan backup tetapi membesarkan database; public object storage memudahkan akses tetapi tidak sesuai untuk data sensitif.

**Keputusan.** PDF dibuat oleh worker dari frozen input. Proposal tetap SIGNED selama proses dan berubah menjadi FINALIZED hanya setelah object berhasil disimpan serta metadata dan checksum tercatat. File disimpan pada private bucket MinIO dengan object key baru per version, bucket versioning, dan SHA-256.

**Konsekuensi.** Tidak ada proposal final tanpa artefak yang dapat diverifikasi. Sistem memerlukan job status, retry idempotent, orphan-file reconciliation, lifecycle storage, dan authorized download atau signed URL berumur sangat singkat. MinIO single-node pada VPS yang sama tidak memberi high availability; persistent volume dan versioning tidak menggantikan backup off-host.

### 15.9 ADR-010 dan ADR-011 — Penyederhanaan Scope MVP

**Masalah.** Multi-currency dan master Institution menambah model, validasi, UI, dan integrasi yang belum dibutuhkan oleh scope saat ini.

**Alternatif.** Multi-currency sejak awal membutuhkan currency pada setiap nilai, exchange-rate policy, dan aturan pembulatan per mata uang. Master Institution berguna untuk deduplication dan integrasi, tetapi membutuhkan lifecycle dan ownership tersendiri.

**Keputusan.** MVP hanya menggunakan IDR, tetapi nilai tetap dimodelkan dengan Decimal dan currency eksplisit agar perluasan tidak tertutup. Institution disimpan sebagai value dan snapshot pada Tender Request, bukan aggregate master terpisah.

**Konsekuensi.** Model dan UI MVP lebih sederhana. Penambahan mata uang atau master Institution kelak membutuhkan migration dan keputusan baru; asumsi IDR tidak boleh tersebar sebagai angka atau string hard-coded di banyak modul.

### 15.10 ADR-012 — Append-only Audit, Bukan Event Sourcing

**Masalah.** Sistem harus dapat menjelaskan siapa melakukan tindakan apa, pada entity/revision mana, kapan, dan mengapa.

**Alternatif.** Operational log saja tidak cukup stabil untuk bukti bisnis karena format dan retention berbeda. Event sourcing memberi histori lengkap sebagai sumber state, tetapi membutuhkan event schema evolution, projection, replay, dan pola pengembangan yang lebih kompleks.

**Keputusan.** Current state disimpan secara normal di tabel domain, sedangkan AuditEvent ditulis append-only dalam transaksi bisnis yang sama. Operational log tetap terpisah untuk diagnosis.

**Konsekuensi.** Audit bisnis dapat ditelusuri tanpa kompleksitas event sourcing. AuditEvent tidak digunakan untuk membangun ulang seluruh state, sehingga snapshot dan revision tetap diperlukan. Update/delete audit harus ditolak oleh application policy dan diperkuat dengan database privilege atau trigger di production.

### 15.11 ADR-013 — Server-rendered Django UI

**Masalah.** MVP membutuhkan UI internal untuk form, review, approval, polling job, dan download, tanpa kebutuhan interaksi client yang sangat kompleks.

**Alternatif.** SPA dengan API memberi interaksi client lebih kaya dan pemisahan frontend, tetapi menambah codebase, authentication surface, state management, dan deployment. Desktop application tidak sesuai dengan akses multi-user berbasis web.

**Keputusan.** Gunakan Django server-rendered UI dan form untuk MVP. Application service tetap dipisahkan dari view agar API dapat ditambahkan tanpa menduplikasi business rule.

**Konsekuensi.** Delivery awal lebih cepat dan security session/CSRF lebih langsung. Pengalaman real-time dibatasi pada polling atau enhancement ringan. Jika kebutuhan UI menjadi lebih interaktif, API atau frontend terpisah dapat ditambahkan dengan tetap memakai application service yang sama.

### 15.12 ADR-014 — Supplier Offer Availability Reusable per Bid

**Masalah.** Dua atau lebih Bid dapat dioptimalkan pada waktu yang sama menggunakan Supplier Offer, harga, dan `available_quantity` yang sama.

**Alternatif.** Global reservation mencegah total penggunaan lintas Bid melampaui quantity, tetapi membutuhkan reservation ledger, expiry, release, dan concurrency control. Mengurangi quantity ketika optimization tidak tepat karena satu run dapat menghasilkan beberapa alternatif dan Bid belum tentu diajukan atau dimenangkan.

**Keputusan.** `available_quantity` hanya menjadi batas kelayakan untuk setiap Procurement Result. Supplier Offer yang sama boleh digunakan oleh beberapa Bid dan sistem tidak mengurangi atau mereservasi quantity pada tahap optimization sampai finalization.

**Konsekuensi.** Dua Bid dapat sama-sama memakai seluruh quantity dari offer yang sama. Ini dapat diterima karena sistem berhenti pada pembuatan Bid Proposal dan tidak menjanjikan stok Supplier. Jika scope kelak mencakup tender award, kontrak, atau Purchase Order, ketersediaan harus dikonfirmasi ulang dan reservation/commitment perlu dimodelkan sebagai keputusan arsitektur baru.

### 15.13 ADR-015 — Satu Docker Compose Deployment

**Masalah.** Web, worker, database, broker, dan object storage perlu dijalankan dengan konfigurasi yang repeatable tanpa kompleksitas orchestrator cluster untuk MVP.

**Alternatif.** Managed services mengurangi beban operasi dan memisahkan failure domain, tetapi menambah biaya serta dependency provider. Kubernetes mendukung multi-host orchestration dan scaling, tetapi terlalu kompleks untuk ukuran MVP. Instalasi process langsung pada VPS lebih sederhana di awal, tetapi dependency, restart, isolation, dan reproducibility lebih sulit dijaga.

**Keputusan.** Gunakan satu Hostinger VPS di Jakarta dan satu Docker Compose deployment. Reverse proxy, Django web, scheduler/reconciliation, optimization worker, document worker, PostgreSQL, Redis, MinIO, OpenTelemetry Collector, Prometheus, dan Grafana berjalan sebagai service/container terpisah pada private Compose network. Deployment ini hanya untuk demo dan Grafana mengirim operational alert ke Telegram.

**Konsekuensi.** Deployment dan local-demo parity menjadi sederhana, tetapi seluruh service berbagi CPU, memory, disk, dan failure domain satu VPS. Database dan object storage menggunakan persistent volume, sedangkan backup terenkripsi sebaiknya dikirim ke lokasi di luar VPS. Arsitektur ini tidak mengklaim high availability dan tidak memiliki SLA atau maintenance window formal; kebutuhan production, HA, atau multi-host akan memerlukan perubahan deployment.

---

## 16. Constraints dan Assumptions

- Aplikasi adalah alat penyusunan penawaran internal, bukan purchasing atau inventory.
- Supplier Offer dicatat user; tidak ada real-time supplier API atau stock reservation.
- available_quantity adalah batas kelayakan pada setiap snapshot/result, bukan reservasi global. Supplier Offer yang sama beserta quantity-nya boleh digunakan bersama oleh beberapa Bid karena Bid belum menjadi purchase order.
- Optimizer MVP hanya meminimalkan total_purchase; gross profit bukan objective optimizer.
- Tie-break deterministic: total purchase, jumlah supplier, lalu stable candidate identifier.
- HPS optional, tetapi bila tersedia divalidasi ulang saat submission dan finalization.
- Electronic signature MVP bukan cryptographic digital signature tersertifikasi.
- Notification hanya in-app.
- Final Document tidak dikirim otomatis ke instansi/portal.
- Waktu event berasal dari server, disimpan UTC, dan ditampilkan sesuai timezone.
- MVP melayani satu perusahaan dan tidak menerapkan organization/tenant boundary.

---

## 17. Decision Register dan Demo Defaults

Seluruh pertanyaan arsitektur untuk demo telah diputuskan. Nilai di bagian ini menjadi default implementasi demo dan dapat dibuka kembali melalui ADR baru jika aplikasi dipromosikan menjadi production.

### 17.1 Keputusan Demo

| No. | Pertanyaan | Keputusan | Dampak arsitektur |
|---|---|---|---|
| 1 | Siapa yang boleh memicu finalization? | Procurement Staff saja. | Endpoint finalization menolak Admin dan Manager. Manager tetap melakukan approval dan approving Manager yang sama melakukan signing. |
| 2 | Apakah MVP memerlukan multi-tenancy? | Tidak. MVP single-company. | `organization_id` tidak diwajibkan pada setiap aggregate. Perlu ADR dan migration baru jika multi-tenancy ditambahkan. |
| 3 | Apa batas optimization? | Maksimum 100 tender item, 50 eligible offer per item, 20 kandidat terbaik disimpan, soft timeout 4 menit, hard timeout 5 menit, satu active run per Tender, dan maksimum dua optimization task bersamaan. | Batas dibuat configurable. Request yang melewati batas ditolak sebelum task dibuat. Benchmark dapat mengubah konfigurasi tanpa mengubah business rule. |
| 4 | Apakah demo memiliki SLA, RPO/RTO, retention, dan maintenance window formal? | Tidak. Deployment ini hanya untuk demo dan dijalankan secara best-effort. Tidak ada SLA, RPO/RTO, retention bisnis, atau maintenance window formal. | Target performa tetap diuji agar demo responsif. Backup sebelum sesi demo dan recovery manual direkomendasikan, tetapi tidak menjadi jaminan layanan production. |
| 5 | Apa deployment dan provider komponen utama? | Satu Hostinger VPS Jakarta dengan Docker Compose. Baseline kapasitas demo: 4 vCPU, 8 GiB RAM, dan 100 GiB NVMe. PostgreSQL, Redis, MinIO, OpenTelemetry Collector, Prometheus, dan Grafana berjalan sebagai service internal. Grafana mengirim operational alert ke Telegram. | Seluruh service berbagi satu failure domain. Gunakan private Compose network, persistent volume untuk PostgreSQL/MinIO/Prometheus, resource limit, health check, serta backup off-host bila data demo perlu dipertahankan. |
| 6 | Bagaimana user dikelola? | Admin membuat, mengubah role, menonaktifkan, dan melakukan reset akun melalui Django Admin. Tidak ada self-registration, invitation, MFA, atau SSO pada MVP. | Aplikasi tetap menyediakan login untuk Procurement Staff dan Manager. Akses Django Admin hanya untuk Admin; password validator, session security, dan audit perubahan akun tetap wajib. |
| 7 | Apa aturan signature image? | Gambar opsional. Jika digunakan, hanya PNG/JPEG yang lolos magic-byte validation, maksimum 1 MiB, dan dimensi 200×80 sampai 2000×1000 px. | File disimpan private di MinIO. Penggantian signature profile hanya berlaku untuk signing berikutnya; signature historis tetap menggunakan object/snapshot lama. |
| 8 | Apa aturan template dan versioning PDF? | Template demo berupa HTML/CSS A4 dengan font Noto Sans yang dipaketkan dan `template_version=1`. Nomor dokumen memakai `BID/{YYYY}/{sequence:06d}/R{revision:02d}`. Masa berlaku penawaran demo adalah 30 hari kalender. | PDF memuat nomor/revision, instansi dan tender, tanggal, masa berlaku, item/quantity/unit price/total, approval, signer, dan document version. Perubahan material membuat Bid Proposal revision baru; regeneration teknis membuat FinalDocument version baru tanpa overwrite. |
| 9 | Apa dampak revisi Tender Request terhadap Bid Proposal lama? | Revisi baru tidak mengubah Bid Proposal atau submission lama. Seluruh versi lama tetap menggunakan tender revision dan snapshot asalnya. | Draft yang menunjuk revision lama tidak boleh disubmit sebagai revision terbaru tanpa explicit rebase/revision dan validasi ulang. Submission, approval, signature, dan Final Document lama tetap immutable. |

Keputusan tambahan yang telah diklarifikasi: `available_quantity` boleh digunakan bersama oleh beberapa Bid. Nilai tersebut adalah batas kelayakan per result, bukan stok atau reservasi global. Sistem tidak mengurangi quantity ketika optimization, selection, submission, approval, atau finalization dijalankan.

### 17.2 Catatan Implementasi Deployment

- **Satu deployment bukan satu container.** Setiap process memiliki container terpisah agar restart, health check, dependency, concurrency, dan resource limit dapat diatur secara independen.
- **PostgreSQL menyimpan data/metadata bisnis; MinIO menyimpan binary.** Database menyimpan object key, MIME type, size, version, checksum, dan snapshot reference. Signature image dan PDF berada pada private bucket MinIO.
- **PostgreSQL dan MinIO wajib memakai persistent volume.** Redis tidak menyimpan fakta bisnis canonical sehingga recovery task tetap berasal dari status PENDING pada PostgreSQL.
- **Volume pada satu VPS bukan backup.** Jika data demo perlu dipertahankan setelah kehilangan VPS, backup terenkripsi harus disalin ke failure domain lain dan diuji restore-nya.
- **MinIO bucket versioning diaktifkan**, tetapi aplikasi tetap memakai object key baru untuk setiap Final Document version dan tidak mengandalkan overwrite.
- **Hostinger harus berupa VPS**, bukan Web atau Cloud Hosting, karena Docker, Django/Python, Celery worker, PostgreSQL, Redis, dan MinIO memerlukan runtime serta process management yang dapat dikendalikan.
- **Pilih lokasi Indonesia/Jakarta saat setup VPS.** Ketersediaan lokasi harus dikonfirmasi di hPanel ketika provisioning karena pilihan lokasi dapat bergantung pada kapasitas provider.
- **Telegram hanya menerima operational alert.** Notifikasi bisnis seperti optimization selesai atau proposal ditolak tetap merupakan in-app notification.
- **Tidak ada maintenance window formal untuk demo.** Deployment dan patch manual dilakukan di luar sesi presentasi; standar production ditentukan jika aplikasi dipromosikan dari demo.
- **GitHub Actions Secrets adalah secret untuk workflow CI/CD**, bukan runtime secret store bagi process Django/Celery yang sudah berjalan. Workflow boleh mengirimkan secret saat deployment, tetapi secret production harus tersedia secara aman di VPS dan tidak ditulis ke repository atau image.
- **Telemetry demo sudah diputuskan:** OpenTelemetry Collector menerima metrics, Prometheus menyimpannya, Grafana menampilkan dashboard dan mengevaluasi alert rule, lalu Telegram menjadi contact point. Loki, Tempo, dan centralized log storage tidak digunakan agar deployment demo tetap ringan.

Referensi implementasi: [Docker Compose production](https://docs.docker.com/compose/how-tos/production/), [Docker Compose volumes](https://docs.docker.com/reference/compose-file/volumes/), [MinIO container deployment](https://min.io/docs/minio/container/index.html), [MinIO object versioning](https://min.io/docs/minio/kubernetes/upstream/administration/object-management/object-versioning.html), [Hostinger server locations](https://support.hostinger.com/en/articles/1583267-where-are-hostinger-servers-located), [Hostinger framework support](https://www.hostinger.com/support/which-programming-languages-and-frameworks-are-supported-at-hostinger/), [GitHub Actions Secrets](https://docs.github.com/en/actions/concepts/security/secrets), [OpenTelemetry overview](https://opentelemetry.io/docs/what-is-opentelemetry/), [Prometheus overview](https://prometheus.io/docs/tutorials/getting_started/), dan [Grafana Telegram contact point](https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/configure-telegram/).

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
