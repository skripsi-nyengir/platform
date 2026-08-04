# Kuesioner User Acceptance Testing (UAT) Berbasis Skala Likert

**Platform:** Anomaly Detection Platform — Live IoT Telemetry  
**Versi/build yang diuji:** ____________________  
**Tanggal pengujian:** ____________________  
**Kode responden:** ____________________  
**Fasilitator:** ____________________

**Versi Google Forms:** gunakan [blueprint-google-forms-uat.md](./blueprint-google-forms-uat.md)
untuk tipe pertanyaan, opsi, pengaturan grid, dan logika percabangan yang siap
diterapkan di Google Forms.

## 1. Tujuan dan ruang lingkup

Kuesioner ini digunakan untuk menilai apakah platform dapat diterima oleh pengguna untuk:

- memantau telemetri sensor secara langsung dan historis;
- mengidentifikasi serta menelusuri indikasi anomali;
- memeriksa dan menangani alert;
- membandingkan informasi evaluasi model;
- menjalankan simulasi/replay pada data uji; dan
- memeriksa kesehatan layanan platform.

Modul inti yang dinilai adalah **Overview**, **Sensor**, **Alerts**, **Model Evaluation**, **Simulation**, dan **System Health**. Modul **EDA** disediakan sebagai bagian opsional karena saat ini diakses melalui URL langsung dan tidak ditampilkan pada navigasi utama.

Instrumen ini adalah kuesioner UAT khusus untuk platform ini, bukan skala psikometrik baku. Jika hasilnya digunakan dalam skripsi atau publikasi, lakukan penelaahan isi oleh ahli dan uji coba instrumen sebelum pengumpulan data utama.

## 2. Persetujuan responden

Informasi yang diberikan akan digunakan untuk mengevaluasi platform. Identitas pribadi tidak perlu dicantumkan. Partisipasi bersifat sukarela dan responden dapat menghentikan pengujian kapan saja.

- [ ] Saya telah memahami tujuan pengujian dan bersedia menjadi responden.

## 3. Profil responden

1. Peran utama:
   - [ ] Operator IoT
   - [ ] Analis data/anomali
   - [ ] Pengelola sistem
   - [ ] Peneliti/mahasiswa
   - [ ] Lainnya: ____________________
2. Pengalaman menggunakan dashboard pemantauan:
   - [ ] Belum pernah
   - [ ] Kurang dari 1 tahun
   - [ ] 1–3 tahun
   - [ ] Lebih dari 3 tahun
3. Pemahaman mengenai IoT dan deteksi anomali:
   - [ ] Pemula
   - [ ] Menengah
   - [ ] Mahir
4. Perangkat yang digunakan: ____________________
5. Sistem operasi dan browser: ____________________
6. Pernah menggunakan platform ini sebelumnya:
   - [ ] Belum pernah
   - [ ] Pernah 1–2 kali
   - [ ] Pernah lebih dari 2 kali

## 4. Skala penilaian

Berikan satu jawaban untuk setiap pernyataan berdasarkan pengalaman selama menjalankan skenario UAT.

| Nilai | Jawaban | Makna |
| ---: | --- | --- |
| 1 | Sangat Tidak Setuju (STS) | Pernyataan sama sekali tidak sesuai dengan pengalaman pengguna |
| 2 | Tidak Setuju (TS) | Pernyataan kurang sesuai dengan pengalaman pengguna |
| 3 | Netral (N) | Pengguna belum dapat menyetujui atau menolak pernyataan |
| 4 | Setuju (S) | Pernyataan sesuai dengan pengalaman pengguna |
| 5 | Sangat Setuju (SS) | Pernyataan sangat sesuai dengan pengalaman pengguna |
| TD | Tidak Dapat Dinilai | Fitur tidak tersedia, tidak diujikan, atau responden tidak memiliki dasar untuk menilai |

`TD` bukan bagian dari skala Likert dan harus dikeluarkan dari perhitungan. Semua pernyataan diberi arah positif sehingga tidak memerlukan pembalikan skor.

## 5. Skenario tugas UAT

Gunakan lingkungan dan data uji. Jangan menjalankan perubahan status alert, aktivasi model, atau replay pada sistem produksi.

Pilihan hasil tugas:

- **Lulus:** tujuan tugas tercapai tanpa bantuan fasilitator.
- **Lulus dengan bantuan:** tujuan tercapai setelah memperoleh petunjuk.
- **Gagal:** tujuan tidak tercapai karena masalah fungsi atau penggunaan.
- **Terblokir:** tugas tidak dapat dijalankan karena data, layanan, atau hak akses tidak tersedia.
- **Tidak diterapkan:** skenario berada di luar peran atau lingkup pengujian responden.

