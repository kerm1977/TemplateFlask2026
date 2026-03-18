import os
import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from sqlalchemy import Column, Integer, String, Text, Boolean, Date

# Importaciones del proyecto existente
from db import Base, engine, SessionLocal
from routes import admin_required

calendario_bp = Blueprint('calendario', __name__)

# --- MODELO DE EVENTO AISLADO ---
# Se crea aquí para no tocar models.py
class Event(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True, autoincrement=True)
    image = Column(String(255))
    name = Column(String(150), nullable=False)
    activity_type = Column(String(100))
    currency = Column(String(10))
    price = Column(Integer)
    reserve = Column(Integer)
    days = Column(Integer)
    
    date_start = Column(Date)
    time_start = Column(String(50))
    location_start = Column(String(150))
    
    transport_type = Column(String(50))
    date_end = Column(Date)
    time_end = Column(String(50))
    
    chat_only = Column(Boolean, default=False)
    
    includes = Column(Text)
    includes_other = Column(String(150))
    
    sinpe = Column(String(150))
    account = Column(String(200))
    additional_info = Column(Text)

# Forzar la creación de la tabla si no existe en la Base de Datos
Event.__table__.create(engine, checkfirst=True)

# --- INYECCIÓN DE EVENTOS AL HOME SIN TOCAR ROUTES.PY ---
@calendario_bp.app_context_processor
def inject_events():
    db = SessionLocal()
    # Traer eventos ordenados por fecha
    events = db.query(Event).order_by(Event.date_start.asc()).all()
    
    meses_es = ['', 'ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
    
    grouped = {}
    for ev in events:
        if ev.date_start:
            month_name = meses_es[ev.date_start.month]
            if month_name not in grouped:
                grouped[month_name] = []
            grouped[month_name].append(ev)
            
    db.close()
    return dict(grouped_events=grouped)

# --- RUTA PARA CREAR LA ACTIVIDAD ---
@calendario_bp.route('/calendario', methods=['GET', 'POST'])
@admin_required
def crear_evento():
    if request.method == 'POST':
        db = SessionLocal()
        try:
            # Procesar Imagen
            image_file = request.files.get('image')
            image_filename = None
            if image_file and image_file.filename != '':
                os.makedirs('static/uploads', exist_ok=True)
                filename = secure_filename(image_file.filename)
                unique_filename = f"event_{int(datetime.now().timestamp())}_{filename}"
                filepath = os.path.join('static/uploads', unique_filename)
                image_file.save(filepath)
                image_filename = unique_filename
            
            days = int(request.form.get('days', 1))
            
            # Fechas comunes
            date_start_str = request.form.get('date_start')
            date_start = datetime.strptime(date_start_str, '%Y-%m-%d').date() if date_start_str else None
            
            date_end_str = request.form.get('date_end')
            date_end = datetime.strptime(date_end_str, '%Y-%m-%d').date() if date_end_str else None
            
            # Includes a JSON
            includes_list = request.form.getlist('includes[]')
            includes_json = json.dumps(includes_list)

            new_event = Event(
                image=image_filename,
                name=request.form.get('name'),
                activity_type=request.form.get('activity_type'),
                currency=request.form.get('currency'),
                price=int(request.form.get('price', 0)),
                reserve=int(request.form.get('reserve', 0)),
                days=days,
                date_start=date_start,
                time_start=request.form.get('time_start'),
                location_start=request.form.get('location_start'),
                transport_type=request.form.get('transport_type') if days > 1 else None,
                date_end=date_end if days > 1 else None,
                time_end=request.form.get('time_end') if days > 1 else None,
                chat_only='chat_only' in request.form,
                includes=includes_json,
                includes_other=request.form.get('includes_other'),
                sinpe=request.form.get('actSinpe'),
                account=request.form.get('actCuenta'),
                additional_info=request.form.get('additional_info')
            )
            
            db.add(new_event)
            db.commit()
            flash('Evento / Caminata creado con éxito', 'success')
            return redirect(url_for('main.home'))
            
        except Exception as e:
            db.rollback()
            flash(f'Error al crear el evento: {str(e)}', 'danger')
        finally:
            db.close()
            
    return render_template('calendario.html')