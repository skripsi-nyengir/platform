# Desain Integrasi Telemetri Langsung

**Tanggal:** 30 Juli 2026  
**Status:** kontrak arsitektur direvisi dan siap untuk perencanaan implementasi  
**Konteks:** demo sidang skripsi untuk perangkat tunggal `b02f3872-ruang-produksi`

Dokumen ini adalah sumber keputusan tunggal untuk integrasi telemetri langsung. Nilai broker, kredensial, dan topik aktual adalah konfigurasi per deployment, bukan keputusan arsitektur yang belum selesai. Tidak ada kode yang diubah oleh dokumen ini.

## 1. Ruang lingkup dan non-goals

Ruang lingkupnya adalah menerima pembacaan sensor dari MQTT, menyimpannya dalam PostgreSQL dengan Timescale pada database yang sama dengan platform saat ini, menjalankan inferensi langsung, menyimpan hasil dan episode alert, serta menampilkannya melalui API dan dua rute UI.

Yang tetap ada adalah data historis, replay, dan fitur yang telah ada. Semua kontrak model yang baru dapat dipilih atau dieksekusi, termasuk jalur preview dan replay baru, harus memakai `window_size=10` secara konsisten. Provenance model 30 tetap dapat dibaca sebagai riwayat, tetapi tidak boleh dipilih atau dieksekusi kembali.

Hal berikut bukan bagian dari desain ini:

- perubahan firmware atau perubahan QoS firmware;
- retensi, penghapusan otomatis, atau kompresi data;
- fallback inferensi simulasi untuk data langsung;
- perangkat kedua, multi-device, autentikasi aplikasi, notifikasi, Kafka, Redis, WebSocket, atau disk spooling;
- database terpisah dari PostgreSQL dan Timescale yang sudah digunakan;
- broker tambahan di deployment aplikasi; broker ephemeral hanya boleh dibuat di profile pengujian E2E dan tidak menjadi dependency produksi.

## 2. Batasan keadaan saat ini

Platform saat ini memiliki API telemetry dan inference berbasis rentang waktu, serta lifecycle alert manual `detected -> acknowledged -> resolved`. Endpoint history mengembalikan waktu dengan zona `Asia/Jakarta`; event audit alert yang sudah ada dicatat sebagai waktu UTC. Migrasi dan kode historis masih memiliki pemeriksaan `window_size=30` pada snapshot preprocessing, preview, seed, import, aktivasi model, dan test tertentu. Di sisi lain, registri model artefak sudah menyatakan `window_size=10`. Ketidaksamaan itu harus dihapus melalui satu migrasi model-wide, bukan dipertahankan sebagai dua kontrak yang dapat dipilih.

Istilah waktu dalam desain ini dibedakan secara tegas:

- **Waktu corpus dan telemetry:** `received_ts timestamp(0) without time zone`, ditafsirkan sebagai waktu lokal `Asia/Jakarta`. Nilai ini sengaja naive agar konsisten dengan corpus yang ada dan digunakan bersama `telemetry_id` sebagai urutan total.
- **Waktu penerimaan dan audit operasional:** `received_at_utc timestamptz` dengan presisi database, serta timestamp aware UTC lain untuk koneksi, heartbeat, command acknowledge/resolve, dan kesalahan. Nilai ini menyatakan instant aktual dan digunakan untuk menghitung gap; nilai audit tidak boleh diturunkan kembali dari waktu corpus.

Untuk setiap payload, kedua nilai dibuat dari satu pembacaan clock: `received_at_utc` menyimpan instant lengkap, sedangkan `received_ts` adalah representasi instant yang sama di `Asia/Jakarta` dan dipotong ke presisi detik. Semua query recovery, window, cursor, dan pagination mengurutkan secara eksplisit dengan `ORDER BY received_ts, telemetry_id`; tidak ada urutan implisit berdasarkan timestamp saja.

## 3. Arsitektur dan aliran data

Komponen minimum adalah firmware yang tidak berubah, broker MQTT, subscriber aplikasi, PostgreSQL dengan Timescale, pemuat pasangan model aktif beserta scaler, engine inferensi, pengelola episode alert, API yang ada, dan UI.

1. Subscriber memvalidasi konfigurasi dan schema database, memperoleh lease writer perangkat, lalu membaca activation live yang aktif.
2. Subscriber merekonstruksi cursor dan state window secara idempoten serta memulai pemuatan pasangan model sebelum membuka konsumsi MQTT.
3. Subscriber terhubung menggunakan MQTT 5, memvalidasi CONNACK, melakukan subscription exact-topic, dan baru menerima traffic setelah SUBACK sukses.
4. Firmware menerbitkan payload valid ke topic yang ditentukan deployment.
5. Di bawah lock ingress nonblocking yang sama, callback MQTT memvalidasi envelope, mengambil kedua receipt timestamp, lalu menangkap `ingress_sequence`, `ingress_generation`, `activation_id`, dan `continuity_epoch` dari state writer yang sudah dimuat. Callback tidak menjalankan query database atau inferensi GPU.
6. Writer berpagar menyimpan telemetry lebih dahulu ke hypertable `live_telemetry` dan menandai status pemrosesannya secara durable.
7. Setelah pasangan model siap, worker menguras telemetry `pending` dari cursor secara terurut, termasuk telemetry yang tiba selama model belum siap. Sampel yang diproses memasuki state sliding window 10 sampel; setelah terdapat 10 sampel berurutan, engine membuat window stride 1 dan menyimpan hasil pada hypertable `live_inference`.
8. Hasil anomaly memperbarui state machine episode dan data alert permanen dalam transaksi yang sama dengan hasil dan cursor pemrosesan.
9. API membaca sumber live yang sama. Rute UI `/` dan `/sensors/b02f3872-ruang-produksi` memakai kontrak API yang sama, sehingga tidak ada data atau logika live yang berbeda per halaman.

