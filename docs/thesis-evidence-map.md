# Peta Bukti Penyusunan Skripsi Jalur Modeling

## Batas Kepemilikan Dua Skripsi

Dokumen ini adalah peta bukti untuk skripsi jalur modeling milik rekan. Skripsi
pengguna memiliki ruang lingkup arsitektur platform, implementasi, integrasi,
antarmuka pengguna, API, manajemen data, pengujian, dan evaluasi platform.

Skripsi jalur modeling memiliki ruang lingkup desain model, pelatihan,
perbandingan model, dan metrik offline. Skripsi platform hanya dapat menyebut
model terpilih serta kontrak antarmukanya sebagai komponen eksternal yang telah
dibekukan untuk kebutuhan integrasi, bukan sebagai bukti atau klaim penelitian
modeling.

## Status dan Hierarki Sumber

Dokumen ini menormalisasi fakta, metode, hasil, dan rujukan dari naskah jurnal
final **“Unsupervised Autoencoders for Anomaly Detection in Bivariate IoT Time
Series”** yang diberikan oleh pengguna pada 31 Juli 2026. Naskah jurnal tersebut
menjadi sumber utama untuk klaim penelitian dan angka hasil.

Artefak eksperimen lama yang tersimpan di repositori tidak boleh dicampurkan
dengan hasil jurnal final apabila jumlah kejadian, ukuran jendela, model,
ambang, atau metriknya berbeda. Secara khusus, angka F1 dari
`backend/anomaly_backend/fixtures/offline_eval/offline_evaluations.json` bukan
angka jurnal final dan tidak digunakan sebagai hasil skripsi.

Pedoman struktur dan gaya berasal dari
`docs/pedoman-penyusunan-tugas-akhir-skripsi-polines-2014.md`.

## Identitas Naskah Jurnal

- Judul: *Unsupervised Autoencoders for Anomaly Detection in Bivariate IoT Time
  Series*.
- Penulis: Liliek Triyono, Suko Tyas Pernanda, Rachmadandy Mahendra Shakti, dan
  Naufal Reky Ardhana.
- Afiliasi: Department of Electrical Engineering, Politeknik Negeri Semarang,
  Semarang, Indonesia.
- Penulis korespondensi: Liliek Triyono (`liliek.triyono@gmail.com`).
- Topik: perbandingan terkontrol lima autoencoder rekonstruksi tanpa pengawasan
  untuk deteksi anomali pada deret waktu IoT bivariat suhu dan kelembapan
  relatif.

## Judul Skripsi Jalur Modeling

**Perbandingan Autoencoder Tanpa Pengawasan untuk Deteksi Anomali pada Deret
Waktu IoT Bivariat**

Judul ini merupakan terjemahan substantif dari judul jurnal dan tidak menambah
ruang lingkup penelitian.

## Rumusan Masalah

1. Seberapa efektif lima varian autoencoder tanpa pengawasan dalam mendeteksi
   kejadian anomali terkontrol pada telemetri IoT bivariat?
2. Algoritma temporal mana yang memberikan keseimbangan precision–recall
   terbaik pada data uji final ketika seluruh model menggunakan kebijakan
   ambang p99,5 yang sama dan dikalibrasi dari skor validasi tanpa injeksi?
3. Seberapa konsisten model yang dipilih berdasarkan validasi melakukan
   generalisasi pada data uji final yang secara kronologis lebih akhir dengan
   evaluasi temporal non-overlapping yang aman terhadap gap?

## Tujuan Penelitian

1. Mengembangkan dan mengevaluasi Conv1D-AE, LSTM-AE, Transformer-AE, GRU-AE,
   dan RNN-AE dalam kerangka rekonstruksi tanpa pengawasan yang sama.
2. Membandingkan kinerja kelima model pada kondisi data, prapemrosesan, ukuran
   jendela, kebijakan ambang, dan unit evaluasi yang dikontrol secara konsisten.
3. Menentukan model dengan keseimbangan precision–recall terbaik pada uji final
   menggunakan F1 berbasis bin temporal non-overlapping sebagai metrik utama.
4. Menganalisis perbedaan antara fidelity rekonstruksi, diskriminasi skor lintas
   ambang, dan kinerja deteksi pada ambang operasi p99,5.
5. Menganalisis perubahan kinerja dari validasi ke uji final sebagai indikator
   generalisasi temporal.

## Manfaat Penelitian

### Manfaat teoretis

- Menambah bukti empiris mengenai pengaruh pilihan arsitektur temporal terhadap
  deteksi anomali rekonstruksi pada data IoT multivariat.
- Menunjukkan bahwa peringkat model bergantung pada metrik dan ambang operasi,
  sehingga satu metrik tidak cukup untuk menyatakan superioritas universal.
- Menyediakan contoh protokol evaluasi yang memisahkan pelatihan bobot,
  pemilihan checkpoint, kalibrasi ambang, validasi berlabel sintetis, dan uji
  final kronologis.

### Manfaat praktis

- Menyediakan dasar pemilihan model untuk sistem awareness terhadap pola tidak
  biasa pada telemetri suhu dan kelembapan.
