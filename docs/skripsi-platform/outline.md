# Blueprint Skripsi Platform

## 1. Identitas dan tujuan blueprint

Judul yang digunakan adalah **Rancang Bangun Platform Web Terintegrasi untuk Analisis dan Pemantauan Anomali pada Deret Waktu IoT Bivariat**.

Blueprint ini adalah rencana penulisan, bukan naskah bab lengkap. Ruang lingkupnya hanya platform: arsitektur, implementasi, integrasi komponen model, manajemen data, API, antarmuka, pengujian, dan evaluasi platform. Setiap penulis lanjutan harus memakai bukti yang ditunjuk pada dokumen ini dan tidak menambah klaim tanpa bukti baru yang dapat ditelusuri.

Pedoman Polines menetapkan lima bab utama, yaitu pendahuluan, tinjauan pustaka, kegiatan pelaksanaan, analisis dan pembahasan, serta kesimpulan. Bab V hanya memuat kesimpulan dan tidak memuat saran. Rincian yang disusun ke bawah pada naskah akhir harus menggunakan angka atau huruf, bukan simbol bullet.

## 2. Batas kepemilikan dan ruang lingkup

| Komponen | Termasuk skripsi platform | Tidak termasuk skripsi platform |
|---|---|---|
| Arsitektur | Desain web, API, basis data, worker, topologi Docker Compose, kontrak integrasi, dan provenance | Desain arsitektur Transformer-AE atau model pembanding lain |
| Data | Import, penyimpanan, segmentasi operasional, provenance, EDA deskriptif, dan penyajian data | Pembentukan dataset eksperimen modeling, evaluasi lima model, atau klaim kualitas dataset untuk model |
| Model | Integrasi checkpoint eksternal, metadata, mount artefak, pemanggilan inferensi, penyimpanan skor, dan publikasi alert | Pelatihan, tuning, pemilihan model pemenang, ablation, biaya komputasi model, atau perbandingan model |
| Ambang | Meneruskan metadata kebijakan ambang yang telah dibekukan ke kontrak integrasi | Menghitung, mengoptimalkan, atau membuktikan universalitas ambang p99.5 |
| Evaluasi | Uji kontrak, uji aplikasi, uji build, uji EDA kanonis, QA manual, dan batas bukti | Mengubah metrik lima model menjadi hasil penelitian platform |
| Antarmuka | SPA React/MUI, tujuh layar, penyajian provenance, alert, EDA, dan status sistem | Klaim pengalaman pengguna formal tanpa evaluasi pengguna yang benar |

Checkpoint Transformer-AE terpilih, kebijakan ambang p99.5, dan metadata modeling diperlakukan sebagai masukan eksternal yang dibekukan dari `/home/reky/Downloads/JOIV_PyTorch_Reconstruction_Validation (1).pdf`. Dokumen tersebut boleh dirujuk untuk menjelaskan kontrak integrasi, tetapi angka perbandingan lima model tidak boleh dilaporkan sebagai hasil skripsi ini.

## 3. Rumusan masalah

1. Bagaimana merancang dan membangun platform web terintegrasi yang mengelola data deret waktu IoT bivariat, analisis eksploratif, proses inferensi berbasis artefak model eksternal, serta pemantauan alert secara terpisah dan dapat ditelusuri?
2. Bagaimana menerapkan kontrak API dan data yang ketat, penyimpanan PostgreSQL/TimescaleDB, worker import, EDA, dan replay, serta publikasi inferensi dan alert yang transaksional untuk menjaga konsistensi hasil platform?
3. Bagaimana hasil verifikasi implementasi platform melalui bukti EDA kanonis, pengujian otomatis, build, pengujian ujung ke ujung berbasis mock, dan QA manual langsung, termasuk keterbatasan serta cacat yang masih ditemukan?

## 4. Tujuan

1. Menghasilkan rancangan dan implementasi platform web yang mengintegrasikan pengelolaan telemetri IoT bivariat, EDA deskriptif, inferensi berbasis artefak eksternal, serta pemantauan alert.
2. Mengimplementasikan arsitektur layanan yang mencakup FastAPI, PostgreSQL/TimescaleDB, worker import, EDA, dan replay, kontrak ketat, pencatatan provenance, serta mekanisme publikasi transaksional.
3. Mendeskripsikan dan mengevaluasi bukti verifikasi yang tersedia secara terbatas, termasuk hasil EDA kanonis, pengujian backend dan frontend, build, E2E berbasis mock, serta QA manual yang berstatus REJECT.

## 5. Manfaat

1. Bagi pengembangan sistem, blueprint ini memberi struktur implementasi yang memisahkan data deskriptif, inferensi, dan lifecycle alert sehingga setiap hasil dapat ditelusuri ke sumber dan kontraknya.
2. Bagi operator, platform menyediakan rancangan untuk meninjau telemetri, hasil EDA, status pekerjaan replay, dan episode alert tanpa menyamakan simulasi atau EDA dengan hasil inferensi model nyata.
3. Bagi akademik, dokumen ini menunjukkan penerapan rekayasa perangkat lunak pada integrasi komponen analitik eksternal tanpa mengklaim kepemilikan atas penelitian pelatihan model.

## 6. Kontribusi yang dapat diklaim

1. Rancangan integrasi platform yang memisahkan EDA deskriptif dari inferensi anomali dan membedakan provenance hasil simulasi, hasil berbasis artefak, dan bukti EDA.
2. Kontrak data serta API ketat untuk data waktu, provenance, hasil inferensi, lifecycle alert, dan respons problem details.
3. Rancangan proses worker dan basis data untuk import, EDA, dan replay yang memakai staging, lifecycle pekerjaan, serta publikasi hasil dan alert secara transaksional.
4. Evaluasi implementasi berbasis bukti lokal yang menyajikan keberhasilan terbatas dan cacat QA secara seimbang.

## 7. Metode penelitian dan pengembangan

Metode yang digunakan adalah rancang bangun terapan dengan siklus rekayasa perangkat lunak berbasis bukti. Narasi Bab III harus menyatakan bahwa metode ini mengevaluasi artefak platform, bukan efektivitas atau superioritas arsitektur pembelajaran mesin.

| Tahap | Kegiatan | Luaran yang ditulis | Bukti atau batas |
|---|---|---|---|
| 1. Analisis kebutuhan dan batas | Menetapkan aktor, aliran data, batas ownership, kebutuhan kontrak, dan status artefak eksternal | Kebutuhan fungsional dan nonfungsional yang terukur | `docs/thesis-evidence-map.md`, PDF JOIV, `.omx/context/...` |
| 2. Perancangan | Merancang konteks layanan, data, endpoint, state machine alert, kontrak artifact, serta SPA | Diagram arsitektur dan desain komponen | `compose.yaml`, `backend/anomaly_backend/contracts.py`, `backend/anomaly_backend/problems.py`, dokumen PRD lokal |
| 3. Implementasi | Mengimplementasikan backend, database, worker, frontend, dan Compose | Matriks komponen terhadap berkas implementasi | Kode dan struktur berkas lokal |
| 4. Verifikasi otomatis | Menjalankan atau memakai rekaman hasil test kontrak, test backend, test frontend, build, dan E2E | Tabel hasil dengan cakupan dan batas | `.omo/evidence/`, `frontend/test-results/.last-run.json` |
| 5. Evaluasi operasional terbatas | Menilai EDA kanonis dan QA manual langsung | Hasil faktual, cacat, dan status penerimaan | `task-21-canonical-integration.txt`, `task-F3-manual-qa-summary.txt` |
| 6. Analisis | Menafsirkan hasil terhadap tujuan platform tanpa membuat klaim di luar bukti | Pembahasan hubungan desain, bukti, dan keterbatasan | Bab IV |

### 7.1 Pemisahan EDA dan inferensi anomali

1. EDA adalah subsistem deskriptif. Bukti yang disajikan meliputi kualitas sumber, pasangan timestamp, cakupan kalender, distribusi, asosiasi, struktur temporal, kandidat perubahan rezim, ketidakpastian, dan metadata audit.
2. EDA tidak menghasilkan label kebenaran, diagnosis sebab fisik, klasifikasi anomali, atau keputusan inferensi model.
3. Inferensi anomali adalah alur berbeda yang menggunakan artefak model eksternal, metadata model, skor, ambang, dan lifecycle alert.
4. Hasil EDA tidak boleh dipakai untuk mengubah ambang p99.5, memilih model, atau mengklaim bahwa suatu observasi adalah anomali referensi.

## 8. Manifest keluaran penulisan

