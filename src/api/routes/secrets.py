from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from src.models import get_session, Secret
from src.api.schemas import SecretCreate, SecretResponse

router = APIRouter(prefix="/secrets", tags=["secrets"])


@router.post("", response_model=SecretResponse)
async def create_or_update_secret(secret: SecretCreate, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Secret).where(Secret.key == secret.key))
    existing = result.scalar_one_or_none()

    if existing:
        existing.value = secret.value
        await session.commit()
        return SecretResponse(key=existing.key, created_at=existing.created_at)

    now = datetime.utcnow().isoformat()
    new_secret = Secret(
        key=secret.key,
        value=secret.value,
        created_at=now,
    )
    session.add(new_secret)
    await session.commit()

    return SecretResponse(key=new_secret.key, created_at=new_secret.created_at)


@router.get("", response_model=list[SecretResponse])
async def list_secrets(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Secret))
    secrets = result.scalars().all()

    return [SecretResponse(key=s.key, created_at=s.created_at) for s in secrets]


@router.delete("/{key}")
async def delete_secret(key: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Secret).where(Secret.key == key))
    secret = result.scalar_one_or_none()

    if not secret:
        raise HTTPException(status_code=404, detail="Secret no encontrado")

    await session.delete(secret)
    await session.commit()

    return {"message": "Secret eliminado"}