- Menyediakan prosedur prapemrosesan yang deterministik dan memperhatikan
  leakage serta gap akuisisi.
- Menyediakan interpretasi operasional trade-off precision, recall, false
  positive, dan false negative untuk lima model.

## Kontribusi Penelitian

1. Perbandingan lima algoritma temporal dalam kerangka autoencoder tanpa
   pengawasan yang sama.
2. Pipeline eksperimen yang memperhatikan leakage dan memisahkan pembelajaran
   bobot, validasi berinjeksi, serta evaluasi final kronologis.
3. Kebijakan ambang p99,5 bersama dengan evaluasi temporal non-overlapping yang
   aman terhadap gap.
4. Analisis validasi-ke-uji yang membedakan fidelity rekonstruksi,
   diskriminasi tanpa ambang, dan kinerja deteksi berambang.

## Batasan Penelitian

1. Data berasal dari satu instalasi IoT anonim dan hanya mencakup dua kanal.
2. Data historis tidak mempunyai label anomali alami.
3. Istilah “tanpa injeksi” hanya berarti tidak ditambahkan anomali sintetis;
   kondisi tersebut tidak menjamin setiap observasi benar-benar normal.
4. Ground truth pengujian dibentuk melalui tujuh keluarga anomali sintetis dan
   tidak membuktikan prevalensi atau kausalitas anomali nyata.
5. Setiap model dilatih dengan satu seed sehingga variasi antarpelatihan belum
   diketahui.
6. Ambang p99,5 bergantung pada kestabilan distribusi skor validasi tanpa
   injeksi.
7. Ukuran bin evaluasi bergantung pada jumlah kejadian injeksi dan tidak dapat
   langsung digunakan sebagai aturan agregasi deteksi online.
8. Penelitian tidak melakukan ablation study, perbandingan biaya komputasi, atau
   validasi lintas dataset.
9. Model hanya menghasilkan skor anomali dan tidak mengklasifikasikan keluarga
   anomali atau penyebab fisiknya.

## Data Penelitian

### Sumber dan kerahasiaan

- Dataset proprietary disediakan oleh perusahaan penulis dan berasal dari satu
  instalasi IoT yang dianonimkan.
- Nama perusahaan, identitas perangkat, lokasi instalasi, tanggal observasi
  persis, telemetry mentah, dan batas min–max hasil fitting dirahasiakan karena
  bersifat operasional.
- Informasi yang dibuka: struktur masalah machine learning, variabel, jumlah
  observasi, prosedur pemrosesan, konfigurasi model, dan hasil agregat.

### Variabel

- `suhu`: temperatur.
- `rh`: kelembapan relatif.
- Kedua kanal dimodelkan secara bersama agar model mempelajari dinamika dalam
  kanal dan kovariasi suhu–kelembapan.

### Ukuran korpus

| Bagian data | Jumlah observasi berpasangan | Proporsi target |
|---|---:|---:|
| Pelatihan | 491.785 | 70% |
| Validasi | 105.425 | 15% |
| Uji final | 105.767 | 15% |
| **Total setelah prapemrosesan** | **702.977** | **100%** |

Pembagian dilakukan berdasarkan durasi kalender secara kronologis, bukan dengan
pengacakan timestamp.

## Prapemrosesan Data

Prapemrosesan bersifat deterministik dan sama bagi seluruh model.

1. **Penyelarasan kanal.** Pengukuran format panjang distandardisasi menurut
   nama kanal, diurutkan berdasarkan timestamp, dan dipivot menjadi satu baris
   pasangan suhu–kelembapan.
2. **Resolusi duplikat.** Sebanyak 78 key duplikat identik mempertahankan satu
   observasi. Audit menemukan 474 key duplikat konflik pada 271 timestamp;
   seluruh 271 pasangan timestamp tersebut dihapus agar konflik tidak
   diselesaikan secara arbitrer.
3. **Penyaringan validitas.** Baris dengan pasangan tidak lengkap, nilai tidak
   positif, nilai sentinel/korup ≥200, kelembapan relatif >100%, atau suhu >50 °C
   dihapus. Satu interval pendek yang dikonfirmasi korup juga dihapus.
4. **Tanpa synthetic smoothing.** Data kanonik tidak di-resample, tidak
   diinterpolasi, dan tidak difilter menggunakan aturan statistical outlier.
5. **Pembagian kronologis.** Timeline terfilter dibagi menjadi 70% pelatihan,
   15% validasi, dan 15% uji final berdasarkan waktu.
6. **Train-only scaling.** Min–max scaling terpisah untuk setiap kanal di-fit
   hanya pada data pelatihan, lalu diterapkan tanpa perubahan pada validasi dan
   uji.
7. **Gap-aware segmentation.** Selisih waktu >60 detik memulai segmen baru.
   Jendela model dan bin evaluasi tidak boleh melintasi gap.
8. **Windowing.** Semua model menggunakan jendela sepuluh observasi berturut
   dengan stride satu.

## Pembuatan Data Evaluasi Berinjeksi

