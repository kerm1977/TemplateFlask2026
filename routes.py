# routes.py

import os
import base64
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from datetime import datetime
import json
import io
import string
import random
from sqlalchemy import extract
import urllib.parse

# Importaciones locales
from db import SessionLocal
from models import User, ExtraField, Notification, BusinessCard, SystemSetting
from users import create_user, get_user_by_email, bcrypt, prepare_export_data, update_password

main_bp = Blueprint('main', __name__)

# --- FUNCIONES AUXILIARES ---
def model_to_dict(obj):
    """Convierte un objeto de SQLAlchemy a diccionario para poder exportarlo a JSON"""
    data = {}
    for c in obj.__table__.columns:
        val = getattr(obj, c.name)
        if isinstance(val, datetime):
            data[c.name] = val.isoformat()
        else:
            data[c.name] = val
    return data

# --- INYECCIÓN DE DATOS GLOBALES (Configuración, Cumpleaños y Usuario) ---
@main_bp.context_processor
def inject_global_data():
    """Inyecta datos a todas las plantillas HTML automáticamente"""
    context = {
        'current_user': None,
        'birthday_users': [],
        'settings': {}
    }
    
    db = SessionLocal()
    try:
        # 1. Cargar Ajustes del Sistema (Nombre App, Tema y Logo)
        settings_list = db.query(SystemSetting).all()
        settings_dict = {s.key: s.value for s in settings_list}
        
        # Valores por defecto si no existen en la base de datos
        context['settings'] = {
            'app_name': settings_dict.get('app_name', 'La Tribu'),
            'site_theme': settings_dict.get('site_theme', 'dark'),
            'app_logo': settings_dict.get('app_logo', None)
        }

        # 2. Lógica de Cumpleaños
        today = datetime.now()
        all_users = db.query(User).all()
        bday_users = []
        
        for u in all_users:
            if u.birth_date:
                b_date = u.birth_date
                if isinstance(b_date, str):
                    try:
                        b_date = datetime.strptime(b_date.split(' ')[0], '%Y-%m-%d')
                    except ValueError:
                        continue 
                
                if b_date.month == today.month and b_date.day == today.day:
                    mensaje = f"¡Hola {u.first_name}! ¡Feliz Cumpleaños! Te deseamos en la Tribu de Los Libres esperamos el mejor día junto a tus amig@s y Familia."
                    u.whatsapp_msg = urllib.parse.quote(mensaje)
                    bday_users.append(u)
                
        context['birthday_users'] = bday_users
        
        # 3. Usuario en sesión
        if 'user_id' in session:
            context['current_user'] = db.query(User).get(session['user_id'])
            
    except Exception as e:
        print(f"Error en context_processor: {e}")
    finally:
        db.close()
        
    return context


