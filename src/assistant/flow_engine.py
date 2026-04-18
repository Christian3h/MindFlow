import httpx
import re
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from src.assistant.models import User, Conversation, Event
from src.assistant.session_manager import get_session_manager
from src.assistant.expense_parser import parse_multiple_expenses, format_expenses_response, should_ask_impulsive
from src.assistant.expense_tracker import save_multiple_transactions, get_daily_total


SYSTEM_PROMPTS = {
    "amable": "Sos MindFlow, un coach personal amigable y empático. Ayudás al usuario a gestionar su día, sueño, finanzas y motivación. NO usás asteriscos, NO usás markdown, NO usás negritas. Siempre respondés en texto plano. No mostrás tu proceso de razonamiento interno. Tu tono es cálido y motivate. Si detectás que el usuario está decaído, lo motivás.",
    "estricto": "Sos MindFlow, un coach personal directo y sin filtro. Decís las cosas como son. No suavizás las críticas. NO usás asteriscos, NO usás markdown, NO usás negritas. Siempre respondés en texto plano. No mostrás tu proceso de razonamiento interno.",
    "sarcástico": "Sos MindFlow, un coach personal irónico pero motivador. Usás humor para señalar errores sin ser cruel. NO usás asteriscos, NO usás markdown, NO usás negritas. Siempre respondés en texto plano. No mostrás tu proceso de razonamiento interno.",
    "neutral": "Sos MindFlow, un coach personal informativo. Sin emocionalismo, solo datos y hechos. NO usás asteriscos, NO usás markdown, NO usás negritas. Siempre respondés en texto plano. No mostrás tu proceso de razonamiento interno.",
    "default": "Sos MindFlow, el asistente personal del usuario. Ayudás con sueño, finanzas, rutina y motivación. NO usás asteriscos, NO usás markdown, NO usás negritas. Siempre respondés en texto plano. No mostrás tu proceso de razonamiento interno. Respondé de forma concisa y útil."
}


def get_time_context() -> str:
    now = datetime.now()
    return (
        f"Hora actual del servidor: {now.strftime('%H:%M')} "
        f"({now.strftime('%A %d de %B de %Y')}). "
        f"Cuando el usuario dice 'en X minutos' o 'dentro de X minutos', "
        f"calculá la hora sumando X minutos a la hora actual. "
        f"Cuando dice 'en X horas', sumá X horas. "
        f"Cuando dice 'mañana', referite a { (now + timedelta(days=1)).strftime('%d/%m/%Y') }. "
        f"Cuando dice 'hoy', referite a { now.strftime('%d/%m/%Y') }."
    )


def parse_relative_time(text: str) -> tuple[str | None, str | None]:
    """
    Parsea expresiones relativas como 'en 5 minutos', 'dentro de 1 hora'.
    Returns (fecha, hora) en formato YYYY-MM-DD HH:MM o (None, None) si no matchea.
    """
    text_lower = text.lower()
    now = datetime.now()

    minuto_match = re.search(r"(?:en|dentro\s+de)\s+(\d+)\s*minutos?", text_lower)
    if minuto_match:
        mins = int(minuto_match.group(1))
        target = now + timedelta(minutes=mins)
        return target.strftime("%Y-%m-%d"), target.strftime("%H:%M"), mins

    hora_match = re.search(r"(?:en\s+|dentro\s+de\s+)(\d+)\s*horas?", text_lower)
    if hora_match:
        horas = int(hora_match.group(1))
        target = now + timedelta(hours=horas)
        return target.strftime("%Y-%m-%d"), target.strftime("%H:%M"), horas * 60

    dia_match = re.search(r"(?:en\s+|dentro\s+de\s+)(\d+)\s*dias?", text_lower)
    if dia_match:
        dias = int(dia_match.group(1))
        target = now + timedelta(days=dias)
        return target.strftime("%Y-%m-%d"), target.strftime("%H:%M"), dias * 24 * 60

    if re.search(r"ma[nñ]ana", text_lower):
        target = now + timedelta(days=1)
        return target.strftime("%Y-%m-%d"), target.strftime("%H:%M"), 24 * 60

    if re.search(r"pasado\s*man[nñ]ana", text_lower):
        target = now + timedelta(days=2)
        return target.strftime("%Y-%m-%d"), target.strftime("%H:%M"), 48 * 60

    return None, None, None


