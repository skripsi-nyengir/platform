# LAMPIRAN

Lampiran ini menyajikan bukti terpilih untuk skripsi platform web terintegrasi pengelolaan telemetri IoT bivariat, EDA deskriptif, replay inferensi, dan pemantauan alert. Lampiran bukan tempat untuk menambah hasil eksperimen modeling. Transformer-AE, checkpoint, metadata pelatihan, dan kebijakan ambang p99,5 adalah masukan eksternal yang dibekukan pada batas integrasi platform. Bukti di bawah dibaca sesuai ruang lingkup rekamannya, bukan sebagai bukti kesiapan produksi, respons waktu nyata, skalabilitas, keamanan, kegunaan formal, aksesibilitas formal, atau keberhasilan inferensi dengan artefak model aktual.

Semua lokasi bukti ditulis sebagai path relatif terhadap root repositori. Salinan lampiran yang dapat dibagikan tidak memuat CSV mentah, payload manifest, secret, kredensial, nilai `.env`, path absolut pribadi, checkpoint, scaler, atau telemetri milik pihak tertentu. Nama screenshot pada Lampiran G adalah referensi bukti, bukan gambar yang dianggap sudah disisipkan ke naskah.

## Lampiran A. Manifest endpoint FastAPI terverifikasi

Manifest sumber yang diverifikasi berisi tepat 28 endpoint, terdiri atas 22 `GET` dan 6 `POST`. Sebanyak 26 endpoint memakai prefix `/api`; dua endpoint tanpa prefix tersebut adalah `/health` dan `/ready`. Tabel A.1 mencantumkan metode, path, handler, sumber relatif, dan tujuan ringkas tanpa menambah rute dari sumber lain.

**Tabel A.1 Manifest 28 endpoint FastAPI**

| No. | Metode | Path | Handler | Sumber relatif | Tujuan ringkas |
|---:|---|---|---|---|---|
| 1 | `GET` | `/api/alert-events` | `alert_events` | `backend/anomaly_backend/routes/alerts.py` | Membaca event lifecycle alert. |
| 2 | `GET` | `/api/alerts/current` | `current_alerts` | `backend/anomaly_backend/routes/alerts.py` | Membaca alert saat ini. |
| 3 | `POST` | `/api/alerts/{alert_id}/acknowledge` | `acknowledge_alert` | `backend/anomaly_backend/routes/alerts.py` | Mengakui alert. |
| 4 | `POST` | `/api/alerts/{alert_id}/resolve` | `resolve_alert` | `backend/anomaly_backend/routes/alerts.py` | Menyelesaikan alert. |
| 5 | `GET` | `/api/devices` | `devices` | `backend/anomaly_backend/routes/preview.py` | Membaca perangkat. |
| 6 | `GET` | `/api/models` | `models` | `backend/anomaly_backend/routes/preview.py` | Membaca model preview. |
| 7 | `POST` | `/api/model-activations` | `model_activation` | `backend/anomaly_backend/routes/preview.py` | Mencatat aktivasi model. |
| 8 | `POST` | `/api/replay-jobs` | `create_replay_job` | `backend/anomaly_backend/routes/preview.py` | Membuat job replay. |
| 9 | `GET` | `/api/replay-jobs/{job_id}` | `replay_job` | `backend/anomaly_backend/routes/preview.py` | Membaca status job replay. |
| 10 | `GET` | `/api/eda/periods` | `eda_periods` | `backend/anomaly_backend/routes/eda.py` | Membaca periode EDA terbit. |
| 11 | `POST` | `/api/eda/compute` | `eda_compute` | `backend/anomaly_backend/routes/eda.py` | Mengajukan komputasi EDA kustom. |
| 12 | `GET` | `/api/eda/jobs/{job_id}` | `eda_job` | `backend/anomaly_backend/routes/eda.py` | Membaca job EDA. |
| 13 | `GET` | `/api/eda/runs/{run_id}` | `eda_run` | `backend/anomaly_backend/routes/eda.py` | Membaca run EDA terbit. |
| 14 | `GET` | `/api/eda/runs/{run_id}/sections/{section}` | `eda_section` | `backend/anomaly_backend/routes/eda.py` | Membaca satu section EDA. |
| 15 | `GET` | `/api/inference-results` | `inference_results` | `backend/anomaly_backend/routes/inference.py` | Membaca hasil inferensi. |
| 16 | `GET` | `/api/injection-events` | `injection_events` | `backend/anomaly_backend/routes/injection.py` | Membaca event injeksi simulasi. |
| 17 | `GET` | `/api/model-evaluations` | `list_model_evaluations` | `backend/anomaly_backend/routes/evaluations.py` | Membaca daftar evaluasi model. |
| 18 | `GET` | `/api/model-evaluations/{version:path}` | `model_evaluation` | `backend/anomaly_backend/routes/evaluations.py` | Membaca evaluasi suatu versi model. |
| 19 | `GET` | `/api/model-registry` | `model_registry` | `backend/anomaly_backend/routes/model_registry.py` | Membaca registry model. |
| 20 | `GET` | `/api/offline-evaluations` | `offline_evaluations` | `backend/anomaly_backend/routes/offline_evaluations.py` | Membaca evaluasi offline. |
| 21 | `GET` | `/api/simulation/models` | `simulation_models` | `backend/anomaly_backend/routes/simulation.py` | Membaca model simulasi. |
| 22 | `POST` | `/api/simulation/active-model` | `set_active_model` | `backend/anomaly_backend/routes/simulation.py` | Menetapkan model simulasi aktif. |
| 23 | `GET` | `/api/simulation/metrics` | `simulation_metrics` | `backend/anomaly_backend/routes/simulation.py` | Membaca metrik simulasi. |
| 24 | `GET` | `/health` | `health` | `backend/anomaly_backend/routes/system.py` | Membaca health layanan. |
| 25 | `GET` | `/ready` | `ready` | `backend/anomaly_backend/routes/system.py` | Membaca readiness layanan. |
| 26 | `GET` | `/api/system/status` | `system_status` | `backend/anomaly_backend/routes/system.py` | Membaca status sistem. |
| 27 | `GET` | `/api/telemetry/latest` | `latest_telemetry` | `backend/anomaly_backend/routes/telemetry.py` | Membaca telemetri terbaru. |
| 28 | `GET` | `/api/telemetry/history` | `telemetry_history` | `backend/anomaly_backend/routes/telemetry.py` | Membaca riwayat telemetri. |

