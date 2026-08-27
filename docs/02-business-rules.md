# Business Rules

## Mini Procurement Contract Optimizer

## 1. Purpose

Dokumen ini mendefinisikan aturan bisnis utama yang harus selalu dipenuhi oleh sistem Mini Procurement Contract Optimizer.

Business rules menjadi acuan untuk:

* application logic,
* validation,
* database constraints,
* background processing,
* approval workflow,
* testing.

---

## 2. Procurement Request Rules

### BR-REQ-001 — Procurement Request as Source of Truth

Procurement request merepresentasikan kebutuhan asli dari instansi.

### BR-REQ-002 — Request Immutability During Optimization

Kebutuhan asli dari instansi tidak boleh diubah hanya untuk mendapatkan hasil optimization yang lebih baik.

### BR-REQ-003 — Requirement Changes

Jika kebutuhan instansi berubah secara resmi, perubahan harus dilakukan melalui update request yang dapat ditelusuri.

### BR-REQ-004 — Minimum Request Item

Procurement request harus memiliki minimal satu item sebelum dapat diproses lebih lanjut.

### BR-REQ-005 — Valid Quantity

Quantity setiap procurement item harus lebih besar dari 0.

---

## 3. Master Data Rules

### BR-MASTER-001 — Approved Master Data

Vendor dan product yang tersedia di sistem dianggap sudah melalui proses validasi bisnis di luar aplikasi.

### BR-MASTER-002 — Active Product

Product yang inactive tidak boleh digunakan untuk procurement baru.

### BR-MASTER-003 — Active Vendor

Vendor yang inactive tidak boleh digunakan sebagai kandidat fulfillment.

### BR-MASTER-004 — Active Vendor Offer

Vendor offer yang inactive tidak boleh digunakan dalam optimization.

### BR-MASTER-005 — Historical Data

Perubahan status vendor, product, atau vendor offer tidak boleh mengubah historical procurement yang sudah diproses.

---

## 4. Vendor Offer Rules

### BR-OFFER-001 — Vendor and Product Relation

Setiap vendor offer harus terkait dengan satu vendor dan satu product.

### BR-OFFER-002 — Valid Base Price

HNA tidak boleh bernilai negatif.

### BR-OFFER-003 — Valid Discount

Discount harus berada pada rentang 0 sampai 100 persen.

### BR-OFFER-004 — Valid Purchase Price

Net purchase price harus lebih besar dari 0 agar offer dapat digunakan dalam optimization.

### BR-OFFER-005 — Price Calculation

Net purchase price dihitung dari HNA dan discount.

```text
net_purchase_price =
HNA - (HNA × discount_percent / 100)
```

### BR-OFFER-006 — Master Data Update

Admin dapat memperbarui vendor offer selama data tersebut masih digunakan sebagai master data aktif.

Perubahan vendor offer tidak boleh otomatis mengubah hasil optimization yang sudah tersimpan.

---

## 5. Candidate Combination Rules

### BR-COMB-001 — Combination Purpose

Candidate combination merepresentasikan alternatif cara memenuhi procurement request.

### BR-COMB-002 — Request Must Remain Unchanged

Perubahan candidate combination tidak boleh mengubah procurement request asli.

### BR-COMB-003 — Eligible Data Only

Candidate combination hanya boleh menggunakan:

* active vendor,
* active product,
* active vendor offer.

### BR-COMB-004 — Combination Editability

Admin dapat mengubah candidate combination sebelum hasil final dikirim untuk approval.

### BR-COMB-005 — Traceability

Setiap candidate combination harus dapat ditelusuri ke procurement request dan vendor offer yang digunakan.

---

## 6. Optimization Rules

### BR-OPT-001 — Background Processing

Optimization harus dijalankan sebagai background job.

### BR-OPT-002 — No Concurrent Duplicate Run

Sistem tidak boleh menjalankan lebih dari satu optimization aktif untuk procurement request yang sama pada waktu yang sama.

### BR-OPT-003 — Optimization Input

Optimizer hanya boleh menggunakan data yang valid dan aktif pada saat optimization dijalankan.

### BR-OPT-004 — Optimization Scope

Optimizer mengevaluasi candidate combination.

Optimizer tidak boleh mengubah kebutuhan procurement dari instansi.

### BR-OPT-005 — Optimization Result

Setiap optimization run harus menghasilkan status yang jelas:

* PENDING
* RUNNING
* COMPLETED
* FAILED

### BR-OPT-006 — Failure Handling

Jika optimization gagal:

* status run harus menjadi `FAILED`,
* error harus dicatat,
* Procurement Staff dapat menjalankan ulang optimization.

### BR-OPT-007 — Snapshot Result

Hasil optimization harus disimpan sebagai snapshot.

Snapshot minimal menyimpan:

* vendor,
* product,
* quantity,
* selling price,
* HNA,
* discount,
* net purchase price,
* total purchase,
* total selling price,
* gross profit,
* margin.

### BR-OPT-008 — Historical Result Protection

Perubahan vendor offer setelah optimization selesai tidak boleh mengubah optimization result lama.

### BR-OPT-009 — Re-run Optimization

Optimization dapat dijalankan ulang sebelum procurement dikirim untuk approval.

Run baru menghasilkan result baru dan tidak menimpa historical run sebelumnya secara diam-diam.

---

## 7. Optimization Calculation Rules

### BR-CALC-001 — Total Selling Price

```text
total_selling_price =
quantity × target_unit_price
```

### BR-CALC-002 — Total Purchase

```text
total_purchase =
quantity × net_purchase_price
```

