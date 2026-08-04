# Blueprint Google Forms — Kuesioner UAT

Blueprint ini adalah versi implementasi Google Forms untuk instrumen pada
[kuesioner-uat-likert.md](./kuesioner-uat-likert.md). Susunan di bawah dapat
dipindahkan ke Google Forms tanpa mengubah konstruk, kode butir, skala, atau
aturan skoring.

## 1. Konfigurasi formulir

| Pengaturan | Nilai yang disarankan |
| --- | --- |
| Judul | `User Acceptance Testing — Anomaly Detection Platform` |
| Mode kuis | Nonaktif |
| Acak urutan pertanyaan | Nonaktif |
| Bilah progres | Aktif |
| Kumpulkan alamat email | Nonaktif jika penelitian menggunakan kode responden anonim |
| Izinkan edit setelah dikirim | Sesuaikan protokol penelitian; tetapkan sebelum pengumpulan dimulai |
| Tujuan respons | Hubungkan ke Google Sheets |
| Pesan konfirmasi | `Terima kasih. Respons UAT Anda telah tersimpan.` |

Gunakan Google Forms **Sections** sesuai urutan blueprint. Jangan memindahkan
pertanyaan percabangan dari akhir section karena alur berikut bergantung pada
`Go to section based on answer`.

## 2. Opsi jawaban tetap

### 2.1 Kolom untuk semua grid Likert

Gunakan tipe pertanyaan **Multiple choice grid** dengan kolom berikut, dalam
urutan yang sama pada setiap dimensi:

1. `1 — Sangat Tidak Setuju`
2. `2 — Tidak Setuju`
3. `3 — Netral`
4. `4 — Setuju`
5. `5 — Sangat Setuju`
6. `TD — Tidak Dapat Dinilai`

Pengaturan setiap grid inti:

- `Require a response in each row`: **aktif**;
- `Limit to one response per column`: **nonaktif**; dan
- `Shuffle row order`: **nonaktif**.

`TD` bukan skor nol. Respons tersebut harus dikeluarkan dari perhitungan.
Semua butir berarah positif sehingga tidak memerlukan *reverse scoring*.

### 2.2 Opsi hasil tugas

Gunakan tipe **Multiple choice**:

- `Lulus`
- `Lulus dengan bantuan`
- `Gagal`
- `Terblokir`
- `Tidak diterapkan`

### 2.3 Opsi tingkat dampak masalah

Gunakan tipe **Dropdown**:

- `Kritis — fungsi inti gagal atau data berisiko salah dipahami`
- `Mayor — fungsi penting terganggu tetapi ada solusi sementara`
- `Minor — tidak menghentikan penyelesaian tugas`

## 3. Struktur section dan pertanyaan

### Section 1 — Persetujuan responden

**Deskripsi section**

> Formulir ini digunakan untuk mengevaluasi Anomaly Detection Platform.
> Identitas pribadi tidak perlu dicantumkan. Partisipasi bersifat sukarela dan
> responden dapat berhenti kapan saja. Waktu pengisian diperkirakan 25–35
> menit setelah skenario pengujian selesai.

| ID | Judul pertanyaan | Tipe | Wajib | Opsi/logika |
| --- | --- | --- | :---: | --- |
| C-01 | `Apakah Anda telah memahami tujuan pengujian dan bersedia menjadi responden?` | Multiple choice | Ya | `Ya, saya bersedia` → Section 2; `Tidak bersedia` → Submit form |

Aktifkan `Go to section based on answer` pada C-01.

### Section 2 — Metadata sesi dan profil responden

