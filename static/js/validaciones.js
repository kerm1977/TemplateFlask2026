/**
 * validaciones.js
 * Centraliza TODAS las validaciones de front-end para los formularios del sistema.
 * Utiliza Event Delegation para que los campos dinámicos se validen automáticamente.
 */

document.addEventListener('DOMContentLoaded', function() {

    // 1. Escuchar eventos de entrada en tiempo real (mientras el usuario escribe)
    document.addEventListener('input', function(e) {
        const target = e.target;

        // Validación para Nombre (Solo letras y MÁXIMO 1 espacio)
        if (target.classList.contains('val-name')) {
            // Eliminar números y caracteres especiales. No permitir espacios al inicio.
            let val = target.value.replace(/[^a-zA-ZáéíóúÁÉÍÓÚñÑ\s]/g, '').replace(/^\s+/, '');
            
            // Restringir a un solo espacio
            const spaces = (val.match(/ /g) || []).length;
            if (spaces > 1) {
                val = val.substring(0, val.lastIndexOf(' '));
            }
            target.value = val;
        } 
        // Validación para Apellidos (Solo letras, CERO espacios)
        else if (target.classList.contains('val-surname')) {
            target.value = target.value.replace(/[^a-zA-ZáéíóúÁÉÍÓÚñÑ]/g, '');
        }
        // Validación para Email (Todo a minúsculas)
        else if (target.classList.contains('val-email')) {
            target.value = target.value.toLowerCase();
        }
        // Validación para Números (Teléfonos, WhatsApp, etc)
        else if (target.classList.contains('val-numeric')) {
            target.value = target.value.replace(/\D/g, ''); // Eliminar todo lo que no sea número
            
            // Lógica de longitud según país si es el teléfono principal
            if (target.name === 'phone') {
                const countryCode = document.getElementById('countryCode')?.value;
                const lengths = { "+506": 8, "+1": 10, "+52": 10, "+34": 9 };
                const maxLength = lengths[countryCode] || 15;
                
                if (target.value.length > maxLength) {
                    target.value = target.value.slice(0, maxLength);
                }
            }
        }
    });

    // 2. Escuchar cuando el usuario termina de escribir (blur/focusout)
    document.addEventListener('focusout', function(e) {
        const target = e.target;
        
        // Forzar Title Case (Primera letra Mayúscula) en Nombres, Apellidos y Títulos descriptivos
        if (target.classList.contains('val-name') || 
            target.classList.contains('val-surname') || 
            target.classList.contains('val-title')) {
            
            if (target.value.length > 0) {
                target.value = target.value.split(' ')
                    .map(word => word.length > 0 ? word.charAt(0).toUpperCase() + word.slice(1).toLowerCase() : '')
                    .join(' ');
            }
        }
    });

    // 3. Limpiar teléfono si el usuario cambia de país
    document.addEventListener('change', function(e) {
        if (e.target.id === 'countryCode') {
            const phoneInput = document.querySelector('input[name="phone"]');
            if (phoneInput) {
                phoneInput.value = "";
                phoneInput.focus();
            }
        }
    });

    // 4. Validación de coincidencia de contraseñas al enviar el formulario
    const form = document.getElementById('registroForm');
    if (form) {
        form.addEventListener('submit', function(e) {
            const pass1 = document.getElementById('pass1');
            const pass2 = document.getElementById('pass2');

            if (pass1 && pass2 && pass1.value !== pass2.value) {
                e.preventDefault();
                alert("⚠️ Las contraseñas no coinciden. Por favor, verifícalas.");
                return false;
            }
        });
    }
});

// 5. Lógica Global para Generar Campos Dinámicos
// Se expone en window para que el botón HTML la pueda llamar directamente
window.addExtraField = function() {
    const type = document.getElementById('extraFieldSelector').value;
    const container = document.getElementById('dynamicFieldsContainer');
    if (!type) return;

    const fieldId = 'field_' + Date.now();
    let html = `<div class="glass-card p-3 mb-3 animate__animated animate__fadeInLeft" id="${fieldId}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="badge bg-orange">${type}</span>
                        <button type="button" class="btn btn-sm btn-outline-danger border-0" onclick="document.getElementById('${fieldId}').remove()">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                    <input type="hidden" name="extra_field_type[]" value="${type}">`;

    // Aplicación de clases validadoras (val-numeric, val-title) inyectadas directamente
    if (['Telefono', 'Whatsapp'].includes(type)) {
        html += `<input type="text" name="extra_field_value[]" class="form-control glass-input val-numeric" placeholder="Número de ${type}" required>`;
    } 
    else if (['Facebook', 'Instagram', 'Direccion'].includes(type)) {
        html += `<input type="text" name="extra_field_desc[]" class="form-control glass-input mb-2 val-title" placeholder="Descripción (Ej: Mi perfil)" required>
                 <input type="url" name="extra_field_value[]" class="form-control glass-input" placeholder="URL o Link" required>`;
    } 
    else if (type === 'Fecha') {
        html += `<input type="text" name="extra_field_desc[]" class="form-control glass-input mb-2 val-title" placeholder="Descripción (Ej: Aniversario)" required>
                 <div class="row g-2">
                    <div class="col-4"><input type="number" name="ef_day[]" class="form-control glass-input" placeholder="Día" min="1" max="31" required></div>
                    <div class="col-4"><input type="number" name="ef_month[]" class="form-control glass-input" placeholder="Mes" min="1" max="12" required></div>
                    <div class="col-4"><input type="number" name="ef_year[]" class="form-control glass-input" placeholder="Año" min="1900" max="2100" required></div>
                 </div>`;
    } 
    else if (['Institucion', 'Provedoor', 'Tienda', 'Fabrica'].includes(type)) {
        html += `<input type="text" name="inst_name[]" class="form-control glass-input mb-2 val-title" placeholder="Nombre de la Institución/Tienda" required>
                 <input type="text" name="inst_phone[]" class="form-control glass-input mb-2 val-numeric" placeholder="Teléfono Institución" required>
                 <input type="text" name="cont_name[]" class="form-control glass-input mb-2 val-title" placeholder="Nombre del Contacto" required>
                 <input type="text" name="cont_phone[]" class="form-control glass-input val-numeric" placeholder="Teléfono Contacto" required>`;
    } 
    else { // Tipo "Otro"
        html += `<input type="text" name="extra_field_value[]" class="form-control glass-input val-title" placeholder="Descripción" required>`;
    }
    
    html += `</div>`;
    container.insertAdjacentHTML('beforeend', html);
    document.getElementById('extraFieldSelector').value = "";
    
    // NOTA: Como usamos Delegación de Eventos, no necesitamos reiniciar ninguna función. 
    // Los nuevos campos ya están protegidos mágicamente.
};