def login_required(f):
    """Decorador simple para proteger rutas"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión primero.', 'warning')
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorador para proteger rutas de administración"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') not in ['Superusuario', 'Administrador']:
            flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('main.home'))
        return f(*args, **kwargs)
    return decorated_function

# --- RUTAS DE NAVEGACIÓN BÁSICA ---

@main_bp.route('/')
def home():
    db = SessionLocal()
    now = datetime.now()
    
    query = db.query(Notification).filter(
        Notification.start_date <= now,
        Notification.end_date >= now,
        Notification.is_active == 1
    )
    
    user_role = session.get('role', 'Visitante')
    if user_role not in ['Superusuario', 'Administrador']:
        query = query.filter(Notification.visibility == 'Todos')
        
    notifications = query.all()
    
    html = render_template('home.html', notifications=notifications)
    db.close()
    return html

# --- AUTENTICACIÓN ---

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        db = SessionLocal()
        user = get_user_by_email(db, email)
        
        if user and bcrypt.check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.first_name
            session['role'] = user.role
            db.close()
            return redirect(url_for('main.home'))
        
        db.close()
        flash('Correo o contraseña incorrectos.', 'danger')
    return render_template('login.html')

@main_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))

@main_bp.route('/recuperar', methods=['GET', 'POST'])
def recuperar():
    """Módulo de recuperación basado en validación de identidad (Sin Email Server)"""
    if request.method == 'POST':
        email = request.form.get('email')
        phone = request.form.get('phone')
        
        day = request.form.get('day')
        month = request.form.get('month')
        year = request.form.get('year')
        
        db = SessionLocal()
        user = get_user_by_email(db, email)
        
        if user:
            try:
                # Convertimos las fechas para compararlas exactamente
                input_birth_date = datetime.strptime(f"{year}-{month}-{day}", '%Y-%m-%d').date()
                
                # Manejo seguro si la base de datos devuelve un datetime o un string (dependiendo del motor DB)
                if isinstance(user.birth_date, datetime):
                    user_birth_date = user.birth_date.date()
                else:
                    user_birth_date = datetime.strptime(user.birth_date.split(' ')[0], '%Y-%m-%d').date()
                
                # Si el teléfono y la fecha de nacimiento COINCIDEN EXACTAMENTE
                if user.phone == phone and user_birth_date == input_birth_date:
                    
                    # Generar contraseña temporal alfanumérica de 6 caracteres
                    temp_password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    
                    # Actualizamos en DB
                    user.password = bcrypt.generate_password_hash(temp_password).decode('utf-8')
                    db.commit()
                    
                    flash(f'¡Identidad verificada! Tu contraseña temporal es: {temp_password} (Cámbiala en tu perfil)', 'success')
                    db.close()
                    return redirect(url_for('main.login'))
                    
            except Exception as e:
                print(f"Error validando fechas: {e}")
                pass
        
        db.close()
        # Si falla en cualquier punto (correo no existe, mal teléfono o mala fecha) damos un error genérico por seguridad
        flash('Los datos proporcionados no coinciden con nuestros registros. Intenta de nuevo.', 'danger')
            
    return render_template('recuperar.html')


@main_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        db = SessionLocal()
        try:
            avatar_filename = 'default.png'
            avatar_base64 = request.form.get('avatar_base64')
            avatar_file = request.files.get('avatar')
            
            os.makedirs('static/img', exist_ok=True)

            if avatar_base64:
                header, encoded = avatar_base64.split(",", 1)
                file_ext = header.split('/')[1].split(';')[0]
                unique_filename = f"avatar_{int(datetime.now().timestamp())}.{file_ext}"
                filepath = os.path.join('static/img', unique_filename)
                with open(filepath, "wb") as fh:
                    fh.write(base64.b64decode(encoded))
                avatar_filename = unique_filename
            elif avatar_file and avatar_file.filename != '':
                filename = secure_filename(avatar_file.filename)
                unique_filename = f"avatar_{int(datetime.now().timestamp())}_{filename}"
                filepath = os.path.join('static/img', unique_filename)
                avatar_file.save(filepath)
                avatar_filename = unique_filename

            user_data = {
                'first_name': request.form.get('first_name'),
                'last_name1': request.form.get('last_name1'),
                'last_name2': request.form.get('last_name2'),
                'email': request.form.get('email'),
                'phone': request.form.get('phone'),
                'birth_date': datetime.strptime(f"{request.form.get('year')}-{request.form.get('month')}-{request.form.get('day')}", '%Y-%m-%d'),
                'password': request.form.get('password'),
                'avatar': avatar_filename
            }
            
            extra_fields_list = []
            field_types = request.form.getlist('extra_field_type[]')
            field_values = request.form.getlist('extra_field_value[]')
            
            for f_type, f_val in zip(field_types, field_values):
                extra_fields_list.append({'type': f_type, 'value': f_val})

            create_user(db, user_data, extra_fields_list)
            flash('Registro exitoso. Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('main.login'))
        except Exception as e:
            flash(f'Error en el registro: {str(e)}', 'danger')
        finally:
            db.close()
            
    return render_template('registro.html')

# --- PERFIL Y DASHBOARD ---

@main_bp.route('/perfil')
@login_required
def perfil():
    db = SessionLocal()
    user = db.query(User).get(session['user_id'])
    export_data = prepare_export_data(user)
    html = render_template('perfil.html', user=user, export_data=export_data)
    db.close()
    return html

@main_bp.route('/editar_perfil', methods=['GET', 'POST'])
@login_required
def editar_perfil():
    db = SessionLocal()
    user = db.query(User).get(session['user_id'])
    
    if request.method == 'POST':
        try:
            avatar_base64 = request.form.get('avatar_base64')
            avatar_file = request.files.get('avatar')
            
            os.makedirs('static/img', exist_ok=True)

            if avatar_base64:
                header, encoded = avatar_base64.split(",", 1)
                file_ext = header.split('/')[1].split(';')[0]
                unique_filename = f"avatar_{int(datetime.now().timestamp())}.{file_ext}"
                filepath = os.path.join('static/img', unique_filename)
                with open(filepath, "wb") as fh:
                    fh.write(base64.b64decode(encoded))
                user.avatar = unique_filename
            elif avatar_file and avatar_file.filename != '':
                filename = secure_filename(avatar_file.filename)
                unique_filename = f"avatar_{int(datetime.now().timestamp())}_{filename}"
                filepath = os.path.join('static/img', unique_filename)
                avatar_file.save(filepath)
                user.avatar = unique_filename

            user.first_name = request.form.get('first_name')
            user.last_name1 = request.form.get('last_name1')
            user.last_name2 = request.form.get('last_name2')
            user.phone = request.form.get('phone')
            
            day = request.form.get('day')
            month = request.form.get('month')
            year = request.form.get('year')
            if day and month and year:
                user.birth_date = datetime.strptime(f"{year}-{month}-{day}", '%Y-%m-%d')
            
            db.query(ExtraField).filter(ExtraField.user_id == user.id).delete()
            
            field_types = request.form.getlist('extra_field_type[]')
            field_values = request.form.getlist('extra_field_value[]')
            
            for f_type, f_val in zip(field_types, field_values):
                if f_type and f_val:
                    new_field = ExtraField(
                        user_id=user.id,
                        field_type=f_type,
                        value=f_val,
                        label=f_type 
                    )
                    db.add(new_field)
            
            user.updated_at = datetime.utcnow()
            db.commit()
            flash('Perfil actualizado con éxito.', 'success')
            return redirect(url_for('main.perfil'))
        except Exception as e:
            db.rollback()
            flash(f'Error al actualizar el perfil: {str(e)}', 'danger')
            return redirect(url_for('main.editar_perfil'))
        finally:
            db.close()

    html = render_template('editar_perfil.html', user=user)
    db.close()
    return html

@main_bp.route('/dashboard')
@admin_required
def dashboard():
    db = SessionLocal()
    users = db.query(User).all()
    stats = {
        'total': len(users),
        'recent': db.query(User).filter(User.created_at >= datetime.now().replace(day=1)).count()
    }
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    total_notifs = db.query(Notification).count()
    total_pages = (total_notifs + per_page - 1) // per_page
    
    notifs = db.query(Notification).order_by(Notification.id.desc()).offset((page-1)*per_page).limit(per_page).all()
    
    cards = db.query(BusinessCard).order_by(BusinessCard.id.desc()).all()
    
    now = datetime.now()
    
    html = render_template('dashboard.html', users=users, stats=stats, notifs=notifs, cards=cards, page=page, total_pages=total_pages, now=now)
    db.close()
    return html

# --- RUTAS DE ADMINISTRACIÓN ---

@main_bp.route('/delete_user/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    db = SessionLocal()
    try:
        user = db.query(User).get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'Usuario no encontrado'})
        
        if user.email in ['kenth1977@gmail.com', 'lthikingcr@gmail.com']:
            return jsonify({'success': False, 'message': 'Acción denegada: Superusuario maestro protegido'})
            
        db.delete(user)
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        db.close()

@main_bp.route('/admin_edit_user/<int:user_id>', methods=['POST'])
@admin_required
def admin_edit_user(user_id):
    db = SessionLocal()
    try:
        user = db.query(User).get(user_id)
        if user:
            user.first_name = request.form.get('first_name')
            user.last_name1 = request.form.get('last_name1')
            user.last_name2 = request.form.get('last_name2')
            user.email = request.form.get('email')
            
            new_role = request.form.get('role')
            if user.email in ['kenth1977@gmail.com', 'lthikingcr@gmail.com']:
                user.role = 'Superusuario'
            else:
                user.role = new_role
                
            db.commit()
            flash('Usuario actualizado correctamente', 'success')
        else:
            flash('Usuario no encontrado', 'danger')
    except Exception as e:
        db.rollback()
        flash(f'Error actualizando usuario: {str(e)}', 'danger')
    finally:
        db.close()
    return redirect(url_for('main.dashboard') + '#usersContent')

# --- CONFIGURACIÓN GLOBAL (App Name, Tema y Logo) ---

@main_bp.route('/admin/update_settings', methods=['POST'])
@admin_required
def update_settings():
    db = SessionLocal()
    try:
        data = {
            'app_name': request.form.get('app_name'),
            'site_theme': request.form.get('site_theme')
        }
        
        # PROCESAR EL NUEVO LOGO GLOBAL
        logo_file = request.files.get('app_logo')
        if logo_file and logo_file.filename != '':
            os.makedirs('static/uploads', exist_ok=True)
            filename = secure_filename(logo_file.filename)
            unique_filename = f"syslogo_{int(datetime.now().timestamp())}_{filename}"
            filepath = os.path.join('static/uploads', unique_filename)
            logo_file.save(filepath)
            data['app_logo'] = unique_filename
            
        for key, value in data.items():
            if value is not None:  # Evita sobreescribir el logo actual con "None" si no suben uno nuevo
                setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
                if setting:
                    setting.value = value
                else:
                    db.add(SystemSetting(key=key, value=value))
        db.commit()
        flash('Configuración del sistema actualizada correctamente.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error al guardar ajustes: {str(e)}', 'danger')
    finally:
        db.close()
    return redirect(url_for('main.dashboard') + '#settingsContent')


# --- NOTIFICACIONES ---
@main_bp.route('/create_notification', methods=['POST'])
@admin_required
def create_notification():
    db = SessionLocal()
    try:
        image_file = request.files.get('image')
        image_filename = None
        
        if image_file and image_file.filename != '':
            os.makedirs('static/uploads', exist_ok=True)
            filename = secure_filename(image_file.filename)
            unique_filename = f"notif_{int(datetime.now().timestamp())}_{filename}"
            filepath = os.path.join('static/uploads', unique_filename)
            image_file.save(filepath)
            image_filename = unique_filename
            
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        
        parsed_start = datetime.strptime(start_date_str, '%Y-%m-%d')
        
        new_notif = Notification(
            image=image_filename,
            start_date=parsed_start,
            end_date=datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59),
            notification_type=request.form.get('notification_type'),
            message=request.form.get('message'),
            visibility=request.form.get('visibility', 'Todos'),
            is_active=1
        )
        
        db.add(new_notif)
        db.commit()
        
        if parsed_start.date() > datetime.now().date():
            flash('Anuncio programado exitosamente. Se publicará en la fecha indicada.', 'success')
        else:
            flash('Anuncio publicado correctamente y visible en el inicio.', 'success')
            
    except Exception as e:
        db.rollback()
        flash(f'Error al publicar notificación: {str(e)}', 'danger')
    finally:
        db.close()
        
    return redirect(url_for('main.dashboard') + '#notifyContent')

@main_bp.route('/edit_notification/<int:notif_id>', methods=['POST'])
@admin_required
def edit_notification(notif_id):
    db = SessionLocal()
    try:
        notif = db.query(Notification).get(notif_id)
        if notif:
            parsed_start = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
            notif.start_date = parsed_start
            notif.end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            notif.notification_type = request.form.get('notification_type')
            notif.message = request.form.get('message')
            notif.visibility = request.form.get('visibility', 'Todos')
            notif.is_active = int(request.form.get('is_active', 1))
            
            image_file = request.files.get('image')
            if image_file and image_file.filename != '':
                os.makedirs('static/uploads', exist_ok=True)
                filename = secure_filename(image_file.filename)
                unique_filename = f"notif_{int(datetime.now().timestamp())}_{filename}"
                filepath = os.path.join('static/uploads', unique_filename)
                image_file.save(filepath)
                notif.image = unique_filename
                
            db.commit()
            
            if parsed_start.date() > datetime.now().date():
                flash('Anuncio actualizado y programado para el futuro.', 'success')
            else:
                flash('Anuncio actualizado correctamente.', 'success')
        else:
            flash('Notificación no encontrada.', 'danger')
    except Exception as e:
        db.rollback()
        flash(f'Error al actualizar notificación: {str(e)}', 'danger')
    finally:
        db.close()
    return redirect(url_for('main.dashboard') + '#notifyContent')

@main_bp.route('/delete_notification/<int:notif_id>', methods=['DELETE'])
@admin_required
def delete_notification(notif_id):
    db = SessionLocal()
    try:
        notif = db.query(Notification).get(notif_id)
        if notif:
            db.delete(notif)
            db.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Notificación no encontrada'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        db.close()

# --- RUTAS DE TARJETAS (BUSINESS CARDS) ---

@main_bp.route('/create_card', methods=['POST'])
@admin_required
def create_card():
    db = SessionLocal()
    try:
        logo_file = request.files.get('logo')
        logo_filename = None
        
        if logo_file and logo_file.filename != '':
            os.makedirs('static/uploads', exist_ok=True)
            filename = secure_filename(logo_file.filename)
            unique_filename = f"card_{int(datetime.now().timestamp())}_{filename}"
            filepath = os.path.join('static/uploads', unique_filename)
            logo_file.save(filepath)
            logo_filename = unique_filename
            
        owner_id_val = request.form.get('owner_id')
        owner_id = int(owner_id_val) if owner_id_val else None

        new_card = BusinessCard(
            owner_id=owner_id,
            logo=logo_filename,
            name=request.form.get('name'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            whatsapp=request.form.get('whatsapp'),
            address=request.form.get('address'),
            schedule=request.form.get('schedule'),
            contact_name=request.form.get('contact_name'),
            theme=request.form.get('theme', 'dark')
        )
        
        db.add(new_card)
        db.commit()
        flash('Tarjeta de presentación creada con éxito.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error al crear tarjeta: {str(e)}', 'danger')
    finally:
        db.close()
        
    return redirect(url_for('main.dashboard') + '#cardsContent')

@main_bp.route('/edit_card/<int:card_id>', methods=['POST'])
@admin_required
def edit_card(card_id):
    db = SessionLocal()
    try:
        card = db.query(BusinessCard).get(card_id)
        if card:
            card.name = request.form.get('name')
            card.phone = request.form.get('phone')
            card.email = request.form.get('email')
            card.whatsapp = request.form.get('whatsapp')
            card.address = request.form.get('address')
            card.schedule = request.form.get('schedule')
            card.contact_name = request.form.get('contact_name')
            card.theme = request.form.get('theme', 'dark')
            
            owner_id_val = request.form.get('owner_id')
            card.owner_id = int(owner_id_val) if owner_id_val else None
            
            logo_file = request.files.get('logo')
            if logo_file and logo_file.filename != '':
                os.makedirs('static/uploads', exist_ok=True)
                filename = secure_filename(logo_file.filename)
                unique_filename = f"card_{int(datetime.now().timestamp())}_{filename}"
                filepath = os.path.join('static/uploads', unique_filename)
                logo_file.save(filepath)
                card.logo = unique_filename
                
            db.commit()
            flash('Tarjeta actualizada correctamente.', 'success')
        else:
            flash('Tarjeta no encontrada.', 'danger')
    except Exception as e:
        db.rollback()
        flash(f'Error al actualizar tarjeta: {str(e)}', 'danger')
    finally:
        db.close()
    return redirect(url_for('main.dashboard') + '#cardsContent')

@main_bp.route('/delete_card/<int:card_id>', methods=['DELETE'])
@admin_required
def delete_card(card_id):
    db = SessionLocal()
    try:
        card = db.query(BusinessCard).get(card_id)
        if card:
            db.delete(card)
            db.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Tarjeta no encontrada'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        db.close()

# --- GESTIÓN DE RESPALDOS (DB Y JSON) Y MODO OFFLINE ---

@main_bp.route('/api/export_json')
@admin_required
def api_export_json():
    """
    Ruta silenciosa requerida por el Dashboard para poblar IndexedDB (Modo Offline).
    Retorna la DB en formato JSON directamente.
    """
    db = SessionLocal()
    try:
        data = {
            'users': [model_to_dict(u) for u in db.query(User).all()],
            'cards': [model_to_dict(c) for c in db.query(BusinessCard).all()],
            'notifs': [model_to_dict(n) for n in db.query(Notification).all()],
            'settings': [model_to_dict(s) for s in db.query(SystemSetting).all()],
            'extra_fields': [model_to_dict(e) for e in db.query(ExtraField).all()]
        }
        return jsonify(data)
    finally:
        db.close()

@main_bp.route('/export_json')
@admin_required
def export_json():
    """Permite al admin descargar TODA la base de datos como un archivo .json"""
    db = SessionLocal()
    try:
        data = {
            'users': [model_to_dict(u) for u in db.query(User).all()],
            'cards': [model_to_dict(c) for c in db.query(BusinessCard).all()],
            'notifs': [model_to_dict(n) for n in db.query(Notification).all()],
            'settings': [model_to_dict(s) for s in db.query(SystemSetting).all()],
            'extra_fields': [model_to_dict(e) for e in db.query(ExtraField).all()]
        }
        json_str = json.dumps(data, indent=4)
        output = io.BytesIO(json_str.encode('utf-8'))
        return send_file(
            output,
            mimetype='application/json',
            as_attachment=True,
            download_name=f"OrangeSys_Backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        )
    finally:
        db.close()

@main_bp.route('/import_json', methods=['POST'])
@admin_required
def import_json():
    """Restaura por completo la DB desde un archivo JSON subido"""
    if 'json_file' not in request.files:
        flash('No se subió ningún archivo.', 'danger')
        return redirect(url_for('main.dashboard') + '#settingsContent')
        
    file = request.files['json_file']
    if file.filename == '':
        flash('Archivo no válido.', 'danger')
        return redirect(url_for('main.dashboard') + '#settingsContent')
        
    if file and file.filename.endswith('.json'):
        db = SessionLocal()
        try:
            data = json.load(file)
            
            # 1. Limpiar TODAS las tablas existentes 
            # (El orden importa por las llaves foráneas: Hijos primero, Padres después)
            db.query(ExtraField).delete()
            db.query(BusinessCard).delete()
            db.query(Notification).delete()
            db.query(SystemSetting).delete()
            db.query(User).delete()
            
            # Función local para asegurar que las fechas string vuelvan a ser datetime
            def parse_dates(item):
                for k, v in item.items():
                    if isinstance(v, str) and ('T' in v or '-' in v) and len(v) >= 10:
                        try:
                            item[k] = datetime.fromisoformat(v)
                        except ValueError:
                            pass
                return item
            
            # 2. Reconstruir Tablas 
            for u_data in data.get('users', []):
                db.add(User(**parse_dates(u_data)))
            db.flush() # Guardar usuarios para tener los IDs listos para las foráneas
            
            for e_data in data.get('extra_fields', []):
                db.add(ExtraField(**parse_dates(e_data)))
            for c_data in data.get('cards', []):
                db.add(BusinessCard(**parse_dates(c_data)))
            for n_data in data.get('notifs', []):
                db.add(Notification(**parse_dates(n_data)))
            for s_data in data.get('settings', []):
                db.add(SystemSetting(**parse_dates(s_data)))
                
            db.commit()
            flash('¡Sistema restaurado desde JSON con éxito!', 'success')
        except Exception as e:
            db.rollback()
            flash(f'Error fatal al procesar el archivo JSON: {str(e)}', 'danger')
        finally:
            db.close()
    else:
        flash('El archivo debe ser estrictamente formato .json', 'danger')
        
    return redirect(url_for('main.dashboard') + '#settingsContent')

@main_bp.route('/export_db')
@admin_required
def export_db():
    """Descarga directamente el archivo local_database.db SQLite"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'local_database.db')
    # Alternativa si el script está en la misma raíz:
    if not os.path.exists(db_path):
        db_path = os.path.join(os.path.dirname(__file__), 'local_database.db')
        
    if os.path.exists(db_path):
        return send_file(
            db_path,
            as_attachment=True,
            download_name=f"OrangeSys_DB_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
        )
    else:
        flash('No se encontró archivo físico de SQLite para descargar. (¿Estás usando MySQL en la nube?)', 'warning')
        return redirect(url_for('main.dashboard') + '#settingsContent')