Manifest ini mengecualikan route dokumentasi atau OpenAPI bawaan framework, duplikasi `ANY` tanpa sumber handler, path client atau mock dengan parameter `:param`, serta path lifecycle mock alternatif. Pengecualian tersebut mencegah route framework, frontend, dan mock dihitung sebagai endpoint FastAPI sumber-backed.

Lima operasi berikut adalah subset EDA dengan detail kontrak yang diverifikasi oleh `docs/eda-v3-operations.md`.

**Tabel A.2 Subset lima operasi EDA terverifikasi**

| Metode dan path | Kontrak ringkas | Hasil atau status yang mungkin | Batas bukti |
|---|---|---|---|
| `GET /api/eda/periods?period_kind=daily|weekly|monthly` | Membaca periode aktif yang sudah terbit penuh. `full_range` tidak diterima pada operasi ini. | Daftar periode atau sumber tidak tersedia. | Tidak membuktikan adanya rute di domain selain EDA. |
| `POST /api/eda/compute` | Menerima range B02 kustom dengan perangkat, zona waktu, jenis periode `custom`, `from`, dan `to`. | `200` untuk cache hit immutable, atau `202` untuk job baru atau koalesensi key aktif. | Komputasi kustom adalah `algorithm-equivalent range computation`, bukan parity publikasi rentang penuh. |
| `GET /api/eda/jobs/{job_id}` | Membaca job EDA. | `queued`, `running`, `succeeded`, atau `failed`. | Status job tidak menyatakan scheduler berjalan karena tidak ada scheduled EDA job. |
| `GET /api/eda/runs/{run_id}` | Membaca run terbit penuh beserta metadata sebelas section. | Run immutable yang diterbitkan. | Run kustom tidak dapat disebut hasil kanonis. |
| `GET /api/eda/runs/{run_id}/sections/{section}` | Membaca satu section. | `complete`, `not_eligible`, atau `failed`. | `not_eligible` adalah hasil diagnostik dengan reason code, bukan payload statistik kosong. |

Untuk subset EDA, `404` berarti job, run, atau section tidak dikenal atau belum terbit; `409` berarti konflik lifecycle tersimpan; `422` berarti validasi ketat gagal; `429` hanya berlaku pada custom cache miss yang berbeda ketika 32 job custom aktif atau antre; dan `503` `eda-source-unavailable` berarti snapshot sumber lengkap yang cocok tidak dapat dipilih. Detail ini bersumber dari `docs/eda-v3-operations.md`; Tabel A.1 menjadi sumber manifest lengkap untuk seluruh 28 endpoint.

