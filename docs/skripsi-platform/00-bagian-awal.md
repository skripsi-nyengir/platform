# BAGIAN AWAL

## Halaman sampul luar

<div align="center">

**Rancang Bangun Platform Web Terintegrasi untuk Analisis dan Pemantauan Anomali pada Deret Waktu IoT Bivariat**

<br><br>

**[TEMPAT LAMBANG POLITEKNIK NEGERI SEMARANG, UKURAN SEKITAR 5 CM]**

<br><br>

Disusun oleh

**[NAMA MAHASISWA]**  
**[NIM]**

<br><br>

**[PROGRAM STUDI]**  
**[JURUSAN]**  
**POLITEKNIK NEGERI SEMARANG**  
**[TAHUN UJIAN]**

</div>

\newpage

## Halaman judul

<div align="center">

**Rancang Bangun Platform Web Terintegrasi untuk Analisis dan Pemantauan Anomali pada Deret Waktu IoT Bivariat**

<br><br>

**[TEMPAT LAMBANG POLITEKNIK NEGERI SEMARANG, UKURAN SEKITAR 5 CM]**

<br><br>

Tugas akhir/skripsi ini disusun untuk melengkapi sebagian persyaratan menjadi Sarjana Terapan

<br><br>

Disusun oleh

**[NAMA MAHASISWA]**  
**[NIM]**

<br><br>

**[PROGRAM STUDI]**  
**[JURUSAN]**  
**POLITEKNIK NEGERI SEMARANG**  
**[BULAN DAN TAHUN UJIAN]**

</div>

\newpage

## Pernyataan keaslian tugas akhir/skripsi

Saya menyatakan dengan sesungguhnya bahwa tugas akhir/skripsi berjudul **Rancang Bangun Platform Web Terintegrasi untuk Analisis dan Pemantauan Anomali pada Deret Waktu IoT Bivariat** yang dibuat untuk melengkapi sebagian persyaratan menjadi Sarjana Terapan pada Program Studi [PROGRAM STUDI], Jurusan [JURUSAN], Politeknik Negeri Semarang, bukan merupakan tiruan atau duplikasi dari tugas akhir/skripsi yang telah dipublikasikan atau digunakan untuk memperoleh gelar pada institusi mana pun. Bagian yang berasal dari sumber lain telah dicantumkan sesuai kaidah ilmiah yang berlaku.

Semarang, [TANGGAL PERNYATAAN]

[TANDA TANGAN]

**[NAMA MAHASISWA]**  
NIM [NIM]

\newpage

## Halaman persetujuan

Tugas akhir/skripsi berjudul **Rancang Bangun Platform Web Terintegrasi untuk Analisis dan Pemantauan Anomali pada Deret Waktu IoT Bivariat** dibuat untuk melengkapi sebagian persyaratan menjadi Sarjana Terapan pada Program Studi [PROGRAM STUDI], Jurusan [JURUSAN], Politeknik Negeri Semarang, dan disetujui untuk diajukan dalam sidang ujian tugas akhir/skripsi.

Semarang, [TANGGAL PERSETUJUAN]

| Pembimbing I | Pembimbing II |
|---|---|
| [TANDA TANGAN] | [TANDA TANGAN] |
| **[NAMA PEMBIMBING I]** | **[NAMA PEMBIMBING II]** |
| NIP [NIP PEMBIMBING I] | NIP [NIP PEMBIMBING II] |

Mengetahui,

Ketua Program Studi [PROGRAM STUDI]

[TANDA TANGAN]

**[NAMA KETUA PROGRAM STUDI]**  
NIP [NIP KETUA PROGRAM STUDI]

\newpage

## Halaman pengesahan

Tugas akhir/skripsi berjudul **Rancang Bangun Platform Web Terintegrasi untuk Analisis dan Pemantauan Anomali pada Deret Waktu IoT Bivariat** telah dipertahankan dalam ujian tugas akhir/skripsi dan diterima sebagai salah satu syarat untuk menjadi Sarjana Terapan pada Program Studi [PROGRAM STUDI], Jurusan [JURUSAN], Politeknik Negeri Semarang, pada [TANGGAL UJIAN].

