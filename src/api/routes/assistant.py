from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime as dt
import httpx
import json
from datetime import datetime

from src.models import get_session, Secret
from src.assistant.db import async_session as assistant_session
from src.assistant.models import User, Conversation, Event
from src.assistant.intent_router import classify_intent
from src.assistant.session_manager import get_session_manager
from src.assistant.flow_engine import (
    call_minimax, get_or_create_user, save_conversation,
    parse_event_from_text, create_event, get_upcoming_events, complete_event,
    format_events_response, get_event_by_title
)
from src.assistant.sleep_parser import parse_sleep_response, format_sleep_summary
from src.assistant.sleep_service import save_sleep_log
from src.assistant.sleep_flow import create_or_update_sleep_flow
from src.engine.scheduler import schedule_event_reminder, unschedule_event_reminder, schedule_event_reminder_minutes

router = APIRouter(prefix="/webhook", tags=["assistant"])


async def get_secret(session: AsyncSession, key: str) -> str | None:
    result = await session.execute(select(Secret).where(Secret.key == key))
    secret = result.scalar_one_or_none()
    return secret.value if secret else None


async def send_telegram_message(chat_id: str, text: str, token: str):
    import re

    def remove_think(text):
        return re.sub(r'<think>[\s\S]*?</think>', '', text).strip()

    text = remove_think(text)

    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10.0
        )