Data asli tidak memiliki label kelas anomali. Anomali terkontrol hanya
ditambahkan pada salinan validasi dan uji final. Versi tanpa injeksi tetap
dipertahankan untuk checkpoint monitoring, perhitungan ambang persentil, dan
pengukuran rekonstruksi.

| Salinan | Jumlah kejadian | Timestamp berlabel | Perkiraan proporsi timeline |
|---|---:|---:|---:|
| Validasi berinjeksi | 207 | 10.542 | ±10% |
| Uji final berinjeksi | 210 | 10.577 | ±10% |

Tujuh keluarga kejadian:

1. **Spike:** excursion singkat dan terbatas dari pola lokal.
2. **Bias:** offset sementara dari baseline lokal.
3. **Drift:** perubahan terarah terbatas selama interval kejadian.
4. **Erratic:** interval pembacaan dengan variasi tinggi yang tidak teratur.
5. **Stuck:** interval datar atau hampir konstan.
6. **Data loss:** interval tanpa sinyal atau menyerupai dropout.
7. **Garbage:** nilai korup atau susunan nilai yang tidak masuk akal.

## Prinsip Autoencoder

Untuk jendela bivariat $X_w \in \mathbb{R}^{L\times C}$ dengan $L=10$ dan
$C=2$, encoder $f_\theta$ menghasilkan representasi laten:

$$
z_w = f_\theta(X_w).
$$

Decoder $g_\phi$ menghasilkan rekonstruksi dengan bentuk yang sama:

$$
\hat{X}_w = g_\phi(z_w).
$$

Bobot dipelajari dengan meminimalkan mean squared reconstruction error pada
jendela pelatihan tanpa injeksi:

$$
\mathcal{L}_{\mathrm{MSE}} = \frac{1}{LC}
\sum_{t=1}^{L}\sum_{c=1}^{C}
\left(X_{w,t,c}-\hat{X}_{w,t,c}\right)^2.
$$

Asumsinya, pola berulang pada data pelatihan akan direkonstruksi lebih baik
daripada pola yang tidak dikenal. Reconstruction error digunakan sebagai skor
anomali, tetapi tidak menjelaskan penyebab fisik ketidaklaziman.

## Model yang Dibandingkan

| Model | Jalur encoder–decoder | Konfigurasi utama |
|---|---|---|
| Conv1D-AE | Conv1D → transposed Conv1D | latent channels=16; internal pad/crop |
| RNN-AE | Tanh RNN → latent → RNN | hidden=32; latent=8; layers=2; dropout=0,1 |
| LSTM-AE | LSTM → latent → LSTM | hidden=32; latent=8; layers=2; dropout=0,1 |
| GRU-AE | GRU → latent → GRU | hidden=32; latent=8; layers=2; dropout=0,1 |
| Transformer-AE | self-attention encoder → decoder | d_model=32; heads=4; encoder+decoder layers=2+2; FF=64; dropout=0,1 |

Kelima implementasi adalah baseline terkontrol yang terinspirasi literatur,
bukan reproduksi literal sistem dalam artikel rujukan.

## Kontrol Pelatihan

- Framework: PyTorch.
- Seed: tetap, satu seed per model.
- Batch size: 512.
- Epoch maksimum: 100.
- Optimizer: Adam.
- Learning rate: $5\times10^{-4}$.
- Weight decay: 0.
- Early stopping patience: 8 epoch.
- Batch pelatihan diacak, tetapi urutan observasi di dalam jendela dipertahankan.
- Checkpoint yang disimpan adalah epoch dengan MSE validasi tanpa injeksi
  terendah.
- Checkpoint Transformer-AE terpilih pada epoch 17.

## Prosedur Eksperimen

1. **Pelatihan bobot.** Autoencoder belajar dari jendela pelatihan tanpa injeksi
   dengan objective MSE. Label sintetis tidak digunakan.
2. **Pemilihan checkpoint.** Setelah setiap epoch, MSE diukur pada validasi
   tanpa injeksi yang lebih akhir secara kronologis. Checkpoint MSE terendah
   disimpan.
3. **Konstruksi kandidat ambang.** Mean+1SD, p99,0, p99,25, p99,5, dan p99,75
   dihitung dari skor timestamp validasi tanpa injeksi. Youden's J dihitung
   terpisah dari skor dan label validasi berinjeksi.
4. **Validasi berinjeksi dan pemilihan kebijakan.** Kandidat dibandingkan pada
   salinan validasi berinjeksi. Kebijakan p99,5 dipilih untuk seluruh model.
   Label validasi memengaruhi pemilihan konfigurasi dan kebijakan, tetapi tidak
   memengaruhi bobot atau nilai numerik persentil p99,5.
5. **Evaluasi final.** Checkpoint dan ambang p99,5 yang sudah dibekukan
   diterapkan pada data uji final tanpa injeksi dan berinjeksi. Label uji tidak
   dipakai untuk keputusan pelatihan atau seleksi.

## Skor Rekonstruksi dan Ambang

Satu skor MSE dihasilkan untuk setiap jendela yang saling overlap. Karena satu
timestamp dapat berada pada hingga sepuluh jendela stride-one, seluruh skor
jendela yang mencakup timestamp tersebut dirata-ratakan menjadi skor timestamp.