Penyimpanan adalah batas durabilitas. Queue ingress memori yang bounded hanya memindahkan envelope tervalidasi dari callback menuju persistence; overflow memakai kebijakan `drop-newest` sebelum durabilitas dan dicatat sebagai batas kontinuitas. Setelah insert commit, database dan cursor komposit menjadi work log durabel; pekerjaan persisten tidak boleh dibuang karena scorer lambat atau tidak tersedia.

### 3.1 Single writer dan fencing

Tepat satu subscriber boleh menulis state live untuk perangkat. Lease disimpan di database dengan `device_id`, token fencing monotonik, identitas owner, `acquired_at_utc`, `heartbeat_at_utc`, dan `expires_at_utc`. Writer memperbarui heartbeat setiap 5 detik memakai waktu database; lease kedaluwarsa setelah 15 detik tanpa heartbeat. Akuisisi atau perpanjangan lease bersifat atomik. Semua transaksi telemetry, status pemrosesan, cursor, inference, dan episode wajib memverifikasi bahwa token fencing masih aktif; writer dengan token lama tidak boleh commit setelah lease berpindah.

Kehilangan lease membuat subscriber berhenti menerima pekerjaan, memutus koneksi MQTT, dan gagal readiness. Instance baru harus memperoleh token baru dan merekonstruksi cursor serta batas segmen sebelum membuka koneksi. CONNACK dan SUBACK boleh diselesaikan ketika model masih dimuat agar telemetry tetap dipersistenkan sebagai `pending`, tetapi readiness baru sehat setelah model siap dan backlog recovery telah dikuras. Client ID MQTT yang stabil membantu mencegah koneksi ganda, tetapi bukan pengganti lease database.

## 4. Kontrak firmware dan MQTT

### 4.1 Firmware read-only

Firmware tidak diubah. Satu-satunya bentuk payload yang diterima adalah:

```json
{"data":[suhu,rh]}
```

`data` wajib berupa array dengan tepat dua angka finite, dengan urutan `suhu` lalu `rh`. Payload yang bukan objek JSON tersebut, memiliki field tambahan, memiliki elemen kurang atau lebih, nilai nonnumerik, `NaN`, atau tak hingga ditolak. Payload tidak membawa `DEVICE_ID` atau timestamp.

Firmware memakai QoS 0. Kehilangan pesan QoS 0 tidak dapat dipulihkan oleh subscriber, broker, database, atau UI. Platform hanya dapat mendeteksi akibatnya ketika jarak penerimaan antar pembacaan valid melewati batas gap.

### 4.2 Kontrak koneksi dan subscription

Subscriber menggunakan MQTT 5 dengan `Clean Start=true` dan CONNECT property eksplisit `Session Expiry Interval=0`, QoS subscription 0, Retain Handling `2` agar retained message tidak dikirim saat subscription dibuat, serta Retain As Published `1` agar retain flag publish tidak dibersihkan broker. Pesan yang datang dengan retain flag ditolak secara defensif, dihitung sebagai payload ditolak, dan tidak menjadi telemetry. Subscriber menerima publish hanya jika topic yang diterima sama persis dengan `MQTT_TOPIC`; wildcard `+` dan `#` dilarang pada konfigurasi.

CONNACK dan SUBACK harus sukses sebelum readiness menjadi sehat. SUBACK wajib dikorelasikan dengan packet identifier subscription yang dikirim dan seluruh reason code-nya harus menyatakan sukses. Disconnect memicu capped exponential backoff dengan full jitter: batas dasar `min(30 detik, 2^attempt detik)` dan delay acak pada interval `0..batas dasar`; attempt di-reset setelah subscription stabil. Reconnect selalu membuat subscription baru dengan aturan yang sama.

TLS wajib untuk deployment nonlokal, termasuk verifikasi CA dan hostname. Broker ACL membatasi principal subscriber ke exact topic dan Client ID deployment. Username, password, dan material TLS diberikan sebagai Docker Compose secret atau file read-only; environment hanya membawa path file. Plaintext tanpa TLS hanya diizinkan pada broker ephemeral profile test yang terisolasi.

### 4.3 Kontrak environment subscriber

Konfigurasi subscriber harus berasal dari environment dan harus divalidasi saat proses mulai:

| Variabel | Kontrak |
| --- | --- |
| `MQTT_BROKER_HOST` | Wajib, nama host atau alamat broker yang tidak kosong. |
| `MQTT_BROKER_PORT` | Wajib, bilangan bulat port yang valid. |
| `MQTT_TOPIC` | Wajib, satu exact topic yang tidak kosong dan tidak mengandung wildcard. |
| `MQTT_USERNAME_FILE` | Opsional, path secret read-only; hanya sah bersama `MQTT_PASSWORD_FILE`. |
| `MQTT_PASSWORD_FILE` | Opsional, path secret read-only; hanya sah bersama `MQTT_USERNAME_FILE`. |
| `MQTT_CLIENT_ID` | Wajib, identitas subscriber yang stabil dan tidak kosong. |
| `MQTT_TLS_ENABLED` | Wajib; `true` di luar profile test terisolasi. |
| `MQTT_CA_FILE` | Wajib ketika TLS aktif, path CA bundle read-only. |
| `LIVE_RUNTIME_MODE` | Opsional, default `production`; hanya service profile E2E terisolasi yang boleh menetapkan `test`. |

Tidak ada daftar device atau konfigurasi per-device. `DEVICE_ID` adalah konstanta tunggal `b02f3872-ruang-produksi` yang diberi oleh subscriber setelah topic dan payload lolos validasi. `MQTT_TLS_ENABLED=false` ditolak kecuali `LIVE_RUNTIME_MODE=test`, dan hanya service E2E pada Compose profile terisolasi yang boleh memasok mode tersebut secara eksplisit. Konfigurasi yang tidak valid menghentikan subscriber sebelum koneksi dan ditampilkan sebagai kondisi readiness gagal. Isi secret tidak pernah disimpan dalam telemetry, response API, log terstruktur yang dapat dilihat pengguna, atau dokumen ini.

## 5. Kontrak telemetry dan persistence

### 5.1 `live_telemetry`

`live_telemetry` adalah hypertable Timescale yang dipartisi oleh `received_ts`. Primary key-nya adalah `(received_ts, telemetry_id)` agar memenuhi constraint unique hypertable. `telemetry_id bigint generated by default as identity` adalah tie-breaker monotonik pada single writer dan tidak diperlakukan sebagai unique key tunggal.

Setiap baris menyimpan paling sedikit `device_id`, `received_ts`, `received_at_utc`, `suhu`, `rh`, `ingress_sequence`, `ingress_generation`, `activation_id` dan `continuity_epoch` yang sudah ditangkap ketika payload diterima, `segment_start_reason` nullable, token fencing writer, dan `processing_status`. Status pemrosesan hanya `pending` atau `processed`; waktu pemrosesan dan alasan boundary disimpan terpisah. Envelope baru menjadi telemetry yang diterima hanya setelah insert commit. Payload yang terkena overflow ingress tidak dibuat sebagai baris telemetry fiktif.

Tidak ada retensi atau penghapusan otomatis. Kegagalan insert berarti sampel itu tidak diterima secara durabel. Subscriber mencatat kesalahan, memperbarui system health, dan tidak membuat inferensi atau alert dari sampel tersebut. Tidak ada disk spool dan tidak ada upaya merekonstruksi pesan MQTT yang telah hilang.

`live_processing_boundaries` adalah tabel PostgreSQL reguler yang append-only. Setiap boundary menyimpan `boundary_id`, perangkat, `continuity_epoch` baru yang monotonik, alasan `startup`, `data_gap`, `model_change`, `overload`, atau `lease_takeover`, waktu UTC, token fencing, counter/rentang yang tersedia, serta nullable anchor `(after_received_ts, after_telemetry_id)` yang menunjuk telemetry terakhir sebelum boundary. Boundary diproses setelah anchor dan sebelum telemetry pertama pada epoch baru; cursor juga menyimpan `last_boundary_id` agar closure/reset idempoten walaupun belum ada telemetry berikutnya. Startup atau takeover meng-anchor boundary pada durable tail sebelum koneksi dibuka, sedangkan backlog lama tetap diproses menurut epoch yang sudah tersimpan.

### 5.2 `live_inference` dan hubungan sumber

`live_inference` adalah hypertable yang dipartisi oleh `score_ts timestamp(0) without time zone`, dengan primary key `(score_ts, inference_id)` dan `inference_id bigint generated by default as identity`. Setiap baris menyimpan `device_id`, `window_start_ts`, `window_end_ts`, `score_ts`, skor finite, threshold finite dan `> 0`, status anomaly, severity saat itu, `model_pair_id`, `activation_id`, `continuity_epoch`, fingerprint window, dan token fencing writer.

`live_inference_sources` adalah tabel PostgreSQL reguler, bukan hypertable. Setiap baris memiliki `source_ordinal` dengan constraint `0..9`, foreign key komposit `(score_ts, inference_id)` ke `live_inference`, dan foreign key komposit `(received_ts, telemetry_id)` ke `live_telemetry`. Primary key `(score_ts, inference_id, source_ordinal)` dan unique `(score_ts, inference_id, received_ts, telemetry_id)` mencegah posisi atau sumber berulang. Insert dilakukan sebagai batch tepat 10 baris dan deferred constraint trigger memverifikasi jumlah ordinal `0..9` lengkap sebelum transaksi commit.