Semua berkas berikut direncanakan sebagai Markdown terpisah pada tahap penulisan berikutnya. Tugas ini hanya membuat `outline.md`; tidak ada bab lengkap atau lampiran lengkap yang dibuat sekarang.

| Urut | Berkas target | Isi dan status |
|---:|---|---|
| 00 | `00-bagian-awal.md` | Halaman awal, abstrak Indonesia dan Inggris, daftar isi, daftar tabel, daftar gambar, daftar lampiran, daftar singkatan. Status: rencana. |
| 01 | `01-bab-i-pendahuluan.md` | Bab I Pendahuluan. Status: rencana. |
| 02 | `02-bab-ii-tinjauan-pustaka.md` | Bab II Tinjauan Pustaka yang hanya relevan dengan platform. Status: rencana. |
| 03 | `03-bab-iii-kegiatan-pelaksanaan.md` | Bab III Kegiatan Pelaksanaan untuk perancangan, pembuatan, dan verifikasi. Status: rencana. |
| 04 | `04-bab-iv-analisis-dan-pembahasan.md` | Bab IV hasil implementasi dan evaluasi yang telah diverifikasi. Status: rencana. |
| 05 | `05-bab-v-kesimpulan.md` | Bab V kesimpulan singkat, tanpa saran. Status: rencana. |
| 06 | `06-daftar-pustaka.md` | Daftar pustaka alfabetis tanpa nomor urut sesuai Polines. Status: rencana. |
| 07 | `07-lampiran.md` | Lampiran bukti terpilih, kontrak, log, dan artefak yang aman dibagikan. Status: rencana. |

## 9. Target panjang naskah

Target ini dirancang untuk menghasilkan sedikitnya 70 halaman utama pada format Polines, yaitu A4, Times New Roman 12, spasi 1,5, margin kiri 4 cm serta margin atas, kanan, dan bawah 3 cm. Angka halaman adalah target kerja, bukan hasil yang dibuat dengan pengulangan atau pengisian kosong.

| Berkas | Target kata | Target halaman DOCX | Alasan substansi |
|---|---:|---:|---|
| 00-bagian-awal.md | 900 sampai 1.200 | 8 sampai 12 halaman awal bernomor Romawi | Abstrak, daftar, dan elemen formal. |
| 01-bab-i-pendahuluan.md | 3.800 sampai 4.500 | 11 sampai 13 | Masalah, scope split, tujuan, manfaat, dan batasan harus eksplisit. |
| 02-bab-ii-tinjauan-pustaka.md | 7.500 sampai 8.500 | 22 sampai 25 | Teori platform, EDA, transaksi, provenance, antarmuka, dan studi terkait. |
| 03-bab-iii-kegiatan-pelaksanaan.md | 7.000 sampai 8.000 | 20 sampai 23 | Tahapan rancangan, implementasi, data, dan skenario verifikasi. |
| 04-bab-iv-analisis-dan-pembahasan.md | 8.000 sampai 9.000 | 23 sampai 27 | Hasil implementasi, bukti verifikasi, QA REJECT, dan keterbatasan. |
| 05-bab-v-kesimpulan.md | 1.000 sampai 1.300 | 3 sampai 4 | Jawaban ringkas terhadap tiga rumusan masalah. |
| Total teks utama Bab I sampai Bab V | 27.300 sampai 31.300 | 79 sampai 92 sebelum penyesuaian tabel dan gambar | Cukup untuk target 70+ halaman tanpa menambah teks pengisi. |
| 06 dan 07 | Bergantung sumber dan bukti | Tidak dihitung sebagai halaman utama | Daftar pustaka dan lampiran dipisahkan dari target isi utama. |

## 10. Katalog bukti lokal yang harus dipakai

| Kode | Bukti terverifikasi | Lokasi lokal | Pemakaian yang diizinkan |
|---|---|---|---|
| E01 | Pedoman lima bab, struktur Bab I sampai Bab V, format, sitasi nama tahun, dan larangan bullet | `docs/pedoman-penyusunan-tugas-akhir-skripsi-polines-2014.md` | Struktur dan gaya naskah. |
| E02 | Batas ownership antara skripsi platform dan jalur modeling | `docs/thesis-evidence-map.md` bagian awal | Menetapkan scope dan larangan klaim. |
| E03 | Checkpoint Transformer-AE, kebijakan p99.5, serta metadata modeling sebagai masukan eksternal | `/home/reky/Downloads/JOIV_PyTorch_Reconstruction_Validation (1).pdf` | Hanya kontrak integrasi dan konteks input beku. |
| E04 | Topologi layanan Docker Compose, PostgreSQL/TimescaleDB, worker, mount `/models:ro`, EDA worker, import, dan Nginx | `compose.yaml` | Diagram arsitektur dan batas deployment lokal. |
| E05 | Kontrak ketat, batas waktu corpus dan operasional, provenance, serta validasi respons | `backend/anomaly_backend/contracts.py` | Penjelasan kontrak data. |
| E06 | Respons problem details, kode status, request ID, dan kegagalan layanan | `backend/anomaly_backend/problems.py` | Penjelasan penanganan error API. |
| E07 | Router FastAPI produksi dan pemisahan endpoint menurut domain | `backend/anomaly_backend/main.py`, `backend/anomaly_backend/routes/` | Manifest endpoint dan arsitektur API. |
| E08 | Tujuh halaman SPA React/MUI | `frontend/src/pages/` | Bukti struktur antarmuka, bukan bukti kegunaan formal. |
| E09 | Skrip build, unit test, lint, dan E2E frontend | `frontend/package.json` | Metode verifikasi frontend. |
| E10 | Bukti kontrak backend EDA, 28 test lulus, 11 section, 13 reason eligibility | `.omo/evidence/task-4-backend-contracts.txt` | Hasil pengujian kontrak EDA. |
| E11 | Bukti test kontrak frontend, 13 test lulus | `.omo/evidence/task-5-frontend-contracts.txt` | Hasil test frontend terbatas. |
| E12 | Bukti EDA kanonis, runtime, memori, jumlah baris, dan test | `.omo/evidence/task-21-canonical-integration.txt` | Hasil evaluasi EDA yang dapat diberi angka. |
| E13 | Bukti unit test frontend dan build sukses beserta peringatan ukuran bundle | `.omo/evidence/task-19-eda-page.txt` | Hasil build dan test frontend dengan batasnya. |
| E14 | Daftar suite Playwright, skenario mock, dan status run terakhir passed | `frontend/tests/e2e/`, `frontend/tests/e2e/helpers.ts`, `frontend/test-results/.last-run.json` | Hanya klaim E2E dengan mock, bukan integrasi backend nyata. |
| E15 | QA manual hidup berstatus REJECT, hal yang berhasil, dan dua blocker | `.omo/evidence/task-F3-manual-qa-summary.txt` | Hasil QA yang wajib dilaporkan apa adanya. |
| E16 | Detail cacat kontrol tanggal | `.omo/evidence/task-F3-manual-qa-datetime-control-defect.txt` | Bukti blocker F3-1. |
| E17 | Respons API `not_eligible` dengan reason code | `.omo/evidence/task-F3-manual-qa-section-uncertainty.txt` dan pasangan change-points | Bukti blocker F3-2. |
| E18 | Kontrak preview, replay, alert, provenance, dan batas artifact | `.omx/plans/prd-b02f3872-platform-preview.md`, `.omx/plans/test-spec-b02f3872-platform-preview.md` | Konteks desain dan batas, bukan bukti keberhasilan produksi. |

## 11. Rencana berkas 00-bagian-awal.md

### 11.1 Struktur yang harus ditulis

1. Halaman sampul luar dan halaman judul memakai judul final, nama, NIM, program studi, jurusan, institusi, serta tahun setelah placeholder administrasi diisi.
2. Pernyataan keaslian, halaman persetujuan, halaman pengesahan, dan kata pengantar mengikuti contoh dalam pedoman Polines.
3. Abstrak bahasa Indonesia maksimum 200 kata memuat masalah platform, tujuan, metode rancang bangun, hasil verifikasi yang benar-benar tersedia, serta kata kunci.
4. Abstract bahasa Inggris harus setara makna, tetapi tidak menerjemahkan secara mekanis istilah Indonesia yang telah memiliki istilah teknis baku.
5. Daftar isi, daftar tabel, daftar gambar, daftar lampiran, daftar singkatan, dan daftar lambang dibuat setelah seluruh naskah stabil.

### 11.2 Bukti dan batas penulisan