Ambang operasi model:

$$
\tau=Q_{0,995}\left(\{e_t^{\text{validasi tanpa injeksi}}\}\right).
$$

Timestamp diprediksi anomali ketika $e_t>\tau$. Pada distribusi validasi yang
dipakai menghitungnya, p99,5 menargetkan exceedance empiris sekitar 0,5%, tetapi
tidak menjamin alert rate 0,5% pada data masa depan.

Youden's J diperlakukan sebagai oracle diagnostic berlabel dan tidak digunakan
sebagai ambang operasi final.

## Metrik Evaluasi

### Rekonstruksi tanpa injeksi

- MSE.
- RMSE.
- MAE.

Metrik tersebut mengukur fidelity rekonstruksi pada skala normalisasi dan bukan
skor klasifikasi anomali.

### Diskriminasi validasi tanpa ambang

- AUC-ROC.
- AUC-PR trapezoidal.

AUC dihitung dari label timestamp validasi berinjeksi dan skor kontinu. AUC uji
final tidak dihitung sehingga tidak boleh dilaporkan.

### Evaluasi bin non-overlapping aman-gap

Ukuran bin:

$$
B=\operatorname{round}\left(0,10\frac{N}{E}\right),
$$

dengan $N$ jumlah timestamp dan $E$ jumlah kejadian injeksi. Alignment dimulai
ulang pada setiap segmen aman-gap. Bin actual-positive jika mengandung minimal
satu timestamp injeksi, dan predicted-positive jika mengandung minimal satu
timestamp dengan skor di atas ambang. Bin yang tidak memiliki cakupan skor
lengkap dikeluarkan.

- Validasi: 51 timestamp per bin.
- Uji final: 50 timestamp per bin.

Nama metrik: **Freeman-inspired gap-safe non-overlapping evaluation-bin F1**.
Rumus ukuran terinspirasi Freeman et al.; gap restarting, disjoint alignment,
overlap-mean timestamp scoring, dan kalibrasi p99,5 adalah adaptasi penelitian.

$$
\mathrm{Precision}=\frac{TP}{TP+FP},\qquad
\mathrm{Recall}=\frac{TP}{TP+FN}.
$$

$$
F1=\frac{2\cdot\mathrm{Precision}\cdot\mathrm{Recall}}
{\mathrm{Precision}+\mathrm{Recall}}.
$$

$$
\mathrm{Accuracy}=\frac{TP+TN}{TP+TN+FP+FN}.
$$

Perhitungan diperiksa secara manual serta menggunakan scikit-learn dan
TorchMetrics.

## Batas Evaluasi Offline

Bin evaluasi adalah unit penelitian, bukan jendela deteksi online, karena
ukurannya bergantung pada jumlah kejadian injeksi yang diketahui. Detektor
online memerlukan aturan agregasi kejadian, latency, dan false-alert control
yang ditentukan secara independen. Properti online tersebut tidak dievaluasi.

## Hasil Validasi pada P99,5

Validasi menggunakan bin non-overlapping 51 timestamp.

| Model | Accuracy | Precision | Recall | F1 | TN | FP | FN | TP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Conv1D-AE | 0,916 | 0,828 | 0,725 | 0,773684 | 1.605 | 61 | 111 | 294 |
| LSTM-AE | 0,910 | **0,878** | 0,627 | 0,731988 | **1.631** | **35** | 151 | 254 |
| Transformer-AE | **0,925** | 0,811 | **0,807** | **0,809406** | 1.590 | 76 | **78** | **327** |
| GRU-AE | 0,923 | 0,836 | 0,758 | 0,795337 | 1.606 | 60 | 98 | 307 |
| RNN-AE | 0,919 | 0,850 | 0,713 | 0,775839 | 1.615 | 51 | 116 | 289 |

Transformer-AE menghasilkan F1 dan recall validasi tertinggi. LSTM-AE memiliki
precision tertinggi dan FP paling sedikit, tetapi recall paling rendah.

## Diskriminasi Timestamp Validasi

| Model | AUC-ROC | AUC-PR |
|---|---:|---:|
| Conv1D-AE | 0,793324 | 0,578328 |
| LSTM-AE | 0,818780 | 0,579843 |
| Transformer-AE | 0,803075 | 0,595453 |
| GRU-AE | 0,779989 | 0,573435 |
| RNN-AE | **0,830417** | **0,600993** |

RNN-AE memimpin kedua AUC, sedangkan Transformer-AE memimpin F1 pada ambang
p99,5. AUC dan F1 menjawab pertanyaan evaluasi yang berbeda.

## Rekonstruksi Uji Final Tanpa Injeksi

| Model | MSE | RMSE | MAE |
|---|---:|---:|---:|
| Conv1D-AE | 0,00004683 | 0,006843 | **0,002889** |
| LSTM-AE | 0,00006931 | 0,008326 | 0,003737 |
| Transformer-AE | **0,00003356** | **0,005793** | 0,003827 |
| GRU-AE | 0,00007549 | 0,008688 | 0,004588 |
| RNN-AE | 0,00008242 | 0,009078 | 0,004294 |