| ID | Judul pertanyaan | Tipe | Wajib | Opsi/validasi |
| --- | --- | --- | :---: | --- |
| M-01 | `Versi/build platform yang diuji` | Short answer | Ya | Contoh: commit SHA, tag, atau nomor build |
| M-02 | `Lingkungan pengujian` | Multiple choice | Ya | `Docker lokal`, `Staging`, `Demo`, `Lainnya` |
| M-03 | `Kode responden` | Short answer | Ya | Jangan meminta nama lengkap |
| M-04 | `Kode/nama fasilitator` | Short answer | Tidak | Kosongkan jika UAT mandiri |
| P-01 | `Peran utama Anda` | Multiple choice | Ya | `Operator IoT`, `Analis data/anomali`, `Pengelola sistem`, `Peneliti/mahasiswa`; aktifkan `Other` |
| P-02 | `Pengalaman menggunakan dashboard pemantauan` | Multiple choice | Ya | `Belum pernah`, `< 1 tahun`, `1–3 tahun`, `> 3 tahun` |
| P-03 | `Pemahaman mengenai IoT dan deteksi anomali` | Multiple choice | Ya | `Pemula`, `Menengah`, `Mahir` |
| P-04 | `Perangkat yang digunakan` | Multiple choice | Ya | `Desktop/laptop`, `Tablet`, `Ponsel`; aktifkan `Other` |
| P-05 | `Sistem operasi dan browser` | Short answer | Ya | Contoh: Ubuntu 24.04 — Chrome 140 |
| P-06 | `Pengalaman menggunakan platform ini` | Multiple choice | Ya | `Belum pernah`, `Pernah 1–2 kali`, `Pernah lebih dari 2 kali` |

Google Forms sudah mencatat waktu pengiriman respons, sehingga pertanyaan
tanggal pengisian tidak perlu ditambahkan kecuali protokol penelitian
memerlukan tanggal yang dimasukkan responden.

### Section 3 — Petunjuk skenario UAT

Tambahkan **Title and description**, bukan pertanyaan:

> Jalankan setiap skenario pada lingkungan dan data uji. Jangan mengubah
> status alert, mengaktifkan model, atau menjalankan replay pada produksi.
> Pilih Lulus jika tujuan tercapai tanpa bantuan; Lulus dengan bantuan jika
> memerlukan petunjuk; Gagal jika tujuan tidak tercapai; Terblokir jika data,
> layanan, atau akses tidak tersedia; dan Tidak diterapkan jika skenario di
> luar lingkup sesi Anda.

Di akhir section, lanjutkan selalu ke Section 4.

### Section 4 — Hasil tugas inti

Untuk setiap skenario UAT-01 sampai UAT-08, tambahkan satu **Title and
description**, kemudian tiga pertanyaan berikut:

1. `[TR-nn] Hasil UAT-nn` — **Multiple choice**, wajib, menggunakan opsi hasil
   tugas pada bagian 2.2.
2. `[TN-nn] Catatan UAT-nn` — **Paragraph**, opsional.
3. `[TE-nn] Tautan bukti/screenshot UAT-nn` — **Short answer**, opsional.

Gunakan tautan bukti sebagai konfigurasi bawaan agar formulir dapat tetap
anonim. Jika pertanyaan diganti menjadi **File upload**, responden harus masuk
ke Akun Google; gunakan opsi tersebut hanya jika konsekuensi identitas dan
akses sudah disetujui dalam protokol penelitian.

#### UAT-01 — Overview

**Deskripsi**

> Buka Overview. Identifikasi jumlah alert aktif, ketersediaan telemetri,
> ketersediaan skor, dan breach tertinggi; lalu ubah rentang waktu.
>
> Hasil yang diharapkan: ringkasan kondisi operasi dapat ditemukan dan data
> menyesuaikan rentang yang dipilih.

#### UAT-02 — Sensor

**Deskripsi**

> Buka Sensor. Periksa nilai telemetri terbaru, ubah rentang waktu, lalu
> telusuri riwayat telemetri, skor inferensi, dan alert terkait.
>
> Hasil yang diharapkan: data terbaru dan historis dapat ditelusuri pada
> periode yang dipilih beserta konteks deteksinya.

#### UAT-03 — Filter dan detail alert

**Deskripsi**