| Bagian | Bukti yang dipakai | Batas |
|---|---|---|
| Judul dan scope | Judul pada blueprint ini, E02, E03 | Tidak menyebut perbandingan lima model sebagai kontribusi penulis. |
| Abstrak | E04 sampai E17 | Tidak menulis klaim real-time, scalable, secure, usable, atau accessibility-compliant. |
| Daftar singkatan | E04, E05, E06 | Minimal mencakup API, EDA, IoT, SPA, RSS, SHA-256, dan WIB. |

### 11.3 Tabel dan gambar yang direncanakan

1. Tidak ada tabel atau gambar substantif di bagian awal.
2. Placeholder daftar tabel dan daftar gambar diisi otomatis pada produksi DOCX.

## 12. Rencana berkas 01-bab-i-pendahuluan.md

### 12.1 BAB I PENDAHULUAN

#### 12.1.1 1.1 Latar Belakang

1. Mulai dari kebutuhan mengelola telemetri IoT bivariat sebagai data berurutan yang memerlukan penyajian, penelusuran provenance, dan pemisahan makna antara data deskriptif dan hasil inferensi.
2. Jelaskan bahwa platform bukan hanya halaman visual. Platform menghubungkan import data, penyimpanan deret waktu, API, worker, EDA, integrasi artefak model eksternal, serta alert.
3. Tegaskan adanya risiko salah tafsir apabila EDA, simulasi preview, dan inferensi berbasis artefak nyata ditampilkan tanpa provenance yang jelas.
4. Nyatakan bahwa model Transformer-AE dan kebijakan p99.5 datang dari penelitian modeling eksternal yang telah dibekukan. Platform tidak meneliti kembali desain, pelatihan, atau perbandingan model.
5. Tutup latar belakang dengan kebutuhan rancang bangun platform yang dapat mendokumentasikan kontrak, data, proses kerja, hasil, dan keterbatasannya.

#### 12.1.2 1.2 Perumusan Masalah

1. Tulis tiga rumusan masalah dari Bagian 3 blueprint ini tanpa mengubah fokusnya menjadi pengujian model.
2. Gunakan kalimat tanya yang dapat dijawab melalui desain dan bukti evaluasi platform.

#### 12.1.3 1.3 Tujuan

1. Tulis tiga tujuan dari Bagian 4 blueprint ini dengan kata kerja menghasilkan, mengimplementasikan, mendeskripsikan, dan mengevaluasi.
2. Hindari kata membuktikan keunggulan model, mengoptimalkan ambang, atau meningkatkan akurasi jika tidak ada eksperimen platform untuk mendukungnya.

#### 12.1.4 1.4 Manfaat

1. Uraikan manfaat bagi implementasi sistem, operator, dan akademik dari Bagian 5 blueprint ini.
2. Nyatakan manfaat sebagai potensi penggunaan artefak platform, bukan manfaat yang telah dibuktikan melalui studi pengguna atau deployment produksi.

#### 12.1.5 1.5 Batasan Masalah

1. Sistem yang dibahas adalah platform web lokal dengan FastAPI, PostgreSQL/TimescaleDB, worker, React/MUI, dan Docker Compose.
2. EDA hanya bersifat deskriptif dan tidak menetapkan ground truth atau sebab fisik anomali.
3. Checkpoint Transformer-AE, p99.5, dan metadata model adalah input eksternal yang dibekukan.
4. Artefak model aktual tidak tersedia di checkout. Mount `/models` yang read-only adalah batas kontrak deployment, bukan bukti inferensi artefak berhasil dijalankan.
5. Tidak ada klaim autentikasi, otorisasi, CI, load testing, pengujian keamanan, SUS formal, atau pengujian aksesibilitas formal karena tidak ada bukti yang memadai.
6. Pengujian E2E frontend menggunakan mock, sehingga tidak membuktikan interaksi end-to-end dengan backend produksi atau artefak model nyata.
7. Hasil QA manual berstatus REJECT karena cacat kontrol tanggal dan penyajian reason code `not_eligible`.

#### 12.1.6 1.6 Sistematika Penulisan

1. Bab I menjelaskan masalah, tujuan, manfaat, batasan, dan sistematika.
2. Bab II menjelaskan teori dan studi terkait yang relevan untuk platform.
3. Bab III menjelaskan tahapan perancangan, implementasi, dan verifikasi.
4. Bab IV menyajikan hasil implementasi, bukti evaluasi, pembahasan, serta keterbatasan.
5. Bab V berisi kesimpulan ringkas yang diturunkan dari Bab IV tanpa saran.

### 12.2 Bukti terverifikasi per bagian Bab I

| Bagian | Bukti primer | Cara memakai bukti |
|---|---|---|
| 1.1 | E02, E03, E04, E18 | Menjelaskan kebutuhan integrasi dan batas ownership. |
| 1.2 dan 1.3 | E02, E04 sampai E08 | Merumuskan masalah dan tujuan platform. |
| 1.4 | E04 sampai E08 | Menetapkan manfaat sebagai manfaat desain, bukan hasil survei. |
| 1.5 | E02, E03, E14, E15 | Membatasi model, artifact, metode evaluasi, dan QA. |
| 1.6 | E01 | Mengikuti lima bab Polines. |

### 12.3 Tabel dan gambar Bab I yang direncanakan

| ID | Judul rencana | Isi | Status bukti |
|---|---|---|---|
| Tabel 1.1 | Pembagian ruang lingkup skripsi platform dan modeling | Ringkasan Bagian 2 blueprint | Siap ditulis dari E02 dan E03. |
| Tabel 1.2 | Batasan penelitian platform | Tujuh batasan pada 1.5 | Siap ditulis dari E02, E14, dan E15. |
| Gambar 1.1 | Posisi skripsi platform dalam ekosistem | Data telemetri, EDA, platform, artefak model eksternal, alert | Placeholder diagram konseptual, bukan arsitektur runtime rinci. |

## 13. Rencana berkas 02-bab-ii-tinjauan-pustaka.md

### 13.1 BAB II TINJAUAN PUSTAKA

#### 13.1.1 2.1 Platform IoT untuk pemantauan data deret waktu

1. Definisikan platform IoT sebagai susunan komponen pengumpulan atau import data, penyimpanan, pemrosesan, penyajian, dan pemantauan yang saling terhubung.
2. Jelaskan bahwa konteks skripsi adalah deret waktu IoT bivariat suhu dan kelembapan relatif, tetapi penelitian tidak mengklaim validasi pada banyak perangkat atau domain.
3. Tinjau kebutuhan provenance, observabilitas proses, dan pemisahan data mentah, hasil proses, serta status pekerjaan.

#### 13.1.2 2.2 Deret waktu IoT bivariat dan batas analisis platform

1. Jelaskan konsep timestamp, pasangan dua kanal, gap, segmentasi, dan zona waktu sebagai kebutuhan data platform.
2. Jelaskan perbedaan skor anomali, alert, label, dan diagnosis. Platform dapat menyimpan dan menampilkan masing-masing objek tanpa menyatakan sebab fisik.
3. Nyatakan bahwa training, tuning, dan evaluasi perbandingan lima autoencoder berada di luar Bab II ini, kecuali konteks singkat untuk menjelaskan kontrak artifact yang dibekukan.

#### 13.1.3 2.3 Integrasi artefak model eksternal

1. Jelaskan konsep artefak model immutable, metadata versi, hash, urutan kanal, window, stride, semantic timestamp skor, ambang, dan provenance.
2. Uraikan target kontrak deploy: artefak dipasang hanya baca di `/models`, diverifikasi checksum sebelum dipakai, lalu dihubungkan ke worker privat. Formulasi ini adalah rancangan integrasi.
3. Tegaskan bahwa checkout saat ini tidak menyediakan artefak model aktual. Karena itu, Bab II tidak boleh menyatakan keberhasilan validasi checksum atau inferensi live.

#### 13.1.4 2.4 Arsitektur aplikasi web dan API

1. Jelaskan FastAPI sebagai lapisan API dengan router domain, kontrak request dan response ketat, serta problem details untuk kesalahan permintaan, konflik, tidak ditemukan, dan layanan tidak tersedia.
2. Jelaskan perbedaan waktu corpus dalam kalender Asia/Jakarta dan instant operasional UTC, karena kedua domain waktu berperan berbeda dalam telemetri, job, lease, dan lifecycle alert.
3. Jelaskan SPA React/MUI sebagai antarmuka yang mengonsumsi kontrak API dan harus menampilkan provenance secara eksplisit.

#### 13.1.5 2.5 PostgreSQL, TimescaleDB, transaksi, dan provenance