## Lampiran B. Ringkasan kontrak ketat, problem details, dan domain waktu

Kontrak backend memakai `StrictModel` pada `backend/anomaly_backend/contracts.py`. Konfigurasinya adalah `strict=True`, `extra="forbid"`, dan `allow_inf_nan=False`. Artinya, konversi tipe longgar yang tidak diizinkan, properti tambahan, `NaN`, dan nilai infinit ditolak pada batas kontrak. Field tertentu dapat bersifat opsional dalam arti boleh tidak dikirim, tetapi tidak boleh dikirim sebagai `null`. Pemeriksaan domain melengkapi bentuk data ini, misalnya `from` harus lebih awal daripada `to`, batas rentang replay adalah 31 hari, jumlah data respons dibatasi, cursor harus sesuai scope, dan batas waktu window harus konsisten dengan timestamp skor.

**Tabel B.1 Ringkasan kontrak dan penanganan masalah**

| Aspek | Bentuk yang diterapkan | Makna untuk platform | Batas klaim |
|---|---|---|---|
| Validasi ketat | Tipe strict, field ekstra dilarang, nilai nonfinite ditolak | Request dan response memiliki bentuk yang dapat diperiksa. | Bukan pembuktian ketahanan terhadap seluruh input berbahaya. |
| Kontrak EDA | Run memiliki 11 section, identitas sumber, konfigurasi, dan algoritme harus konsisten. | Hasil EDA dapat ditelusuri pada run dan section. | Bukan pembuktian kualitas ilmiah statistik EDA. |
| `not_eligible` | Section diagnostik membawa reason code serta detail tanpa payload statistik. | Ketiadaan statistik tidak dibaca sebagai nol. | UI harus tetap meneruskan reason code secara jelas. Temuan F3-2 menunjukkan hal ini belum terpenuhi. |
| Problem details | `application/problem+json` dengan `type`, `title`, `status`, `detail`, `instance`, `request_id`, dan `errors` jika relevan. | Error API dapat dikorelasikan dan dibaca konsisten. | `request_id` bukan autentikasi, otorisasi, atau audit keamanan. |
| Pemetaan masalah | `InvalidQuery`, `NotFound`, `Conflict`, request validation, dependency, dan SQLAlchemy dipetakan ke respons terstruktur. | Kontrak membedakan masalah input, data tidak ditemukan, konflik, dan layanan sementara tidak tersedia. | Tabel ini merangkum kategori lintas domain; detail per-rute tetap mengikuti kontrak masing-masing. |

Waktu corpus dan waktu operasional tidak ekuivalen. `HistoricalDateTime` merepresentasikan kalender historis `Asia/Jakarta` tanpa offset. Bentuk ini dipakai untuk telemetri, rentang corpus, batas window, serta waktu episode alert. `OperationalInstant` mewajibkan RFC3339 UTC dengan akhiran `Z` dan dipakai untuk job dibuat, job dimulai atau selesai, lease, heartbeat, command, dan event lifecycle. Pemisahan ini mencegah waktu fenomena dalam data disamakan dengan waktu tindakan aplikasi. Ia tidak membuktikan seluruh masalah zona waktu pada semua client telah diuji.

## Lampiran C. Topologi Docker Compose yang aman dibagikan

Topologi berikut diringkas dari `compose.yaml`. Ringkasan sengaja tidak menyalin nilai variabel lingkungan, nama basis data, kata sandi, port host, `.env`, atau path host. Bind mount eksternal hanya dijelaskan menurut kelas data dan mode aksesnya. Pada berkas sumber, nilai privat dipasok melalui lingkungan deployment dan tidak dicetak dalam lampiran.

**Tabel C.1 Layanan, jaringan, dan fungsi**