Transformer-AE mempunyai MSE dan RMSE terendah. Conv1D-AE mempunyai MAE
terendah. Error rekonstruksi rendah tidak otomatis menjamin F1 tertinggi.

## Deteksi Uji Final Berinjeksi

Uji final berisi 419 bin actual-positive dari total 2.125 bin.

| Model | Accuracy | Precision | Recall | F1 | TN | FP | FN | TP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Conv1D-AE | 0,908235 | 0,829 | 0,675 | 0,744737 | 1.648 | 58 | 136 | 283 |
| LSTM-AE | 0,891765 | **0,852** | 0,551 | 0,669565 | **1.666** | **40** | 188 | 231 |
| Transformer-AE | **0,929412** | 0,845758 | **0,785203** | **0,814356** | 1.646 | 60 | **90** | **329** |
| GRU-AE | 0,907294 | 0,803 | 0,704 | 0,750636 | 1.634 | 72 | 124 | 295 |
| RNN-AE | 0,905412 | 0,815 | 0,673 | 0,737255 | 1.642 | 64 | 137 | 282 |

Peringkat F1 uji final:

1. Transformer-AE: 0,814356.
2. GRU-AE: 0,750636.
3. Conv1D-AE: 0,744737.
4. RNN-AE: 0,737255.
5. LSTM-AE: 0,669565.

Transformer-AE mendeteksi 329 dari 419 bin positif dan melewatkan 90 bin.
LSTM-AE merupakan model paling konservatif: precision tertinggi dan FP paling
sedikit, tetapi FN paling banyak dan recall terendah.

## Generalisasi Validasi ke Uji Final

| Model | F1 Validasi | F1 Uji Final | Selisih |
|---|---:|---:|---:|
| Conv1D-AE | 0,773684 | 0,744737 | -0,028947 |
| LSTM-AE | 0,731988 | 0,669565 | -0,062423 |
| Transformer-AE | 0,809406 | 0,814356 | **+0,004950** |
| GRU-AE | 0,795337 | 0,750636 | -0,044701 |
| RNN-AE | 0,775839 | 0,737255 | -0,038584 |

Transformer-AE satu-satunya model yang F1-nya meningkat sedikit pada uji final.

Alert rate timestamp pada uji final tanpa injeksi:

| Model | Alert rate |
|---|---:|
| Conv1D-AE | 0,91% |
| LSTM-AE | 0,77% |
| Transformer-AE | 0,63% |
| GRU-AE | 1,11% |
| RNN-AE | 1,41% |

Nilai tersebut berbeda dari target exceedance ±0,5% pada distribusi validasi,
menunjukkan bahwa persentil validasi tidak menjamin alert fraction yang sama
pada split lebih akhir.

## Interpretasi yang Diizinkan

- Transformer-AE adalah model terkuat **di bawah protokol eksperimen tetap**
  karena memperoleh F1 uji final tertinggi.
- Hasil tidak membuktikan bahwa Transformer secara universal lebih baik.
- RNN-AE terbaik untuk ranking skor lintas ambang pada validasi berdasarkan AUC.
- LSTM-AE paling presisi tetapi paling tidak sensitif pada uji final.
- Kekuatan model bergantung pada tujuan evaluasi, metrik, ambang, data, dan unit
  temporal.
- Eksperimen tidak mengisolasi mekanisme arsitektur sehingga F1 Transformer-AE
  tidak boleh semata-mata diklaim akibat self-attention.
- Perbandingan numerik langsung dengan artikel rujukan tidak sah karena dataset,
  label, ambang, dan unit evaluasinya berbeda.

## Daftar Gambar yang Harus Disediakan

1. **Gambar 4.1:** Profil radar lima model yang menggabungkan accuracy,
   precision, recall, dan F1 uji final dengan AUC-ROC dan AUC-PR validasi; tanpa
   composite score.
2. **Gambar 4.2:** Riwayat loss pelatihan dan validasi Transformer-AE dengan
   checkpoint terpilih pada epoch 17.
3. **Gambar 4.3:** Rekonstruksi representatif Transformer-AE pada data uji final
   tanpa injeksi selama 200 jendela overlap.
4. **Gambar 4.4:** Rekonstruksi kejadian representatif Transformer-AE untuk bias,
   data loss, drift, erratic, garbage, spike, dan stuck.
5. **Gambar 4.5:** Distribusi skor timestamp uji final Transformer-AE dengan
   ambang p99,5 yang dibekukan dan confusion matrix bin 50 timestamp.

Gambar belum tersedia sebagai berkas terpisah di workspace. Skripsi harus
memakai placeholder dan instruksi penggantian, bukan menciptakan gambar palsu.

## Kesimpulan Berbasis Bukti

1. Kelima algoritma dapat digunakan sebagai komponen temporal dalam kerangka
   autoencoder rekonstruksi tanpa pengawasan untuk telemetri IoT bivariat.
2. Transformer-AE memberi keseimbangan precision–recall uji final terbaik pada
   kebijakan p99,5 dan evaluasi bin aman-gap.