> Buka Alerts. Filter berdasarkan sensor, status, serta waktu; pilih satu
> episode alert dan periksa riwayatnya.
>
> Hasil yang diharapkan: daftar alert mengikuti filter dan detail episode yang
> dipilih dapat diperiksa.

#### UAT-04 — Lifecycle alert

**Deskripsi**

> Pada alert uji, lakukan acknowledge dan, jika skenario mengizinkan, resolve
> dengan catatan.
>
> Hasil yang diharapkan: status lifecycle dan riwayat alert berubah sesuai
> tindakan serta memberikan umpan balik yang jelas.

#### UAT-05 — Model Evaluation

**Deskripsi**

> Buka Model Evaluation. Bandingkan sedikitnya dua model menggunakan metadata
> training dan metrik evaluasi offline.
>
> Hasil yang diharapkan: identitas model, metrik, threshold, dan sumber dataset
> dapat ditemukan serta dibandingkan.

#### UAT-06 — Simulation

**Deskripsi**

> Buka Simulation. Pilih/aktifkan artifact model uji, jalankan injected replay
> jika hasil belum tersedia, pantau progres, lalu periksa metrik dan
> visualisasi hasil.
>
> Hasil yang diharapkan: alur pemilihan model, replay, status pekerjaan, dan
> hasil simulasi dapat diselesaikan dengan benar.

#### UAT-07 — System Health

**Deskripsi**

> Buka System Health. Tentukan kondisi umum sistem, waktu pembaruan terakhir,
> dan status setiap layanan.
>
> Hasil yang diharapkan: kondisi serta kesegaran status dapat dipahami dan
> layanan yang bermasalah dapat diidentifikasi.

#### UAT-08 — Navigasi, tema, dan ukuran layar

**Deskripsi**

> Berpindah di antara seluruh menu utama dan ubah tema terang/gelap. Ulangi
> satu tugas pada ukuran layar yang digunakan.
>
> Hasil yang diharapkan: navigasi, fokus halaman, tema, dan tata letak tetap
> dapat digunakan tanpa kehilangan konteks penting.

### Section 5 — Likert A: Kesesuaian fungsional

**Judul grid:** `A. Kesesuaian fungsional`  
**Tipe:** Multiple choice grid  
**Deskripsi:** `Nilai setiap pernyataan berdasarkan pengalaman selama UAT.`

**Rows**

1. `KF-01 — Halaman Overview memungkinkan saya mengetahui kondisi operasi terkini tanpa harus membuka halaman lain.`
2. `KF-02 — Filter rentang waktu menampilkan data sesuai periode yang saya pilih.`
3. `KF-03 — Halaman Sensor menampilkan nilai telemetri terbaru untuk sensor yang dipilih.`
4. `KF-04 — Halaman Sensor menampilkan riwayat telemetri untuk periode yang dipilih.`
5. `KF-05 — Filter pada halaman Alerts menghasilkan daftar alert sesuai kriteria yang dipilih.`
6. `KF-06 — Detail alert menampilkan riwayat episode yang saya pilih.`
7. `KF-07 — Tindakan acknowledge atau resolve memperbarui status alert sesuai tindakan yang dilakukan.`
8. `KF-08 — Halaman Model Evaluation menyediakan informasi yang saya perlukan untuk membandingkan model.`
9. `KF-09 — Halaman Simulation memungkinkan saya menyelesaikan alur pemilihan model hingga pemeriksaan hasil replay.`
10. `KF-10 — Halaman System Health menampilkan kondisi layanan yang diperlukan untuk memeriksa kesiapan platform.`

Gunakan kolom dan pengaturan grid pada bagian 2.1.

### Section 6 — Likert B: Kualitas dan kejelasan informasi

**Judul grid:** `B. Kualitas dan kejelasan informasi`  
**Tipe:** Multiple choice grid

**Rows**

