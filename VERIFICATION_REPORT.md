# AASHA Verification Report — Phase F/G Offline PWA Service Worker Precache & Release Readiness
- **Timestamp**: `2026-11-14T14:53:21.414168+00:00`
- **Branch**: `aios/v2-bootstrap`
- **Completed Focus Unit**: `PHASE_F_G_END_TO_END_RELEASE_READINESS_AND_OFFLINE_PWA_SERVICE_WORKER_PRECACHE_VERIFICATION`
- **Service Worker (`sw.js`)**: `CACHE_VERSION = "aasha-student-pwa-v2.2"`, precaching 26 legacy bundles + 26 paired `*_Learning.html` & `*_Arena.html` modules + `/teas_content.db.gz` + `/api/catalogue/learn-arena-modules`.
- **Merkle Cache Manifest (`sw_cache_manifest.json`)**: `53` verified on-disk assets (`47` HTML5 modules, all `< 20 MiB`, `0` external URLs), Merkle root `2f6d7043965b84876e6f8fb89bed9b7c38f059647a0f02ba0c0d435f493abf4c`.
- **Next Focus Unit**: `PHASE_G_TEACHER_STUDIO_BATCH_PDF_UPLOAD_AND_LIVE_PREVIEW_BRIDGE`