@router.post("/telegram")
async def telegram_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    update = body.get("message", {})

    if not update:
        return {"ok": True}

    chat_id = str(update.get("chat", {}).get("id", ""))
    user_id = chat_id
    text = update.get("text", "").strip()
    first_name = update.get("chat", {}).get("first_name", "")

    if not text:
        return {"ok": True}

    token_secret = await get_secret(session, "TELEGRAM_BOT_TOKEN")
    if not token_secret:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN no configurado")

    api_key = await get_secret(session, "MINIMAX_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="MINIMAX_API_KEY no configurado")

    intent = classify_intent(text)

    # Si el intent es unknown, usamos MiniMax para clasificar
    if intent == "unknown":
        from src.assistant.intent_router import classify_intent_with_minimax
        intent, _ = await classify_intent_with_minimax(api_key, text)

    sm = get_session_manager()
    conversation_history = sm.get_conversation_history(user_id, limit=15)
    sm.add_message(user_id, "user", text, intent)

    bot_response = None

    async with assistant_session() as asess:
        user = await get_or_create_user(asess, user_id, first_name)
        tono = user.tono_coach or "default"

        if intent == "sueno":
            parsed = parse_sleep_response(text)
            if parsed:
                await save_sleep_log(
                    user_id=user_id,
                    hora_acostado=parsed.get("hora_acostado"),
                    hora_levantado=parsed.get("hora_levantado"),
                    duracion_horas=parsed.get("duracion_horas"),
                    energia_al_despertar=parsed.get("energia_al_despertar"),
                    fecha=parsed.get("fecha"),
                )
                bot_response = format_sleep_summary(parsed)
                await save_conversation(asess, user_id, text, bot_response, intent)
            else:
                bot_response = "No pude entender los datos de sueño. Por favor decime: hora que te acostaste, hora que te levantaste y energía 1-10."
                await save_conversation(asess, user_id, text, bot_response, intent)
        elif intent == "evento_crear":
            event_data = parse_event_from_text(text)
            if event_data:
                event = await create_event(asess, user_id, event_data)

                if event.fecha and event.hora:
                    fecha_parts = event.fecha.split("-")
                    year, month, day = int(fecha_parts[0]), int(fecha_parts[1]), int(fecha_parts[2])
                    hour, minute = int(event.hora.split(":")[0]), int(event.hora.split(":")[1])
                    event_datetime = datetime(year, month, day, hour, minute)

                    anticipacion_minutos = event_data.get("anticipacion_minutos")
                    if anticipacion_minutos is not None and anticipacion_minutos > 0:
                        schedule_event_reminder_minutes(event.id, event_datetime, anticipacion_minutos)
                    else:
                        schedule_event_reminder(event.id, event_datetime, event.anticipacion_aviso_horas)

                fecha_str = datetime.strptime(event.fecha, "%Y-%m-%d").strftime("%d/%m") if event.fecha else "sin fecha"
                bot_response = f"Evento creado:\n  Titulo: {event.titulo}\n  Fecha: {fecha_str}"
                if event.hora:
                    bot_response += f" a las {event.hora}"
                bot_response += f"\nTipo: {event.tipo}"
                if event.recurrente:
                    bot_response += f"\n🔁 Recurrente: {event.frecuencia_recurrencia}"
            else:
                bot_response = "No pude entender el evento. Intentá: 'agregá cita con doctor mañana 3pm'"
            await save_conversation(asess, user_id, text, bot_response, intent)
        elif intent == "evento_ver":
            events = await get_upcoming_events(asess, user_id, days=7)
            bot_response = format_events_response(events)
            await save_conversation(asess, user_id, text, bot_response, intent)
        elif intent == "evento_completar":
            from src.assistant.flow_engine import get_event_by_title
            event = await get_event_by_title(asess, user_id, text)
            if event:
                await complete_event(asess, event.id)
                unschedule_event_reminder(event.id)
                bot_response = f"✓ Marcado como completado: {event.titulo}"
            else:
                bot_response = "No encontré ningún evento activo para completar. Quizás ya fue completado o no existe."
            await save_conversation(asess, user_id, text, bot_response, intent)
        elif intent == "pregunta_programada":
            event_data = parse_event_from_text(text)
            if event_data and event_data.get("fecha") and event_data.get("hora"):
                event = await create_event(asess, user_id, event_data)

                if event.fecha and event.hora:
                    fecha_parts = event.fecha.split("-")
                    year, month, day = int(fecha_parts[0]), int(fecha_parts[1]), int(fecha_parts[2])
                    hour, minute = int(event.hora.split(":")[0]), int(event.hora.split(":")[1])
                    event_datetime = datetime(year, month, day, hour, minute)

                    anticipacion_minutos = event_data.get("anticipacion_minutos")
                    if anticipacion_minutos is not None and anticipacion_minutos > 0:
                        safe_minutes = max(anticipacion_minutos, 2)
                        schedule_event_reminder_minutes(event.id, event_datetime, safe_minutes)
                    else:
                        schedule_event_reminder(event.id, event_datetime, event.anticipacion_aviso_horas)

                fecha_str = datetime.strptime(event.fecha, "%Y-%m-%d").strftime("%d/%m") if event.fecha else "sin fecha"
                anticipacion = event_data.get("anticipacion_minutos") or event.anticipacion_aviso_horas * 60
                anticipacion_str = f"{anticipacion} minutos" if anticipacion < 60 else f"{anticipacion // 60} horas"
                bot_response = (
                    f"✓ Guardado. Te recuerdo '{event.titulo}' "
                    f"{anticipacion_str} antes (a las {event.hora})"
                )
            else:
                bot_response = (
                    "No pude entender el momento. Decime algo como 'recuerdame en 5 minutos que tengo que...'"
                )
            await save_conversation(asess, user_id, text, bot_response, intent)
        elif intent == "rutina_crear":
            bot_response = ("Dale, vamos a crear tu rutina.\n\n"
                          "Decime: ¿cómo querés llamar a tu rutina y a qué hora querés que te la recuerde? "
                          "Ejemplo: 'creá mi rutina mañana a las 7am'")
            await save_conversation(asess, user_id, text, bot_response, intent)
        else:
            bot_response = await call_minimax(api_key, text, conversation_history, tono)
            await save_conversation(asess, user_id, text, bot_response, intent)

        sm.add_message(user_id, "assistant", bot_response)

    try:
        await send_telegram_message(chat_id, bot_response, token_secret)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    return {"ok": True}


@router.get("/telegram/set")
async def set_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    token = await get_secret(session, "TELEGRAM_BOT_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN no configurado")

    host = request.headers.get("host", "")
    protocol = "https" if request.headers.get("x-forwarded-proto", "http") == "https" else "http"
    webhook_url = f"{protocol}://{host}/webhook/telegram"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={"url": webhook_url},
            timeout=10.0
        )
        response.raise_for_status()
        data = response.json()

    return {"webhook_url": webhook_url, "response": data}


@router.post("/sleep/flow/{chat_id}")
async def create_sleep_flow(chat_id: str, session: AsyncSession = Depends(get_session)):
    flow = await create_or_update_sleep_flow(user_id=chat_id, chat_id=chat_id)
    return {
        "flow_id": flow.id,
        "name": flow.name,
        "enabled": bool(flow.enabled),
        "schedule": "0 7 * * *"
    }