1. `KI-01 — Nama sensor, satuan pengukuran, dan istilah domain ditampilkan dengan jelas.`
2. `KI-02 — Penandaan zona waktu WIB dan UTC membantu saya memahami waktu kejadian dengan benar.`
3. `KI-03 — Platform membedakan data live, data historis, metrik training, evaluasi offline, dan hasil simulasi secara jelas.`
4. `KI-04 — Informasi provenance model, dataset, dan threshold memudahkan saya menelusuri asal suatu hasil.`
5. `KI-05 — Grafik dan tabel menyajikan data dalam bentuk yang mudah saya interpretasikan.`
6. `KI-06 — Status dan tingkat keparahan dapat dibedakan dengan jelas melalui teks atau label yang tersedia.`

Gunakan kolom dan pengaturan grid pada bagian 2.1.

### Section 7 — Likert C: Kemudahan penggunaan dan aksesibilitas

**Judul grid:** `C. Kemudahan penggunaan dan aksesibilitas`  
**Tipe:** Multiple choice grid

**Rows**

1. `KU-01 — Nama dan susunan menu memudahkan saya menemukan halaman yang dibutuhkan.`
2. `KU-02 — Urutan langkah pada setiap tugas terasa logis.`
3. `KU-03 — Label serta pilihan pada filter dan kontrol mudah dipahami.`
4. `KU-04 — Platform memberikan umpan balik yang jelas ketika data sedang dimuat atau proses sedang berjalan.`
5. `KU-05 — Pesan kesalahan dan pilihan mencoba kembali membantu saya melanjutkan tugas.`
6. `KU-06 — Tata letak, ukuran teks, dan kontras warna membuat informasi mudah dibaca.`
7. `KU-07 — Peralihan tema terang dan gelap bekerja tanpa mengurangi keterbacaan informasi.`

Gunakan kolom dan pengaturan grid pada bagian 2.1.

### Section 8 — Likert D: Kinerja dan keandalan

**Judul grid:** `D. Kinerja dan keandalan`  
**Tipe:** Multiple choice grid

**Rows**

1. `KK-01 — Waktu pemuatan awal halaman dapat diterima untuk kebutuhan saya.`
2. `KK-02 — Navigasi, filter, dan tindakan pengguna memberikan respons dalam waktu yang dapat diterima.`
3. `KK-03 — Pembaruan data live dan status sistem tidak menampilkan keadaan yang membingungkan atau saling bertentangan.`
4. `KK-04 — Platform tetap stabil selama seluruh skenario UAT yang saya jalankan.`

Gunakan kolom dan pengaturan grid pada bagian 2.1.

### Section 9 — Likert E dan keputusan lingkup EDA

**Judul grid:** `E. Penerimaan keseluruhan`  
**Tipe:** Multiple choice grid

**Rows**

1. `PK-01 — Platform mendukung kebutuhan saya untuk memantau dan menelusuri anomali sensor.`
2. `PK-02 — Saya yakin dapat menggunakan platform ini dengan sedikit atau tanpa bantuan.`
3. `PK-03 — Secara keseluruhan, platform layak diterima untuk tujuan penggunaan yang telah ditetapkan.`

Gunakan kolom dan pengaturan grid pada bagian 2.1.

Setelah grid, tambahkan pertanyaan berikut sebagai pertanyaan terakhir pada
section:

| ID | Judul pertanyaan | Tipe | Wajib | Opsi/logika |
| --- | --- | --- | :---: | --- |
| E-00 | `Apakah modul EDA termasuk dalam sesi UAT Anda?` | Multiple choice | Ya | `Ya` → Section 10; `Tidak` → Section 11 |

Aktifkan `Go to section based on answer` pada E-00.

### Section 10 — EDA opsional

Tambahkan **Title and description**:

> UAT-E01 — Buka `/eda`, pilih hasil precompute atau hitung rentang kustom,
> lalu telusuri kualitas data, pola temporal, hubungan Suhu–RH, perubahan
> rezim, dan metadata audit.
>
> Hasil yang diharapkan: run EDA beserta provenance dan panel analisis dapat
> dimuat serta ditelusuri.