3. Hasil model bergantung pada metrik: RNN-AE memimpin AUC validasi, LSTM-AE
   memimpin precision uji final, dan Transformer-AE memimpin F1 uji final.
4. Generalisasi temporal tidak seragam. Empat model mengalami penurunan F1,
   sementara Transformer-AE meningkat 0,004950.
5. Kesimpulan dibatasi pada satu dataset anonim, dua kanal, satu seed, anomali
   sintetis, dan protokol evaluasi offline.

## Saran/Future Work dari Jurnal

Pedoman Polines menyatakan Bab V cukup berisi kesimpulan tanpa saran. Rencana
lanjutan berikut dapat ditempatkan pada bagian keterbatasan Bab IV atau catatan
setelah kesimpulan jika jurusan mengizinkan:

- multiple training seeds;
- dataset tambahan;
- architecture ablation;
- perbandingan computational cost;
- alternatif temporal metrics;
- aturan agregasi kejadian dan false-alert control untuk detektor online.

## Daftar Pustaka Sumber Jurnal

Urutan berikut mempertahankan identitas [1]–[48] dari jurnal. Pada naskah
skripsi, sitasi dapat diubah menjadi gaya nama–tahun sesuai pedoman Polines,
sedangkan daftar pustaka disusun alfabetis dan tidak diberi nomor.

1. Pang, G., Shen, C., Cao, L., dan van den Hengel, A. 2021. “Deep learning for
   anomaly detection: A review”. *ACM Computing Surveys*. 54(2): 1–38.
   https://doi.org/10.1145/3439950.
2. Blázquez-García, A., Conde, A., Mori, U., dan Lozano, J. A. 2022. “A review
   on outlier/anomaly detection in time series data”. *ACM Computing Surveys*.
   54(3): 1–33. https://doi.org/10.1145/3444690.
3. Zamanzadeh Darban, Z., Webb, G. I., Pan, S., Aggarwal, C., dan Salehi, M.
   2025. “Deep learning for time series anomaly detection: A survey”. *ACM
   Computing Surveys*. 57(1), artikel 15: 1–42.
   https://doi.org/10.1145/3691338.
4. Yahya, M. A., Moya, A. R., dan Ventura, S. 2025. “Deep learning for
   multivariate time series anomaly detection: An evaluation of
   reconstruction-based methods”. *Artificial Intelligence Review*. 58,
   artikel 400. https://doi.org/10.1007/s10462-025-11401-9.
5. Sayyaf, M. I., Pascacio, P., Zhu, N., dan Renaudin, V. 2025. “Time-series
   anomaly detection for sensor data: Models, metrics, and methodologies—A
   review”. *IEEE Sensors Journal*. 25(24): 43603–43619.
   https://doi.org/10.1109/JSEN.2025.3616395.
6. Sgueglia, A., Di Sorbo, A., Visaggio, C. A., dan Canfora, G. 2022. “A
   systematic literature review of IoT time series anomaly detection
   solutions”. *Future Generation Computer Systems*. 134: 170–186.
   https://doi.org/10.1016/j.future.2022.04.005.
7. Belay, M. A., Blakseth, S. S., Rasheed, A., dan Rossi, P. S. 2023.
   “Unsupervised anomaly detection for IoT-based multivariate time series:
   Existing solutions, performance analysis and future directions”. *Sensors*.
   23(5), artikel 2844. https://doi.org/10.3390/s23052844.
8. Schmidl, S., Wenig, P., dan Papenbrock, T. 2022. “Anomaly detection in time
   series: A comprehensive evaluation”. *Proceedings of the VLDB Endowment*.
   15(9): 1779–1797. https://doi.org/10.14778/3538598.3538602.
9. Garg, A., Zhang, W., Samaran, J., Savitha, R., dan Foo, C.-S. 2022. “An
   evaluation of anomaly detection and diagnosis in multivariate time series”.
   *IEEE Transactions on Neural Networks and Learning Systems*.
   https://doi.org/10.1109/TNNLS.2021.3105827.
10. Kim, S., Choi, K., Choi, H.-S., Lee, B., dan Yoon, S. 2022. “Towards a
    rigorous evaluation of time-series anomaly detection”. *Proceedings of the
    AAAI Conference on Artificial Intelligence*. 36(7): 7194–7201.
    https://doi.org/10.1609/aaai.v36i7.20680.
11. Huet, A., Navarro, J. M., dan Rossi, D. 2022. “Local evaluation of time
    series anomaly detection algorithms”. *Proceedings of the 28th ACM SIGKDD
    Conference on Knowledge Discovery and Data Mining*: 635–645.
    https://doi.org/10.1145/3534678.3539339.
12. Sørbø, S. dan Ruocco, M. 2024. “Navigating the metric maze: A taxonomy of
    evaluation metrics for anomaly detection in time series”. *Data Mining and
    Knowledge Discovery*. 38: 1027–1068.
    https://doi.org/10.1007/s10618-023-00988-8.
