# routes.py

import os
import base64
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from datetime import datetime
import json
import io
from sqlalchemy import extract
import urllib.parse

# Importaciones locales
from db import SessionLocal
from models import User, ExtraField, Notification, BusinessCard
from users import create_user, get_user_by_email, bcrypt, prepare_export_data, update_password

main_bp = Blueprint('main', __name__)

# --- INYECCIÓN DE DATOS GLOBALES (Cumpleaños y Usuario Actual) ---
@main_bp.context_processor
def inject_global_data():
    """Inyecta datos a todas las plantillas HTML automáticamente"""
    context = {
        'current_user': None,
        'birthday_users': []
    }
    
    db = SessionLocal()
    try:
        today = datetime.now()
        
        all_users = db.query(User).all()
        bday_users = []
        
        for u in all_users:
            if u.birth_date:
                # Manejo robusto: Si SQLite devuelve un string en vez de objeto Datetime
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
    
    # Consultar notificaciones activas
    query = db.query(Notification).filter(
        Notification.start_date <= now,
        Notification.end_date >= now,
        Notification.is_active == 1
    )
    
    # Lógica de Visibilidad: Si no es admin, solo ve las de "Todos"
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
    
    now = datetime.now()
    
    html = render_template('dashboard.html', users=users, stats=stats, notifs=notifs, page=page, total_pages=total_pages, now=now)
    db.close()
    return html

# --- RUTAS DE ADMINISTRACIÓN (DASHBOARD) ---

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
    return redirect(url_for('main.dashboard'))

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
        
        # Feedback inteligente al usuario según si la notificación es para hoy o el futuro
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

# --- FUNCIONES DE EXPORTACIÓN ---

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