@router.get("/sleep/stats/{user_id}")
async def get_sleep_stats(user_id: str):
    from src.assistant.sleep_service import get_sleep_stats
    stats = await get_sleep_stats(user_id, days=7)
    return stats


@router.post("/questions")
async def create_scheduled_question(
    user_id: str,
    pregunta: str,
    cron_expr: str,
    respuesta_parser: str | None = None,
    session: AsyncSession = Depends(get_session)
):
    from src.assistant.models import ScheduledQuestion
    from src.engine.scheduler import schedule_question

    question = ScheduledQuestion(
        user_id=user_id,
        pregunta=pregunta,
        cron_expr=cron_expr,
        respuesta_parser=respuesta_parser,
        activo=1
    )
    session.add(question)
    await session.commit()
    await session.refresh(question)

    schedule_question(question.id, cron_expr)

    return {
        "id": question.id,
        "pregunta": question.pregunta,
        "cron_expr": question.cron_expr,
        "activo": bool(question.activo)
    }


@router.get("/questions/{user_id}")
async def list_scheduled_questions(user_id: str, session: AsyncSession = Depends(get_session)):
    from sqlalchemy import select
    from src.assistant.models import ScheduledQuestion

    result = await session.execute(
        select(ScheduledQuestion).where(ScheduledQuestion.user_id == user_id)
    )
    questions = result.scalars().all()

    return [
        {
            "id": q.id,
            "pregunta": q.pregunta,
            "cron_expr": q.cron_expr,
            "activo": bool(q.activo),
            "ultimo_envio": q.ultimo_envio,
            "ultima_respuesta": q.ultiman_respuesta
        }
        for q in questions
    ]


@router.delete("/questions/{question_id}")
async def delete_scheduled_question(question_id: str, session: AsyncSession = Depends(get_session)):
    from sqlalchemy import select
    from src.assistant.models import ScheduledQuestion
    from src.engine.scheduler import unschedule_question

    result = await session.execute(
        select(ScheduledQuestion).where(ScheduledQuestion.id == question_id)
    )
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    unschedule_question(question_id)
    await session.delete(question)
    await session.commit()

    return {"ok": True}


@router.patch("/questions/{question_id}/toggle")
async def toggle_scheduled_question(question_id: str, session: AsyncSession = Depends(get_session)):
    from sqlalchemy import select
    from src.assistant.models import ScheduledQuestion
    from src.engine.scheduler import schedule_question, unschedule_question

    result = await session.execute(
        select(ScheduledQuestion).where(ScheduledQuestion.id == question_id)
    )
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    question.activo = 0 if question.activo else 1
    await session.commit()

    if question.activo:
        schedule_question(question.id, question.cron_expr)
    else:
        unschedule_question(question.id)

    return {"id": question.id, "activo": bool(question.activo)}


@router.post("/routines")
async def create_routine(
    user_id: str,
    nombre: str,
    dias_semana: str | None = None,
    hora_recordatorio: str | None = None,
    anticipacion_minutos: int = 15,
    session: AsyncSession = Depends(get_session)
):
    from src.assistant.models import Routine
    from src.engine.scheduler import schedule_routine_reminder

    routine = Routine(
        user_id=user_id,
        nombre=nombre,
        dias_semana=dias_semana,
        hora_recordatorio=hora_recordatorio,
        anticipacion_minutos=anticipacion_minutos,
        activa=1
    )
    session.add(routine)
    await session.commit()
    await session.refresh(routine)

    if hora_recordatorio:
        schedule_routine_reminder(routine.id, f"0 {hora_recordatorio} * * *")

    return {
        "id": routine.id,
        "nombre": routine.nombre,
        "dias_semana": routine.dias_semana,
        "hora_recordatorio": routine.hora_recordatorio,
        "activa": bool(routine.activa)
    }