Tambahkan pertanyaan:

| ID | Judul pertanyaan | Tipe | Wajib |
| --- | --- | --- | :---: |
| TR-E01 | `Hasil UAT-E01` | Multiple choice | Ya |
| TN-E01 | `Catatan UAT-E01` | Paragraph | Tidak |
| TE-E01 | `Tautan bukti/screenshot UAT-E01` | Short answer | Tidak |

TR-E01 menggunakan opsi hasil tugas pada bagian 2.2.

Tambahkan grid:

**Judul grid:** `F. Modul EDA`  
**Tipe:** Multiple choice grid

**Rows**

1. `EDA-01 — Kontrol precompute dan rentang kustom memudahkan saya memilih run EDA yang dibutuhkan.`
2. `EDA-02 — Pembagian hasil ke dalam bagian kualitas data, pola temporal, hubungan Suhu–RH, struktur temporal, dan metadata memudahkan penelusuran.`
3. `EDA-03 — Provenance run dan batas metodologi EDA ditampilkan dengan jelas.`
4. `EDA-04 — Visualisasi EDA mudah diinterpretasikan untuk eksplorasi data historis.`
5. `EDA-05 — Modul EDA mendukung kebutuhan saya untuk memahami karakteristik data sensor.`

Gunakan kolom dan pengaturan grid pada bagian 2.1. Atur section agar selalu
berlanjut ke Section 11. Skor EDA dilaporkan terpisah dari skor inti.

### Section 11 — Umpan balik terbuka

Semua pertanyaan menggunakan tipe **Paragraph** dan bersifat opsional agar
responden tidak dipaksa membuat komentar yang tidak mereka miliki.

| ID | Judul pertanyaan |
| --- | --- |
| O-01 | `Tugas mana yang gagal, terblokir, atau memerlukan bantuan? Jelaskan langkah dan kondisinya.` |
| O-02 | `Informasi atau istilah apa yang paling membingungkan?` |
| O-03 | `Fitur apa yang paling membantu pekerjaan Anda?` |
| O-04 | `Perbaikan apa yang paling penting sebelum platform diterima?` |
| O-05 | `Apakah ada fitur atau informasi yang Anda perlukan tetapi belum tersedia?` |
| O-06 | `Komentar tambahan` |

Sebagai pertanyaan terakhir pada section, tambahkan:

| ID | Judul pertanyaan | Tipe | Wajib | Opsi/logika |
| --- | --- | --- | :---: | --- |
| D-00 | `Apakah Anda menemukan masalah yang perlu dicatat secara khusus?` | Multiple choice | Ya | `Ya` → Section 12; `Tidak` → Submit form |

Aktifkan `Go to section based on answer` pada D-00.

### Section 12 — Catatan masalah

Blok masalah pertama wajib karena section ini hanya ditampilkan kepada
responden yang menjawab `Ya` pada D-00. Blok kedua dan ketiga opsional.

#### Masalah 1 — wajib

| ID | Judul pertanyaan | Tipe | Wajib |
| --- | --- | --- | :---: |
| D1-01 | `Skenario terkait` | Dropdown | Ya |
| D1-02 | `Deskripsi masalah` | Paragraph | Ya |
| D1-03 | `Langkah untuk memunculkan kembali masalah` | Paragraph | Ya |
| D1-04 | `Tingkat dampak` | Dropdown | Ya |
| D1-05 | `Tautan bukti/screenshot` | Short answer | Tidak |

#### Masalah 2 — opsional

Gunakan kode D2-01 sampai D2-05 dengan judul dan tipe yang sama. Semua
pertanyaan bersifat opsional.

#### Masalah 3 — opsional

Gunakan kode D3-01 sampai D3-05 dengan judul dan tipe yang sama. Semua
pertanyaan bersifat opsional.

Opsi `Skenario terkait`:

- UAT-01 sampai UAT-08;
- UAT-E01;
- Umum/tidak terkait satu skenario.