Fingerprint window adalah SHA-256 dari byte UTF-8 tanpa final newline dengan header `live-window-v1\n{device_id}\n{model_pair_id}\n{activation_id}\n{continuity_epoch}` yang diikuti tepat 10 baris `{source_ordinal}|{received_ts}|{telemetry_id}`. Sumber diurutkan menurut `source_ordinal`, `received_ts` diformat `YYYY-MM-DDTHH:MM:SS`, ID memakai desimal ASCII, dan seluruh separator literal. Dengan demikian hash tidak bergantung pada serialisasi objek atau locale. Unique key idempoten `(score_ts, model_pair_id, activation_id, continuity_epoch, window_fingerprint)` menyertakan kolom partisi Timescale. `score_ts` adalah `received_ts` sumber ordinal 9, sehingga retry window yang sama menghasilkan key yang sama.

Untuk telemetry yang menghasilkan inferensi, insert hasil, 10 source link, perubahan status telemetry, cursor pemrosesan, pembaruan episode, alert, dan event alert berlangsung dalam satu transaksi. Telemetry warm-up atau boundary tetap mengubah status dan memajukan cursor dalam transaksi berpagar yang sama meskipun tidak menghasilkan inferensi. Konflik idempoten tidak boleh menambah hasil, alert, atau event kedua.

## 6. Kontrak inferensi langsung

Cadence yang diharapkan adalah satu pembacaan setiap 6 detik. Gap dihitung dari selisih dua `received_at_utc` berurutan dalam urutan total `(received_ts, telemetry_id)`:

| Jarak instant penerimaan | Perlakuan |
| --- | --- |
| `<= 12.000000` detik | Sampel diterima sebagai lanjutan segmen aktif. |
| `> 12.000000` detik | Terjadi data gap. Segmen dan sliding window di-reset, episode anomaly terbuka ditutup dengan alasan `data_gap`, lalu sampel berikutnya memulai segmen baru. |

Window terdiri dari 10 baris berurutan dan memakai stride 1. Sampel ke-10 pada segmen membuat window pertama, kemudian setiap sampel berikutnya membuat satu window baru. Window tidak boleh menyeberangi data gap, perubahan `continuity_epoch`, startup/takeover boundary, kehilangan lease, overflow ingress, atau perubahan activation.

### 6.1 Sliding state, ingress queue, dan backlog durabel

Sliding state adalah `deque` berkapasitas tepat 10 dan hanya berisi sampel kontinu yang sudah diproses. Struktur ini terpisah dari queue ingress FIFO berkapasitas 100 envelope yang belum persisten. Setiap envelope membawa immutable `ingress_sequence`, `ingress_generation`, `activation_id`, `continuity_epoch`, dan receipt timestamps yang ditangkap di bawah lock ingress yang sama. Callback lalu memakai `put_nowait`; consumer tunggal melakukan insert sesuai FIFO.

Jika queue penuh, envelope terbaru ditolak dengan kebijakan `drop-newest`. Di bawah lock ingress, drop pertama setelah enqueue sukses terakhir menaikkan `ingress_generation` dan `continuity_epoch`, lalu mencatat control boundary setelah `ingress_sequence` terakhir yang berhasil diterima. Hanya drop berturut-turut tanpa enqueue sukses di antaranya yang boleh digabung ke counter boundary itu. Begitu satu envelope generation baru berhasil di-enqueue, drop berikutnya wajib membuat generation dan boundary baru; urutan `drop X -> enqueue Y -> drop Z` menghasilkan dua boundary yang mengapit Y. Envelope yang sudah queued mempertahankan generation lama. Consumer menggabungkan FIFO dan control boundary menurut sequence: setelah seluruh envelope sampai anchor berhasil dipersistenkan, boundary dipersistenkan dengan key telemetry anchor tersebut sebelum envelope generation baru, sekalipun tidak ada envelope baru. Ketika cursor mencapai boundary, worker menutup episode terbuka dengan alasan `overload`, me-reset sliding state, dan memajukan `last_boundary_id`. Payload yang jatuh sebelum durabilitas tidak diberi telemetry palsu dan tidak diklaim dapat dipulihkan. Jika proses berhenti sebelum control boundary tersimpan, boundary `startup` atau `lease_takeover` untuk ingress baru mencegah window berikutnya menyeberangi ketidakpastian tersebut.

Setelah telemetry persisten, database adalah work log tanpa batas kehilangan sebesar 100. Worker membaca backlog dalam page yang bounded tepat menurut `(received_ts, telemetry_id)`, menggabungkannya dengan boundary ber-anchor, dan tidak boleh melompati baris `pending`. Cursor durable menyimpan key telemetry terakhir yang efeknya telah commit, `last_boundary_id`, `continuity_epoch`, dan token fencing. Cursor maju untuk warm-up, boundary, atau hasil hanya setelah efeknya commit atomik. Jika model sementara tidak siap, konsumsi berhenti pada baris itu, retry model berjalan, health menjadi `degraded`, readiness gagal, dan pekerjaan persisten tidak diubah menjadi skip atau dibuang.

### 6.2 Pasangan model dan activation epoch

Pemilihan model live terpisah dari selection preview dan replay. `live_model_pairs` menyimpan pasangan immutable model, checkpoint, scaler, feature order `[suhu, rh]`, `window_size=10`, `stride=1`, threshold finite `> 0`, serta hash terpisah untuk manifest model, checkpoint, manifest scaler, dan file scaler. Perubahan runtime masuk sebagai `live_model_activation_requests`; hanya writer pemegang lease yang boleh menerapkannya. `live_model_activations` membuat `activation_id` monotonik untuk setiap aktivasi pasangan pada perangkat, dan `live_model_selections` menunjuk satu activation aktif. Endpoint preview atau replay tidak dapat menulis ketiga seam live tersebut.