@router.get("/routines/{user_id}")
async def list_routines(user_id: str, session: AsyncSession = Depends(get_session)):
    from src.assistant.models import Routine, RoutineBlock
    from sqlalchemy import select

    result = await session.execute(select(Routine).where(Routine.user_id == user_id))
    routines = result.scalars().all()

    response = []
    for routine in routines:
        blocks_result = await session.execute(
            select(RoutineBlock).where(RoutineBlock.routine_id == routine.id)
        )
        blocks = blocks_result.scalars().all()

        response.append({
            "id": routine.id,
            "nombre": routine.nombre,
            "dias_semana": routine.dias_semana,
            "hora_recordatorio": routine.hora_recordatorio,
            "activa": bool(routine.activa),
            "bloques": [
                {
                    "id": b.id,
                    "nombre": b.nombre,
                    "hora_inicio": b.hora_inicio,
                    "hora_fin": b.hora_fin,
                    "categoria": b.categoria,
                    "prioridad": b.prioridad
                }
                for b in blocks
            ]
        })

    return response


@router.post("/routines/{routine_id}/blocks")
async def add_routine_block(
    routine_id: str,
    nombre: str,
    hora_inicio: str,
    hora_fin: str,
    categoria: str | None = None,
    prioridad: str = "media",
    session: AsyncSession = Depends(get_session)
):
    from src.assistant.models import RoutineBlock

    block = RoutineBlock(
        routine_id=routine_id,
        nombre=nombre,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        categoria=categoria,
        prioridad=prioridad
    )
    session.add(block)
    await session.commit()
    await session.refresh(block)

    return {
        "id": block.id,
        "nombre": block.nombre,
        "hora_inicio": block.hora_inicio,
        "hora_fin": block.hora_fin,
        "categoria": block.categoria,
        "prioridad": block.prioridad
    }


@router.delete("/routines/{routine_id}")
async def delete_routine(routine_id: str, session: AsyncSession = Depends(get_session)):
    from sqlalchemy import select
    from src.assistant.models import Routine, RoutineBlock
    from src.engine.scheduler import unschedule_routine_reminder

    result = await session.execute(select(Routine).where(Routine.id == routine_id))
    routine = result.scalar_one_or_none()

    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")

    unschedule_routine_reminder(routine_id)

    blocks_result = await session.execute(
        select(RoutineBlock).where(RoutineBlock.routine_id == routine_id)
    )
    for block in blocks_result.scalars().all():
        await session.delete(block)

    await session.delete(routine)
    await session.commit()

    return {"ok": True}


@router.get("/dashboard/{user_id}")
async def get_user_dashboard(user_id: str, session: AsyncSession = Depends(get_session)):
    from sqlalchemy import select
    from src.assistant.models import Event, ScheduledQuestion, Routine, RoutineBlock

    events_result = await session.execute(
        select(Event).where(
            Event.user_id == user_id,
            Event.completado == 0
        ).order_by(Event.fecha.asc())
    )
    events = events_result.scalars().all()

    questions_result = await session.execute(
        select(ScheduledQuestion).where(ScheduledQuestion.user_id == user_id)
    )
    questions = questions_result.scalars().all()

    routines_result = await session.execute(
        select(Routine).where(Routine.user_id == user_id)
    )
    routines = routines_result.scalars().all()

    routine_blocks = {}
    for routine in routines:
        blocks_result = await session.execute(
            select(RoutineBlock).where(RoutineBlock.routine_id == routine.id)
        )
        routine_blocks[routine.id] = [
            {"nombre": b.nombre, "hora_inicio": b.hora_inicio, "hora_fin": b.hora_fin}
            for b in blocks_result.scalars().all()
        ]

    return {
        "events": [
            {
                "id": e.id,
                "titulo": e.titulo,
                "fecha": e.fecha,
                "hora": e.hora,
                "tipo": e.tipo,
                "recurrente": bool(e.recurrente),
                "frecuencia": e.frecuencia_recurrencia,
                "anticipacion": e.anticipacion_aviso_horas
            }
            for e in events
        ],
        "questions": [
            {
                "id": q.id,
                "pregunta": q.pregunta,
                "cron_expr": q.cron_expr,
                "activo": bool(q.activo),
                "ultimo_envio": q.ultimo_envio
            }
            for q in questions
        ],
        "routines": [
            {
                "id": r.id,
                "nombre": r.nombre,
                "hora_recordatorio": r.hora_recordatorio,
                "activa": bool(r.activa),
                "bloques": routine_blocks.get(r.id, [])
            }
            for r in routines
        ]
    }