Opsi `Tingkat dampak` menggunakan daftar pada bagian 2.3. Setelah section ini,
pilih `Submit form`.

## 4. Aturan pengolahan di Google Sheets

Pertahankan sheet respons mentah tanpa perubahan. Buat sheet kedua untuk
pembersihan dan analisis.

Karena jawaban Likert diawali angka, satu sel dapat dikonversi menjadi skor
dengan formula berikut:

```text
=IFERROR(VALUE(REGEXEXTRACT(C2,"^[1-5]")),"")
```

Ganti pemisah argumen koma dengan titik koma jika lokal Google Sheets
menggunakannya. Formula menghasilkan sel kosong untuk `TD`, sehingga `AVERAGE`
tidak memperlakukannya sebagai nol.

```text
Rata-rata dimensi = AVERAGE(rentang skor valid dimensi)

Indeks penerimaan (%) = AVERAGE(rentang seluruh skor inti) / 5 × 100%

Kelulusan mandiri (%) = jumlah "Lulus"
                        / (jumlah "Lulus" + "Lulus dengan bantuan" + "Gagal")

Penyelesaian total (%) = (jumlah "Lulus" + "Lulus dengan bantuan")
                         / (jumlah "Lulus" + "Lulus dengan bantuan" + "Gagal")
```

Jangan memasukkan kolom EDA ke indeks penerimaan inti. `Terblokir` dan `Tidak
diterapkan` tidak masuk penyebut tingkat kelulusan, tetapi harus dilaporkan
terpisah.

## 5. Checklist sebelum publikasi formulir

- [ ] Form bukan kuis dan urutan pertanyaan tidak diacak.
- [ ] Percabangan C-01, E-00, dan D-00 menuju section yang benar.
- [ ] Semua grid menggunakan **Multiple choice grid**, bukan Checkbox grid.
- [ ] `Require a response in each row` aktif pada seluruh grid yang tampil.
- [ ] `Limit to one response per column` nonaktif pada seluruh grid.
- [ ] Urutan baris dan kolom grid tidak diacak.
- [ ] Opsi `TD` tersedia dan tidak dipetakan menjadi nol.
- [ ] Uji alur tidak bersedia → formulir langsung berakhir.
- [ ] Uji alur tanpa EDA → Section 10 dilewati.
- [ ] Uji alur dengan EDA → UAT-E01 dan grid EDA tampil.
- [ ] Uji alur tanpa masalah → Section 12 dilewati.
- [ ] Uji satu respons pada desktop dan ponsel menggunakan fitur Preview.
- [ ] Verifikasi setiap row grid muncul sebagai kolom terpisah di Google Sheets.
- [ ] Bekukan susunan pertanyaan setelah pengumpulan data utama dimulai.

## 6. Catatan kompatibilitas

- Google Forms mendukung percabangan section hanya dari pertanyaan Multiple
  choice atau Dropdown; karena itu C-01, E-00, dan D-00 menggunakan Multiple
  choice.
- Multiple choice grid menerima satu pilihan per row. Opsi pembatasan satu
  respons per column harus dinonaktifkan karena banyak pernyataan boleh
  memperoleh nilai Likert yang sama.
- File upload mengharuskan responden masuk ke Akun Google. Blueprint memakai
  tautan bukti sebagai default untuk mempertahankan kemungkinan respons anonim.
- Screenshot antarmuka boleh ditambahkan sebagai gambar referensi pada
  deskripsi skenario, tetapi tidak diperlukan pada setiap butir Likert dan
  tidak boleh membocorkan jawaban tugas yang sedang menguji keterlihatan fitur.

Referensi resmi Google:

- [Show questions based on answers](https://support.google.com/docs/answer/141062?hl=en)
- [How to set rules for your form](https://support.google.com/docs/answer/3378864?hl=en)
- [Fix common errors while responding to a Google Form](https://support.google.com/docs/answer/15473134?hl=en-en)
- [How to use Google Forms](https://support.google.com/docs/answer/6281888?hl=en)