13. Paparrizos, J., Boniol, P., Palpanas, T., Tsay, R. S., Elmore, A., dan
    Franklin, M. J. 2022. “Volume under the surface: A new accuracy evaluation
    measure for time-series anomaly detection”. *Proceedings of the VLDB
    Endowment*. 15(11): 2774–2787.
    https://doi.org/10.14778/3551793.3551830.
14. Boniol, P. et al. 2025. “VUS: Effective and efficient accuracy measures for
    time-series anomaly detection”. *The VLDB Journal*. 34(3).
    https://doi.org/10.1007/s00778-025-00907-x.
15. Tatbul, N., Lee, T. J., Zdonik, S., Alam, M., dan Gottschlich, J. 2018.
    “Precision and recall for time series”. *Advances in Neural Information
    Processing Systems*. 31.
16. Freeman, C., Merriman, J., Beaver, I., dan Mueen, A. 2021. “Experimental
    comparison and survey of twelve time series anomaly detection algorithms”.
    *Journal of Artificial Intelligence Research*. 72: 849–899.
    https://doi.org/10.1613/jair.1.12698.
17. Audibert, J., Michiardi, P., Guyard, F., Marti, S., dan Zuluaga, M. A. 2020.
    “USAD: Unsupervised anomaly detection on multivariate time series”.
    *Proceedings of the 26th ACM SIGKDD International Conference on Knowledge
    Discovery and Data Mining*: 3395–3404.
    https://doi.org/10.1145/3394486.3403392.
18. Malhotra, P., Ramakrishnan, A., Anand, G., Vig, L., Agarwal, P., dan Shroff,
    G. 2016. “LSTM-based encoder-decoder for multi-sensor anomaly detection”.
    *arXiv:1607.00148*.
19. Wei, Y., Jang-Jaccard, J., Xu, W., Sabrina, F., Camtepe, S., dan Boulic, M.
    2023. “LSTM-autoencoder-based anomaly detection for indoor air quality
    time-series data”. *IEEE Sensors Journal*. 23(4): 3787–3800.
    https://doi.org/10.1109/JSEN.2022.3230361.
20. Zhang, C. et al. 2019. “A deep neural network for unsupervised anomaly
    detection and diagnosis in multivariate time series data”. *Proceedings of
    the AAAI Conference on Artificial Intelligence*. 33: 1409–1416.
    https://doi.org/10.1609/aaai.v33i01.33011409.
21. Zhang, Y., Chen, Y., Wang, J., dan Pan, Z. 2023. “Unsupervised deep anomaly
    detection for multi-sensor time-series signals”. *IEEE Transactions on
    Knowledge and Data Engineering*. 35(2): 2118–2132.
    https://doi.org/10.1109/TKDE.2021.3102110.
22. Tayeh, T., Aburakhia, S., Myers, R., dan Shami, A. 2022. “An
    attention-based ConvLSTM autoencoder with dynamic thresholding for
    unsupervised anomaly detection in multivariate time series”. *Machine
    Learning and Knowledge Extraction*. 4: 350–370.
    https://doi.org/10.3390/make4020015.
23. Tian, R., Liboni, L., dan Capretz, M. 2022. “Anomaly detection with
    convolutional autoencoder for predictive maintenance”. *2022 9th
    International Conference on Soft Computing & Machine Intelligence*.
    https://doi.org/10.1109/ISCMI56532.2022.10068441.
24. Chen, H., Li, X., dan Liu, W. 2024. “Multivariate time series anomaly
    detection by fusion of deep convolution residual autoencoding
    reconstruction model and ConvLSTM forecasting model”. *Computers &
    Security*. 137, artikel 103581.
    https://doi.org/10.1016/j.cose.2023.103581.
25. Fan, J., Liu, Z., Wu, H., Wu, J., Si, Z., Hao, P., dan Luan, T. H. 2023.
    “LUAD: A lightweight unsupervised anomaly detection scheme for multivariate
    time series data”. *Neurocomputing*. 557, artikel 126644.
    https://doi.org/10.1016/j.neucom.2023.126644.
26. Tuli, S., Casale, G., dan Jennings, N. R. 2022. “TranAD: Deep Transformer
    networks for anomaly detection in multivariate time series data”.
    *Proceedings of the VLDB Endowment*. 15(6): 1201–1214.
    https://doi.org/10.14778/3514061.3514067.
27. Vaswani, A. et al. 2017. “Attention is all you need”. *Advances in Neural
    Information Processing Systems*. 30: 5998–6008.
28. Xu, J., Wu, H., Wang, J., dan Long, M. 2022. “Anomaly Transformer: Time
    series anomaly detection with association discrepancy”. *International
    Conference on Learning Representations*.
29. Lai, K.-H., Zha, D., Xu, J., Zhao, Y., Wang, G., dan Hu, X. 2021.
    “Revisiting time series outlier detection: Definitions and benchmarks”.
    *Advances in Neural Information Processing Systems: Datasets and Benchmarks
    Track*. 34.
30. Wenig, P., Schmidl, S., dan Papenbrock, T. 2024. “Anomaly detectors for
    multivariate time series: The proof of the pudding is in the eating”. *2024
    IEEE 40th International Conference on Data Engineering Workshops*.
    https://doi.org/10.1109/ICDEW61823.2024.00018.