1. Jelaskan peran PostgreSQL/TimescaleDB dalam penyimpanan telemetri, hasil inferensi, alert, job replay, dan metadata sumber.
2. Jelaskan prinsip staging, idempotensi, immutable history, snapshot model ketika job dibuat, serta publikasi hasil dan alert pada transaksi akhir.
3. Jelaskan bahwa transaksi menjaga konsistensi perubahan dalam ruang lingkup implementasi yang diperiksa. Jangan menyebutnya sebagai jaminan keamanan, skalabilitas, atau ketahanan produksi.

#### 13.1.6 2.6 Worker import, EDA, dan replay

1. Jelaskan worker import sebagai proses membaca sumber read-only dan menerbitkan data setelah validasi.
2. Jelaskan worker EDA sebagai proses komputasi deskriptif yang memiliki identitas sumber, versi algoritme, dan hash konfigurasi.
3. Jelaskan worker replay sebagai proses latar belakang untuk memperoleh skor, membangun episode alert, dan mencatat lifecycle pekerjaan.
4. Bedakan tugas worker replay dari proses pelatihan model. Worker replay tidak melatih atau memilih model.

#### 13.1.7 2.7 EDA deskriptif dan pemisahannya dari inferensi

1. Jelaskan EDA sebagai analisis kualitas, distribusi, asosiasi, cakupan temporal, struktur temporal, kandidat perubahan rezim, dan metadata audit.
2. Nyatakan interpretasi yang dilarang: korelasi bukan kausalitas, flag kualitas bukan ground truth, dan kandidat perubahan rezim bukan label anomali.
3. Jelaskan bahwa EDA memakai run dengan provenance dan status `not_eligible`, sehingga ketiadaan hasil statistik tidak boleh dipresentasikan sebagai nilai nol atau kegagalan sistem tanpa konteks.

#### 13.1.8 2.8 Alert dan lifecycle state machine

1. Definisikan episode alert sebagai pengelompokan window anomali berurutan dengan konteks perangkat, versi model, provenance, job replay, dan segmen yang sama.
2. Jelaskan status `detected`, `acknowledged`, dan `resolved`, serta event lifecycle append-only.
3. Jelaskan alasan pemisahan waktu episode dengan waktu pembuatan dan penerimaan command agar pembaca tidak mencampur waktu data dengan waktu operasional.

#### 13.1.9 2.9 Evaluasi platform dan antarmuka dashboard

1. Jelaskan evaluasi implementasi sebagai kombinasi pengujian kontrak, pengujian otomatis, build, bukti EDA kanonis, dan QA manual.
2. Gunakan literatur dashboard dan UX hanya untuk menyusun kriteria evaluasi, bukan untuk menyatakan bahwa platform ini telah lulus SUS atau studi usability formal.
3. Tegaskan bahwa E2E berbasis mock menguji perilaku antarmuka yang diskenariokan, bukan bukti integrasi backend atau model aktual.

#### 13.1.10 2.10 Studi terkait, kesenjangan, dan kerangka pikir

1. Bandingkan studi terkait berdasarkan fokus platform IoT, pemantauan, EDA atau kualitas data, evaluasi platform, serta dashboard.
2. Nyatakan kesenjangan secara terbatas: blueprint ini memusatkan integrasi web, provenance, EDA terpisah, kontrak artifact eksternal, dan evaluasi implementasi berbasis bukti lokal.
3. Tutup dengan kerangka pikir yang menghubungkan input data, import, penyimpanan, EDA, replay inferensi, alert, API, SPA, dan evaluasi.

### 13.2 Bukti terverifikasi per bagian Bab II

| Bagian | Bukti primer | Bukti literatur yang direncanakan | Batas |
|---|---|---|---|
| 2.1 dan 2.2 | E02, E03, E18 | Mofidul et al. 2022, Gillespie et al. 2023, Dineva et al. 2022 | Tidak menggeneralisasi satu implementasi lokal. |
| 2.3 | E03, E04, E18 | Zamanzadeh Darban et al. 2025 hanya sebagai latar, bukan hasil platform | Artifact aktual tidak ada di checkout. |
| 2.4 | E05, E06, E07, E08, E09 | Calderon et al. 2023 | Jumlah endpoint harus berasal dari manifest yang dibekukan. |
| 2.5 | E04, E18 | García-Valls et al. 2022 | Tidak mengklaim skala atau keamanan. |
| 2.6 dan 2.7 | E04, E10, E12 | Muñoz et al. 2024 | EDA bukan inferensi. |
| 2.8 | E05, E18 | Mofidul et al. 2022 | State machine dibahas sebagai implementasi platform. |
| 2.9 | E09, E11, E13, E14, E15 | Almasi et al. 2023, Choma et al. 2024 | Tidak menyebut SUS atau aksesibilitas formal. |
| 2.10 | Seluruh katalog E01 sampai E18 | Semua sumber pada peta sitasi | Metadata bibliografis lengkap harus diverifikasi sebelum daftar pustaka final. |

### 13.3 Tabel dan gambar Bab II yang direncanakan

| ID | Judul rencana | Isi | Status bukti |
|---|---|---|---|
| Tabel 2.1 | Istilah dan batas makna platform | EDA, inferensi, skor, alert, label, provenance, artifact | Siap dari E02, E03, E05, dan E18. |
| Tabel 2.2 | Perbandingan EDA dan inferensi anomali | Tujuan, input, output, worker, bukti, larangan interpretasi | Siap dari E04, E10, dan E12. |
| Tabel 2.3 | Kontrak artifact model eksternal | Metadata yang wajib tersedia dan status saat ini | Siap sebagai desain dari E03 dan E18. |
| Tabel 2.4 | Studi terkait platform dan dashboard | Fokus, metode, relevansi, batas penggunaan | Diisi setelah tautan Consensus diverifikasi. |
| Gambar 2.1 | Kerangka pikir platform | Aliran data hingga evaluasi | Placeholder diagram konseptual. |
| Gambar 2.2 | Pemisahan domain waktu | WIB untuk corpus dan UTC untuk operasi | Placeholder diagram dari E05 dan E18. |
| Gambar 2.3 | State machine lifecycle alert | detected, acknowledged, resolved | Placeholder diagram dari E05 dan E18. |

## 14. Rencana berkas 03-bab-iii-kegiatan-pelaksanaan.md

### 14.1 BAB III KEGIATAN PELAKSANAAN

#### 14.1.1 3.1 Metode dan tahapan kegiatan

1. Nyatakan metode rancang bangun terapan dan enam tahap pada Bagian 7 blueprint ini.
2. Jelaskan keluaran tiap tahap, kriteria selesai, serta hubungan bukti desain dengan bukti verifikasi.
3. Jangan mengubah Bab III menjadi metodologi eksperimen lima model.

#### 14.1.2 3.2 Analisis kebutuhan dan kebutuhan sistem

1. Identifikasi kebutuhan pengelolaan telemetri, EDA, replay, alert, model registry, provenance, dan status sistem.
2. Jelaskan kebutuhan fungsional berdasarkan tujuh layar SPA, endpoint API, dan lifecycle job.
3. Jelaskan kebutuhan kualitas secara hati-hati sebagai kebutuhan desain, misalnya validasi ketat, konsistensi transaksi, dan keterlacakan provenance.
4. Bedakan kebutuhan kualitas dari klaim terbukti. Tidak ada target throughput, SLA, pentest, atau hasil SUS yang dapat diisi.

#### 14.1.3 3.3 Perancangan arsitektur sistem

1. Rancang topologi Docker Compose: Nginx sebagai pintu publik, FastAPI API, PostgreSQL/TimescaleDB, layanan migrasi dan seed, worker replay, worker EDA, layanan import profil, serta CLI ops.
2. Rancang jaringan backend internal dan jaringan publik sesuai Compose.
3. Rancang worker inferensi agar membaca artifact dari `/models` secara read-only. Verifikasi checksum artifact adalah syarat sebelum artifact digunakan, tetapi belum dibuktikan berjalan karena artifact tidak tersedia lokal.
4. Rancang batas antara API yang melayani request singkat dan worker yang menjalankan proses panjang.

#### 14.1.4 3.4 Perancangan data, kontrak, dan penanganan kesalahan

1. Rancang data waktu corpus sebagai kalender Asia/Jakarta dan instant operasional sebagai RFC3339 UTC.
2. Rancang model kontrak ketat dengan penolakan field tambahan, nilai nonfinite, null yang tidak diizinkan, rentang waktu tidak valid, serta respons berukuran terkendali.
3. Rancang problem details yang membawa tipe, judul, status, detail, instance, request ID, dan detail validasi yang relevan.
4. Rancang metadata provenance untuk sumber data, konfigurasi, versi algoritme, versi model, hash, dan basis deteksi.