| Kelompok | Service Compose | Peran | Jaringan atau profile | Batas penyajian aman |
|---|---|---|---|---|
| Persistence | `db` | PostgreSQL dengan TimescaleDB dan volume `db_data`. | `backend` internal. | Tidak mencantumkan kredensial atau nilai koneksi. |
| Bootstrap | `migrate`, `seed` | Migrasi Alembic lalu inisialisasi data. | `backend`; bergantung pada kesehatan `db` dan keberhasilan tahap sebelumnya. | Menjelaskan urutan bootstrap lokal, bukan rollout produksi. |
| Aplikasi | `api` | FastAPI dan health check internal. | `backend`; menunggu `seed`. | Tidak memuat konfigurasi rahasia. |
| Replay | `worker` | Memproses job replay dan jalur artifact-backed bila artefak tersedia. | `backend`; mount artefak container `/models:ro`. | Hanya kontrak mount baca saja. Checkpoint aktual tidak dibagikan dan tidak tersedia pada checkout. |
| EDA | `eda-worker`, `eda-cli` | Mengklaim job EDA dan menyediakan CLI operator. | `backend`; `eda-cli` berada pada profile `ops`. | Batas memori worker yang dikonfigurasi ialah `2147483648` byte, bukan hasil kapasitas umum. |
| Import | `import`, `eda-import`, `sim-import` | Import corpus legacy, sumber EDA, dan corpus simulasi yang berbeda. | `backend`; masing-masing memakai profile operasi. | Sumber dipasang read-only, tanpa menampilkan path host, CSV, manifest payload, atau data injeksi. |
| Pintu masuk web | `nginx` | Menyajikan frontend dan menjembatani layanan web ke jaringan internal. | `public` dan `backend`; layanan lain tidak berada pada `public`. | Deskripsi jaringan bukan audit keamanan atau bukti TLS, WAF, maupun hardening. |

`backend` dideklarasikan internal dan `public` hanya dihubungkan ke `nginx`. `migrate` menjalankan upgrade sampai head, `seed` menunggu migrasi sukses, sedangkan API dan worker menunggu seed. `eda-worker` memiliki lease, heartbeat, batas percobaan, dan batas waktu melalui konfigurasi lingkungan. Urutan ini membantu menjelaskan dependensi lokal, tetapi tidak menghilangkan seluruh risiko startup atau operasi lingkungan lain. Layanan import dan CLI adalah profile operator, bukan scheduler kontinu.

## Lampiran D. Identitas rilis EDA kanonis dan logical key

Identitas berikut berasal dari `docs/eda-v3-operations.md` dan direkam lagi pada `.omo/evidence/task-21-canonical-integration.txt`. Rilis dapat disebut hasil parity terbit hanya apabila `canonical_release=true` dan `period_kind=full_range`. Label yang tepat adalah `published v3 release`. Hasil daily, weekly, monthly, atau custom harus diberi label `algorithm-equivalent range computation`, walaupun menggunakan algoritme dan identitas sumber yang sama.

**Tabel D.1 Identitas rilis B02 v3 yang dibekukan**

| Field | Nilai persis |
|---|---|
| Device | `b02f3872-39a2-4b6f-a4ec-045a287fde4b` |
| Zona waktu | `Asia/Jakarta` |
| Versi algoritme | `bivariate_b02f3872_eda_v3+vendor.37565a5341be56e9a0a88d55ce1dbfe6ae25b0fe` |
| Hash konfigurasi | `1081a79b8452075df4baf2f88f6ed3094f90286c0e17ee7d666e0b8072ba8452` |
| SHA-256 sumber | `b8ae739a427681735792f02eea14dd8b7fc53f5265630a7e9a62b846f7b8040f` |
| SHA-256 manifest sumber | `196178e7424bd2e92268606f0ef33237d2329bdfefd9dce592283c07a697d486` |
| Alembic head | `20260726_0003` |
| Seed | `20260724` |
| Logical key proof kanonis | `192ff4e9bf008f0ff8075466b2891d376de2c9b2b9a8094f7add3e7acbfa5c3f` |

Logical key adalah SHA-256 dari JSON kanonis atas `(source_sha256, from_ts, to_ts, period_kind, algorithm_version, config_hash)`. Trigger dan UUID snapshot sengaja tidak menjadi bagian key. Hasil immutable yang terbit lengkap dengan 11 section menjadi cache hit, sedangkan request yang memakai key sama saat job masih `queued` atau `running` akan berkoalesensi. Logical key ini menautkan satu komputasi dengan identitasnya, bukan checksum checkpoint model dan bukan pengganti manifest artefak modeling.

## Lampiran E. Hasil proof integrasi EDA kanonis

Proof berikut berstatus `PASS`, direkam pada 27 Juli 2026 dalam `.omo/evidence/task-21-canonical-integration.txt`. Perintah proof memakai basis data terisolasi acak, sumber authority read-only, migrasi, import, komputasi rentang penuh, pembacaan API, reimport idempoten, dan cleanup. Path absolut pada perintah asli tidak dicantumkan ulang karena bukan bahan lampiran yang aman dibagikan.

**Tabel E.1 Hasil persis proof kanonis**

