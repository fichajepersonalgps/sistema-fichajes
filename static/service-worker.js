// Nombre del cache para que la app funcione más rápido
const CACHE_NAME = 'fichajes-v1';

// Evento de instalación
self.addEventListener('install', (event) => {
    console.log('Service Worker instalado');
});

// Evento para activar el worker
self.addEventListener('activate', (event) => {
    console.log('Service Worker activo');
});

// Escuchar mensajes en segundo plano (vibración y sonido)
self.addEventListener('push', function(event) {
    const title = 'Nuevo Mensaje de Trabajo';
    const options = {
        body: 'Tienes un mensaje nuevo en el chat.',
        vibrate: [200, 100, 200],
        tag: 'mensaje-notif',
        renotify: true
    };
    event.waitUntil(self.registration.showNotification(title, options));
});