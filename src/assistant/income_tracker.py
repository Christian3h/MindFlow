from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.assistant.models import Income


async def save_income(
    session: AsyncSession,
    user_id: str,
    monto: float,
    fuente: str | None = None,
    fecha: str | None = None,
    notas: str | None = None
) -> Income:
    now = datetime.now(timezone.utc)
    
    income = Income(
        user_id=user_id,
        monto=str(monto),
        fuente=fuente,
        fecha=fecha or now.strftime("%Y-%m-%d"),
        notas=notas
    )
    
    session.add(income)
    await session.commit()
    await session.refresh(income)
    
    return income


async def get_incomes_by_date_range(
    session: AsyncSession,
    user_id: str,
    start_date: str,
    end_date: str
) -> list[Income]:
    result = await session.execute(
        select(Income)
        .where(Income.user_id == user_id)
        .where(Income.fecha >= start_date)
        .where(Income.fecha <= end_date)
        .order_by(Income.fecha.desc())
    )
    return list(result.scalars().all())


async def get_recent_incomes(session: AsyncSession, user_id: str, limit: int = 10) -> list[Income]:
    result = await session.execute(
        select(Income)
        .where(Income.user_id == user_id)
        .order_by(Income.fecha.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_monthly_total(session: AsyncSession, user_id: str, year: int, month: int) -> float:
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    
    result = await session.execute(
        select(func.sum(Income.monto.cast(type=float)))
        .where(Income.user_id == user_id)
        .where(Income.fecha >= start_date)
        .where(Income.fecha < end_date)
    )
    
    total = result.scalar_one_or_none()
    return total if total else 0.0


async def get_income_by_id(session: AsyncSession, income_id: str, user_id: str) -> Income | None:
    result = await session.execute(
        select(Income)
        .where(Income.id == income_id)
        .where(Income.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_latest_income(session: AsyncSession, user_id: str) -> Income | None:
    result = await session.execute(
        select(Income)
        .where(Income.user_id == user_id)
        .order_by(Income.fecha.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def delete_income(session: AsyncSession, income_id: str, user_id: str) -> bool:
    result = await session.execute(
        select(Income).where(Income.id == income_id).where(Income.user_id == user_id)
    )
    income = result.scalar_one_or_none()
    
    if income:
        await session.delete(income)
        await session.commit()
        return True
    
    return False