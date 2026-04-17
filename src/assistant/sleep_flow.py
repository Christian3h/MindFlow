from datetime import datetime, time
from uuid import uuid4
import json

from sqlalchemy import select

from src.models import async_session, Flow
from src.engine.scheduler import schedule_flow


DEFAULT_MORNING_FLOW = {
    "name": "Buenos Dias - Registro de Sueno",
    "description": "Flow que pregunta al usuario como durmio",
    "trigger_type": "cron",
    "trigger_config": {"schedule": "0 7 * * *"},
    "nodes": [
        {
            "id": "node_1",
            "type": "minimax.chat",
            "config": {
                "system_prompt": "Sos MindFlow, el asistente personal. Es las 7am. El usuario se acaba de despertar. Preguntale de forma amigable como durmio: '¿Cómo dormiste? Decime a qué hora te acostaste, a qué hora te levantaste y cómo te sentís (energía 1-10).'",
                "model": "MiniMax-M2.7",
                "temperature": 0.7
            }
        },
        {
            "id": "node_2",
            "type": "telegram.send",
            "config": {
                "message": "{{node_1.response}}",
                "chat_id": "{{secrets.DEFAULT_CHAT_ID}}"
            }
        }
    ]
}


async def create_or_update_sleep_flow(user_id: str, chat_id: str) -> Flow:
    flow_name = f"sleep_flow_{user_id}"

    async with async_session() as session:
        result = await session.execute(select(Flow).where(Flow.name == flow_name))
        existing = result.scalar_one_or_none()

        nodes = DEFAULT_MORNING_FLOW["nodes"].copy()
        for node in nodes:
            if node["type"] == "telegram.send":
                node["config"]["chat_id"] = chat_id

        flow_data = {
            "name": flow_name,
            "description": f"Flow de registro de sueño para usuario {user_id}",
            "trigger_type": "cron",
            "trigger_config": json.dumps({"schedule": "0 7 * * *"}),
            "nodes": json.dumps(nodes),
        }

        if existing:
            for key, value in flow_data.items():
                setattr(existing, key, value)
            flow = existing
        else:
            flow = Flow(
                id=str(uuid4()),
                name=flow_name,
                description=flow_data["description"],
                enabled=True,
                trigger_type="cron",
                trigger_config=flow_data["trigger_config"],
                nodes=flow_data["nodes"],
            )
            session.add(flow)

        await session.commit()
        await session.refresh(flow)

        schedule_flow(flow.id, "0 7 * * *")

        return flow


async def get_sleep_flow(user_id: str) -> Flow | None:
    flow_name = f"sleep_flow_{user_id}"

    async with async_session() as session:
        result = await session.execute(select(Flow).where(Flow.name == flow_name))
        return result.scalar_one_or_none()


async def delete_sleep_flow(user_id: str):
    flow_name = f"sleep_flow_{user_id}"

    async with async_session() as session:
        result = await session.execute(select(Flow).where(Flow.name == flow_name))
        flow = result.scalar_one_or_none()

        if flow:
            from src.engine.scheduler import unschedule_flow
            unschedule_flow(flow.id)
            await session.delete(flow)
            await session.commit()


async def parse_and_save_sleep(user_id: str, text: str, chat_id: str) -> dict | None:
    from src.assistant.sleep_parser import parse_sleep_response, format_sleep_summary
    from src.assistant.sleep_service import save_sleep_log

    parsed = parse_sleep_response(text)
    if not parsed:
        return None

    log = await save_sleep_log(
        user_id=user_id,
        hora_acostado=parsed.get("hora_acostado"),
        hora_levantado=parsed.get("hora_levantado"),
        duracion_horas=parsed.get("duracion_horas"),
        energia_al_despertar=parsed.get("energia_al_despertar"),
        fecha=parsed.get("fecha"),
    )

    return {
        "saved": True,
        "log_id": log.id,
        "summary": format_sleep_summary(parsed)
    }