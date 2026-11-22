
// AASHA Offline Service Worker (0 Cloud Dependencies)
const CACHE_NAME = 'aasha-field-cache-v1';
const ASSETS_TO_CACHE = ["NCERT-G06-MATH-CH07-FRACTIONS_Interactive_v7_multimodal_field.html", "NCERT-G06-SCI-CH04-SORTING-MATERIALS_Interactive_v7_multimodal_field.html", "NCERT-G07-MATH-CH02-FRACTIONS-DECIMALS_Interactive_v7_multimodal_field.html", "NCERT-G07-SCI-CH04-HEAT_Interactive_v7_multimodal_field.html", "NCERT-G08-MATH-CH01-RATIONAL-NUMBERS_Interactive_v7_multimodal_field.html", "NCERT-G08-SCI-CH11-FORCE-PRESSURE_Interactive_v7_multimodal_field.html", "NCERT-G09-MATH-CH02-POLYNOMIALS_Interactive_v7_multimodal_field.html", "NCERT-G09-SCI-CH08-MOTION_Interactive_v7_multimodal_field.html", "NCERT-G10-MATH-CH03-PAIR-LINEAR-EQUATIONS_Interactive_v7_multimodal_field.html", "NCVET-PSSCIVE-L4-AGRI-PRECISION-DRIP-JAL-SEVA_Interactive_v7_multimodal_field.html", "teacher_field_dashboard.html"];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[ServiceWorker] Pre-caching offline modules');
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
