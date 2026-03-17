# app.py

import os
from flask import Flask, session
from flask_bcrypt import Bcrypt
from datetime import datetime

# Importaciones locales
from db import engine, Base, SessionLocal
from models import User
from users import bcrypt

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuración de carpetas para PWA y estáticos
app.static_folder = 'static'
app.template_folder = 'templates'

def inject_superusers():
    """
    Inyecta automáticamente 2 superusuarios en la base de datos si no existen.
    Estos usuarios tienen el rol 'Superusuario' y se crean al iniciar la app.
    """
    db = SessionLocal()
    try:
        superusers_data = [
            {
                "first_name": "System",
                "last_name1": "Admin",
                "last_name2": "One",
                "email": "admin1@sistema.local",
                "password": "SuperPassword2025!",
                "phone": "00000000",
                "birth_date": datetime(1990, 1, 1)
            },
            {
                "first_name": "Root",
                "last_name2": "Admin",
                "last_name1": "Two",
                "email": "admin2@sistema.local",
                "password": "RootSecure2025*",
                "phone": "00000000",
                "birth_date": datetime(1990, 1, 1)
            }
        ]

        for data in superusers_data:
            exists = db.query(User).filter(User.email == data['email']).first()
            if not exists:
                hashed_pw = bcrypt.generate_password_hash(data['password']).decode('utf-8')
                new_su = User(
                    first_name=data['first_name'],
                    last_name1=data['last_name1'],
                    last_name2=data['last_name2'],
                    email=data['email'],
                    password=hashed_pw,
                    phone=data['phone'],
                    birth_date=data['birth_date'],
                    role='Superusuario'
                )
                db.add(new_su)
        db.commit()
    except Exception as e:
        print(f"Error inyectando superusuarios: {e}")
        db.rollback()
    finally:
        db.close()

def init_app():
    """Inicialización de base de datos y componentes"""
    # Crear tablas si no existen
    Base.metadata.create_all(bind=engine)
    
    # Inyectar superusuarios
    inject_superusers()
    
    # Aquí se registrarán los Blueprints en el siguiente paso
    from routes import main_bp
    app.register_blueprint(main_bp)

if __name__ == '__main__':
    init_app()
    # Configuración para correr localmente o en red (Tailscale)
    app.run(host='0.0.0.0', port=5000, debug=True)