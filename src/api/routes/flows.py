from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
import json
from datetime import datetime

from src.models import get_session, Flow
from src.api.schemas import FlowCreate, FlowUpdate, FlowResponse
from src.engine import update_flow_schedule

router = APIRouter(prefix="/flows", tags=["flows"])


@router.post("", response_model=FlowResponse)
async def create_flow(flow: FlowCreate, session: AsyncSession = Depends(get_session)):
    now = datetime.utcnow().isoformat()
    new_flow = Flow(
        id=str(uuid4()),
        name=flow.name,
        description=flow.description,
        enabled=False,
        trigger_type=flow.trigger_type or "manual",
        trigger_config=json.dumps(flow.trigger_config) if flow.trigger_config else None,
        nodes=json.dumps(flow.nodes),
        created_at=now,
        updated_at=now,
    )
    session.add(new_flow)
    await session.commit()
    await session.refresh(new_flow)

    trigger_cfg = json.loads(new_flow.trigger_config) if new_flow.trigger_config else None
    await update_flow_schedule(
        new_flow.id,
        bool(new_flow.enabled),
        new_flow.trigger_type,
        trigger_cfg
    )

    return FlowResponse(
        id=new_flow.id,
        name=new_flow.name,
        description=new_flow.description,
        enabled=bool(new_flow.enabled),
        trigger_type=new_flow.trigger_type,
        trigger_config=trigger_cfg,
        nodes=json.loads(new_flow.nodes),
        created_at=new_flow.created_at,
        updated_at=new_flow.updated_at,
    )


@router.get("", response_model=list[FlowResponse])
async def list_flows(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Flow))
    flows = result.scalars().all()

    return [
        FlowResponse(
            id=f.id,
            name=f.name,
            description=f.description,
            enabled=bool(f.enabled),
            trigger_type=f.trigger_type,
            trigger_config=json.loads(f.trigger_config) if f.trigger_config else None,
            nodes=json.loads(f.nodes),
            created_at=f.created_at,
            updated_at=f.updated_at,
        )
        for f in flows
    ]


@router.get("/{flow_id}", response_model=FlowResponse)
async def get_flow(flow_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Flow).where(Flow.id == flow_id))
    flow = result.scalar_one_or_none()

    if not flow:
        raise HTTPException(status_code=404, detail="Flow no encontrado")

    return FlowResponse(
        id=flow.id,
        name=flow.name,
        description=flow.description,
        enabled=bool(flow.enabled),
        trigger_type=flow.trigger_type,
        trigger_config=json.loads(flow.trigger_config) if flow.trigger_config else None,
        nodes=json.loads(flow.nodes),
        created_at=flow.created_at,
        updated_at=flow.updated_at,
    )


@router.put("/{flow_id}", response_model=FlowResponse)
async def update_flow(flow_id: str, flow_update: FlowUpdate, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Flow).where(Flow.id == flow_id))
    flow = result.scalar_one_or_none()

    if not flow:
        raise HTTPException(status_code=404, detail="Flow no encontrado")

    if flow_update.name is not None:
        flow.name = flow_update.name
    if flow_update.description is not None:
        flow.description = flow_update.description
    if flow_update.enabled is not None:
        flow.enabled = int(flow_update.enabled)
    if flow_update.trigger_type is not None:
        flow.trigger_type = flow_update.trigger_type
    if flow_update.trigger_config is not None:
        flow.trigger_config = json.dumps(flow_update.trigger_config)
    if flow_update.nodes is not None:
        flow.nodes = json.dumps(flow_update.nodes)

    flow.updated_at = datetime.utcnow().isoformat()

    await session.commit()
    await session.refresh(flow)

    trigger_cfg = json.loads(flow.trigger_config) if flow.trigger_config else None
    await update_flow_schedule(
        flow.id,
        bool(flow.enabled),
        flow.trigger_type,
        trigger_cfg
    )

    return FlowResponse(
        id=flow.id,
        name=flow.name,
        description=flow.description,
        enabled=bool(flow.enabled),
        trigger_type=flow.trigger_type,
        trigger_config=trigger_cfg,
        nodes=json.loads(flow.nodes),
        created_at=flow.created_at,
        updated_at=flow.updated_at,
    )


@router.delete("/{flow_id}")
async def delete_flow(flow_id: str, session: AsyncSession = Depends(get_session)):
    from src.engine.scheduler import unschedule_flow

    result = await session.execute(select(Flow).where(Flow.id == flow_id))
    flow = result.scalar_one_or_none()

    if not flow:
        raise HTTPException(status_code=404, detail="Flow no encontrado")

    unschedule_flow(flow_id)
    await session.delete(flow)
    await session.commit()

    return {"message": "Flow eliminado"}


@router.post("/{flow_id}/run")
async def run_flow(flow_id: str, session: AsyncSession = Depends(get_session)):
    from src.engine import FlowExecutor
    from src.models import Secret

    result = await session.execute(select(Flow).where(Flow.id == flow_id))
    flow = result.scalar_one_or_none()

    if not flow:
        raise HTTPException(status_code=404, detail="Flow no encontrado")

    secrets_result = await session.execute(select(Secret))
    secrets = {s.key: s.value for s in secrets_result.scalars().all()}

    executor = FlowExecutor(session)
    flow_data = {
        "id": flow.id,
        "nodes": flow.nodes,
        "trigger_config": flow.trigger_config,
    }

    result = await executor.execute_flow(flow_id, flow_data, secrets)

    return result


@router.get("/{flow_id}/executions")
async def list_flow_executions(flow_id: str, session: AsyncSession = Depends(get_session)):
    from src.models import Execution

    result = await session.execute(select(Flow).where(Flow.id == flow_id))
    flow = result.scalar_one_or_none()

    if not flow:
        raise HTTPException(status_code=404, detail="Flow no encontrado")

    executions_result = await session.execute(
        select(Execution).where(Execution.flow_id == flow_id).order_by(Execution.started_at.desc())
    )
    executions = executions_result.scalars().all()

    return [
        {
            "id": e.id,
            "flow_id": e.flow_id,
            "status": e.status,
            "started_at": e.started_at,
            "finished_at": e.finished_at,
            "error": e.error,
        }
        for e in executions
    ]
