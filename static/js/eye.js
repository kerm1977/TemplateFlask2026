// eye.js

/**
 * Gestiona la visibilidad de las contraseñas en los campos de entrada.
 * Busca elementos con la clase 'toggle-password' y alterna el tipo de input.
 */

document.addEventListener('DOMContentLoaded', function() {
    const togglePasswordButtons = document.querySelectorAll('.toggle-password');

    togglePasswordButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Obtener el ID del input objetivo desde el atributo data-target
            const targetId = this.getAttribute('data-target');
            const passwordInput = document.getElementById(targetId);
            const icon = this.querySelector('i');

            if (passwordInput) {
                // Alternar el tipo de entrada
                if (passwordInput.type === 'password') {
                    passwordInput.type = 'text';
                    // Cambiar icono a ojo tachado o abierto según Bootstrap Icons
                    icon.classList.remove('bi-eye');
                    icon.classList.add('bi-eye-slash');
                } else {
                    passwordInput.type = 'password';
                    // Revertir icono
                    icon.classList.remove('bi-eye-slash');
                    icon.classList.add('bi-eye');
                }
            }
        });
    });
});