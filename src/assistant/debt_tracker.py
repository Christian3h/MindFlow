from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.assistant.models import Debt, DebtPayment


async def save_debt(
    session: AsyncSession,
    user_id: str,
    entidad: str,
    monto_original: float,
    monto_actual: float | None = None,
    cuota_valor: float | None = None,
    cuota_numero: int | None = None,
    cuotas_totales: int | None = None,
    fecha_inicio: str | None = None,
    notas: str | None = None
) -> Debt:
    now = datetime.now(timezone.utc)
    
    debt = Debt(
        user_id=user_id,
        entidad=entidad,
        monto_original=str(monto_original),
        monto_actual=str(monto_actual if monto_actual is not None else monto_original),
        cuota_valor=str(cuota_valor) if cuota_valor is not None else None,
        cuota_numero=cuota_numero,
        cuotas_totales=cuotas_totales,
        fecha_inicio=fecha_inicio or now.strftime("%Y-%m-%d"),
        notas=notas
    )
    
    session.add(debt)
    await session.commit()
    await session.refresh(debt)
    
    return debt


async def get_active_debts(session: AsyncSession, user_id: str) -> list[Debt]:
    result = await session.execute(
        select(Debt)
        .where(Debt.user_id == user_id)
        .where(Debt.activa == 1)
        .order_by(Debt.fecha_creacion.desc())
    )
    return list(result.scalars().all())


async def get_debt_by_id(session: AsyncSession, debt_id: str, user_id: str) -> Debt | None:
    result = await session.execute(
        select(Debt)
        .where(Debt.id == debt_id)
        .where(Debt.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_debt_by_entity(session: AsyncSession, user_id: str, entidad: str) -> Debt | None:
    result = await session.execute(
        select(Debt)
        .where(Debt.user_id == user_id)
        .where(Debt.entidad.ilike(f"%{entidad}%"))
        .where(Debt.activa == 1)
    )
    return result.scalar_one_or_none()


async def update_debt_balance(session: AsyncSession, debt_id: str, new_balance: float) -> Debt | None:
    result = await session.execute(
        select(Debt).where(Debt.id == debt_id)
    )
    debt = result.scalar_one_or_none()
    
    if debt:
        debt.monto_actual = str(new_balance)
        if float(new_balance) <= 0:
            debt.activa = 0
        await session.commit()
        await session.refresh(debt)
    
    return debt


async def record_debt_payment(
    session: AsyncSession,
    debt_id: str,
    user_id: str,
    monto: float,
    notas: str | None = None
) -> DebtPayment:
    now = datetime.now(timezone.utc)
    fecha = now.strftime("%Y-%m-%d")
    
    payment = DebtPayment(
        debt_id=debt_id,
        user_id=user_id,
        monto=str(monto),
        fecha=fecha,
        notas=notas
    )
    
    session.add(payment)
    
    debt = await get_debt_by_id(session, debt_id, user_id)
    if debt:
        new_balance = float(debt.monto_actual) - monto
        debt.monto_actual = str(new_balance)
        debt.cuota_numero = (debt.cuota_numero or 0) + 1
        if new_balance <= 0:
            debt.activa = 0
    
    await session.commit()
    await session.refresh(payment)
    
    return payment


async def get_debt_payments(session: AsyncSession, debt_id: str) -> list[DebtPayment]:
    result = await session.execute(
        select(DebtPayment)
        .where(DebtPayment.debt_id == debt_id)
        .order_by(DebtPayment.fecha.desc())
    )
    return list(result.scalars().all())


async def get_total_debt(session: AsyncSession, user_id: str) -> float:
    result = await session.execute(
        select(func.sum(Debt.monto_actual.cast(type=float)))
        .where(Debt.user_id == user_id)
        .where(Debt.activa == 1)
    )
    total = result.scalar_one_or_none()
    return total if total else 0.0


async def delete_debt(session: AsyncSession, debt_id: str, user_id: str) -> bool:
    result = await session.execute(
        select(Debt).where(Debt.id == debt_id).where(Debt.user_id == user_id)
    )
    debt = result.scalar_one_or_none()
    
    if debt:
        debt.activa = 0
        await session.commit()
        return True
    
    return False