| ID | Skenario yang dilakukan | Hasil yang diharapkan | Hasil aktual | Catatan/bukti |
| --- | --- | --- | --- | --- |
| UAT-01 | Buka **Overview**, identifikasi jumlah alert aktif, ketersediaan telemetri, ketersediaan skor, dan breach tertinggi; lalu ubah rentang waktu. | Ringkasan kondisi operasi dapat ditemukan dan data menyesuaikan rentang yang dipilih. | __________ | __________ |
| UAT-02 | Buka **Sensor**, periksa nilai telemetri terbaru, ubah rentang waktu, lalu telusuri riwayat telemetri, skor inferensi, dan alert terkait. | Data sensor terbaru dan historis dapat ditelusuri pada periode yang dipilih beserta konteks deteksinya. | __________ | __________ |
| UAT-03 | Buka **Alerts**, filter berdasarkan sensor, status, serta waktu; pilih satu episode alert dan periksa riwayatnya. | Daftar alert mengikuti filter dan detail episode yang dipilih dapat diperiksa. | __________ | __________ |
| UAT-04 | Pada alert uji, lakukan **acknowledge** dan, jika skenario mengizinkan, **resolve** dengan catatan. | Status lifecycle dan riwayat alert berubah sesuai tindakan serta memberikan umpan balik yang jelas. | __________ | __________ |
| UAT-05 | Buka **Model Evaluation**, bandingkan sedikitnya dua model menggunakan metadata training dan metrik evaluasi offline. | Identitas model, metrik, threshold, dan sumber dataset dapat ditemukan serta dibandingkan. | __________ | __________ |
| UAT-06 | Buka **Simulation**, pilih/aktifkan artifact model uji, jalankan injected replay jika hasil belum tersedia, pantau progres, lalu periksa metrik dan visualisasi hasil. | Alur pemilihan model, replay, status pekerjaan, dan hasil simulasi dapat diselesaikan dengan benar. | __________ | __________ |
| UAT-07 | Buka **System Health**, tentukan kondisi umum sistem, waktu pembaruan terakhir, dan status setiap layanan. | Kondisi serta kesegaran status sistem dapat dipahami dan layanan yang bermasalah dapat diidentifikasi. | __________ | __________ |
| UAT-08 | Berpindah di antara seluruh menu utama dan ubah tema terang/gelap; ulangi satu tugas pada ukuran layar yang digunakan. | Navigasi, fokus halaman, tema, dan tata letak tetap dapat digunakan tanpa kehilangan konteks penting. | __________ | __________ |
| UAT-E01 (opsional) | Buka `/eda`, pilih hasil precompute atau hitung rentang kustom, lalu telusuri bagian kualitas data, pola temporal, hubungan Suhu–RH, perubahan rezim, dan metadata audit. | Run EDA beserta provenance dan panel analisis dapat dimuat serta ditelusuri. | __________ | __________ |

## 6. Pernyataan skala Likert

### A. Kesesuaian fungsional

| Kode | Pernyataan | Skor 1–5/TD |
| --- | --- | :---: |
| KF-01 | Halaman Overview memungkinkan saya mengetahui kondisi operasi terkini tanpa harus membuka halaman lain. | ____ |
| KF-02 | Filter rentang waktu menampilkan data sesuai periode yang saya pilih. | ____ |
| KF-03 | Halaman Sensor menampilkan nilai telemetri terbaru untuk sensor yang dipilih. | ____ |
| KF-04 | Halaman Sensor menampilkan riwayat telemetri untuk periode yang dipilih. | ____ |
| KF-05 | Filter pada halaman Alerts menghasilkan daftar alert sesuai kriteria yang dipilih. | ____ |
| KF-06 | Detail alert menampilkan riwayat episode yang saya pilih. | ____ |
| KF-07 | Tindakan acknowledge atau resolve memperbarui status alert sesuai tindakan yang dilakukan. | ____ |
| KF-08 | Halaman Model Evaluation menyediakan informasi yang saya perlukan untuk membandingkan model. | ____ |
| KF-09 | Halaman Simulation memungkinkan saya menyelesaikan alur pemilihan model hingga pemeriksaan hasil replay. | ____ |
| KF-10 | Halaman System Health menampilkan kondisi layanan yang diperlukan untuk memeriksa kesiapan platform. | ____ |

### B. Kualitas dan kejelasan informasi

| Kode | Pernyataan | Skor 1–5/TD |
| --- | --- | :---: |
| KI-01 | Nama sensor, satuan pengukuran, dan istilah domain ditampilkan dengan jelas. | ____ |
| KI-02 | Penandaan zona waktu WIB dan UTC membantu saya memahami waktu kejadian dengan benar. | ____ |
| KI-03 | Platform membedakan data live, data historis, metrik training, evaluasi offline, dan hasil simulasi secara jelas. | ____ |
| KI-04 | Informasi provenance model, dataset, dan threshold memudahkan saya menelusuri asal suatu hasil. | ____ |
| KI-05 | Grafik dan tabel menyajikan data dalam bentuk yang mudah saya interpretasikan. | ____ |
| KI-06 | Status dan tingkat keparahan dapat dibedakan dengan jelas melalui teks atau label yang tersedia. | ____ |

