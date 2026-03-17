# routes.py

import os
import base64
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from datetime import datetime
import json
import io

# Importaciones locales
from db import SessionLocal
from models import User, ExtraField, Notification, BusinessCard
from users import create_user, get_user_by_email, bcrypt, prepare_export_data, update_password

main_bp = Blueprint('main', __name__)

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
    # Obtener notificaciones activas para el flash en Home
    now = datetime.utcnow()
    notifications = db.query(Notification).filter(
        Notification.start_date <= now,
        Notification.end_date >= now,
        Notification.is_active == 1
    ).all()
    
    # Renderizar ANTES de cerrar la base de datos
    html = render_template('home.html', notifications=notifications)
    db.close()
    return html

# --- AUTENTICACIÓN ---

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember')
        
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
            # Procesar el Avatar (Acepta archivo crudo o base64 recortado del editor)
            avatar_filename = 'default.png'
            avatar_base64 = request.form.get('avatar_base64')
            avatar_file = request.files.get('avatar')
            
            os.makedirs('static/img', exist_ok=True) # Asegurar que la carpeta existe

            if avatar_base64:
                # Si viene del editor visual (Cropper)
                header, encoded = avatar_base64.split(",", 1)
                file_ext = header.split('/')[1].split(';')[0]
                unique_filename = f"avatar_{int(datetime.utcnow().timestamp())}.{file_ext}"
                filepath = os.path.join('static/img', unique_filename)
                with open(filepath, "wb") as fh:
                    fh.write(base64.b64decode(encoded))
                avatar_filename = unique_filename
            elif avatar_file and avatar_file.filename != '':
                # Si viene como archivo tradicional sin editar
                filename = secure_filename(avatar_file.filename)
                unique_filename = f"avatar_{int(datetime.utcnow().timestamp())}_{filename}"
                filepath = os.path.join('static/img', unique_filename)
                avatar_file.save(filepath)
                avatar_filename = unique_filename

            # Procesar datos básicos
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
            
            # Procesar campos extra dinámicos
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
    
    # Renderizar ANTES de cerrar la base de datos para evitar DetachedInstanceError
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
            # Procesar el Avatar (Acepta archivo crudo o base64 recortado del editor)
            avatar_base64 = request.form.get('avatar_base64')
            avatar_file = request.files.get('avatar')
            
            os.makedirs('static/img', exist_ok=True)

            if avatar_base64:
                # Si viene del editor visual (Cropper)
                header, encoded = avatar_base64.split(",", 1)
                file_ext = header.split('/')[1].split(';')[0]
                unique_filename = f"avatar_{int(datetime.utcnow().timestamp())}.{file_ext}"
                filepath = os.path.join('static/img', unique_filename)
                with open(filepath, "wb") as fh:
                    fh.write(base64.b64decode(encoded))
                user.avatar = unique_filename
            elif avatar_file and avatar_file.filename != '':
                # Si viene como archivo tradicional
                filename = secure_filename(avatar_file.filename)
                unique_filename = f"avatar_{int(datetime.utcnow().timestamp())}_{filename}"
                filepath = os.path.join('static/img', unique_filename)
                avatar_file.save(filepath)
                user.avatar = unique_filename

            # Actualizar datos básicos
            user.first_name = request.form.get('first_name')
            user.last_name1 = request.form.get('last_name1')
            user.last_name2 = request.form.get('last_name2')
            user.phone = request.form.get('phone')
            
            # Actualizar fecha de nacimiento
            day = request.form.get('day')
            month = request.form.get('month')
            year = request.form.get('year')
            if day and month and year:
                user.birth_date = datetime.strptime(f"{year}-{month}-{day}", '%Y-%m-%d')
            
            # Limpiar campos dinámicos antiguos para evitar duplicados
            db.query(ExtraField).filter(ExtraField.user_id == user.id).delete()
            
            # Recopilar e insertar los nuevos campos dinámicos
            field_types = request.form.getlist('extra_field_type[]')
            field_values = request.form.getlist('extra_field_value[]')
            
            for f_type, f_val in zip(field_types, field_values):
                if f_type and f_val:
                    new_field = ExtraField(
                        user_id=user.id,
                        field_type=f_type,
                        value=f_val,
                        label=f_type # Por defecto usamos el tipo como etiqueta
                    )
                    db.add(new_field)
            
            # Actualizar timestamp
            user.updated_at = datetime.utcnow()
            
            db.commit()
            flash('Perfil actualizado con éxito.', 'success')
            db.close()
            return redirect(url_for('main.perfil'))
            
        except Exception as e:
            db.rollback()
            flash(f'Error al actualizar el perfil: {str(e)}', 'danger')
            db.close()
            return redirect(url_for('main.editar_perfil'))

    # Si es GET, renderizamos ANTES de cerrar la sesión
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
        'recent': db.query(User).filter(User.created_at >= datetime.utcnow().replace(day=1)).count()
    }
    
    # Renderizar ANTES de cerrar la base de datos
    html = render_template('dashboard.html', users=users, stats=stats)
    db.close()
    return html

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