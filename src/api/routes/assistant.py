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
from src.engine.scheduler import schedule_event_reminder, unschedule_event_reminder

router = APIRouter(prefix="/webhook", tags=["assistant"])


async def get_secret(session: AsyncSession, key: str) -> str | None:
    result = await session.execute(select(Secret).where(Secret.key == key))
    secret = result.scalar_one_or_none()
    return secret.value if secret else None


async def send_telegram_message(chat_id: str, text: str, token: str):
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