### BR-CALC-003 — Gross Profit

```text
gross_profit =
total_selling_price - total_purchase
```

### BR-CALC-004 — Margin

```text
margin_percent =
(gross_profit / total_selling_price) × 100
```

### BR-CALC-005 — Zero Selling Price

Jika total selling price bernilai 0, margin tidak boleh menyebabkan division-by-zero error.

---

## 8. Notification Rules

### BR-NOTIF-001 — Optimization Completion Notification

Setelah optimization selesai, Procurement Staff yang menjalankan proses harus menerima in-app notification.

### BR-NOTIF-002 — Failure Notification

Jika optimization gagal, Procurement Staff harus dapat mengetahui bahwa proses gagal.

### BR-NOTIF-003 — Notification Traceability

Notification harus dapat dikaitkan dengan procurement request atau optimization run terkait.

---

## 9. Approval Rules

### BR-APP-001 — Submission Eligibility

Procurement hanya dapat dikirim untuk approval jika:

* optimization berhasil,
* terdapat selected result,
* status procurement memungkinkan submission.

### BR-APP-002 — Waiting Approval State

Setelah submit, procurement harus masuk ke status `WAITING_APPROVAL`.

### BR-APP-003 — Manager Authority

Hanya user dengan role Manager yang dapat melakukan approve atau reject.

### BR-APP-004 — Approval Eligibility

Manager hanya dapat approve procurement yang berada pada status `WAITING_APPROVAL`.

### BR-APP-005 — Rejection Eligibility

Manager hanya dapat reject procurement yang berada pada status `WAITING_APPROVAL`.

### BR-APP-006 — Rejection Reason

Manager wajib memberikan alasan ketika melakukan rejection.

### BR-APP-007 — Approval Audit

Setiap submission, approval, dan rejection harus dicatat.

Minimal mencatat:

* action,
* actor,
* timestamp,
* note jika ada.

---

## 10. Electronic Signature Rules

### BR-SIGN-001 — Signature Eligibility

Contract hanya dapat ditandatangani setelah procurement disetujui.

### BR-SIGN-002 — Signer

Hanya Manager yang melakukan approval yang dapat memberikan electronic signature.

### BR-SIGN-003 — Signature Metadata

Saat signing, sistem harus menyimpan minimal:

* signed_by,
* signed_at,
* signer_name.

### BR-SIGN-004 — Signature Image

Signature image bersifat opsional untuk MVP.

### BR-SIGN-005 — Signed Contract Immutability

Setelah contract ditandatangani, data contract final tidak boleh diubah secara diam-diam.

---

## 11. Contract Generation Rules

### BR-CONTRACT-001 — PDF Eligibility

Final contract PDF hanya dapat dibuat setelah contract ditandatangani.

### BR-CONTRACT-002 — Approved Result

Contract harus menggunakan optimization result yang telah disetujui.

### BR-CONTRACT-003 — Contract Content

Contract final harus merepresentasikan:

* procurement request,
* selected optimization result,
* vendor information,
* price snapshot,
* approval information,
* signature information.

### BR-CONTRACT-004 — Historical Consistency

Perubahan master data setelah contract dibuat tidak boleh mengubah isi contract final.

### BR-CONTRACT-005 — Regeneration

Jika terjadi perubahan material setelah signing, sistem tidak boleh mengubah PDF lama secara diam-diam.

Perubahan harus menghasilkan versi baru atau proses approval ulang.

---

## 12. Procurement Status Rules

Lifecycle utama:

```text
DRAFT
  ↓
OPTIMIZING
  ↓
OPTIMIZED
  ↓
WAITING_APPROVAL
  ↓
APPROVED
  ↓
SIGNED
  ↓
GENERATED
```

Failure state:

```text
OPTIMIZING
    ↓
OPTIMIZATION_FAILED
```

Rejection state:

```text
WAITING_APPROVAL
        ↓
     REJECTED
```

### BR-STATUS-001

Procurement baru dibuat dengan status `DRAFT`.

### BR-STATUS-002

Procurement masuk ke `OPTIMIZING` ketika background optimization dimulai.

### BR-STATUS-003

Procurement menjadi `OPTIMIZED` hanya setelah optimization berhasil.

### BR-STATUS-004

Procurement menjadi `WAITING_APPROVAL` setelah berhasil disubmit.

### BR-STATUS-005

Procurement menjadi `APPROVED` setelah disetujui Manager.

### BR-STATUS-006

Procurement menjadi `SIGNED` setelah Manager memberikan electronic signature.

### BR-STATUS-007

Procurement menjadi `GENERATED` setelah final contract PDF berhasil dibuat.

---

## 13. Auditability Rules

Sistem harus memungkinkan proses utama ditelusuri.

Minimal harus dapat diketahui:

* siapa membuat procurement request,
* siapa menjalankan optimization,
* kapan optimization dijalankan,
* result mana yang dipilih,
* siapa submit approval,
* siapa approve atau reject,
* kapan approval dilakukan,
* siapa melakukan signing,
* kapan signing dilakukan,
* kapan contract PDF dibuat.

---

## 14. MVP Assumptions

Untuk MVP:

* vendor onboarding berada di luar sistem,
* MoU management berada di luar sistem,
* vendor dan product diinput manual,
* notification hanya in-app,
* electronic signature bersifat sederhana,
* tidak menggunakan cryptographic certificate,
* satu level Manager approval sudah cukup,
* optimizer bekerja pada candidate combination yang tersedia,
* advanced optimization belum menjadi fokus utama.
