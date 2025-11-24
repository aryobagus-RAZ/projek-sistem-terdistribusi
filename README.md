# Proyek Otomasi Rumah Pintar dengan MQTT

---
Anggota Kelompok:
1. Alif Putra Roy - 256150100111011
2. Aryo Bagus Kusumadewa Tutuko - 256150100111019
3. Muhammad Daffa Firmansyah - 256150100111010 

---

## Pendahuluan
Proyek ini adalah sistem untuk membuat rumah menjadi **Rumah Pintar** menggunakan protokol komunikasi ringan bernama **MQTT (Message Queuing Telemetry Transport)**.

Tujuan utamanya adalah memungkinkan pengguna untuk mengontrol dan memantau perangkat rumah dari jarak jauh, hanya melalui koneksi internet.

---

## Motivasi

MQTT dipilih karena sangat efisien, menjadikannya pilihan ideal untuk perangkat IoT:

* **Efisiensi Protokol:** Model *publish/subscribe* MQTT yang bersifat asinkron menghilangkan kebutuhan *polling* terus menerus. Hal ini secara signifikan mengurangi *traffic* jaringan dan memperpanjang masa baterai pada sensor dengan sumber daya terbatas.

* **Penyederhanaan Integrasi:** MQTT (Message Queuing Telemetry Transport) menyediakan protokol komunikasi mesin-ke-mesin yang ringan menggunakan arsitektur *publish/subscribe* dengan broker, sehingga menyederhanakan integrasi perangkat dan pertukaran data asinkron.

* **Infrastruktur Modern:** Platform rumah pintar modern memanfaatkan **broker MQTT berbasis *cloud*** untuk menyediakan infrastruktur yang aman, andal, dan berbiaya rendah untuk otomasi jarak jauh. 

---

## Latar Belakang dan Permasalahan

Sistem rumah pintar lama dan beberapa implementasi MQTT saat ini punya tiga masalah besar:

### 1. Jangkauan Terbatas
Sistem otomasi rumah lama (seperti yang pakai RFID dan inframerah) terbatas pada jangkauan operasional sekitar 10 meter dan harus tanpa penghalang (*line-of-sight*).
* **Dampaknya:** Keterbatasan fisik ini menghambat cakupan seluruh rumah (terutama rumah bertingkat) dan menghilangkan peluang pembentukan jaringan sensor terdistribusi.

### 2. Jaringan Rawan Mati (*Single Point of Failure* - SPOF)
Topologi *client-broker-server* dalam MQTT menimbulkan SPOF.
* **Dampaknya:** Ketika broker tidak tersedia—karena gangguan jaringan atau *crash server*—seluruh sistem otomasi menjadi tidak berfungsi.

---

## Usulan Solusi

Kami merancang solusi untuk mengatasi tiga masalah di atas:

### A. Jaringan Lebih Kuat & Tahan Mati
Untuk mengatasi masalah pada point **1** dan **2**:

* Kami akan menambahkan fitur **pengecekan kesehatan (*health check*)** dan **sambung ulang otomatis (*auto reconnect*)** untuk memastikan perangkat mencoba terhubung kembali ke broker jika putus.
* Kami akan memprioritaskan topik-topik penting (*relay*) agar disinkronkan terlebih dahulu untuk menjaga fungsionalitas utama.

---
