# app.py

import os
from flask import Flask, session, send_from_directory
from datetime import datetime

# Importaciones locales
from db import engine, Base, SessionLocal
from models import User
from users import bcrypt
from routes import main_bp

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuración de carpetas para PWA y estáticos
app.static_folder = 'static'
app.template_folder = 'templates'

@app.route('/sw.js')
def serve_sw():
    """
    Ruta crítica para PWA: Sirve el Service Worker desde la raíz 
    aunque el archivo físico esté en la carpeta static.
    """
    return send_from_directory(app.static_folder, 'sw.js')

@app.route('/manifest.json')
def serve_manifest():
    """Sirve el manifiesto desde la raíz"""
    return send_from_directory(app.static_folder, 'manifest.json')

def inject_superusers():
    """
    Inyecta automáticamente a los administradores principales en la base de datos.
    Garantiza que siempre existan y tengan el rol de 'Superusuario'.
    """
    db = SessionLocal()
    try:
        # Credenciales maestras solicitadas
        superusers_data = [
            {
                "first_name": "Kenth",
                "last_name1": "Admin",
                "last_name2": "Principal",
                "email": "kenth1977@gmail.com",
                "password": "CR129x7848n",
                "phone": "00000000",
                "birth_date": datetime(1977, 1, 1)
            },
            {
                "first_name": "LT",
                "last_name1": "Hiking",
                "last_name2": "CR",
                "email": "lthikingcr@gmail.com",
                "password": "CR129x7848n",
                "phone": "00000000",
                "birth_date": datetime(1990, 1, 1)
            }
        ]

        for data in superusers_data:
            user = db.query(User).filter(User.email == data['email']).first()
            
            if not user:
                # Si no existen, los creamos con la contraseña encriptada
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
            else:
                # Si ya existían, garantizamos que su rol SIEMPRE sea Superusuario
                if user.role != 'Superusuario':
                    user.role = 'Superusuario'
                    
        db.commit()
    except Exception as e:
        print(f"Error inyectando superusuarios: {e}")
        db.rollback()
    finally:
        db.close()

# --- INICIALIZACIÓN AUTOMÁTICA ---
# Al ponerlo dentro de app_context, garantizamos que se ejecute SIEMPRE al arrancar
# el servidor, independientemente de si usas 'flask run' o 'python app.py'
with app.app_context():
    # 1. Crear tablas si no existen
    Base.metadata.create_all(bind=engine)
    # 2. Inyectar superusuarios maestros garantizados
    inject_superusers()

# Registrar los Blueprints (Rutas)
app.register_blueprint(main_bp)

if __name__ == '__main__':
    # Configuración para correr localmente o en red
    app.run(host='0.0.0.0', port=5000, debug=True)