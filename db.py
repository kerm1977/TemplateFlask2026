# db.py

import os
import socket
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Definición de la Base para los modelos
Base = declarative_base()

def get_db_engine():
    """
    Función inteligente para determinar el motor de base de datos:
    1. PythonAnywhere: Detecta el dominio de PA.
    2. Tailscale/Red: Intenta conectar al host de MySQL local expuesto.
    3. Local: Si no hay red o variables, usa SQLite.
    """
    
    # --- CONFIGURACIÓN DE PARÁMETROS ---
    MYSQL_USER = 'tu_usuario_mysql'
    MYSQL_PASSWORD = 'tu_password_mysql'
    MYSQL_DB = 'tu_nombre_db'
    
    # IP de Tailscale de la máquina que tiene MySQL (servidor local para el mundo)
    MYSQL_HOST_TAILSCALE = '100.x.y.z' 
    
    # Host predeterminado de PythonAnywhere
    MYSQL_HOST_PA = f"{MYSQL_USER}.mysql.pythonanywhere-services.com"

    # 1. Verificación para PythonAnywhere
    if 'PYTHONANYWHERE_DOMAIN' in os.environ:
        conn_string = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST_PA}/{MYSQL_DB}"
        return create_engine(conn_string, pool_recycle=280)

    # 2. Verificación para Tailscale / MySQL Remoto
    # Intentamos ver si el puerto 3306 está abierto en la IP de Tailscale antes de fallar
    try:
        # Timeout corto para no retrasar el inicio de la app
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((MYSQL_HOST_TAILSCALE, 3306))
        sock.close()
        
        if result == 0:
            conn_string = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST_TAILSCALE}/{MYSQL_DB}"
            return create_engine(conn_string)
    except Exception:
        pass

    # 3. Fallback: SQLite Local (Uso desarrollo/desconectado)
    db_path = os.path.join(os.path.dirname(__file__), 'local_database.db')
    return create_engine(f"sqlite:///{db_path}")

# Inicialización de motor y sesión
engine = get_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db_session():
    """Generador de sesión para ser usado como dependencia o contexto"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()