Model dan scaler dimuat serta diverifikasi sebagai satu pasangan atomik. Hasil scorer wajib finite. Setiap telemetry dinilai hanya oleh pasangan immutable milik `activation_id` yang sudah terikat saat insert. Pasangan activation lama boleh tetap resident hanya untuk menguras telemetry yang memang telah terikat sebelum pergantian; pasangan itu tidak boleh dipakai untuk telemetry activation baru dan bukan fallback. Jika artefak, CUDA yang diwajibkan artefak, atau scaler untuk baris terdepan belum siap, telemetry tetap `pending`, inferensi berhenti pada posisi itu, system health menjadi `degraded`, readiness gagal, dan pasangan tersebut dicoba dimuat kembali. Tidak ada skor simulasi atau threshold pengganti.

Untuk menerapkan request activation, writer lebih dahulu memvalidasi pasangan dan menyiapkan immutable activation ID di database tanpa memegang lock ingress. Di bawah lock ingress singkat tidak ada I/O: writer hanya mencatat control marker setelah `ingress_sequence` terakhir, menukar cached activation pointer, dan menaikkan `ingress_generation` serta `continuity_epoch` untuk envelope berikutnya. Consumer mempersistenkan activation selection dan boundary dalam satu transaksi berpagar setelah seluruh envelope sampai sequence anchor commit dan sebelum envelope baru, sekalipun belum ada envelope baru. Jika transaksi tertahan atau gagal, callback tetap nonblocking; consumer tidak boleh mempersistenkan envelope generation baru sampai activation/boundary commit. Envelope yang sudah queued tetap membawa activation/generation lama. Transaksi publikasi memverifikasi lease, ordered source IDs, serta `activation_id` dan `continuity_epoch` yang sudah terikat pada seluruh source; hasil yang dihitung untuk binding lain ditolak. Perubahan selection tidak mengubah binding baris lama: backlog lama boleh commit hanya memakai pasangan immutable yang sudah ditetapkan, sedangkan telemetry baru memakai activation baru. Saat cursor mencapai boundary, worker menutup episode activation lama dengan alasan `model_change` dan me-reset sliding state sebelum menilai baris epoch baru. `model_pair_id` yang sama tetapi diaktifkan ulang tetap menghasilkan `activation_id` baru.

### 6.3 Recovery restart

Setelah memperoleh lease dan membaca activation aktif, subscriber membaca cursor, processing boundary, dan paling banyak 9 sampel `processed` terakhir dari activation serta `continuity_epoch` aktif dalam urutan `(received_ts, telemetry_id)`. Rekonstruksi state lama dan penetapan boundary `startup` atau `lease_takeover` yang di-anchor pada durable tail untuk ingress baru harus selesai sebelum koneksi MQTT dibuka. Setelah pasangan model siap, worker memindai seluruh baris `pending` dan boundary sesudah cursor dalam page bounded serta urutan anchor; telemetry baru hanya ditambahkan di belakang backlog. Boundary memajukan `last_boundary_id` dan me-reset state, sedangkan backlog lama tetap memakai epoch dan pasangan yang telah tersimpan.

Recovery dinyatakan selesai setelah backlog pada snapshot startup terkuras; telemetry yang datang sesudah snapshot tetap diproses melalui urutan yang sama. Fingerprint, unique key, transaksi atomik, dan token fencing menjamin hasil serta alert yang sudah commit tidak dibuat ulang. Crash sebelum commit meninggalkan unit kerja untuk retry lengkap; crash setelah commit melanjutkan dari cursor yang ikut commit.

## 7. Migrasi kontrak model dari 30 ke 10

Migrasi ini berlaku untuk seluruh kontrak model yang baru dapat dipilih atau dieksekusi, bukan hanya jalur live. Nilai `window_size=10` dan `stride=1` harus menjadi kontrak tunggal untuk:

- preprocessing snapshot dan constraint database;
- metadata, manifest, scaler, dan artefak model;
- import corpus, seed, preview, aktivasi model, pembuatan replay baru, simulator historis, API, fixture, dan test;
- validasi dan response registry model.

Migrasi database populated mempertahankan provenance model 30 untuk riwayat, tetapi menandainya legacy, nonselectable, dan nonexecutable. Artifact 30 tidak boleh sekadar dilabel ulang menjadi 10. Active selection lama harus dipindahkan ke pasangan 10 yang benar atau dikosongkan secara eksplisit; migrasi gagal jika hasilnya membuat live selection, preview, atau replay menunjuk kontrak 30.

Seed harus melakukan upsert perubahan kontrak yang dimaksud, bukan bergantung pada `ON CONFLICT DO NOTHING`. Submission replay dan setiap transisi worker replay memperoleh PostgreSQL transaction-level shared advisory lock dengan key kontrak yang tetap. Migrasi memperoleh exclusive advisory lock yang sama dan menahannya selama precheck serta perubahan schema/data, lalu menolak berjalan ketika ada replay job nonterminal. Dengan demikian job baru tidak dapat lolos di antara precheck dan cutover. Setelah migrasi, data historis dan provenance 30 tetap dapat dibaca, tetapi tidak ada endpoint, job, atau selection yang dapat menjalankannya. Model atau scaler 10 juga ditolak bila tidak cocok dengan dua fitur `[suhu, rh]`, stride 1, hash artifact yang terverifikasi, atau threshold finite `> 0`.

