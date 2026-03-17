// validaciones.js

/**
 * Gestiona todas las validaciones de front-end para el registro y perfil.
 * Incluye restricciones de caracteres, formatos de texto y lógica de teléfonos por país.
 */

document.addEventListener('DOMContentLoaded', function() {
    initValidators();
});

/**
 * Inicializa los escuchadores de eventos para los campos del formulario.
 * Se puede llamar nuevamente al agregar campos dinámicos.
 */
function initValidators() {
    // 1. Validación de Nombres y Apellidos
    // No permite números, caracteres especiales y fuerza inicio en Mayúscula.
    const nameInputs = document.querySelectorAll('.val-name, .val-surname');
    nameInputs.forEach(input => {
        input.addEventListener('input', function() {
            // Eliminar números y caracteres especiales (permitir letras y espacios)
            let val = this.value.replace(/[0-9!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/g, '');
            
            // Restringir a un solo espacio si es el nombre (val-name)
            if (this.classList.contains('val-name')) {
                const spaces = (val.match(/ /g) || []).length;
                if (spaces > 1) {
                    val = val.substring(0, val.lastIndexOf(' '));
                }
            } else {
                // Apellidos no permiten espacios
                val = val.replace(/\s/g, '');
            }

            this.value = val;
        });

        input.addEventListener('blur', function() {
            // Forzar que inicie en Mayúscula (Title Case)
            if (this.value.length > 0) {
                this.value = this.value.split(' ')
                    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
                    .join(' ');
            }
        });
    });

    // 2. Validación de Email (Pasar a minúsculas automáticamente)
    const emailInputs = document.querySelectorAll('.val-email');
    emailInputs.forEach(input => {
        input.addEventListener('input', function() {
            this.value = this.value.toLowerCase();
        });
    });

    // 3. Validación de campos Numéricos (Teléfonos, WhatsApp, etc.)
    const numericInputs = document.querySelectorAll('.val-numeric');
    numericInputs.forEach(input => {
        input.addEventListener('input', function() {
            // Eliminar cualquier cosa que no sea número
            this.value = this.value.replace(/\D/g, '');
            
            // Si es el teléfono principal, aplicar restricciones por país
            if (this.name === 'phone') {
                applyCountryPhoneLogic(this);
            }
        });
    });
}

/**
 * Lógica para restringir la cantidad de números según el país seleccionado.
 */
function applyCountryPhoneLogic(input) {
    const countryCode = document.getElementById('countryCode')?.value;
    
    // Mapa de longitudes de teléfono por país
    const lengths = {
        "+506": 8,   // Costa Rica
        "+1": 10,    // USA/Canada
        "+52": 10,   // México
        "+34": 9     // España
    };

    const maxLength = lengths[countryCode] || 15;
    
    if (input.value.length > maxLength) {
        input.value = input.value.slice(0, maxLength);
    }
}

// Escuchar cambios en el selector de país para limpiar el teléfono si cambia el formato
const countrySelector = document.getElementById('countryCode');
if (countrySelector) {
    countrySelector.addEventListener('change', function() {
        const phoneInput = document.querySelector('input[name="phone"]');
        if (phoneInput) phoneInput.value = ""; 
    });
}

/**
 * Validación global antes de enviar el formulario
 */
const form = document.getElementById('registroForm');
if (form) {
    form.addEventListener('submit', function(e) {
        const pass1 = document.getElementById('pass1').value;
        const pass2 = document.getElementById('pass2').value;

        if (pass1 !== pass2) {
            e.preventDefault();
            alert("Las contraseñas no coinciden."); // Reemplazar con UI de mensaje en producción
            return false;
        }
    });
}