31. Bhattacharya, D., Mukherjee, S., Kamanchi, C., Ekambaram, V., Jati, A., dan
    Dayama, P. 2025. “Towards unbiased evaluation of time-series anomaly
    detector”. *2025 IEEE International Conference on Acoustics, Speech and
    Signal Processing*. https://doi.org/10.1109/ICASSP49660.2025.10890568.
32. Ghorbani, R., Reinders, M. J. T., dan Tax, D. M. J. 2024. “PATE:
    Proximity-aware time series anomaly evaluation”. *Proceedings of the 30th
    ACM SIGKDD Conference on Knowledge Discovery and Data Mining*.
    https://doi.org/10.1145/3637528.3671971.
33. Paszke, A. et al. 2019. “PyTorch: An imperative style, high-performance
    deep learning library”. *Advances in Neural Information Processing
    Systems*. 32.
34. Pedregosa, F. et al. 2011. “Scikit-learn: Machine learning in Python”.
    *Journal of Machine Learning Research*. 12: 2825–2830.
35. Detlefsen, N. S. et al. 2022. “TorchMetrics—Measuring reproducibility in
    PyTorch”. *Journal of Open Source Software*. 7(70), artikel 4101.
    https://doi.org/10.21105/joss.04101.
36. Gorman, M., Ding, X., Maguire, L., dan Coyle, D. 2023. “Anomaly detection
    in batch manufacturing processes using localized reconstruction errors from
    1-D convolutional autoencoders”. *IEEE Transactions on Semiconductor
    Manufacturing*. 36(1): 147–150.
    https://doi.org/10.1109/TSM.2022.3216032.
37. Gong, X., Liao, S., Hu, F., Hu, X., dan Liu, C. 2022. “Autoencoder-based
    anomaly detection for time series data in complex systems”. *2022 IEEE Asia
    Pacific Conference on Circuits and Systems*: 428–433.
    https://doi.org/10.1109/APCCAS55924.2022.10090260.
38. Delibasoglu, I. dan Heintz, F. 2024. “Time series anomaly detection
    leveraging MSE feedback with AutoEncoder and RNN”. *31st International
    Symposium on Temporal Representation and Reasoning*. LIPIcs 318: 17:1–17:12.
    https://doi.org/10.4230/LIPIcs.TIME.2024.17.
39. Fu, S., Gao, X., Li, B., Zhai, F., Lu, J., Xue, B., Yu, J., dan Xiao, C.
    2024. “Multivariate time series anomaly detection via separation,
    decomposition, and dual Transformer-based autoencoder”. *Applied Soft
    Computing*. 159, artikel 111671.
    https://doi.org/10.1016/j.asoc.2024.111671.
40. Rahmani, J., Daneshgadeh Çakmakçı, S., Detken, K. O., dan Sikora, A. 2026.
    “An operational hybrid SIEM framework for OT anomaly detection”. *Sensors*.
    26(10), artikel 3155. https://doi.org/10.3390/s26103155.
41. Dang, T.-B., Le, D.-T., Kim, M., dan Choo, H. 2022. “A general model for
    long-short term anomaly generation in sensory data”. *2022 16th
    International Conference on Ubiquitous Information Management and
    Communication*: 1–5. https://doi.org/10.1109/IMCOM53663.2022.9721783.
42. Lee, J. dan Moon, J. 2025. “Platform for labeling based on unsupervised time
    series data anomaly detection”. *2025 IEEE/IEIE International Conference on
    Consumer Electronics-Asia*.
    https://doi.org/10.1109/ICCE-Asia67487.2025.11263526.
43. Abououf, M., Mizouni, R., Singh, S., Otrok, H., dan Damiani, E. 2022.
    “Self-supervised online and lightweight anomaly and event detection for IoT
    devices”. *IEEE Internet of Things Journal*. 9(24): 25285–25299.
    https://doi.org/10.1109/JIOT.2022.3196049.
44. Hermansa, M. et al. 2022. “Sensor-based predictive maintenance with
    reduction of false alarms—A case study in heavy industry”. *Sensors*. 22(1),
    artikel 226. https://doi.org/10.3390/s22010226.
45. Kingma, D. P. dan Ba, J. 2015. “Adam: A method for stochastic
    optimization”. *International Conference on Learning Representations*.
46. Bergmeir, C. dan Benítez, J. M. 2012. “On the use of cross-validation for
    time series predictor evaluation”. *Information Sciences*. 191: 192–213.
    https://doi.org/10.1016/j.ins.2011.12.028.
47. Davis, J. dan Goadrich, M. 2006. “The relationship between
    precision-recall and ROC curves”. *Proceedings of the 23rd International
    Conference on Machine Learning*: 233–240.
    https://doi.org/10.1145/1143844.1143874.
48. Zhou, H., Chung, S., Waqar, M. M., et al. 2025. “Unsupervised anomaly
    detection with continuous-time model for pig farm environmental data”.
    *Agriculture*. 15(13), artikel 1419.
    https://doi.org/10.3390/agriculture15131419.