## 8. State machine episode dan lifecycle alert

State episode otomatis dipisahkan dari lifecycle manual alert yang sudah ada.

| Keadaan episode | Peristiwa | Hasil |
| --- | --- | --- |
| Tidak ada episode aktif | Anomaly pertama | Buka episode dan buat satu alert baru dengan status lifecycle `detected`. |
| Episode terbuka | Anomaly berikutnya | Tambahkan hasil ke episode, reset penghitung normal, dan hanya naikkan severity bila perlu. |
| Episode terbuka | Normal pertama atau kedua berturut-turut | Tambahkan recovery point dan lanjutkan episode. |
| Episode terbuka | Normal ketiga berturut-turut | Tutup episode dengan alasan `normal_recovery`. |
| Episode terbuka | Gap `> 12` detik | Tutup episode segera dengan alasan `data_gap`, buang window parsial. |
| Episode terbuka | Activation model berubah | Tutup episode dengan alasan `model_change`, buang window parsial. |
| Episode terbuka | Boundary kehilangan ingress karena overload | Tutup episode dengan alasan `overload`, buang window parsial. |
| Episode tertutup | Anomaly baru | Buat alert dan episode baru yang terpisah. |

Severity dihitung dari `score / threshold`:

- `warning` jika rasio `> 1x` sampai `<= 2x`;
- `critical` jika rasio `> 2x`.

Severity hanya boleh meningkat selama episode yang sama, dari `warning` ke `critical`. Severity tidak turun karena skor berikutnya lebih rendah. Penutupan episode teknis tidak mengubah lifecycle alert secara otomatis. Alert tetap berstatus `detected` sampai operator menjalankan acknowledge, lalu resolve, melalui lifecycle yang sudah ada.

Operator boleh acknowledge alert saat episode teknis masih terbuka, tetapi resolve ditolak dengan HTTP `409` sampai episode ditutup. Setelah penutupan teknis, resolve hanya mengubah lifecycle alert dan tidak membuka, menutup, atau menggabungkan episode lain.

Watchdog pada writer aktif berjalan setiap 1 detik dan memeriksa pembacaan valid terakhir menggunakan `received_at_utc`. Jika waktu database menjadi tepat atau kurang dari `last_received_at_utc + 12 detik`, episode tidak berubah; ketika waktu database secara ketat melewati batas itu, watchdog menutup episode terbuka sebagai `data_gap` dalam transaksi berpagar. Penutupan ini idempoten. Jika sampel berikut datang lebih dahulu, pemeriksaan gap pada sampel dan watchdog diserialkan oleh lease serta lock state episode sehingga hanya satu close event dibuat.

Riwayat alert dan event adalah permanen. Detail alert menyimpan tepat 10 source readings yang membentuk window anomaly pertama, lalu setiap hasil episode beserta source reading unik yang dirujuknya, serta tiga hasil normal berturut-turut berikut source-nya yang menutup episode. Untuk alasan selain `normal_recovery`, detail menyimpan konteks yang tersedia dan alasan penutupan tanpa mengarang recovery point.

## 9. API, UI, rolling range, dan health

API live memakai pola telemetry, inference, dan alert yang sudah ada. Tidak boleh dibuat API paralel khusus halaman root atau fallback simulasi. Kontrak query tunggal menerima perangkat, rentang waktu, dan mode bucket. Endpoint latest, history, inference results, current alerts, alert event, acknowledge, dan resolve yang telah ada disesuaikan agar sumber live dapat dibaca dengan semantik yang sama.

Pagination history menggunakan keyset cursor opaque. Cursor telemetry memuat filter, snapshot upper bound, dan key terakhir `(received_ts, telemetry_id)`; cursor inference memakai `(score_ts, inference_id)`. Request halaman pertama menetapkan upper bound yang tetap untuk seluruh rangkaian halaman, sehingga insert baru tidak menggeser atau menggandakan halaman. Cursor dengan filter, device, rentang, atau bucket berbeda ditolak.

Kedua rute UI berikut menunjukkan device dan sumber API yang sama:

- `/`
- `/sensors/b02f3872-ruang-produksi`

Keduanya melakukan polling setiap 3 detik. Query rolling menggunakan parameter URL kanonik `range=1h|6h|12h|24h`; setiap poll menghitung ulang `[now_utc-range, now_utc]`, sehingga range benar-benar bergerak. Default adalah `range=1h`. Custom memakai `start` dan `end` ISO 8601 ber-offset dan merupakan interval tetap yang tidak bergeser pada poll atau refresh. URL yang ambigu atau mencampur `range` dengan `start/end` ditolak.

Aturan bucket adalah:

| Rentang | Bucket dan agregasi |
| --- | --- |
| Rolling 1 jam | Raw, diurutkan dengan key total. |
| Rolling 6, 12, atau 24 jam | `time_bucket('1 minute', ...)`. Telemetry mengembalikan rata-rata `suhu` dan `rh`, minimum, maksimum, jumlah sampel, serta timestamp awal/akhir bucket. Inference memilih rasio `score/threshold` maksimum, `bool_or(is_anomaly)`, severity maksimum, dan row model/activation dari rasio maksimum; tie dipecahkan oleh key terbaru. |
| Custom | Lebar whole-minute terkecil `max(60, 60 * ceil((end-start dalam detik)/(600*60)))` detik agar maksimal 600 bucket, dengan agregasi yang sama seperti bucket 1 menit. |