| Penguji I | Penguji II | Penguji III |
|---|---|---|
| [TANDA TANGAN] | [TANDA TANGAN] | [TANDA TANGAN] |
| **[NAMA PENGUJI I]** | **[NAMA PENGUJI II]** | **[NAMA PENGUJI III]** |
| NIP [NIP PENGUJI I] | NIP [NIP PENGUJI II] | NIP [NIP PENGUJI III] |

Mengesahkan,

Ketua Jurusan [JURUSAN]

[TANDA TANGAN]

**[NAMA KETUA JURUSAN]**  
NIP [NIP KETUA JURUSAN]

\newpage

## Kata pengantar

Puji syukur ke hadirat Tuhan Yang Maha Esa atas rahmat dan karunia-Nya sehingga tugas akhir/skripsi berjudul **Rancang Bangun Platform Web Terintegrasi untuk Analisis dan Pemantauan Anomali pada Deret Waktu IoT Bivariat** dapat disusun. Naskah ini membahas perancangan, implementasi, integrasi, serta verifikasi terbatas platform web untuk pengelolaan telemetri IoT bivariat, analisis eksploratif, pemanggilan inferensi berbasis artefak eksternal, dan pemantauan alert.

Ucapan terima kasih disampaikan kepada pihak-pihak yang memberikan arahan, dukungan akademik, dan bantuan langsung selama pelaksanaan tugas akhir/skripsi ini.

1. [NAMA PEMBIMBING I], selaku Pembimbing I.
2. [NAMA PEMBIMBING II], selaku Pembimbing II.
3. [NAMA KETUA PROGRAM STUDI], selaku Ketua Program Studi [PROGRAM STUDI].
4. [NAMA ATAU UNIT YANG MEMBERIKAN BANTUAN LANGSUNG].
5. Keluarga serta pihak lain yang memberikan dukungan selama penyusunan tugas akhir/skripsi.

Keterbatasan penelitian dijelaskan secara eksplisit pada bagian utama naskah.

Semarang, [BULAN DAN TAHUN]

**[NAMA MAHASISWA]**

\newpage

## Abstrak

*[NAMA MAHASISWA], “Rancang Bangun Platform Web Terintegrasi untuk Analisis dan Pemantauan Anomali pada Deret Waktu IoT Bivariat”, Tugas Akhir/Skripsi Sarjana Terapan Program Studi [PROGRAM STUDI], Jurusan [JURUSAN], Politeknik Negeri Semarang, di bawah bimbingan [NAMA PEMBIMBING I] dan [NAMA PEMBIMBING II], [BULAN DAN TAHUN], [JUMLAH HALAMAN] halaman.*

Pengelolaan telemetri IoT bivariat memerlukan pemisahan yang jelas antara data deskriptif, hasil simulasi, dan hasil inferensi yang bergantung pada artefak model eksternal. Penelitian ini bertujuan merancang dan membangun platform web yang mengintegrasikan import data, penyimpanan deret waktu, analisis data eksploratif, kontrak API, worker pemrosesan, replay inferensi, dan pemantauan alert. Metode yang digunakan adalah rancang bangun terapan berbasis bukti implementasi lokal. Platform dirancang dengan FastAPI, PostgreSQL/TimescaleDB, worker import, worker analisis data eksploratif, worker replay, antarmuka React/Material UI, serta Docker Compose. Checkpoint Transformer-AE dan kebijakan ambang p99,5 diperlakukan sebagai masukan eksternal yang dibekukan, bukan objek pelatihan atau perbandingan penelitian ini. Bukti EDA kanonis mencatat dua pengujian lulus terhadap 6.931.792 baris mentah. Bukti verifikasi lain mencakup pengujian kontrak, pengujian frontend, build, pengujian ujung ke ujung berbasis mock, dan QA manual. QA manual berstatus REJECT karena dua cacat yang terdokumentasi. Artefak model aktual tidak tersedia pada checkout sehingga keberhasilan inferensi berbasis artefak tidak diklaim.

