// sw.js

// Aumentamos la versión del caché para forzar la actualización en los navegadores de los usuarios
const CACHE_NAME = 'orange-sys-v2';

// Recursos básicos y rutas principales para cachear en la instalación inicial
const ASSETS_TO_CACHE = [
    '/',
    '/login',
    '/home',
    '/dashboard',
    '/perfil',
    '/static/css/main.css',
    '/static/js/validaciones.js',
    '/static/js/eye.js',
    '/static/js/bootstrap.bundle.min.js',
    '/static/css/bootstrap/bootstrap.min.css',
    '/static/img/default.png'
];

// Evento de instalación: se encarga de precachear los recursos estáticos y rutas principales
self.addEventListener('install', (event) => {
    // skipWaiting fuerza a que el nuevo Service Worker se active inmediatamente
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('Caché abierto. Precacheando recursos iniciales...');
            // Utilizamos addAll pero controlamos errores individuales si falta algún archivo
            return Promise.allSettled(
                ASSETS_TO_CACHE.map(url => cache.add(url).catch(err => console.log(`Fallo al cachear ${url}:`, err)))
            );
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
                        console.log('Borrando caché antiguo:', cache);
                        return caches.delete(cache);
                    }
                })
            );
        }).then(() => {
            // Toma el control de todas las pestañas abiertas inmediatamente
            return self.clients.claim();
        })
    );
});

// Evento de recuperación (fetch): La verdadera inteligencia Offline
self.addEventListener('fetch', (event) => {
    // Excluir peticiones a la API o recursos externos ajenos a la app
    if (event.request.method !== 'GET' || !event.request.url.startsWith(self.location.origin)) {
        return;
    }

    // Estrategia 1: NETWORK FIRST (Red primero, luego Caché) para páginas HTML (Navegación)
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request)
                .then((networkResponse) => {
                    // Si hay red, guardamos una copia fresca en caché silenciosamente
                    return caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, networkResponse.clone());
                        return networkResponse;
                    });
                })
                .catch(() => {
                    // SI NO HAY RED (Offline): Devolvemos la última copia guardada del HTML
                    console.log('Modo Offline detectado. Sirviendo página desde Caché:', event.request.url);
                    return caches.match(event.request);
                })
        );
    } 
    // Estrategia 2: CACHE FIRST (Caché primero, luego Red) para estáticos (Imágenes, CSS, JS)
    else {
        event.respondWith(
            caches.match(event.request).then((cachedResponse) => {
                if (cachedResponse) {
                    return cachedResponse; // Devolver rápido desde caché
                }
                
                // Si no está en caché, lo busca en internet y lo guarda dinámicamente
                return fetch(event.request).then((networkResponse) => {
                    // Solo cachear recursos válidos de la carpeta /static/
                    if (networkResponse && networkResponse.status === 200 && event.request.url.includes('/static/')) {
                        const responseToCache = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, responseToCache);
                        });
                    }
                    return networkResponse;
                }).catch(() => {
                    // Failsafe para imágenes faltantes estando offline
                    if (event.request.url.match(/\.(jpe?g|png|gif|svg)$/i)) {
                        return caches.match('/static/img/default.png');
                    }
                });
            })
        );
    }
});