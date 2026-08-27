# Product Overview

## Mini Procurement Contract Optimizer

## 1. Product Summary

Mini Procurement Contract Optimizer adalah aplikasi web berbasis Django untuk membantu perusahaan memproses kebutuhan procurement dari sebuah instansi menggunakan vendor dan produk yang sudah tersedia pada master data internal.

Sistem berfokus pada pencatatan kebutuhan procurement, penyusunan kandidat kombinasi vendor dan produk, proses optimasi, approval Manager, electronic signature sederhana, dan pembuatan kontrak final dalam format PDF.

Vendor dan produk yang digunakan pada sistem diasumsikan sudah melalui proses kerja sama dan validasi bisnis di luar aplikasi.

---

## 2. Problem Statement

Proses procurement yang dilakukan menggunakan spreadsheet atau proses manual memiliki beberapa keterbatasan:

* Data vendor dan produk sulit dikelola secara konsisten.
* Perbandingan kombinasi vendor dilakukan secara manual.
* Perhitungan harga, gross profit, dan margin rentan terhadap kesalahan karena dihitung manual.
* Hasil pemilihan vendor sulit ditelusuri kembali.
* Approval dan finalisasi kontrak belum memiliki workflow yang terstruktur.

Sistem ini dibuat untuk menjadikan proses procurement lebih terstruktur, traceable, dan repeatable.

---

## 3. Product Goal

Tujuan utama MVP adalah:

* Mencatat kebutuhan procurement dari instansi.
* Mengelola master vendor, produk, dan vendor offer.
* Membuat optimizer pemilihan kandidat item-item yang memberikan margin tertinggi antara harga vendor dengan tawaran dari instansi.
* Mendukung review dan approval oleh Manager.
* Menghasilkan kontrak final dalam format PDF yang sudah ditandatangani oleh manager.

---

## 4. Users and Roles

### Admin

Admin bertanggung jawab mengelola master data dan kandidat kombinasi procurement.

Hak akses utama:

* Mengelola master product.
* Mengelola master vendor.
* Mengelola vendor offer.
* Mengatur kandidat kombinasi yang dapat digunakan dalam proses optimizer.

Admin tidak mengubah kebutuhan asli dari instansi untuk mendapatkan hasil optimizer yang lebih baik.

### Procurement Staff

Procurement Staff bertanggung jawab memproses kebutuhan procurement.

Hak akses utama:

* Membuat procurement request.
* Menambahkan kebutuhan dari instansi.
* Menjalankan optimizer.
* Melihat status optimizer.
* Menerima notifikasi ketika optimizer selesai.
* Melihat hasil optimizer.
* Mengajukan hasil procurement untuk approval.
* Mengakses kontrak final.

### Manager

Manager bertanggung jawab melakukan review dan approval.

Hak akses utama:

* Melihat procurement yang menunggu approval.
* Melihat kebutuhan instansi dan hasil optimizer.
* Approve atau reject procurement.
* Memberikan electronic signature pada procurement (sudah dalam bentuk kontrak) yang disetujui.

---

## 5. Core Concept

Sistem membedakan antara kebutuhan asli dari instansi dengan cara internal perusahaan memenuhi kebutuhan tersebut.

### Procurement Request

Procurement Request merepresentasikan kebutuhan asli dari instansi.

Contoh:

```text id="d5yqku"
Product A
Quantity: 1,000

Product B
Quantity: 500
```

Data kebutuhan tersebut menjadi acuan utama dan tidak boleh berubah hanya karena proses optimasi.

### Candidate Combination

Candidate Combination merupakan alternatif cara memenuhi kebutuhan tersebut menggunakan vendor dan offer yang tersedia.

Contoh:

```text id="krknad"
Combination A
Product A → Vendor A
Product B → Vendor B
```

atau:

```text id="ltxjxa"
Combination B
Product A → Vendor C
Product B → Vendor A
```

Optimizer mengevaluasi candidate combination untuk menentukan hasil terbaik.

Procurement staff bisa memperbaharui hasil optimizer sebelum mengirim ke manager untuk aproval.

---

## 6. High-Level Process

```text id="an156u"
Procurement Request
        ↓
Run Optimizer
        ↓
Optimization Result
        ↓
Notification to Procurement Staff
        ↓
      Review  --> can be modify
        ↓
Submit for Approval
        ↓
Manager Approve / Reject
        ↓
Electronic Signature
        ↓
Generate Contract PDF
```

---

## 7. MVP Scope

MVP mencakup:

* Authentication.
* Role-based access.
* Master product.
* Master vendor.
* Vendor offer.
* Procurement request.
* Procurement request items.
* Candidate combination.
* Optimization result.
* In-app notification.
* Manager approval and rejection.
* Electronic signature sederhana.
* Contract PDF generation.

---

## 8. System Boundary

### Inside System

Sistem menangani:

* Vendor dan product master.
* Vendor offer.
* Procurement request.
* Candidate combination.
* Optimization.
* Notification.
* Approval.
* Electronic signature.
* Contract generation.

### Outside System

Sistem tidak menangani:

* Vendor onboarding.
* Vendor qualification.
* Negosiasi vendor.
* MoU atau legal agreement.
* Supplier payment.
* Accounting.
* Inventory fulfillment.
* Shipping.
* Vendor discovery.

Vendor yang tersedia pada master data dianggap sudah valid berdasarkan proses bisnis di luar sistem.

---

## 9. Key Product Principles

### Preserve Original Request

Kebutuhan procurement dari instansi harus tetap menjadi source of truth.

Optimizer tidak boleh mengubah kebutuhan tersebut.

### Separate Requirement from Solution

Procurement request menjelaskan apa yang dibutuhkan instansi.

Candidate combination menjelaskan bagaimana perusahaan kita dapat memenuhi kebutuhan tersebut menggunakan item-item dari vendor.

### Traceable Optimization

Hasil optimizer harus dapat ditelusuri kembali ke procurement request dan data vendor yang digunakan.


### Controlled Finalization

Procurement hanya dapat menjadi kontrak final setelah melalui approval dan electronic signature Manager.

---

## 10. Out of Scope

Fitur berikut tidak termasuk MVP:

* Vendor onboarding dan MoU management.
* Automated vendor discovery.
* Excel vendor import.
* OCR catalog.
* Fuzzy product matching.
* Advanced optimization.
* Multi-level approval.
* Email notification.
* WhatsApp notification.
* Cryptographic digital signature.
* Accounting integration.
* Payment processing.
* Inventory integration.
* ERP integration.

---

## 11. Success Criteria

MVP dianggap berhasil apabila user dapat menjalankan proses berikut secara end-to-end:

```text id="yhgpe0"
Create Procurement Request
        ↓
Define Institution Requirements
        ↓
Prepare Candidate Combinations
        ↓
Run Optimizer
        ↓
Receive Completion Notification
        ↓
Review Optimization Result
        ↓
Submit for Approval
        ↓
Manager Approve
        ↓
Manager Sign
        ↓
Generate Final Contract PDF
```

Selain itu:

* Kebutuhan asli dari instansi tetap konsisten.
* Optimizer hanya mengevaluasi cara memenuhi kebutuhan tersebut.
* Hasil optimizer dapat ditelusuri dan diubah oleh procurement staff.
* Procurement Staff menerima notifikasi setelah optimizer selesai.
* Approval dapat ditelusuri.
* Contract final hanya dibuat setelah approval dan signature.