| Indikator | Nilai persis | Batas interpretasi |
|---|---:|---|
| Exit code | `0` | Keberhasilan perintah yang direkam. |
| Pytest kanonis | `2 passed in 2147.53s (0:35:47)` | Dua test marker kanonis, bukan seluruh suite atau SLA. |
| Status parity | `pass` | Hanya bagi identitas rilis dan full range pada Tabel D.1. |
| Runtime parity | `1030.4646068310249 seconds` | Bukan waktu respons API atau kinerja realtime. |
| Runtime worker full range terisolasi | `989.6441833919962 seconds` | Bukan throughput kontinu atau benchmark deployment lain. |
| Peak RSS | `1,251,999,744 bytes` | Di bawah limit `2,147,483,648 bytes` pada proof tersebut saja. |
| Raw rows | `6,931,792` | Jumlah sumber kanonis, bukan volume perangkat atau domain umum. |
| Exact pairs | `3,460,865` | Pairing timestamp eksak, bukan nearest-time join atau label anomali. |
| Screened pairs | `3,405,332` | Hasil screening rilis tertentu, bukan ground truth normal. |
| Excluded pairs | `55,533` | Selisih audit pairing, bukan tingkat kegagalan sensor universal. |
| Reimport | `idempotent noop: true` | Skenario import identik pada proof. |
| Scope yang dipangkas | Period matrix, cache-hit POST, sumber korup, repeated CLI backfill, dan interupsi worker | Tidak diklaim telah diuji oleh task ini. |

**Tabel E.2 Hash sebelas section yang diterbitkan**

| Section | SHA-256 payload |
|---|---|
| `audit_metadata` | `36c66b76437fa61d3fee9214249b5f792d1c6961f4072ac1ad65013f0225f6dd` |
| `change_points` | `8ebf5d4a097c1a4a3fe31e4ee87f06f1bf85303dee5735187d1f7903341c0fd9` |
| `joint_density` | `83c9f543befb735b3ac4cd2faca778099cbe3a3e4601ab32bc4927d00a1decd3` |
| `quality_excerpt` | `c8ddcdb3fff1dfaa385d2670a6b6f4d5afab6848c76bf6861b95f246a4fb02ef` |
| `quality_overview` | `1d6a2f9ff2bd556ee5dfaaf6a2bb86bb725e99ff782153792d6cdb740f639c76` |
| `relationships` | `799e9f130b63ef6207da21b8fe4e14a92ef138f2ecad73c37a0d2fcd0363e233` |
| `stationarity` | `0e361968060f59397c6ae51bdff6373df72946e2e15c9ea0a194edc97cfe6f1a` |
| `temporal_coverage` | `e220c21d1a9628a5aa34350df60de9d49adeb99a0a7124ca945bc8921213104c` |
| `temporal_distribution` | `f4198601ff80f094542b20010e1fe2baeb3c7e8bf6a9ed47284f4fd0a396757f` |
| `uncertainty` | `54d6ab6f533d0f33baa8df139818aa9c2d5d4b6e9e09be66ae3c7e921ab92844` |
| `univariate` | `947487c3ed5bd711e5765ee5c82bfbdd46630a0179cd62e6f052c74d78fbf307` |

Task yang sama merekam cleanup tanpa basis data `task21_*` atau `task21_verify_*` dan tanpa container compose run setelah selesai. Layanan demo jangka panjang tetap berjalan. Packaging proof mencatat `eda-import` menggunakan target `eda-worker`, `eda-cli` tetap pada runtime, regresi toolchain `5 passed, 2 skipped`, koleksi marker kanonis tepat dua test, serta suite backend ordinary terisolasi `232 passed, 2 skipped, 2 canonical deselected in 50.92s`. Rekaman juga mencatat basedpyright scope task tanpa error, tetapi terdapat tiga baseline error di luar change set. Catatan tersebut tidak mengubah status proof kanonis atau menyatakan seluruh repositori bebas cacat.

## Lampiran F. Ringkasan verifikasi backend, frontend, build, dan E2E

**Tabel F.1 Matriks bukti verifikasi otomatis**