@main_bp.route('/import_db', methods=['POST'])
@admin_required
def import_db():
    """Sobrescribe el archivo SQLite actual con el subido"""
    if 'db_file' not in request.files:
        flash('No se subió ningún archivo.', 'danger')
        return redirect(url_for('main.dashboard') + '#settingsContent')
    
    file = request.files['db_file']
    if file.filename == '':
        flash('Archivo no válido.', 'danger')
        return redirect(url_for('main.dashboard') + '#settingsContent')
        
    if file and file.filename.endswith(('.db', '.sqlite')):
        try:
            db_path = os.path.join(os.path.dirname(__file__), 'local_database.db')
            file.save(db_path)
            flash('Base de datos reemplazada con éxito. RECOMIENDO REINICIAR EL SERVIDOR FLASK para evitar errores de caché.', 'success')
        except Exception as e:
            flash(f'Error al restaurar archivo físico DB: {str(e)}', 'danger')
    else:
        flash('Formato de archivo incorrecto. Debe ser .db o .sqlite', 'danger')
        
    return redirect(url_for('main.dashboard') + '#settingsContent')

# --- FUNCIONES DE EXPORTACIÓN TXT y UTILIDADES DE CONTRASEÑA ---

@main_bp.route('/export/txt')
@admin_required
def export_all_users_txt():
    db = SessionLocal()
    users = db.query(User).all()
    output = io.StringIO()
    
    for user in users:
        data = prepare_export_data(user)
        output.write(f"--- USUARIO: {user.email} ---\n")
        for key, val in data.items():
            output.write(f"{key}: {val}\n")
        output.write("\n")
    
    db.close()
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/plain',
        as_attachment=True,
        download_name=f"usuarios_{datetime.now().strftime('%Y%m%d')}.txt"
    )

@main_bp.route('/update_password', methods=['POST'])
@login_required
def change_password_route():
    current_pw = request.form.get('current_password')
    new_pw = request.form.get('new_password')
    
    db = SessionLocal()
    user = db.query(User).get(session['user_id'])
    
    if update_password(db, user, current_pw, new_pw):
        flash('Contraseña actualizada correctamente.', 'success')
    else:
        flash('La contraseña actual es incorrecta.', 'danger')
    
    db.close()
    return redirect(url_for('main.perfil'))

@main_bp.route('/verify_password', methods=['POST'])
@login_required
def verify_password():
    current_pw = request.form.get('current_password')
    db = SessionLocal()
    user = db.query(User).get(session['user_id'])
    is_valid = bcrypt.check_password_hash(user.password, current_pw)
    db.close()
    return jsonify({'valid': is_valid})