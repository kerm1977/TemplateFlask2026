// sw.js

// Nombre del caché para la aplicación
const CACHE_NAME = 'orange-sys-v1';

// Recursos básicos para cachear inmediatamente
const ASSETS_TO_CACHE = [
    '/',
    '/static/main.css',
    '/static/js/validaciones.js',
    '/static/js/eye.js',
    '/static/js/bootstrap.bundle.min.js',
    '/static/css/bootstrap/bootstrap.min.css',
    '/static/img/default.png'
];

// Evento de instalación: se encarga de precachear los recursos estáticos
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
});

// Evento de activación: limpia cachés antiguos si se actualiza la versión
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cache) => {
                    if (cache !== CACHE_NAME) {
                        return caches.delete(cache);
                    }
                })
            );
        })
    );
});

// Evento de recuperación (fetch): sirve recursos desde el caché o la red
self.addEventListener('fetch', (event) => {
    event.respondWith(
        caches.match(event.request).then((response) => {
            // Retorna el recurso desde el caché si existe, de lo contrario lo busca en la red
            return response || fetch(event.request);
        }).catch(() => {
            // Opcional: podrías retornar una página de "Offline" aquí
        })
    );
});