Rentang API minimum adalah lebih dari 0 detik dan maksimum 24 jam. Semua boundary memakai interval half-open `[start, end)`, kecuali endpoint latest. Response menyatakan timezone, bucket size aktual, range start/end, dan apakah data raw atau agregat.

System health menampilkan setidaknya status konfigurasi, lease/fencing dan heartbeat database, hasil CONNACK/SUBACK, koneksi MQTT, waktu heartbeat proses, waktu pembacaan valid terakhir, gap terakhir, jumlah payload invalid atau retained, kegagalan persistence terakhir, jumlah `drop-newest` ingress dan boundary yang masih pending, depth queue ingress, backlog durabel dan cursor, recovery/readiness, activation model dan scaler aktif, seluruh hash verification, serta status retry inferensi.

Liveness hanya membuktikan event loop proses dan heartbeat lokal masih bergerak; liveness tidak bergantung pada broker, database, atau model. Readiness membuktikan schema valid, lease aktif, heartbeat database belum melewati dua interval, recovery selesai, model siap, koneksi MQTT aktif, dan SUBACK sukses. System health menggabungkan dependency menjadi `healthy`, `degraded`, atau `failed` dengan alasan yang dapat dibaca pengguna. Nilai kredensial, path secret internal, dan isi secret tidak pernah dikembalikan.

## 10. Penanganan kesalahan

- Payload atau topic invalid dan retained publish ditolak, dihitung di health, dan tidak disimpan atau dinilai.
- Putus koneksi MQTT memicu reconnect dengan capped backoff dan subscription ulang. Pesan yang hilang selama putus tetap hilang karena QoS 0.
- Kegagalan database tidak boleh menghasilkan telemetry, skor, cursor, atau alert fiktif. Kesalahan dicatat pada health; tanpa insert durable tidak ada retry payload setelah callback selesai.
- Overflow queue ingress menolak envelope terbaru sebelum persistence, mencatat counter, dan mewajibkan boundary `overload` durabel sebelum insert berikutnya. Backlog yang sudah persisten tidak boleh dibuang atau dilompati.
- Kegagalan model atau scaler menghentikan inferensi terurut pada telemetry `pending` dan memicu retry pemuatan pasangan aktif. Telemetry tidak dialihkan ke simulator atau model lain.
- Gap `> 12` detik selalu menutup episode aktif dan me-reset window, baik dideteksi oleh sampel berikut maupun watchdog.
- Kehilangan lease menolak commit writer lama, memutus konsumsi MQTT, dan memerlukan startup serta recovery lengkap oleh writer baru.
- Error API harus mempertahankan validasi rentang waktu, device tunggal, keyset cursor, snapshot upper bound, dan bucket. Response menampilkan kesalahan yang dapat ditindak tanpa menyertakan secret.

## 11. Pengujian dan kriteria penerimaan

### Pengujian yang wajib ada

