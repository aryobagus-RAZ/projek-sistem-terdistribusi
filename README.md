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

## Gambaran Umum

* **publisher.py:**
Kode ini mensimulasikan lima sensor secara virtual yaitu suhu, kelembaban, gerakan, cahaya dan pintu. Setiap sensor secara periodik mem-publish pesan JSON ke topik seperti `home/livingroom/temperature` dan mendengarkan acknowledgement pada topik `ack/<sensor_id>`
* **dashboard.py:**
Kode ini merupakan subscriber ke topik sensor, dan juga mengirim pesan acknowledgement kembali ke setiap sensor. Dashboard ini menggunakan framework Flask untuk membangun aplikasi website.

---

## Fitur Tambahan

Dashboard menampilkan langsung data terbaru serta timestamp yang dikirimkan dari lima sensor.
Terdapat juga `Event Log` yang menunjukkan peristiwa terstruktur dengan arah, sehingga pembaca dapat melacak pesan yang dikirim.
Pada Dashboard juga tersedia fitur berupa visual grafik untuk melihat tren nilai sensor dari waktu ke waktu.

---

## Desain dan Arsitektur

* **Broker:**
Broker MQTT yang digunakan adalah Mosquitto dengan fungsi untuk menangani pesan yang dikirim dari publisher dan subscriber.
* **Struktur Topik:**
    -  Data Sensor: `home/<room>/<sensor>` (contoh: `home/livingroom/temperature`)
    - Acknowledgement: `ack/<sensor-id>` (contoh: `ack/livingroom-temperature-abc123`)
* **Alur Pesan:**
    1. `publisher` ke `broker` (publish data sensor)
    2. `broker` ke `subsciber` (dashboard (sebagai subscriber) menerima pesan)
    3. `subscriber` ke `broker` (dashboard mempublish `ack` ke `ack/<sensor-id>`)
    4. `broker` ke `publisher` (publisher menerima `ack`)

---

## Getting Started

1. Install dan Jalankan Broker MQTT Mosquitto
- Download Mosquitto dari https://mosquitto.org/download/ atau instal melalui Chocolatey: `choco install mosquitto`
- Jalankan broker menggunakan port default (1883)

```powershell
mosquitto -v
```

2. Install dependensi serta siapkan lingkungan Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Jalankan Dashboard (subsciber + web UI)

```powershell
python dashboard.py --broker localhost --port 1883 --host 0.0.0.0 --webport 5000
```

4. Jalankan Publisher

```powershell
python publisher.py --broker localhost --port 1883
```

5. Buka web `http://localhost:5000` pada browser untuk melihat langsung aktivitas sensornya

---

## Tampilan Program

1. Lima sensor (suhu, kelembaban, cahaya, gerakan, pintu) sebagai publisher
![5-publishers]([https://i.imgur.com/sCOaI8N.png](https://imgur.com/a/y9FZjYg))
2. Aktivitas pengiriman data antar publisher-broker-subscriber
![event-log](https://i.imgur.com/BLR8NKx.png)
3. Alur data sensor dari publisher ke broker dan diterima subscriber dengan mekanisme konfirmasi (ACK)
![terminal-activiity](https://i.imgur.com/pmmSPxT.png)
   


 