| Lapisan | Bukti dan hasil | Peringatan atau batas yang wajib terlihat | Path bukti |
|---|---|---|---|
| Kontrak backend EDA | `28 passed in 0.17s`, 11 section, 13 eligibility reason. | Suite fokus kontrak, bukan seluruh backend dan bukan uji kualitas statistik. | `.omo/evidence/task-4-backend-contracts.txt` |
| Proof EDA kanonis | `2 passed in 2147.53s`, parity `pass`, ordinary backend `232 passed, 2 skipped, 2 canonical deselected`. | Scope hanya release dan skenario yang direkam; beberapa skenario dipangkas. | `.omo/evidence/task-21-canonical-integration.txt` |
| Kontrak frontend | 3 test file dan `13 passed`. | Node memberi `ExperimentalWarning` karena localStorage tidak memiliki localstorage file. | `.omo/evidence/task-5-frontend-contracts.txt` |
| Test halaman EDA | `EdaPage.test.tsx`: 1 file dan `5 passed`; kelompok EDA, charts, pages: 21 file dan `137 passed`. | jsdom memperingatkan `HTMLCanvasElement.getContext()` belum diimplementasikan tanpa paket canvas. Test lulus bukan bukti rendering browser produksi. | `.omo/evidence/task-19-eda-page.txt` |
| Test preview dan query inferensi | 2 test file dan `8 passed`. | Peringatan localStorage Node tetap tercatat. | `.omo/evidence/task-19-eda-page.txt` |
| Build frontend | `tsc -b && vite build` berhasil, 2.332 modul ditransformasi, selesai dalam `497ms`. | Berkas JS utama `1,677.75 kB`, gzip `496.49 kB`; Vite memperingatkan chunk lebih besar dari 500 kB setelah minifikasi. Build sukses bukan klaim optimasi performa. | `.omo/evidence/task-19-eda-page.txt` |
| E2E frontend | Status run terakhir `passed`. | Helper memakai `AppMockScenario`, parameter `__scenario`, mock state, dan kegagalan fetch deterministik. Bukti hanya perjalanan frontend terskenario, bukan integrasi FastAPI, database, worker, atau artefak model nyata. | `frontend/test-results/.last-run.json`, `frontend/tests/e2e/helpers.ts`, `frontend/tests/e2e/` |

Seluruh hasil F hanya menjelaskan scope test yang direkam. `passed` pada E2E tidak boleh disingkat menjadi “integrasi ujung ke ujung lulus” tanpa kata `mock`. Peringatan localStorage dan canvas juga tidak disembunyikan. Keduanya tidak otomatis menjadi defect produk, tetapi menandai batas lingkungan pengujian yang berbeda dari browser aktual.

## Lampiran G. QA manual langsung dan status penerimaan

Verdict QA manual adalah **`REJECT`**. Status ini berdiri bersama hasil automated test yang lulus dan tidak boleh diturunkan menjadi catatan kosmetik. Rekaman QA membuktikan beberapa perilaku baik pada skenario lokal, tetapi dua blocker menyentuh kontrol rentang dan transparansi status statistik sehingga penerimaan antarmuka menyeluruh ditolak.

**Tabel G.1 Bukti baik yang diamati**

| Area | Observasi | Scope dan batas |
|---|---|---|
| Empty precompute | Heading dan instruksi untuk memakai rentang kustom serta menghitung EDA terlihat, tanpa panel kosong tanpa konteks. | Skenario URL default. |
| Existing 30 hari | 9 section lengkap merender chart atau tabel berisi, 24 permukaan chart atau image tidak nol, dan 2 section expected `not_eligible`. | Run kustom, bukan proof kanonis full range. |
| Provenance dan disclaimer | Label `Komputasi rentang setara-algoritme` serta tiga disclaimer EDA terlihat. | Bukti pemisahan EDA dari ground truth, kausalitas, dan deteksi model pada flow yang diperiksa. |
| Responsif | Tidak ada page horizontal overflow pada 1440, 1280, dan 390 pixel. Tabel mobile memakai `overflow-x:auto` lokal. | Bukan uji semua perangkat atau ukuran viewport. |
| Keyboard dan focus | Tab order, lima anchor, dialog focus, Escape, focus return, dan retry via Enter diamati. | Bukan sertifikasi aksesibilitas formal. |
| Console normal | `0 errors, 0 warnings` pada flow default, compute, existing run, 1280, 390, dan datetime control. | Bukan bukti tidak ada error untuk seluruh penggunaan. |

**Tabel G.2 Blocker QA yang menyebabkan `REJECT`**