async def get_or_create_user(session: AsyncSession, user_id: str, nombre: str | None = None) -> User:
    from sqlalchemy import select
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(id=user_id, nombre=nombre)
        session.add(user)
        await session.commit()
    return user


async def save_conversation(
    session: AsyncSession,
    user_id: str,
    mensaje_usuario: str,
    respuesta_bot: str | None,
    intencion: str | None = None,
    contexto_json: dict | None = None
):
    import json
    conversation = Conversation(
        user_id=user_id,
        mensaje_usuario=mensaje_usuario,
        respuesta_bot=respuesta_bot,
        intencion=intencion,
        contexto_json=json.dumps(contexto_json) if contexto_json else None
    )
    session.add(conversation)
    await session.commit()


async def handle_expense_intent(
    session: AsyncSession,
    user_id: str,
    text: str,
    api_key: str,
    conversation_history: list[dict],
    system_tone: str = "default"
) -> tuple[str, dict]:
    expenses = parse_multiple_expenses(text)
    
    if not expenses:
        return await call_minimax(api_key, text, conversation_history, system_tone), {}
    
    saved = await save_multiple_transactions(session, user_id, expenses)
    
    today_total = await get_daily_total(session, user_id)
    response = format_expenses_response(expenses, today_total)
    
    context = {
        "expenses": [{"id": t.id, "monto": t.monto, "categoria": t.categoria} for t in saved],
        "ask_impulsive": should_ask_impulsive(expenses)
    }
    
    return response, context


async def process_expense_confirmation(
    session: AsyncSession,
    user_id: str,
    text: str,
    pending_expenses: list[dict],
    api_key: str,
    conversation_history: list[dict],
    system_tone: str = "default"
) -> str:
    from src.assistant.expense_tracker import mark_transaction_impulsive
    
    text_lower = text.lower().strip()
    
    impulsive_keywords = ["sí", "si", "yea", "yep", "claro", "dale", "ok", "bueno", "va", "perfect", "afirmativo", "confirmar", "si fue", "sí fue", "impulsivo", "si era"]
    no_impulsive_keywords = ["no", "nope", "nah", "no fue", "nah", "no importar", "nada", "salir", "listo", "no era", "fue normal", "normal"]
    
    is_impulsive = any(text_lower.startswith(k) for k in impulsive_keywords)
    
    for expense_data in pending_expenses:
        if is_impulsive:
            await mark_transaction_impulsive(session, expense_data["id"], True)
    
    if is_impulsive:
        return "Okay, registrado como gasto impulsivo. Sesión controlada ✓"
    else:
        return "Listo, sin problema. ¿Algo más?"


