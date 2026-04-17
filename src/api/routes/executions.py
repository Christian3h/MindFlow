from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import json

from src.models import get_session, Execution
from src.api.schemas import ExecutionResponse, ExecutionUpdate

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(execution_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Execution).where(Execution.id == execution_id))
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(status_code=404, detail="Ejecucion no encontrada")

    return ExecutionResponse(
        id=execution.id,
        flow_id=execution.flow_id,
        status=execution.status,
        started_at=execution.started_at,
        finished_at=execution.finished_at,
        error=execution.error,
        context=json.loads(execution.context) if execution.context else None,
    )


@router.patch("/{execution_id}")
async def update_execution(
    execution_id: str,
    update_data: ExecutionUpdate,
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(select(Execution).where(Execution.id == execution_id))
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(status_code=404, detail="Ejecucion no encontrada")

    execution.status = update_data.status
    if update_data.error is not None:
        execution.error = update_data.error
    if update_data.finished_at is not None:
        execution.finished_at = update_data.finished_at

    await session.commit()

    return {"message": "Ejecucion actualizada", "id": execution_id}
