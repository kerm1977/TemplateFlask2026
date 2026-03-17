# users.py

import json
import re
from datetime import datetime
from flask_bcrypt import Bcrypt
from sqlalchemy.orm import Session
from models import User, ExtraField, BusinessCard, Notification

bcrypt = Bcrypt()

def format_title_case(text):
    """Asegura que cada palabra inicie en mayúscula (Title Case)"""
    if not text:
        return ""
    return ' '.join(word.capitalize() for word in text.split())

def validate_name(name):
    """
    Valida que el nombre no contenga números ni caracteres especiales.
    Permite un solo espacio para nombres compuestos.
    """
    if not name:
        return False
    # Regex: Solo letras y un espacio opcional en el medio
    pattern = r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ]+( [a-zA-ZáéíóúÁÉÍÓÚñÑ]+)?$'
    return bool(re.match(pattern, name))

def get_user_by_email(db: Session, email):
    return db.query(User).filter(User.email == email.lower()).first()

def create_user(db: Session, data, extra_fields=None):
    """
    Crea un usuario aplicando las reglas de formato y hashing de contraseña.
    """
    hashed_pw = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    
    new_user = User(
        first_name=format_title_case(data['first_name']),
        last_name1=format_title_case(data['last_name1']),
        last_name2=format_title_case(data['last_name2']),
        email=data['email'].lower(),
        phone=data['phone'],
        birth_date=data['birth_date'], # Objeto datetime esperado
        password=hashed_pw,
        avatar=data.get('avatar', 'default.png'),
        role=data.get('role', 'Usuario')
    )
    
    db.add(new_user)
    db.flush() # Para obtener el ID antes del commit final
    
    if extra_fields:
        for field in extra_fields:
            # Si es un campo complejo (Proveedor, etc.), el value viene como dict/JSON
            val = field['value']
            if isinstance(val, dict):
                val = json.dumps(val)
                
            new_field = ExtraField(
                user_id=new_user.id,
                field_type=field['type'],
                label=field.get('label', ''),
                value=val
            )
            db.add(new_field)
            
    db.commit()
    return new_user

def prepare_export_data(user: User):
    """
    Prepara un diccionario con la información del usuario filtrando campos vacíos,
    None o null para las exportaciones a WhatsApp o TXT.
    """
    data = {
        "Nombre Completo": f"{user.first_name} {user.last_name1} {user.last_name2}",
        "Email": user.email,
        "Teléfono": user.phone,
        "Fecha de Nacimiento": user.birth_date.strftime('%d/%m/%Y'),
        "Rol": user.role,
        "Registro": user.created_at.strftime('%d/%m/%Y %H:%M')
    }
    
    # Agregar campos extra
    for field in user.extra_fields:
        try:
            # Intentar cargar como JSON si es complejo
            val = json.loads(field.value)
            if isinstance(val, dict):
                for k, v in val.items():
                    if v and str(v).strip():
                        data[f"{field.field_type} - {k}"] = v
            else:
                if val and str(val).strip():
                    data[field.label or field.field_type] = val
        except:
            if field.value and str(field.value).strip():
                data[field.label or field.field_type] = field.value

    # Filtrar finales (No exportar vacíos, None o null)
    return {k: v for k, v in data.items() if v not in [None, "None", "null", ""]}

def update_password(db: Session, user: User, current_pw, new_pw):
    """Valida contraseña actual y actualiza a la nueva"""
    if bcrypt.check_password_hash(user.password, current_pw):
        user.password = bcrypt.generate_password_hash(new_pw).decode('utf-8')
        db.commit()
        return True
    return False