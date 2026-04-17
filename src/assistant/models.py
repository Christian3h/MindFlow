from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import Column, String, Text, Integer, func

from .db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nombre = Column(String, nullable=True)
    zona_horaria = Column(String, default="America/Bogota")
    tono_coach = Column(String, default="amable")
    fecha_creacion = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    timestamp = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())
    mensaje_usuario = Column(Text, nullable=False)
    respuesta_bot = Column(Text, nullable=True)
    intencion = Column(String, nullable=True)
    contexto_json = Column(Text, nullable=True)


class SleepLog(Base):
    __tablename__ = "sleep_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    fecha = Column(String, nullable=False)
    hora_acostado = Column(String, nullable=True)
    hora_levantado = Column(String, nullable=True)
    duracion_horas = Column(String, nullable=True)
    calidad = Column(Integer, nullable=True)
    energia_al_despertar = Column(Integer, nullable=True)
    notas = Column(Text, nullable=True)


class Routine(Base):
    __tablename__ = "routines"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    nombre = Column(String, nullable=False)
    activa = Column(Integer, default=1)
    dias_semana = Column(String, nullable=True)


class RoutineBlock(Base):
    __tablename__ = "routine_blocks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    routine_id = Column(String, nullable=False)
    nombre = Column(String, nullable=False)
    hora_inicio = Column(String, nullable=False)
    hora_fin = Column(String, nullable=False)
    categoria = Column(String, nullable=True)
    prioridad = Column(String, default="media")


class DailyCheckin(Base):
    __tablename__ = "daily_checkins"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    fecha = Column(String, nullable=False)
    hora = Column(String, nullable=False)
    bloque_esperado = Column(String, nullable=True)
    estaba_haciendo = Column(Text, nullable=True)
    estaba_en_rutina = Column(Integer, default=0)
    energia_momento = Column(Integer, nullable=True)
    notas = Column(Text, nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    fecha = Column(String, nullable=False)
    monto = Column(String, nullable=False)
    tipo = Column(String, nullable=False)
    categoria = Column(String, nullable=True)
    subcategoria = Column(String, nullable=True)
    descripcion = Column(Text, nullable=True)
    fue_impulsivo = Column(Integer, nullable=True)
    metodo_pago = Column(String, nullable=True)


class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    titulo = Column(String, nullable=False)
    fecha = Column(String, nullable=False)
    hora = Column(String, nullable=True)
    tipo = Column(String, default="recordatorio")
    recurrente = Column(Integer, default=0)
    frecuencia_recurrencia = Column(String, nullable=True)
    anticipacion_aviso_horas = Column(Integer, default=24)
    completado = Column(Integer, default=0)


class DailySummary(Base):
    __tablename__ = "daily_summary"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    fecha = Column(String, nullable=False)
    horas_dormido = Column(String, nullable=True)
    energia_promedio = Column(String, nullable=True)
    bloques_cumplidos = Column(Integer, default=0)
    bloques_totales = Column(Integer, default=0)
    porcentaje_cumplimiento = Column(String, nullable=True)
    gasto_total_dia = Column(String, nullable=True)
    estado_animo = Column(String, nullable=True)
    notas_bot = Column(Text, nullable=True)
