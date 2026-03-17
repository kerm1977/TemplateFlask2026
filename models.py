# models.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from db import Base

class User(Base):
    """Modelo principal de usuario con roles y datos básicos"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(100), nullable=False)
    last_name1 = Column(String(100), nullable=False)
    last_name2 = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    phone = Column(String(20), nullable=False)
    birth_date = Column(DateTime, nullable=False)
    password = Column(String(255), nullable=False)
    avatar = Column(String(255), default='default.png')
    
    # Roles: Superusuario (inyectado), Administrador, Colaborador, Usuario
    role = Column(String(50), default='Usuario') 
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    extra_fields = relationship("ExtraField", back_populates="user", cascade="all, delete-orphan")

class ExtraField(Base):
    """Modelo para almacenar los campos dinámicos agregados en el registro"""
    __tablename__ = 'extra_fields'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    
    field_type = Column(String(50), nullable=False)
    label = Column(String(100)) 
    value = Column(Text, nullable=False)
    
    user = relationship("User", back_populates="extra_fields")

class BusinessCard(Base):
    """Modelo para las tarjetas de presentación empresariales/personales"""
    __tablename__ = 'business_cards'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey('users.id'))
    logo = Column(String(255))
    name = Column(String(150), nullable=False)
    phone = Column(String(20))
    email = Column(String(150))
    whatsapp = Column(String(20))
    address = Column(Text)
    schedule = Column(Text)
    contact_name = Column(String(150))
    
    # Guarda el color de fondo elegido
    theme = Column(String(50), default='dark') 
    
    created_at = Column(DateTime, default=datetime.utcnow)

class Notification(Base):
    """Modelo para el notificador de mensajes flash en el Home"""
    __tablename__ = 'notifications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    image = Column(String(255)) 
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    
    notification_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    visibility = Column(String(50), default='Todos')
    is_active = Column(Integer, default=1)

class SystemSetting(Base):
    """NUEVO: Almacena configuraciones globales del sistema (Nombre app, Tema, etc.)"""
    __tablename__ = 'system_settings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(String(255), nullable=True)