| ID | Kondisi dan hasil yang diharapkan | Observasi | Dampak | Berkas bukti relatif |
|---|---|---|---|---|
| F3-1 | Pada custom range 1440px, pengubahan **Dari** harus menyimpan timestamp pilihan dan menyinkronkan URL serta control state. | Input tanggal yang dicoba berubah atau kembali menjadi `2025-06-23`; URL mula-mula mempertahankan nilai lama lalu menghapus parameter `from`. | Pengguna tidak dapat memastikan range yang akan dihitung. | `.omo/evidence/task-F3-manual-qa-datetime-control-defect.png`; `.omo/evidence/task-F3-manual-qa-datetime-control-defect.txt` |
| F3-2 | Kartu `not_eligible` harus menyatakan reason API secara eksplisit. | Kartu uncertainty dan change points hanya menyatakan belum memenuhi syarat statistik, tanpa `block_longer_than_run` dan `insufficient_daily_medians`. Outcome eligibility benar, tetapi diagnosis tidak cukup transparan. | Reason code tidak diteruskan dari kontrak API ke presentasi UI secara memadai. | `.omo/evidence/task-F3-manual-qa-not-eligible-uncertainty.png`; `.omo/evidence/task-F3-manual-qa-not-eligible-change-points.png`; `.omo/evidence/task-F3-manual-qa-section-uncertainty.txt`; `.omo/evidence/task-F3-manual-qa-section-change-points.txt` |

Rekaman utama berada pada `.omo/evidence/task-F3-manual-qa-summary.txt`. Rekaman itu juga mencatat transisi job `queued`, `running`, `running`, `succeeded` dan cache hit pada pengulangan, tetapi fakta tersebut tidak menggugurkan `REJECT`. Tidak ada screenshot yang dianggap tersemat dalam lampiran ini sampai pemilik naskah menyetujui penyisipan gambar asli beserta caption dan scope QA-nya.

## Lampiran H. Kontrak artefak eksternal yang dapat dibagikan

Skrip platform memiliki batas kontrak terhadap artefak eksternal. Artefak yang diharapkan berada di mount container baca saja `/models:ro`, direferensikan menurut versi yang diregistrasi, dan diverifikasi terhadap manifest sebelum digunakan oleh worker artifact-backed. Lampiran ini hanya menjelaskan field kontrak. Ia tidak menyertakan checkpoint, manifest artefak, bobot, scaler, isi telemetri, atau checksum artefak model karena artefak aktual tidak tersedia pada checkout dan tidak ada checksum yang sah untuk dicetak.

**Tabel H.1 Field kontrak artefak yang dapat dibagikan**

| Field atau aturan | Fungsi pada batas integrasi | Status bukti dan batas |
|---|---|---|
| Model family dan registered version | Memilih identitas artefak yang dikonsumsi worker. | Metadata platform dapat dibahas tanpa menyatakan pemilihan model oleh skripsi ini. |
| `runtime_kind` dan `score_provenance` | Memisahkan `artifact` dengan `artifact_backed` dari `preview_simulator` dengan `simulated_preview`. | Preview tidak boleh ditampilkan sebagai hasil artefak nyata. |
| Urutan kanal, window, stride, dan semantik timestamp skor | Menentukan bentuk input dan hubungan skor dengan window. | Field kontrak, bukan hasil pelatihan atau evaluasi model. |
| Kebijakan threshold | Meneruskan kebijakan ambang yang dibekukan ke replay. | Kebijakan p99,5 dimiliki jalur modeling eksternal; platform tidak menghitung, mengoptimalkan, atau membuktikan universalitasnya. |
| `manifest_sha256` artefak | Digunakan worker untuk membandingkan hash berkas sebelum load. | Nilai aktual tidak tersedia dan tidak dipalsukan pada lampiran ini. |
| Lokasi artefak relatif | Versi terdaftar dipetakan ke `model.pt` di bawah `/models`. | Internal container path saja; tidak ada path host privat. |
| Pemuatan | `weights_only=True`, evaluasi tanpa gradien, dan CUDA diwajibkan oleh rancangan worker. | Kode dapat ditelusuri, tetapi tidak ada bukti checkpoint nyata dimuat, hash lolos, GPU tersedia, atau inferensi artifact-backed dieksekusi. |
| Scaler dan preprocessing snapshot | Menjaga kompatibilitas input replay dengan corpus terkait. | Objek scaler dan nilainya tidak dibagikan dalam lampiran. |

Kepemilikan dibatasi secara tegas. Skripsi platform mengelola mount, registry, kontrak, provenance, replay, dan penyajian status. Skripsi modeling memiliki kepemilikan atas Transformer-AE, pemilihan atau pelatihan model, validitas checkpoint, dan p99,5. Tidak adanya artefak aktual merupakan batas bukti, bukan bukti bahwa integrasi artifact-backed telah berhasil berjalan.

## Lampiran I. Matriks traceability rumusan masalah, tujuan, bukti, dan simpulan

Matriks ini menautkan tiga rumusan masalah pada tujuan, komponen, bukti, pembahasan Bab IV, dan butir simpulan Bab V yang telah difinalisasi. Matriks menjaga agar kesimpulan tidak membawa klaim baru atau metrik modeling.