### C. Kemudahan penggunaan dan aksesibilitas

| Kode | Pernyataan | Skor 1–5/TD |
| --- | --- | :---: |
| KU-01 | Nama dan susunan menu memudahkan saya menemukan halaman yang dibutuhkan. | ____ |
| KU-02 | Urutan langkah pada setiap tugas terasa logis. | ____ |
| KU-03 | Label serta pilihan pada filter dan kontrol mudah dipahami. | ____ |
| KU-04 | Platform memberikan umpan balik yang jelas ketika data sedang dimuat atau proses sedang berjalan. | ____ |
| KU-05 | Pesan kesalahan dan pilihan mencoba kembali membantu saya melanjutkan tugas. | ____ |
| KU-06 | Tata letak, ukuran teks, dan kontras warna membuat informasi mudah dibaca. | ____ |
| KU-07 | Peralihan tema terang dan gelap bekerja tanpa mengurangi keterbacaan informasi. | ____ |

### D. Kinerja dan keandalan

| Kode | Pernyataan | Skor 1–5/TD |
| --- | --- | :---: |
| KK-01 | Waktu pemuatan awal halaman dapat diterima untuk kebutuhan saya. | ____ |
| KK-02 | Navigasi, filter, dan tindakan pengguna memberikan respons dalam waktu yang dapat diterima. | ____ |
| KK-03 | Pembaruan data live dan status sistem tidak menampilkan keadaan yang membingungkan atau saling bertentangan. | ____ |
| KK-04 | Platform tetap stabil selama seluruh skenario UAT yang saya jalankan. | ____ |

### E. Penerimaan keseluruhan

| Kode | Pernyataan | Skor 1–5/TD |
| --- | --- | :---: |
| PK-01 | Platform mendukung kebutuhan saya untuk memantau dan menelusuri anomali sensor. | ____ |
| PK-02 | Saya yakin dapat menggunakan platform ini dengan sedikit atau tanpa bantuan. | ____ |
| PK-03 | Secara keseluruhan, platform layak diterima untuk tujuan penggunaan yang telah ditetapkan. | ____ |

### F. Modul EDA — opsional dan tidak masuk skor inti

Isi bagian ini hanya jika UAT-E01 termasuk dalam lingkup pengujian.

| Kode | Pernyataan | Skor 1–5/TD |
| --- | --- | :---: |
| EDA-01 | Kontrol precompute dan rentang kustom memudahkan saya memilih run EDA yang dibutuhkan. | ____ |
| EDA-02 | Pembagian hasil ke dalam bagian kualitas data, pola temporal, hubungan Suhu–RH, struktur temporal, dan metadata memudahkan penelusuran. | ____ |
| EDA-03 | Provenance run dan batas metodologi EDA ditampilkan dengan jelas. | ____ |
| EDA-04 | Visualisasi EDA mudah diinterpretasikan untuk eksplorasi data historis. | ____ |
| EDA-05 | Modul EDA mendukung kebutuhan saya untuk memahami karakteristik data sensor. | ____ |

## 7. Pertanyaan terbuka

1. Tugas mana yang gagal, terblokir, atau memerlukan bantuan? Jelaskan langkah dan kondisi saat masalah muncul.  
   ________________________________________________________________________

2. Informasi atau istilah apa yang paling membingungkan?  
   ________________________________________________________________________

3. Fitur apa yang paling membantu pekerjaan Anda?  
   ________________________________________________________________________

4. Perbaikan apa yang paling penting sebelum platform diterima?  
   ________________________________________________________________________

5. Apakah ada fitur atau informasi yang Anda perlukan tetapi belum tersedia?  
   ________________________________________________________________________

6. Komentar tambahan:  
   ________________________________________________________________________

## 8. Catatan masalah

| ID | Skenario | Deskripsi masalah | Tingkat dampak | Bukti/screenshot | Status tindak lanjut |
| --- | --- | --- | --- | --- | --- |
| 1 | ______ | ______ | Kritis / Mayor / Minor | ______ | ______ |
| 2 | ______ | ______ | Kritis / Mayor / Minor | ______ | ______ |
| 3 | ______ | ______ | Kritis / Mayor / Minor | ______ | ______ |

Panduan tingkat dampak:

- **Kritis:** fungsi inti tidak dapat diselesaikan, data berisiko salah dipahami, atau tidak ada solusi sementara.
- **Mayor:** fungsi penting terganggu, tetapi masih ada solusi sementara.
- **Minor:** masalah tampilan, istilah, atau kenyamanan yang tidak menghentikan tugas.

## 9. Perhitungan hasil

### 9.1 Skor Likert

Hitung hanya jawaban bernilai 1–5. Jawaban `TD` tidak masuk pembilang maupun penyebut.

```text
Rata-rata butir = jumlah skor valid butir / jumlah responden valid butir

Rata-rata dimensi = jumlah seluruh skor valid dalam dimensi
                    / jumlah seluruh jawaban valid dalam dimensi

Indeks penerimaan (%) = jumlah seluruh skor valid
                        / (5 × jumlah seluruh jawaban valid) × 100%
```

Interpretasi deskriptif rata-rata:

| Rentang rata-rata | Interpretasi |
| ---: | --- |
| 1,00–1,80 | Sangat tidak diterima |
| 1,81–2,60 | Tidak diterima |
| 2,61–3,40 | Netral/perlu evaluasi lebih lanjut |
| 3,41–4,20 | Diterima |
| 4,21–5,00 | Sangat diterima |

### 9.2 Keberhasilan tugas

```text
Tingkat kelulusan mandiri (%) = jumlah Lulus
                                / (jumlah Lulus + Lulus dengan bantuan + Gagal) × 100%

Tingkat penyelesaian total (%) = (jumlah Lulus + Lulus dengan bantuan)
                                 / (jumlah Lulus + Lulus dengan bantuan + Gagal) × 100%
```

Keluarkan **Terblokir** dan **Tidak diterapkan** dari penyebut, tetapi laporkan keduanya secara terpisah. Dengan cara ini, kebutuhan bantuan tidak tertutup oleh angka penyelesaian total.

### 9.3 Usulan keputusan penerimaan

Kriteria berikut adalah aturan proyek yang perlu disepakati sebelum pengujian, bukan batas universal:

| Keputusan | Kriteria minimum yang disarankan |
| --- | --- |
| Diterima | Seluruh skenario inti yang kritis lulus; tidak ada masalah kritis terbuka; rata-rata keseluruhan ≥ 4,00; dan setiap dimensi ≥ 3,50. |
| Diterima bersyarat | Tidak ada masalah kritis terbuka, tetapi terdapat tugas mayor yang memerlukan perbaikan atau rata-rata keseluruhan 3,41–3,99. Semua perbaikan harus memiliki rencana tindak lanjut. |
| Belum diterima | Ada skenario kritis yang gagal, ada masalah kritis terbuka, rata-rata keseluruhan < 3,41, atau dimensi Kesesuaian Fungsional < 3,41. |

Keputusan akhir tidak boleh didasarkan pada rata-rata Likert saja. Hasil tugas, tingkat dampak masalah, komentar responden, dan bukti pengujian harus dinilai bersama.

## 10. Rekapitulasi evaluator

| Ukuran | Hasil |
| --- | ---: |
| Jumlah responden | ____ |
| Tingkat kelulusan mandiri tugas inti | ____% |
| Tingkat penyelesaian total tugas inti | ____% |
| Rata-rata Kesesuaian Fungsional | ____ / 5 |
| Rata-rata Kualitas dan Kejelasan Informasi | ____ / 5 |
| Rata-rata Kemudahan Penggunaan dan Aksesibilitas | ____ / 5 |
| Rata-rata Kinerja dan Keandalan | ____ / 5 |
| Rata-rata Penerimaan Keseluruhan | ____ / 5 |
| Indeks penerimaan inti | ____% |
| Jumlah masalah kritis/mayor/minor | ____ / ____ / ____ |
| Keputusan akhir | Diterima / Diterima bersyarat / Belum diterima |

## 11. Catatan penerapan pada formulir digital

- Implementasi Google Forms yang kompatibel tersedia pada
  [blueprint-google-forms-uat.md](./blueprint-google-forms-uat.md).
- Blueprint memetakan tabel skenario menjadi pertanyaan hasil, catatan, dan
  bukti; memetakan setiap dimensi ke *multiple-choice grid*; serta memisahkan
  modul EDA menggunakan percabangan section.
- Gunakan pilihan `1–5` dan `TD`; jangan mengubah `TD` menjadi skor nol.
- Simpan hasil tugas, skor Likert, dan catatan masalah sebagai tiga kelompok
  data yang berbeda.
- Jika instrumen digunakan untuk penelitian, lakukan telaah bahasa dan
  relevansi butir oleh pembimbing/ahli domain. Uji reliabilitas per dimensi
  hanya jika jumlah responden memadai; jangan menarik kesimpulan reliabilitas
  dari sampel UAT yang sangat kecil.
