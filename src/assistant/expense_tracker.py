from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.assistant.models import Transaction


async def save_transaction(
    session: AsyncSession,
    user_id: str,
    monto: float,
    categoria: str,
    descripcion: str | None = None,
    subcategoria: str | None = None,
    fue_impulsivo: int | None = None,
    metodo_pago: str | None = None
) -> Transaction:
    now = datetime.now(timezone.utc)
    fecha = now.strftime("%Y-%m-%d")
    
    transaction = Transaction(
        user_id=user_id,
        fecha=fecha,
        monto=str(monto),
        tipo="gasto",
        categoria=categoria,
        subcategoria=subcategoria,
        descripcion=descripcion,
        fue_impulsivo=fue_impulsivo,
        metodo_pago=metodo_pago
    )
    
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    
    return transaction


async def save_multiple_transactions(
    session: AsyncSession,
    user_id: str,
    expenses: list
) -> list[Transaction]:
    transactions = []
    
    for expense in expenses:
        transaction = await save_transaction(
            session=session,
            user_id=user_id,
            monto=expense.monto,
            categoria=expense.categoria,
            descripcion=expense.descripcion,
            subcategoria=expense.subcategoria,
            metodo_pago=expense.metodo_pago
        )
        transactions.append(transaction)
    
    return transactions


async def get_daily_total(session: AsyncSession, user_id: str, fecha: str | None = None) -> float:
    if fecha is None:
        fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    result = await session.execute(
        select(func.sum(Transaction.monto.cast(type=float)))
        .where(Transaction.user_id == user_id)
        .where(Transaction.fecha == fecha)
        .where(Transaction.tipo == "gasto")
    )
    
    total = result.scalar_one_or_none()
    return total if total else 0.0


async def get_transactions_by_date_range(
    session: AsyncSession,
    user_id: str,
    start_date: str,
    end_date: str
) -> list[Transaction]:
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.fecha >= start_date)
        .where(Transaction.fecha <= end_date)
        .order_by(Transaction.fecha.desc())
    )
    
    return list(result.scalars().all())


async def get_recent_transactions(session: AsyncSession, user_id: str, limit: int = 10) -> list[Transaction]:
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.fecha.desc())
        .limit(limit)
    )
    
    return list(result.scalars().all())


async def get_category_summary(session: AsyncSession, user_id: str, fecha: str) -> dict[str, float]:
    result = await session.execute(
        select(Transaction.categoria, func.sum(Transaction.monto.cast(type=float)))
        .where(Transaction.user_id == user_id)
        .where(Transaction.fecha == fecha)
        .where(Transaction.tipo == "gasto")
        .group_by(Transaction.categoria)
    )
    
    return {row[0]: row[1] for row in result.all()}


async def mark_transaction_impulsive(session: AsyncSession, transaction_id: str, impulsive: bool) -> Transaction | None:
    result = await session.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()
    
    if transaction:
        transaction.fue_impulsivo = 1 if impulsive else 0
        await session.commit()
        await session.refresh(transaction)
    
    return transaction


async def delete_transaction(session: AsyncSession, transaction_id: str) -> bool:
    result = await session.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()
    
    if transaction:
        await session.delete(transaction)
        await session.commit()
        return True
    
    return False