**Kata kunci:** alert, analisis data eksploratif, deret waktu IoT, integrasi platform, provenance.

\newpage

## Abstract

*[STUDENT NAME], “Design and Development of an Integrated Web Platform for Anomaly Analysis and Monitoring in Bivariate IoT Time Series”, Applied Bachelor Final Project/Thesis, [STUDY PROGRAM], [DEPARTMENT], Politeknik Negeri Semarang, supervised by [SUPERVISOR I] and [SUPERVISOR II], [MONTH AND YEAR], [NUMBER OF PAGES] pages.*

Managing bivariate IoT telemetry requires a clear separation between descriptive data, simulation results, and inference results that depend on external model artifacts. This study aims to design and develop a web platform that integrates data import, time-series storage, exploratory data analysis, API contracts, processing workers, inference replay, and alert monitoring. The study applies an evidence-based engineering approach using local implementation artifacts. The platform is designed with FastAPI, PostgreSQL/TimescaleDB, import, exploratory-analysis, and replay workers, a React/Material UI interface, and Docker Compose. The Transformer-AE checkpoint and the p99.5 threshold policy are treated as frozen external inputs rather than training or model-comparison objects in this study. Canonical EDA evidence records two passing tests over 6,931,792 raw rows. Other verification evidence includes contract tests, frontend tests, a build, mock-based end-to-end tests, and manual quality assurance. The manual quality-assurance verdict is REJECT because two defects are documented. The actual model artifact is unavailable in the checkout; therefore, artifact-based inference execution is not claimed.

**Keywords:** alert, exploratory data analysis, IoT time series, platform integration, provenance.

\newpage

## Daftar isi

[DAFTAR ISI DIHASILKAN OTOMATIS SETELAH SELURUH JUDUL, NOMOR HALAMAN, DAN LAMPIRAN STABIL]

## Daftar tabel

[DAFTAR TABEL DIHASILKAN OTOMATIS DARI SELURUH CAPTION TABEL PADA NASKAH FINAL]

## Daftar gambar

[DAFTAR GAMBAR DIHASILKAN OTOMATIS DARI SELURUH CAPTION GAMBAR PADA NASKAH FINAL]

## Daftar lampiran

[DAFTAR LAMPIRAN DIHASILKAN OTOMATIS SETELAH LAMPIRAN BUKTI YANG DISETUJUI DITETAPKAN]

## Daftar singkatan

| Singkatan | Kepanjangan |
|---|---|
| API | *Application Programming Interface* |
| CI | *Continuous Integration* |
| CLI | *Command-Line Interface* |
| CSV | *Comma-Separated Values* |
| CUDA | *Compute Unified Device Architecture* |
| E2E | *End-to-End* |
| ECDF | *Empirical Cumulative Distribution Function* |
| EDA | *Exploratory Data Analysis* |
| GPU | *Graphics Processing Unit* |
| IoT | *Internet of Things* |
| JSON | *JavaScript Object Notation* |
| MQTT | *Message Queuing Telemetry Transport* |
| MUI | *Material UI* |
| QA | *Quality Assurance* |
| RH | *Relative Humidity* |
| RSS | *Resident Set Size* |
| SHA-256 | *Secure Hash Algorithm 256-bit* |
| SLA | *Service-Level Agreement* |
| SPA | *Single-Page Application* |
| SUS | *System Usability Scale* |
| TLS | *Transport Layer Security* |
| UEQ | *User Experience Questionnaire* |
| UI | *User Interface* |
| URL | *Uniform Resource Locator* |
| UTC | *Coordinated Universal Time* |
| UX | *User Experience* |
| WIB | Waktu Indonesia Barat |

## Daftar lambang

[DAFTAR LAMBANG DIHASILKAN JIKA NASKAH FINAL MEMUAT LAMBANG ATAU PERSAMAAN YANG MEMERLUKAN DAFTAR TERPISAH]

> Catatan konversi: nomor halaman bagian awal menggunakan angka Romawi kecil. Tata letak akhir mengikuti ketentuan ukuran kertas, huruf, margin, dan spasi pada pedoman Politeknik Negeri Semarang.