#### 14.1.5 3.5 Perancangan alur import dan EDA

1. Rancang import dari sumber read-only menuju staging lalu publikasi terkontrol.
2. Rancang EDA dengan identitas sumber, hash konfigurasi, hash manifest, dan sebelas section hasil.
3. Rancang status pekerjaan EDA dan status `not_eligible` yang menyimpan reason code secara eksplisit.
4. Nyatakan bahwa EDA tidak mengirim input ke proses pelatihan atau seleksi model dalam ruang lingkup skripsi.

#### 14.1.6 3.6 Perancangan alur replay, inferensi, dan alert

1. Rancang replay sebagai job eksplisit dengan snapshot versi model, interval, lifecycle queued, running, succeeded, atau failed, dan lease worker.
2. Rancang write path dengan staging hasil dan checkpoint episode pada tiap chunk.
3. Rancang publikasi final dalam satu transaksi yang memindahkan hasil inferensi dan alert, menutup episode terbuka, membersihkan staging, dan menandai job berhasil.
4. Rancang alert sebagai episode, bukan sekadar satu baris per skor, dengan status detected, acknowledged, dan resolved yang append-only.

#### 14.1.7 3.7 Perancangan antarmuka pengguna

1. Rancang tujuh layar SPA: Overview, Sensor Detail, EDA, Model Evaluation, Simulation, Alerts, dan System Health.
2. Rancang penandaan provenance, zona waktu, keadaan kosong, kesalahan, loading, dan status job pada setiap layar yang memerlukannya.
3. Rancang antarmuka tanpa menyamakan badge preview dengan artifact-backed inference.
4. Rancang pengujian responsif dan keyboard sebagai bagian pemeriksaan implementasi, bukan sertifikasi aksesibilitas.

#### 14.1.8 3.8 Rencana verifikasi dan evaluasi

1. Tetapkan test kontrak backend dan frontend untuk kontrak request, response, dan error.
2. Tetapkan test backend terhadap migrasi, database, lifecycle job, EDA, import, dan worker sesuai suite yang tersedia.
3. Tetapkan test frontend, lint, build TypeScript dan Vite, serta test produksi yang tercantum pada `package.json`.
4. Tetapkan Playwright E2E dengan pernyataan eksplisit bahwa skenario memakai mock.
5. Tetapkan proof EDA kanonis terisolasi sebagai evaluasi yang dapat melaporkan jumlah baris, runtime, dan RSS.
6. Tetapkan QA manual langsung sebagai gerbang penerimaan yang dapat menghasilkan PASS atau REJECT.

### 14.2 Bukti terverifikasi per bagian Bab III

| Bagian | Bukti primer | Isi yang boleh ditulis |
|---|---|---|
| 3.1 dan 3.2 | E01, E02, E18 | Metode, kebutuhan, dan batas. |
| 3.3 | E04, E07, E18 | Topologi Compose dan pemisahan API-worker. |
| 3.4 | E05, E06, E18 | Kontrak ketat dan problem details. |
| 3.5 | E04, E10, E12 | Import, EDA, identitas, dan reason code. |
| 3.6 | E05, E18 | Replay, snapshot, staging, transaksi, dan lifecycle alert. |
| 3.7 | E08, E09, E14 | Tujuh layar dan rencana test UI. |
| 3.8 | E10 sampai E17 | Metode evaluasi dan batas cakupan test. |

### 14.3 Tabel dan gambar Bab III yang direncanakan

| ID | Judul rencana | Isi | Status bukti |
|---|---|---|---|
| Tabel 3.1 | Kebutuhan fungsional platform | Kebutuhan, aktor, modul, acceptance evidence | Dirumuskan dari E18. |
| Tabel 3.2 | Kebutuhan kualitas dan batas verifikasi | Kontrak, provenance, transaksi, dan hal yang belum diuji | Dirumuskan dari E05, E06, E14, dan E15. |
| Tabel 3.3 | Rancangan endpoint FastAPI | Tepat 28 endpoint, domain, input, output, error utama | Placeholder sampai manifest endpoint dibekukan dari router dan OpenAPI. |
| Tabel 3.4 | Rancangan tabel atau entitas data | Corpus, telemetry, job, hasil inferensi, alert, event, run EDA | Dirumuskan dari E04, E05, dan E18. |
| Tabel 3.5 | Skenario verifikasi platform | Lapisan, alat, bukti, batas interpretasi | Siap dari E09 sampai E17. |
| Gambar 3.1 | Arsitektur Docker Compose | Service dan jaringan publik atau internal | Placeholder berbasis E04. |
| Gambar 3.2 | Diagram sekuens import dan EDA | Sumber, staging, worker, basis data, API, SPA | Placeholder berbasis E04, E10, dan E12. |
| Gambar 3.3 | Diagram sekuens replay dan publikasi alert | API, DB, worker, staging, hasil, alert | Placeholder berbasis E05 dan E18. |
| Gambar 3.4 | Diagram struktur SPA tujuh layar | Navigasi dan sumber data tiap layar | Placeholder berbasis E08. |

## 15. Rencana berkas 04-bab-iv-analisis-dan-pembahasan.md

### 15.1 BAB IV ANALISIS DAN PEMBAHASAN

#### 15.1.1 4.1 Hasil implementasi arsitektur platform

1. Sajikan topologi Compose yang terverifikasi: `db` memakai TimescaleDB, `migrate`, `seed`, `api`, `worker`, `eda-worker`, `eda-cli`, `import`, `eda-import`, `sim-import`, dan `nginx`.
2. Jelaskan API FastAPI terdiri dari 28 endpoint menurut manifest endpoint yang harus dibekukan sebelum draf final. Uraikan berdasarkan domain, bukan dengan menyalin kode router.
3. Sajikan PostgreSQL/TimescaleDB sebagai persistence layer serta peran jaringan internal backend dan Nginx pada jaringan publik.
4. Jelaskan mount artifact `/models` sebagai read-only pada worker. Nyatakan jelas bahwa artifact model tidak ada di checkout, sehingga hanya konfigurasi mount dan kontrak integrasinya yang dapat dibahas.

#### 15.1.2 4.2 Hasil implementasi kontrak dan problem details

1. Sajikan kontrak ketat yang menolak properti tambahan, nilai nonfinite, format waktu yang salah, dan rentang yang tidak valid.
2. Sajikan pemisahan timestamp corpus dan instant operasional, termasuk tujuan tampilan zona waktu dan lifecycle job.
3. Sajikan problem details sebagai bentuk respons error terstruktur yang memuat request ID, tanpa menyatakan jaminan keamanan sistem.
4. Gunakan hasil `28 passed in 0.17s`, 11 sections, dan 13 eligibility reasons sebagai bukti terbatas untuk kontrak EDA.

#### 15.1.3 4.3 Hasil implementasi import, EDA, dan provenance

1. Jelaskan import EDA yang menggunakan sumber dan manifest read-only, identity source, versi algoritme, hash konfigurasi, dan snapshot immutable.
2. Jelaskan sebelas section EDA serta makna status `not_eligible` sebagai hasil diagnostik, bukan payload kosong yang sukses.
3. Laporkan proof kanonis secara persis: `2 passed in 2147.53s`, parity runtime `1030.4646068310249s`, isolated full-range worker runtime `989.6441833919962s`, peak RSS `1,251,999,744 bytes`, dan batas memori `2,147,483,648 bytes`.
4. Laporkan jumlah kanonis secara persis: `6,931,792` raw rows, `3,460,865` exact pairs, dan `3,405,332` screened pairs. Jangan membulatkan atau menaikkan hasil ini menjadi SLA, klaim skalabilitas, atau klaim performa umum.
5. Tekankan kembali bahwa EDA hanya deskriptif dan tidak merupakan hasil inferensi anomali maupun dasar untuk mengubah parameter model.

#### 15.1.4 4.4 Hasil implementasi replay, inferensi, dan alert

1. Jelaskan desain replay worker, lifecycle job, snapshot model saat submit, lease, checkpoint, dan staging.
2. Jelaskan bahwa hasil inferensi serta alert dipublikasikan secara transaksional setelah proses chunk selesai, sesuai rancangan dan test plan lokal.
3. Jelaskan alert state machine detected, acknowledged, dan resolved dengan event append-only serta episode alert.
4. Bedakan semua penjelasan desain integrasi artifact dari bukti eksekusi artifact nyata. Status artifact model aktual adalah tidak tersedia di checkout.