async def call_minimax(
    api_key: str,
    user_message: str,
    conversation_history: list[dict],
    system_tone: str = "default"
) -> str:
    system_prompt = SYSTEM_PROMPTS.get(system_tone, SYSTEM_PROMPTS["default"])
    time_context = get_time_context()
    system_prompt = f"{time_context}\n\n{system_prompt}"

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.minimax.io/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "MiniMax-M2.7",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2048,
                "extra_body": {"reasoning_split": True}
            },
            timeout=60.0
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def parse_event_from_text(text: str) -> dict | None:
    text_lower = text.lower()
    
    tipos_evento = {
        "cita": ["cita", "doctor", "médico", "reunión", "reunion"],
        "cumpleaños": ["cumple", "birthday"],
        "deadline": ["deadline", "entrega", "fecha límite", "fecha limite"],
        "recordatorio": ["recordar", "recordatorio", "no olvidar"]
    }
    
    tipo = "recordatorio"
    for tipo_name, keywords in tipos_evento.items():
        if any(kw in text_lower for kw in keywords):
            tipo = tipo_name
            break
    
    hora_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text, re.IGNORECASE)
    hora = None
    if hora_match:
        hour = int(hora_match.group(1))
        minute = int(hora_match.group(2)) if hora_match.group(2) else 0
        period = hora_match.group(3)
        if period:
            if period.lower() == "pm" and hour != 12:
                hour += 12
            elif period.lower() == "am" and hour == 12:
                hour = 0
        else:
            noche_keywords = ["dormir", "dormir", "noche", "cama", "sueño", "sueno", "acostado", "dormi"]
            is_noche = any(kw in text_lower for kw in noche_keywords)
            
            if is_noche:
                if hour == 12:
                    hour = 0
            else:
                ahora = datetime.now()
                if hour >= 13 and hour <= 23:
                    pass
                elif hour < ahora.hour:
                    if hour < 12:
                        hour += 12
                elif hour == ahora.hour:
                    pass
                else:
                    if hour > 12 and ahora.hour < 12:
                        hour -= 12
        hora = f"{hour:02d}:{minute:02d}"
    
    fecha_relativa, hora_relativa, anticipacion_minutos = parse_relative_time(text)
    if fecha_relativa:
        fecha = fecha_relativa
        if hora_relativa:
            hora = hora_relativa
    else:
        fecha = None
        anticipacion_minutos = None
    
    fecha_map = {
        "pasado mañana": datetime.now() + timedelta(days=2),
        "pasado manana": datetime.now() + timedelta(days=2),
        "mañana": datetime.now() + timedelta(days=1),
        "manana": datetime.now() + timedelta(days=1),
        "hoy": datetime.now(),
    }
    
    if not fecha:
        for fecha_str, fecha_obj in fecha_map.items():
            if fecha_str in text_lower:
                fecha = fecha_obj.strftime("%Y-%m-%d")
                break
    
    if not fecha:
        dia_match = re.search(r"(?<!\d)(\d{1,2})(?:\s*(?:de\s+)?|\s*[/]\s*)(?:ene(?:ro)?|feb(?:rero)?|mar(?:zo)?|abr(?:il)?|may(?:o)?|jun(?:io)?|jul(?:io)?|ago(?:sto)?|sep(?:tiembre)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?)(?:\s*[/]\s*(\d{1,2}))?(?!\d)", text, re.IGNORECASE)
        if dia_match:
            try:
                dia = int(dia_match.group(1))
                hoy = datetime.now()
                fecha = datetime(hoy.year, hoy.month, dia)
                if fecha < hoy:
                    fecha = fecha.replace(year=fecha.year + 1)
                fecha = fecha.strftime("%Y-%m-%d")
            except:
                pass
    
    recurrente = 0
    frecuencia = None
    if re.search(r"semanal|cada\s+semana|todos?\s+(?:los\s+)?(?:martes|miércoles|jueves|viernes|sábado|domingo|lunes)", text_lower):
        recurrente = 1
        frecuencia = "semanal"
    elif re.search(r"mensual|cada\s+mes|todos?\s+los\s+meses", text_lower):
        recurrente = 1
        frecuencia = "mensual"
    elif re.search(r"anual|cada\s+año|todos?\s+(?:los\s+)?(?:eneros?|febreros?|etc)", text_lower):
        recurrente = 1
        frecuencia = "anual"
    
    titulo = None
    
    hacer_match = re.search(r"hacer\s+(?:mi\s+)?(.+?)$", text, re.IGNORECASE)
    if hacer_match:
        raw = hacer_match.group(1).strip()
        skip = {"duolingo", "practica", "ejercicio", "tarea", "recha", "deber", "la", "el", "mi", "que", "una", "un"}
        words = [w for w in raw.split() if w.lower() not in skip and len(w) > 1]
        titulo = " ".join(words) if words else raw
    
    if not titulo or len(titulo) < 3:
        cita_match = re.search(r"reunion\s+con\s+(.+?)(?:\s*$|$)", text, re.IGNORECASE)
        if cita_match:
            titulo = f"Reunion con {cita_match.group(1).strip()}"
        else:
            cita_match2 = re.search(r"cita\s+con\s+(.+?)(?:\s+a\s+las|$)", text, re.IGNORECASE)
            if cita_match2:
                titulo = f"Cita con {cita_match2.group(1).strip()}"
            else:
                tengo_match = re.search(r"tengo\s+(?:que\s+)?(.+?)(?:\s+dentro|$)", text, re.IGNORECASE)
                if tengo_match:
                    titulo = tengo_match.group(1).strip()
                else:
                    reunion_match = re.search(r"(?:la\s+)?reunion\s+(?:con\s+)?(.+?)$", text, re.IGNORECASE)
                    if reunion_match:
                        titulo = f"Reunion con {reunion_match.group(1).strip()}"
    
    if not titulo or len(titulo) < 3:
        tarea_match = re.search(r"(?:mi\s+)?tarea\s+(?:de\s+)?(.+?)$", text, re.IGNORECASE)
        if tarea_match:
            titulo = f"Tarea de {tarea_match.group(1).strip()}"
        else:
            titulo_match = re.search(r"(?:la\s+)?reunion\s+(?:con\s+)?(.+?)$", text, re.IGNORECASE)
            if titulo_match:
                titulo = f"Reunion con {titulo_match.group(1).strip()}"
    
    if not titulo or len(titulo) < 3:
        titulo = f"Evento {datetime.now().strftime('%H:%M')}"
    
    titulo = re.sub(r"^(de|del|para|con|en|es|una|un)\s+", "", titulo, flags=re.IGNORECASE).strip()
    if not titulo:
        titulo = f"Evento {datetime.now().strftime('%H:%M')}"
    
    anticipacion = 24
    if anticipacion_minutos is not None and anticipacion_minutos > 0:
        anticipacion = max(1, anticipacion_minutos // 60)
        if anticipacion_minutos < 60:
            anticipacion = 1
    
    return {
        "titulo": titulo,
        "fecha": fecha,
        "hora": hora,
        "tipo": tipo,
        "recurrente": recurrente,
        "frecuencia_recurrencia": frecuencia,
        "anticipacion_aviso_horas": anticipacion,
        "anticipacion_minutos": anticipacion_minutos
    }


async def create_event(session: AsyncSession, user_id: str, event_data: dict) -> Event:
    from sqlalchemy import select
    
    titulo = event_data.get("titulo", "Sin título")
    fecha = event_data.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    hora = event_data.get("hora")
    tipo = event_data.get("tipo", "recordatorio")
    recurrente = event_data.get("recurrente", 0)
    frecuencia = event_data.get("frecuencia_recurrencia")
    anticipacion = event_data.get("anticipacion_aviso_horas", 24)
    anticipacion_minutos = event_data.get("anticipacion_minutos")
    
    event = Event(
        user_id=user_id,
        titulo=titulo,
        fecha=fecha,
        hora=hora,
        tipo=tipo,
        recurrente=recurrente,
        frecuencia_recurrencia=frecuencia,
        anticipacion_aviso_horas=anticipacion,
        anticipacion_aviso_minutos=anticipacion_minutos,
        completado=0
    )
    
    session.add(event)
    await session.commit()
    await session.refresh(event)
    
    return event


async def get_upcoming_events(session: AsyncSession, user_id: str, days: int = 7) -> list[Event]:
    from sqlalchemy import select, and_, or_
    
    hoy = datetime.now().strftime("%Y-%m-%d")
    limite = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    
    result = await session.execute(
        select(Event).where(
            and_(
                Event.user_id == user_id,
                Event.completado == 0,
                Event.fecha >= hoy,
                Event.fecha <= limite
            )
        ).order_by(Event.fecha.asc(), Event.hora.asc())
    )
    
    return list(result.scalars().all())


async def complete_event(session: AsyncSession, event_id: str) -> Event | None:
    from sqlalchemy import select
    
    result = await session.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if event:
        event.completado = 1
        await session.commit()
        await session.refresh(event)
    
    return event


async def get_event_by_title(session: AsyncSession, user_id: str, title_part: str) -> Event | None:
    from sqlalchemy import select, or_, and_
    
    result = await session.execute(
        select(Event).where(
            and_(
                Event.user_id == user_id,
                Event.completado == 0,
                or_(
                    Event.titulo.ilike(f"%{title_part}%"),
                    Event.titulo.ilike(f"%{title_part.rstrip('s')}%")
                )
            )
        ).order_by(Event.fecha.asc())
    )
    
    return result.scalar_one_or_none()


def format_events_response(events: list[Event]) -> str:
    if not events:
        return "No tenes eventos programados en los proximos dias."
    
    lines = ["Tus proximos eventos:"]
    
    current_date = None
    for event in events:
        if event.fecha != current_date:
            current_date = event.fecha
            fecha_obj = datetime.strptime(event.fecha, "%Y-%m-%d")
            dia_nombre = fecha_obj.strftime("%A").capitalize()
            lines.append(f"  {dia_nombre} {fecha_obj.strftime('%d/%m')}")
        
        emoji = "[x]" if event.completado else "[ ]"
        hora_str = event.hora if event.hora else "Sin hora"
        tipo_emoji = {"cita": "[CITA]", "cumpleaños": "[CUMPLE]", "deadline": "[ALERTA]", "recordatorio": "[AVISO]"}.get(event.tipo, "[EVENTO]")
        
        lines.append(f"  {emoji} {tipo_emoji} {hora_str} - {event.titulo}")
        
        if event.recurrente:
            lines.append(f"      [RECURRENTE] {event.frecuencia_recurrencia}")
    
    return "\n".join(lines)