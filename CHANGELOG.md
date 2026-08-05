# Changelog

## [0.1.2](https://github.com/skripsi-nyengir/platform/compare/v0.1.1...v0.1.2) (2026-08-05)


### Bug Fixes

* production health and backup deployment ([fc9ad6c](https://github.com/skripsi-nyengir/platform/commit/fc9ad6cc65eca83f119c6f41ad857fb3004276a5))

## [0.1.1](https://github.com/skripsi-nyengir/platform/compare/v0.1.0...v0.1.1) (2026-08-05)


### Bug Fixes

* **ci:** repair production deployment gates ([65f88ba](https://github.com/skripsi-nyengir/platform/commit/65f88ba6bccb0ecaa9dab4eb7c006f1673de23de))
* **ci:** repair production deployment gates ([029859c](https://github.com/skripsi-nyengir/platform/commit/029859c370e3aee8fd53ba1566b364dd239be5a3))

## 0.1.0 (2026-08-04)


### Features

* **alerts-ui:** paginated alert tables and denser overview ([e76d866](https://github.com/skripsi-nyengir/platform/commit/e76d8660537d14ddec0d9fefe4ceaab3bace2652))
* **bins:** append-only non-overlapping post-inference alert bins ([e866359](https://github.com/skripsi-nyengir/platform/commit/e866359c0e25a8c4afead443e6f09b60c4568b99))
* **bins:** derive post-inference bins from live inference ([f7e78f2](https://github.com/skripsi-nyengir/platform/commit/f7e78f2549e901fc9548bc8cf938740c35b16a31))
* **data:** export bounded data dialog rows as CSV ([744d8a0](https://github.com/skripsi-nyengir/platform/commit/744d8a01f52e09964a7171a0882abb6ab10204a5))
* **frontend:** /simulation page (model picker, replay, detection charts) ([a883509](https://github.com/skripsi-nyengir/platform/commit/a883509245a243fe77312213cf6005762ae85f9f))
* **frontend:** add switchable light and dark themes ([e445af2](https://github.com/skripsi-nyengir/platform/commit/e445af22eec3100f974ed30fbdcbb8650629a044))
* **frontend:** compact active-alerts section and human-readable WIB timestamps ([f8aec9d](https://github.com/skripsi-nyengir/platform/commit/f8aec9d1c0f6c424351d78183e37b2434e72742d))
* **frontend:** Datadog-style detection charts with reconstruction band ([7ccb190](https://github.com/skripsi-nyengir/platform/commit/7ccb19093f3e1e24e6725b9cc0af8068f2d4e5b6))
* **frontend:** events-per-interval view in operational panel ([62a1d04](https://github.com/skripsi-nyengir/platform/commit/62a1d0416a67c4d57357153c210cb78846406186))
* **frontend:** reconstruction chart and short live ranges ([f6b8813](https://github.com/skripsi-nyengir/platform/commit/f6b881344b7e148b3ae92132025a8d3dc740d384))
* **frontend:** refine telemetry dashboards ([9d98b60](https://github.com/skripsi-nyengir/platform/commit/9d98b6083b138ea5b05b0dc452c465abf3b2e313))
* **frontend:** server-computed sim metrics + all-events navigator ([c689209](https://github.com/skripsi-nyengir/platform/commit/c68920928db2dd6a1faf4d918a96bbed84bd8ae9))
* **live:** multi-bundle bootstrap and GPU runtime for point-threshold models ([67536fd](https://github.com/skripsi-nyengir/platform/commit/67536fd10f938bebdeff753bbbc792121b920235))
* **live:** real-time MQTT telemetry ingestion and scoring pipeline ([e561dca](https://github.com/skripsi-nyengir/platform/commit/e561dcace1e68bc8ded58146eedf81d59ce5722a))
* **live:** real-time MQTT telemetry ingestion and scoring pipeline ([3cb56d5](https://github.com/skripsi-nyengir/platform/commit/3cb56d5f4d071952d74ec991dea9f508ca77c7bf))
* **live:** store and serve reconstruction values for live inference ([b590d13](https://github.com/skripsi-nyengir/platform/commit/b590d13d35cd92fa219a52e34364e22a98e84e85))
* **model-evaluation:** show only the 5 real window-10 models ([dad9bed](https://github.com/skripsi-nyengir/platform/commit/dad9bede1ca618f1ba4e07c107bc0b23bb6719da))
* ship CPU production release pipeline ([78f4585](https://github.com/skripsi-nyengir/platform/commit/78f4585f1e6d2b2fce38aa1ff104e0280e5c5905))
* ship CPU production release pipeline ([2ff1913](https://github.com/skripsi-nyengir/platform/commit/2ff19134b8167049190f116e3826a63484199101))
* **sim:** add GET /api/injection-events ([75db057](https://github.com/skripsi-nyengir/platform/commit/75db057c8f2c7e753baf8f4959d785e766a8d763))
* **sim:** artifact-backed replay inference on GPU worker ([8506e37](https://github.com/skripsi-nyengir/platform/commit/8506e373167d100e9275415e00124d6cde581329))
* **sim:** bucket operational events per time interval ([d8fc13d](https://github.com/skripsi-nyengir/platform/commit/d8fc13d4c25b92a0c0460dd22efb964f16519cf4))
* **sim:** complete window-10 roster (conv1d/lstm/transformer) ([db0d60f](https://github.com/skripsi-nyengir/platform/commit/db0d60f0ff11fb518cc98c67e86669482f340102))
* **sim:** emit reconstruction band on artifact inference ([f281bc2](https://github.com/skripsi-nyengir/platform/commit/f281bc2b828582322caf7ca1908f1b576a7451e5))
* **sim:** serve inference-results and telemetry-history for the sim device ([25d65d4](https://github.com/skripsi-nyengir/platform/commit/25d65d421736998a7eb8eb50b24dcd8fbd6ff615))
* **sim:** sim model listing + active-model switch for the picker ([43dc417](https://github.com/skripsi-nyengir/platform/commit/43dc4170ff09d794e389cf654407fadb37f352dd))
* **sim:** window-10 models + research/operational metrics endpoint ([fee70c3](https://github.com/skripsi-nyengir/platform/commit/fee70c31c8d369cfec8b81f41d09f9d7b52e0cef))


### Bug Fixes

* **backend:** align readiness with migration head ([d740e40](https://github.com/skripsi-nyengir/platform/commit/d740e40a0e0a962200cce1492c1913d5e4722847))
* **ci:** install pinned runtime tooling ([6d96628](https://github.com/skripsi-nyengir/platform/commit/6d9662809a203b4e915a93b79c4692fdc7d1574c))
* **ci:** tolerate cross-runner screenshot rasterization ([7cb4427](https://github.com/skripsi-nyengir/platform/commit/7cb442735c89549571ff4d06be4f6e248152716c))
* **frontend:** guard crypto.randomUUID for insecure contexts ([1ded4af](https://github.com/skripsi-nyengir/platform/commit/1ded4af7a90353469fd561116454a14b973a79f0))
* **live:** order live processing by ingress_sequence to survive same-second collisions ([486eca1](https://github.com/skripsi-nyengir/platform/commit/486eca16014562d9b3e87d30ca180cea7ec7926f))
* **live:** recover from window desync instead of retrying forever ([0a077ae](https://github.com/skripsi-nyengir/platform/commit/0a077ae2aa7ad93e91a02faf76821d1b07f7f07f))
* **live:** surface scoring stalls in system health and log defer tracebacks ([fd270d8](https://github.com/skripsi-nyengir/platform/commit/fd270d8f11bfc477d9f1dcefdd3eb5e6760d851b))
