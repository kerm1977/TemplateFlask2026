    // --- Lógica del Editor de Avatar (Cropper) ---
    let cropper;
    const avatarInput = document.getElementById('avatarInput');
    const imageToCrop = document.getElementById('imageToCrop');
    const cropModalElement = document.getElementById('cropModal');
    const cropModal = new bootstrap.Modal(cropModalElement);
    const avatarPreview = document.getElementById('avatarPreview');
    const avatarBase64Input = document.getElementById('avatarBase64');

    // 1. Al seleccionar un archivo, abrir el modal
    avatarInput.addEventListener('change', function(e) {
        const files = e.target.files;
        if (files && files.length > 0) {
            const reader = new FileReader();
            reader.onload = function(event) {
                imageToCrop.src = event.target.result;
                cropModal.show();
            };
            reader.readAsDataURL(files[0]);
        }
    });

    // 2. Al abrir el modal, inicializar Cropper.js
    cropModalElement.addEventListener('shown.bs.modal', function() {
        cropper = new Cropper(imageToCrop, {
            aspectRatio: 1, // Fuerza un cuadrado perfecto
            viewMode: 1,
            dragMode: 'move',
            autoCropArea: 0.9,
            restore: false,
            guides: true,
            center: true,
            highlight: false,
            cropBoxMovable: true,
            cropBoxResizable: true,
            toggleDragModeOnDblclick: false,
        });
    });

    // 3. Al cerrar el modal, destruir la instancia
    cropModalElement.addEventListener('hidden.bs.modal', function() {
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
        // Si no guardó un recorte, limpiar el input file para que pueda volver a elegir el mismo
        if (!avatarBase64Input.value) {
            avatarInput.value = '';
        }
    });

    // 4. Botones de Zoom Manual
    document.getElementById('btnZoomIn').addEventListener('click', () => { if(cropper) cropper.zoom(0.1); });
    document.getElementById('btnZoomOut').addEventListener('click', () => { if(cropper) cropper.zoom(-0.1); });

    // 5. Botón de Recortar y Guardar
    document.getElementById('btnCropSave').addEventListener('click', function() {
        if (!cropper) return;
        
        // Obtener el lienzo recortado a tamaño estandarizado (300x300)
        const canvas = cropper.getCroppedCanvas({
            width: 300,
            height: 300,
            imageSmoothingEnabled: true,
            imageSmoothingQuality: 'high',
        });
        
        // Convertir a Base64
        const base64Image = canvas.toDataURL('image/png');
        
        // Asignar a la vista previa y al input oculto
        avatarPreview.src = base64Image;
        avatarBase64Input.value = base64Image;
        
        // Cerrar el modal
        cropModal.hide();
    });

    // --- Lógica de Campos Dinámicos ---
    function addExtraField() {
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

        // Lógica de inputs según selección
        if (['Telefono', 'Whatsapp'].includes(type)) {
            html += `<input type="text" name="extra_field_value[]" class="form-control glass-input val-numeric" placeholder="Número de ${type}" required>`;
        } 
        else if (['Facebook', 'Instagram', 'Direccion'].includes(type)) {
            html += `<input type="text" name="extra_field_desc[]" class="form-control glass-input mb-2" placeholder="Descripción (Ej: Mi perfil)">
                     <input type="url" name="extra_field_value[]" class="form-control glass-input" placeholder="URL o Link" required>`;
        }
        else if (type === 'Fecha') {
            html += `<input type="text" name="extra_field_desc[]" class="form-control glass-input mb-2" placeholder="Descripción (Ej: Aniversario)">
                     <div class="row g-2">
                        <div class="col-4"><input type="number" name="ef_day[]" class="form-control glass-input" placeholder="Día" min="1" max="31"></div>
                        <div class="col-4"><input type="number" name="ef_month[]" class="form-control glass-input" placeholder="Mes" min="1" max="12"></div>
                        <div class="col-4"><input type="number" name="ef_year[]" class="form-control glass-input" placeholder="Año" min="1900" max="2100"></div>
                     </div>`;
        }
        else if (['Institucion', 'Provedoor', 'Tienda', 'Fabrica'].includes(type) || type === 'Institucion') {
            html += `<input type="text" name="inst_name[]" class="form-control glass-input mb-2" placeholder="Nombre de la Institución/Tienda" required>
                     <input type="text" name="inst_phone[]" class="form-control glass-input mb-2 val-numeric" placeholder="Teléfono Institución">
                     <input type="text" name="cont_name[]" class="form-control glass-input mb-2" placeholder="Nombre del Contacto">
                     <input type="text" name="cont_phone[]" class="form-control glass-input val-numeric" placeholder="Teléfono Contacto">`;
        }
        else {
            html += `<input type="text" name="extra_field_value[]" class="form-control glass-input" placeholder="Descripción" required>`;
        }

        html += `</div>`;
        container.insertAdjacentHTML('beforeend', html);
        document.getElementById('extraFieldSelector').value = "";
        
        // Reinicializar validadores para los nuevos elementos
        if (window.initValidators) window.initValidators();
    }