#### 15.1.5 4.5 Hasil implementasi antarmuka React/MUI

1. Sajikan tujuh layar SPA dan fungsi utama masing-masing layar.
2. Jelaskan pemanfaatan React, Material UI, React Query, router, grafik, dan data grid berdasarkan `frontend/package.json` dan struktur sumber.
3. Sajikan penandaan provenance dan state antarmuka sebagai mekanisme untuk mengurangi salah tafsir antara EDA, preview simulasi, dan inferensi artifact-backed.
4. Hindari kata usable atau accessible sebagai status akhir. Nyatakan hanya bukti keyboard, focus, responsif, dan QA yang benar-benar ada.

#### 15.1.6 4.6 Hasil pengujian otomatis

1. Laporkan backend canonical integration: `2 passed in 2147.53s`, parity runtime `1030.4646068310249s`, isolated full-range worker runtime `989.6441833919962s`, peak RSS `1,251,999,744 bytes`, serta ordinary backend suite terisolasi `232 passed`, `2 skipped`, dan `2 canonical deselected` sesuai rekaman E12.
2. Laporkan kontrak EDA backend: `28 passed in 0.17s`, 11 sections, dan 13 eligibility reasons sesuai E10.
3. Laporkan kontrak frontend: `13 passed` sesuai E11.
4. Laporkan test frontend EDA yang direkam: `21 test files passed` dan `137 tests passed`. Sebutkan peringatan implementasi canvas pada lingkungan jsdom jika membahas log.
5. Laporkan build frontend berhasil, termasuk fakta terdapat peringatan chunk JavaScript terkompresi gzip `496.49 kB`. Jangan mengubahnya menjadi klaim optimasi performa.
6. Laporkan status E2E terakhir passed, tetapi suite menggunakan `AppMockScenario` dan mock state. Oleh sebab itu, bukti hanya menunjukkan alur frontend terskenario, bukan E2E dengan backend atau model nyata.

#### 15.1.7 4.7 Hasil QA manual langsung

1. Nyatakan verdict QA manual adalah REJECT.
2. Sajikan hasil baik yang benar-benar diamati: sembilan section EDA lengkap ter-render, dua section `not_eligible`, 24 surface chart atau image tidak nol, tidak ada overflow halaman pada 1440, 1280, dan 390 pixel, serta tidak ada error atau warning konsol pada flow yang diperiksa.
3. Sajikan blocker F3-1: perubahan kontrol Dari pada rentang custom tidak mempertahankan timestamp yang dipilih dan URL atau kontrol tidak tersinkron.
4. Sajikan blocker F3-2: kartu `not_eligible` tidak menampilkan reason code API `block_longer_than_run` atau `insufficient_daily_medians`, walaupun outcome eligibility benar.
5. Nyatakan bahwa hasil QA REJECT menghalangi klaim penerimaan antarmuka secara menyeluruh.

#### 15.1.8 4.8 Pembahasan terpadu

1. Hubungkan arsitektur worker, kontrak data, provenance, dan transaksi dengan tujuan menjaga pemisahan makna hasil platform.
2. Bahas proof EDA kanonis sebagai bukti reproduksibilitas untuk rilis dan konfigurasi tertentu, bukan bukti performa semua rentang atau semua deployment.
3. Bahas pengujian otomatis sebagai bukti setiap lapisan yang terbatas, bukan bukti bebas cacat.
4. Bahas QA REJECT sebagai temuan yang menunjukkan mengapa test otomatis dan QA manual perlu dipisahkan.
5. Bahas status artifact yang tidak tersedia sebagai batas utama integrasi checkpoint model dalam checkout saat ini.

#### 15.1.9 4.9 Keterbatasan

1. Autentikasi dan otorisasi belum dievaluasi sebagai kemampuan sistem.
2. CI belum dibuktikan melalui konfigurasi dan eksekusi pipeline yang tersedia.
3. Load testing belum dilakukan.
4. Pengujian keamanan belum dilakukan.
5. Evaluasi SUS formal belum dilakukan.
6. Pengujian aksesibilitas formal belum dilakukan.
7. E2E frontend menggunakan mock dan tidak membuktikan integrasi backend nyata.
8. Artifact model aktual tidak tersedia di checkout sehingga checksum validation dan inferensi artifact-backed tidak dapat diklaim berjalan.
9. QA manual berstatus REJECT akibat dua blocker yang terdokumentasi.

### 15.2 Bukti terverifikasi per bagian Bab IV

| Bagian | Bukti primer | Nilai atau status yang wajib dipertahankan |
|---|---|---|
| 4.1 | E04, E07, E08, E18 | Compose topology, 28 endpoint setelah manifest dibekukan, tujuh layar SPA, artifact tidak tersedia. |
| 4.2 | E05, E06, E10 | Strict contract dan problem details, `28 passed in 0.17s`, 11 sections, 13 eligibility reasons. |
| 4.3 | E04, E10, E12 | `2 passed in 2147.53s`; parity `1030.4646068310249s`; worker `989.6441833919962s`; RSS `1,251,999,744 bytes` di bawah `2,147,483,648 bytes`; `6,931,792` raw rows; `3,460,865` exact pairs; `3,405,332` screened pairs. |
| 4.4 | E05, E18 | Transaksi, state machine, dan batas artifact sebagai desain serta implementasi yang ditelusuri. |
| 4.5 | E08, E09, E14, E15 | React/MUI tujuh layar, test UI, bukti keyboard terbatas, tanpa sertifikasi usability atau aksesibilitas. |
| 4.6 | E10, E11, E12, E13, E14 | Test dan build sesuai angka rekaman, E2E mock limitation. |
| 4.7 | E15, E16, E17 | Verdict REJECT dan dua blocker apa adanya. |
| 4.8 dan 4.9 | E02 sampai E18 | Pembahasan berbatas bukti dan daftar keterbatasan. |

### 15.3 Tabel dan gambar Bab IV yang direncanakan

| ID | Judul rencana | Isi | Status bukti |
|---|---|---|---|
| Tabel 4.1 | Realisasi komponen platform | Komponen, berkas, peran, status bukti | Siap dari E04 sampai E09. |
| Tabel 4.2 | Manifest 28 endpoint FastAPI | Domain endpoint, metode, tujuan, kontrak dan error | Placeholder sampai endpoint manifest persis dibekukan. |
| Tabel 4.3 | Section EDA dan batas interpretasi | Sebelas section, output, reason `not_eligible`, larangan klaim | Siap dari E10 dan `docs/eda-v3-operations.md`. |
| Tabel 4.4 | Hasil proof EDA kanonis | Raw rows, pairs, runtime, RSS, test pass, identity hash | Siap dari E12. |
| Tabel 4.5 | Ringkasan verifikasi otomatis | Backend, frontend, build, E2E, bukti dan keterbatasan | Siap dari E10 sampai E14. |
| Tabel 4.6 | Hasil QA manual | Bukti yang diamati, blocker, verdict, dampak | Siap dari E15 sampai E17. |
| Tabel 4.7 | Keterbatasan evaluasi | Keterbatasan, dampak terhadap klaim, status | Siap dari E14, E15, dan E18. |
| Gambar 4.1 | Topologi layanan yang direalisasikan | Diagram Compose dengan jaringan dan volume | Placeholder, buat dari E04 tanpa menambah komponen. |
| Gambar 4.2 | Alur data dan provenance | Import, database, EDA, replay, alert, UI | Placeholder, buat dari E04, E05, dan E18. |
| Gambar 4.3 | Struktur navigasi tujuh layar | Overview sampai System Health | Placeholder, buat dari E08. |
| Gambar 4.4 | Lifecycle job replay dan alert | queued sampai terminal dan state alert | Placeholder, buat dari E05 dan E18. |
| Gambar 4.5 | Bukti tampilan EDA kanonis | Gunakan tangkapan bukti lokal yang relevan dan beri provenance | Placeholder. Jangan membuat screenshot sintetis. |
| Gambar 4.6 | Bukti cacat kontrol tanggal F3-1 | Masukkan `task-F3-manual-qa-datetime-control-defect.png` bila disetujui | Bukti ada, tampilkan sebagai defect, bukan keberhasilan. |
| Gambar 4.7 | Bukti `not_eligible` F3-2 | Gunakan pasangan screenshot uncertainty atau change-points bila disetujui | Bukti ada, tampilkan sebagai defect, bukan keberhasilan. |

## 16. Rencana berkas 05-bab-v-kesimpulan.md

### 16.1 BAB V KESIMPULAN

#### 16.1.1 5.1 Kesimpulan