**Tabel I.1 Traceability skripsi platform**

| Rumusan masalah | Tujuan terkait | Komponen dan luaran platform | Bukti utama | Pembahasan Bab IV | Arah simpulan Bab V | Batas yang wajib dipertahankan |
|---|---|---|---|---|---|---|
| RM-1: Bagaimana merancang dan membangun platform web terintegrasi untuk telemetri, EDA, inferensi artefak eksternal, dan alert yang terpisah serta dapat ditelusuri? | Tujuan 1: menghasilkan rancangan dan implementasi integrasi telemetri, EDA, inferensi artefak eksternal, dan alert. | Compose, FastAPI, PostgreSQL atau TimescaleDB, worker import, EDA, replay, tujuh layar SPA, provenance, dan lifecycle alert. | `compose.yaml`; `docs/skripsi-platform/03-bab-iii-kegiatan-pelaksanaan.md`; `docs/skripsi-platform/04-bab-iv-analisis-dan-pembahasan.md`; `docs/eda-v3-operations.md`. | 4.1 arsitektur, 4.3 import EDA dan provenance, 4.4 replay dan alert, 4.5 SPA. | Kesimpulan 1 dan 2: platform terintegrasi dirancang dan diimplementasikan dengan batas ownership. | Tidak menyatakan model terbaik, inferensi live, realtime, scalable, secure, usable, atau accessible. |
| RM-2: Bagaimana menerapkan kontrak API dan data ketat, persistence, worker, dan publikasi transaksional untuk menjaga konsistensi hasil? | Tujuan 2: mengimplementasikan layanan, kontrak ketat, provenance, dan publikasi transaksional. | `StrictModel`, problem details, domain waktu, snapshot, logical key, staging replay, publikasi hasil serta event alert. | `backend/anomaly_backend/contracts.py`; `backend/anomaly_backend/problems.py`; `docs/eda-v3-operations.md`; `.omo/evidence/task-4-backend-contracts.txt`; `.omo/evidence/task-21-canonical-integration.txt`. | 4.2 kontrak dan problem details, 4.3 provenance EDA, 4.4 staging, transaksi, dan lifecycle alert. | Kesimpulan 2: desain menggabungkan kontrak, worker, persistence, dan provenance. | Konsistensi dibahas dalam scope implementasi dan transaksi database, bukan jaminan availability, keamanan, atau exactly-once lintas infrastruktur. |
| RM-3: Bagaimana hasil verifikasi melalui proof EDA, test otomatis, build, E2E mock, dan QA manual, termasuk keterbatasan serta cacat? | Tujuan 3: mendeskripsikan dan mengevaluasi bukti terbatas beserta cacat yang ditemukan. | Proof kanonis, test kontrak backend dan frontend, test halaman EDA, build, Playwright mock, serta QA manual. | `.omo/evidence/task-21-canonical-integration.txt`; `.omo/evidence/task-4-backend-contracts.txt`; `.omo/evidence/task-5-frontend-contracts.txt`; `.omo/evidence/task-19-eda-page.txt`; `.omo/evidence/task-F3-manual-qa-summary.txt`; `frontend/test-results/.last-run.json`. | 4.6 verifikasi otomatis, 4.7 QA manual, 4.8 pembahasan terpadu, 4.9 keterbatasan. | Kesimpulan 3 sampai 5: proof EDA dan test memberi bukti terbatas, E2E memakai mock, QA `REJECT`, dan batas klaim dipertahankan. | Tidak menyembunyikan warning test, mock boundary, ketiadaan artefak aktual, atau blocker F3-1 dan F3-2. |

Sumber pengendali matriks adalah Bab I, Bab III, Bab IV, Bab V, Lampiran A-H, `compose.yaml`, `docs/eda-v3-operations.md`, serta `.omo/evidence/task-4-backend-contracts.txt`, `.omo/evidence/task-5-frontend-contracts.txt`, `.omo/evidence/task-19-eda-page.txt`, `.omo/evidence/task-21-canonical-integration.txt`, dan `.omo/evidence/task-F3-manual-qa-summary.txt`. Apabila revisi endpoint, artefak model aktual, atau bukti QA perbaikan tersedia kemudian, perubahan hanya boleh dibuat dengan menambah bukti baru yang dapat ditelusuri. Bukti baru tidak boleh menghapus catatan keterbatasan historis tanpa menyatakan tanggal, scope, dan hasil verifikasi penggantinya.