- Unit test payload MQTT untuk bentuk tepat `{"data":[suhu,rh]}`, dua angka finite, field tambahan, seluruh bentuk invalid, retained flag, dan topic yang tidak exact-match.
- Unit test MQTT 5 untuk Clean Start, CONNECT Session Expiry Interval 0, Retain Handling 2, Retain As Published 1, CONNACK/SUBACK packet-id gating, reconnect capped exponential backoff dengan jitter, runtime-mode TLS guard, serta readiness sebelum dan sesudah subscription.
- Unit test batas gap tepat `12.000000` versus lebih dari 12 detik, tie timestamp dengan urutan `telemetry_id`, watchdog idempoten, window 10 baris stride 1, dan reset pada semua batas segmen.
- Unit test pemisahan sliding deque 10 dari queue ingress 100, immutable sequence/generation/activation envelope, `drop-newest` saat drain konkuren, boundary overload pada perubahan generation, activation handoff ketika queue berisi data, backlog persisten lebih dari 100 yang tetap diproses, cursor yang maju pada warm-up/boundary/result commit, serta recovery yang tidak melintasi `continuity_epoch`.
- Unit test pasangan model dan scaler, seluruh hash terpisah, threshold positif finite, score finite, pending retry, activation epoch, fencing scorer lama, selection live terpisah dari preview/replay, serta larangan fallback simulasi.
- Unit test state machine: pembukaan anomaly pertama, tiga normal untuk penutupan, `data_gap`, `model_change`, `overload`, severity warning dan critical, escalation only, resolve `409` ketika episode terbuka, dan episode baru setelah episode tertutup.
- Integration test DDL Timescale untuk key komposit kedua hypertable dan foreign key tabel bridge reguler, source ordinal 0..9, fingerprint deterministik, unique key idempoten, serta transaksi result-source-cursor-episode-alert.
- Integration test migrasi populated 30 ke 10 pada PostgreSQL dan Timescale yang sama, termasuk provenance legacy, seed upsert, active selection, penolakan replay job aktif, submit/start replay yang berlomba tepat setelah precheck, shared/exclusive advisory-lock protocol, model 30 nonselectable/nonexecutable, dan API.
- Integration test dua subscriber bersamaan, lease takeover, fencing token lama, startup ordering, recovery crash sebelum/sesudah commit, serta konteks detail alert 10 sebelum, episode, dan recovery.
- API dan UI test untuk stable keyset pagination dengan concurrent insert, rolling URL range, custom fixed range, half-open boundary, bucket raw/1 menit/adaptif, agregasi anomaly maksimum, polling 3 detik, kedua rute UI, serta pemisahan liveness, readiness, dan system health.
- Failure test untuk broker terputus, SUBACK ditolak, retained publish, payload invalid, database gagal, model tidak tersedia, queue overload, dan penegasan bahwa kehilangan QoS 0 tidak dipulihkan.
- E2E nyata memakai project/profile Compose terisolasi berisi broker ephemeral, image `timescale/timescaledb:2.28.3-pg17` yang sama dengan deployment, migrasi sebenarnya, subscriber sebenarnya, API sebenarnya, dan build frontend production tanpa MSW. Gate dua tahap menyalakan dependency dan service sampai ready, kemudian menjalankan runner `live-e2e` secara terpisah dan selalu membersihkan project/volume melalui trap; one-shot init container tidak boleh menghentikan runner. Test menerbitkan MQTT lalu membuktikan aliran telemetry, 10-source inference, alert, API, dan kedua rute UI. Smoke test artefak asli diberi tag GPU dan tidak boleh diganti scorer simulasi.
- Backup pra-migrasi diverifikasi, lalu logical restore rehearsal dijalankan ke database disposable baru dengan versi PostgreSQL/Timescale yang sama. Alur tunggal memakai `pg_dump -Fc`, membuat target dan extension, memanggil `timescaledb_pre_restore()`, menjalankan `pg_restore` serial tanpa `-j`, memanggil `timescaledb_post_restore()`, lalu menjalankan migrasi dan smoke API. Script menolak source dan target yang sama. Hasil mencatat durasi, checksum/row count utama, versi extension, dan keberhasilan aplikasi membaca target tanpa menimpa database sumber.

### Kriteria penerimaan

1. Satu payload valid pada exact topic menghasilkan satu telemetry live dengan `received_ts` naive `Asia/Jakarta`, `received_at_utc` dari instant yang sama, dan key Timescale yang valid.
2. Setelah 10 sampel kontinu dalam activation dan `continuity_epoch` yang sama, setiap sampel baru menghasilkan tepat satu window stride 1, 10 source ordinal, fingerprint deterministik, dan hasil inferensi persisten dengan score finite serta threshold finite `> 0`.
3. Gap tepat 12 detik masih kontinu; gap lebih dari 12 detik tidak dapat melintasi window dan menutup episode aktif sebagai `data_gap`, termasuk saat tidak ada sampel berikutnya.
4. Saturasi queue ingress menerapkan `drop-newest` sebelum persistence, tidak mengubah tag immutable item lama, menaikkan generation untuk item baru, dan menempatkan boundary `overload` tepat pada transisi generation meskipun drain berjalan konkuren; backlog yang sudah persisten, termasuk lebih dari 100 baris, tetap diproses terurut setelah restart.
5. Alert pertama pada episode dibuat sebagai `detected`, resolve ditolak selama episode terbuka, penutupan teknis tidak otomatis resolve, dan episode baru menghasilkan alert terpisah.
6. Severity mengikuti batas rasio yang ditetapkan dan tidak pernah turun dalam episode; model change, overload, dan data gap memiliki close reason yang dapat diaudit.
7. Restart dan lease takeover tidak menggandakan result atau alert, tidak menerima commit token lama, serta melanjutkan urutan `(received_ts, telemetry_id)` dari persistence.
8. Selection live tidak dapat diubah oleh preview/replay; setiap hasil terikat pada immutable `model_pair_id` dan `activation_id`, dan aktivasi baru tidak mencampur window lama.
9. Semua jalur executable platform menyatakan `window_size=10` dan `stride=1`; provenance 30 boleh tetap terbaca tetapi tidak selectable atau executable.
10. `/` dan `/sensors/b02f3872-ruang-produksi` menampilkan sumber API live yang sama dengan polling 3 detik, rolling range URL-backed, keyset cursor stabil, dan agregasi bucket yang ditetapkan.
11. Readiness baru sehat setelah lease, recovery, model, koneksi, dan SUBACK siap; liveness tetap menjadi pemeriksaan proses yang terpisah.
12. Script E2E dua tahap membuktikan MQTT ke UI tanpa MSW tanpa berhenti pada one-shot init container, dan logical restore gate ke database baru berhasil sebelum migrasi diizinkan.
13. Deployment migrasi menghentikan writer dan job mutating, mengambil backup konsisten pada cutover, lalu menjalankan migrasi; RPO database sampai titik cutover adalah 0. Pesan QoS 0 yang terbit selama penghentian atau setelah snapshot tetapi sebelum rollback tidak dapat dipulihkan dan harus dinyatakan sebagai batas RPO operasional, bukan diklaim tersimpan.
14. Tidak ada retensi, firmware change, fallback simulasi, disk spool, atau teknologi di luar ruang lingkup yang masuk ke implementasi.