1. Simpulkan bahwa platform dirancang dan diimplementasikan sebagai integrasi web untuk telemetri IoT bivariat, EDA deskriptif, replay inferensi, dan pemantauan alert dengan batas ownership yang jelas terhadap penelitian modeling.
2. Simpulkan bahwa desain menggabungkan FastAPI, kontrak dan problem details ketat, PostgreSQL/TimescaleDB, worker import, EDA, dan replay, SPA React/MUI tujuh layar, serta topologi Docker Compose. Tambahkan bahwa mount artifact read-only `/models` merupakan kontrak integrasi, sedangkan artifact aktual tidak tersedia di checkout.
3. Simpulkan bukti evaluasi terbatas yang positif: EDA kanonis mencatat `2 passed in 2147.53s`, parity runtime `1030.4646068310249s`, isolated full-range worker runtime `989.6441833919962s`, peak RSS `1,251,999,744 bytes` di bawah `2,147,483,648 bytes`, `6,931,792` raw rows, `3,460,865` exact pairs, dan `3,405,332` screened pairs.
4. Simpulkan bahwa test otomatis dan build memberikan bukti terbatas sesuai cakupannya, tetapi E2E memakai mock dan QA manual berstatus REJECT akibat cacat kontrol tanggal serta reason code `not_eligible` yang tidak ditampilkan.
5. Tutup dengan batas klaim: tidak ada kesimpulan tentang superioritas model, inferensi real-time, skalabilitas, keamanan, usability formal, aksesibilitas formal, atau integrasi artifact nyata.

#### 16.1.2 Aturan penulisan Bab V

1. Panjang target 1.000 sampai 1.300 kata.
2. Tidak memuat subbab saran, rekomendasi, rencana masa depan, atau daftar pekerjaan berikutnya.
3. Setiap butir kesimpulan harus dapat ditelusuri ke Bagian 15.2 dan tidak membawa angka baru.

### 16.2 Bukti terverifikasi per bagian Bab V

| Bagian | Bukti primer | Batas |
|---|---|---|
| Kesimpulan 1 dan 2 | E02 sampai E09, E18 | Sebut desain dan implementasi, bukan klaim production-ready. |
| Kesimpulan 3 | E12 | Pertahankan angka dan konteks kanonis. |
| Kesimpulan 4 | E10 sampai E17 | Nyatakan E2E mock serta QA REJECT. |
| Kesimpulan 5 | E02, E03, E14, E15, E18 | Tegaskan batas tanpa menambahkan saran. |

### 16.3 Tabel dan gambar Bab V yang direncanakan

1. Tidak ada tabel atau gambar baru yang diperlukan.
2. Bab V hanya dapat merujuk tabel atau gambar dari Bab IV jika membantu menautkan kesimpulan dengan bukti.

## 17. Rencana berkas 06-daftar-pustaka.md

Daftar pustaka disusun alfabetis, tanpa nomor urut, dan hanya memuat sumber yang benar-benar diacu di Bab I sampai Bab IV. Gaya nama tahun mengikuti pedoman Polines. Jangan menulis DOI jika DOI tidak telah diverifikasi. Untuk kandidat yang berasal dari Consensus, rekam URL Consensus persis sebagai tautan verifikasi, bukan sebagai DOI.

### 17.1 Peta sitasi kandidat

