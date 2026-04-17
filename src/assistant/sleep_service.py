from datetime import datetime
from typing import Optional

from sqlalchemy import select

from src.assistant.db import async_session
from src.assistant.models import SleepLog, User


async def save_sleep_log(
    user_id: str,
    hora_acostado: str | None,
    hora_levantado: str,
    duracion_horas: float | None,
    energia_al_despertar: int | None,
    fecha: str | None = None,
    notas: str | None = None
) -> SleepLog:
    async with async_session() as session:
        log = SleepLog(
            user_id=user_id,
            fecha=fecha or datetime.now().strftime("%Y-%m-%d"),
            hora_acostado=hora_acostado,
            hora_levantado=hora_levantado,
            duracion_horas=str(duracion_horas) if duracion_horas else None,
            energia_al_despertar=energia_al_despertar,
            notas=notas
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log


async def get_last_sleep_log(user_id: str) -> SleepLog | None:
    async with async_session() as session:
        result = await session.execute(
            select(SleepLog)
            .where(SleepLog.user_id == user_id)
            .order_by(SleepLog.fecha.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def get_sleep_stats(user_id: str, days: int = 7) -> dict:
    async with async_session() as session:
        result = await session.execute(
            select(SleepLog)
            .where(SleepLog.user_id == user_id)
            .order_by(SleepLog.fecha.desc())
            .limit(days)
        )
        logs = result.scalars().all()

        if not logs:
            return {"avg_duration": None, "avg_energy": None, "days_logged": 0}

        durations = [float(l.duracion_horas) for l in logs if l.duracion_horas]
        energies = [l.energia_al_despertar for l in logs if l.energia_al_despertar]

        return {
            "avg_duration": sum(durations) / len(durations) if durations else None,
            "avg_energy": sum(energies) / len(energies) if energies else None,
            "days_logged": len(logs),
            "logs": [
                {
                    "fecha": l.fecha,
                    "duracion": l.duracion_horas,
                    "energia": l.energia_al_despertar
                }
                for l in logs
            ]
        }