| Kode | Sitasi dalam teks | Fungsi pada skripsi platform | Bab rencana | Tautan verifikasi |
|---|---|---|---|---|
| C01 | Mofidul et al. (2022) | Konteks infrastruktur IIoT terintegrasi, akuisisi, deteksi, dan pemantauan | 2.1, 2.10 | [Consensus](https://consensus.app/papers/details/ea2aadc4e4705364a38be18e4000cc6e/?utm_source=unknown) |
| C02 | Gillespie et al. (2023) | Konteks pemantauan anomali berbasis IoT pada domain transportasi | 2.1, 2.10 | [Consensus](https://consensus.app/papers/details/cdb12ca118fd52d1941e6a441b815135/?utm_source=unknown) |
| C03 | Calderon et al. (2023) | Konteks framework pemantauan dan evaluasi performa platform IoT | 2.4, 2.10 | [Consensus](https://consensus.app/papers/details/697b2574e046597784b8df3213ce69ac/?utm_source=unknown) |
| C04 | Almasi et al. (2023) | Landasan penyusunan kriteria evaluasi dashboard, bukan bukti SUS platform | 2.9 | [Consensus](https://consensus.app/papers/details/7a4cef80335e59c0acd3a13ebfeb5ab9/?utm_source=unknown) |
| C05 | García-Valls et al. (2022) | Proses evaluasi platform IoT pada domain sensitif waktu | 2.5, 2.9 | [Consensus](https://consensus.app/papers/details/134fa9cd5a9455f487d42a5564202949/?utm_source=unknown) |
| C06 | Dineva et al. (2022) | Contoh sistem pemantauan cerdas berbasis data cloud | 2.1, 2.10 | [Consensus](https://consensus.app/papers/details/0800f8dfd5ba508c859aee282f980b6a/?utm_source=unknown) |
| C07 | Choma et al. (2024) | Konteks evaluasi UX aplikasi IoT, bukan bukti UX platform ini | 2.9 | [Consensus](https://consensus.app/papers/details/c60f242b51af580c933038e7240114d2/?utm_source=unknown) |
| C08 | Muñoz et al. (2024) | Konteks anomaly detection untuk quality assurance infrastruktur IoT | 2.7, 2.10 | [Consensus](https://consensus.app/papers/details/8f1b33da0d1e5a4a9b157c28886327c6/?utm_source=unknown) |
| C09 | Zamanzadeh Darban et al. (2025) | Batas konsep deep learning time-series anomaly detection dan pemisahan ownership modeling | 2.2, 2.3 | DOI: `https://doi.org/10.1145/3691338`; [Consensus](https://consensus.app/papers/details/638cea4edb7c5ce886c3332adb6b7371/?utm_source=unknown) |
| C10 | Politeknik Negeri Semarang (2014) | Pedoman struktur, gaya, sitasi, dan Bab V tanpa saran | 1 sampai 5 | `docs/pedoman-penyusunan-tugas-akhir-skripsi-polines-2014.md` |
| C11 | Triyono et al. | Kontrak checkpoint Transformer-AE dan p99.5 sebagai input eksternal beku | 1.1, 1.5, 2.3, 3.3, 4.4 | `/home/reky/Downloads/JOIV_PyTorch_Reconstruction_Validation (1).pdf` |

### 17.2 Metadata kandidat yang harus diverifikasi sebelum daftar final

| Kode | Metadata yang telah disediakan | Verifikasi yang masih diperlukan |
|---|---|---|
| C01 | Mofidul et al. 2022, *Sensors*, “Real-Time Energy Data Acquisition, Anomaly Detection, and Monitoring System: Implementation of a Secured, Robust, and Integrated Global IIoT Infrastructure with Edge and Cloud AI” | Volume, nomor, halaman atau artikel, dan DOI hanya bila tersedia pada sumber sah. |
| C02 | Gillespie et al. 2023, *Sustainability*, “Real-Time Anomaly Detection in Cold Chain Transportation Using IoT Technology” | Metadata bibliografis lengkap. |
| C03 | Calderon et al. 2023, *Information Systems Frontiers*, “Monitoring Framework for the Performance Evaluation of an IoT Platform with Elasticsearch and Apache Kafka” | Metadata bibliografis lengkap. |
| C04 | Almasi et al. 2023, *BioMed Research International*, “Usability Evaluation of Dashboards: A Systematic Literature Review of Tools” | Metadata bibliografis lengkap. |
| C05 | García-Valls et al. 2022, *Sensors*, “An Evaluation Process for IoT Platforms in Time-Sensitive Domains” | Metadata bibliografis lengkap. |
| C06 | Dineva et al. 2022, *Sensors*, “Cloud Data-Driven Intelligent Monitoring System for Interactive Smart Farming” | Metadata bibliografis lengkap. |
| C07 | Choma et al. 2024, “UX evaluation of IoT-based applications for Smart Cities: a rapid systematic review” | Jurnal atau penerbit, volume, nomor, halaman atau artikel. |
| C08 | Muñoz et al. 2024, *Internet of Things*, “Anomaly detection system for data quality assurance in IoT infrastructures based on machine learning” | Metadata bibliografis lengkap. |
| C09 | Zamanzadeh Darban et al. 2025, *ACM Computing Surveys*, “Deep Learning for Time Series Anomaly Detection: A Survey” | Metadata bibliografis lengkap selain DOI yang sudah tersedia. |

## 18. Rencana berkas 07-lampiran.md

### 18.1 Struktur lampiran yang harus ditulis

1. Lampiran A memuat manifest endpoint FastAPI sebanyak 28 endpoint setelah diekspor atau diverifikasi dari OpenAPI pada revisi yang akan diserahkan.
2. Lampiran B memuat ringkasan kontrak data penting, problem details, serta domain waktu corpus dan operasional.
3. Lampiran C memuat topologi Docker Compose dan konfigurasi service yang aman dibagikan tanpa `.env`, secret, atau path pribadi.
4. Lampiran D memuat ringkasan identitas rilis EDA, termasuk source hash, manifest hash, configuration hash, dan algorithm version yang sudah dicatat pada bukti kanonis.
5. Lampiran E memuat log hasil canonical integration EDA yang dipilih, termasuk dua test lulus, jumlah raw rows, runtime, dan peak RSS.
6. Lampiran F memuat ringkasan hasil test backend, frontend, build, dan E2E dengan cap jelas bahwa E2E memakai mock.
7. Lampiran G memuat bukti QA manual berstatus REJECT dan kedua cacat blocker, termasuk gambar asli bila diizinkan.
8. Lampiran H memuat metadata kontrak artefak eksternal yang dapat dibagikan, tanpa menyertakan checkpoint, telemetry mentah, scaler, kredensial, atau path absolut.
9. Lampiran I memuat matriks traceability antara rumusan masalah, tujuan, komponen, bukti, dan kesimpulan.

### 18.2 Bukti dan batas lampiran

| Lampiran | Bukti primer | Larangan |
|---|---|---|
| A | E07 dan OpenAPI yang dibekukan | Jangan menebak endpoint agar jumlahnya menjadi 28. |
| B | E05 dan E06 | Jangan menyertakan data request privat. |
| C | E04 | Jangan menyertakan `.env`, password, atau secret. |
| D dan E | E12 serta `docs/eda-v3-operations.md` | Jangan menyertakan raw CSV atau manifest privat. |
| F | E10 sampai E14 | Jangan menyebut E2E sebagai live integration. |
| G | E15 sampai E17 | Jangan menyembunyikan status REJECT atau blocker. |
| H | E03 dan E18 | Jangan menyertakan artifact model yang tidak tersedia atau membuat checksum palsu. |
| I | Bagian 3 sampai 6 blueprint ini | Jangan menghubungkan kesimpulan dengan bukti modeling yang bukan milik skripsi platform. |

## 19. Rencana evaluasi platform yang harus dipertahankan

| Lapisan evaluasi | Bukti terverifikasi saat ini | Interpretasi yang diizinkan | Interpretasi yang dilarang |
|---|---|---|---|
| Kontrak EDA backend | `28 passed in 0.17s`, 11 sections, 13 eligibility reasons | Kontrak EDA yang direkam telah diuji pada scope tersebut | Semua endpoint atau seluruh sistem bebas cacat |
| Backend ordinary suite | `232 passed`, `2 skipped`, `2 canonical deselected` pada rekaman terisolasi | Regresi backend yang direkam lulus | Jaminan produksi atau cakupan keamanan |
| EDA kanonis | `2 passed in 2147.53s`; parity `1030.4646068310249s`; worker `989.6441833919962s`; RSS `1,251,999,744 bytes`; `6,931,792` raw rows; `3,460,865` exact pairs; `3,405,332` screened pairs | Reproduksibilitas rilis kanonis pada lingkungan bukti | SLA, scalable, real-time, atau hasil universal |
| Kontrak frontend | `13 passed` | Kontrak frontend yang dipilih telah diuji | Usability atau accessibility-compliant |
| Test frontend EDA | `21 test files passed`, `137 tests passed` | Perilaku komponen yang direkam telah diuji | Semua visual browser nyata bebas masalah |
| Build frontend | TypeScript dan Vite build selesai; gzip JavaScript `496.49 kB` | Artefak build dihasilkan pada rekaman | Bundle optimal atau performa halaman terjamin |
| E2E Playwright | Status run terakhir passed, skenario memakai mock | Alur frontend terskenario dapat dijalankan | Backend nyata, worker nyata, atau model artifact nyata terintegrasi |
| QA manual langsung | REJECT dengan dua blocker | Defect ditemukan secara manual dan harus dianalisis | Penerimaan antarmuka atau siap produksi |

## 20. Klaim yang dilarang dalam seluruh naskah

1. Jangan mengklaim penulis merancang, melatih, memilih, membandingkan, atau membuktikan keunggulan Transformer-AE maupun lima model lain.
2. Jangan memasukkan metrik lima model sebagai hasil penelitian platform.
3. Jangan menyebut p99.5 sebagai ambang optimal universal atau sebagai ambang yang dihitung oleh penelitian ini.
4. Jangan menyebut platform real-time, scalable, secure, production-ready, usable, atau accessibility-compliant tanpa bukti baru yang eksplisit.
5. Jangan menyebut EDA sebagai deteksi anomali, ground truth, diagnosis fisik, atau bukti hubungan kausal.
6. Jangan menyebut E2E mock sebagai integrasi end-to-end dengan backend nyata, database nyata, worker nyata, atau artifact nyata.
7. Jangan menyebut validasi checksum artifact atau inferensi artifact-backed berhasil jika artifact aktual masih tidak tersedia di checkout.
8. Jangan menyembunyikan QA manual REJECT, F3-1, atau F3-2.
9. Jangan membuat screenshot, angka performa, hasil pengujian, pengguna, respons SUS, hasil keamanan, maupun bukti CI yang tidak ada.
10. Jangan memodifikasi atau menjadikan `docs/thesis-evidence-map.md` sebagai naskah skripsi platform.

## 21. Status resolusi dan placeholder penulisan final

| ID | Placeholder | Penanggung jawab atau sumber | Dampak bila belum selesai |
|---|---|---|---|
| P01 | Nama, NIM, program studi, jurusan, pembimbing, dan tahun | Data administrasi mahasiswa | Bagian awal tidak dapat difinalkan. |
| P02 | Selesai. Tautan C01 sampai C09 telah dicatat persis dan ditangkap secara berurutan dari Consensus dengan `year_min=2021`. | Bagian 17.1 blueprint ini | Tidak lagi menjadi blocker. |
| P03 | Metadata bibliografis lengkap C01 sampai C09 | Sumber artikel yang diverifikasi | Daftar pustaka belum boleh difinalkan. |
| P04 | Manifest endpoint yang membuktikan jumlah tepat 28 | Snapshot OpenAPI atau inventaris router pada revisi final | Tabel 3.3 dan 4.2 tidak boleh diisi dengan tebakan. |
| P05 | Commit atau tag repositori yang menjadi basis naskah | Revisi source akhir | Reproduksibilitas implementasi tidak lengkap. |
| P06 | Manifest dan artifact model eksternal beserta checksum | Pemasok model eksternal | Tidak boleh mengklaim artifact-backed inference atau checksum validation berhasil. |
| P07 | Keputusan perbaikan atau penerimaan cacat F3-1 dan F3-2 | Siklus perbaikan QA berikutnya | Bab IV harus tetap menyatakan REJECT. |
| P08 | Persetujuan penggunaan screenshot bukti lokal | Pemilik data atau pembimbing | Gunakan placeholder gambar bila tidak disetujui. |
| P09 | Bukti CI, load test, security test, SUS, dan accessibility test formal jika kelak dilakukan | Eksperimen baru yang terdokumentasi | Tetap menjadi keterbatasan dan tidak boleh dihapus dari naskah. |

## 22. Instruksi singkat untuk penulis lanjutan

1. Muat hanya file chapter yang sedang dikerjakan, blueprint ini, dan bukti yang ditautkan untuk section tersebut.
2. Tulis dengan bahasa Indonesia baku, tanpa kata ganti orang, dan gunakan istilah asing secara miring bila belum diserap.
3. Gunakan sitasi nama tahun pada setiap klaim dari literatur. Untuk fakta implementasi, sebutkan artefak bukti lokal di narasi kerja atau lampiran, bukan sebagai sitasi jurnal.
4. Jika bukti belum ada, tulis sebagai keterbatasan atau placeholder. Jangan mengisinya melalui asumsi.
5. Penyusunan draf bab dapat dilanjutkan secara offline dengan placeholder metadata yang eksplisit. Finalisasi `06-daftar-pustaka.md` harus menunggu P03, sedangkan P04 sampai P06 hanya membatasi section yang bergantung langsung pada endpoint, revisi source, atau artifact model tersebut.
