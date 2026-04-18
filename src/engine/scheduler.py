import json
from typing import Optional
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from src.models import async_session, Flow, Secret
from src.assistant.models import Event


_scheduler: Optional[AsyncIOScheduler] = None
_running_flows: set[str] = set()


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def run_flow_job(flow_id: str):
    if flow_id in _running_flows:
        print(f"[SCHEDULER] Flow {flow_id} already running, skipping")
        return

    _running_flows.add(flow_id)

    try:
        from src.engine import FlowExecutor

        async with async_session() as session:
            from sqlalchemy import select

            result = await session.execute(select(Flow).where(Flow.id == flow_id))
            flow = result.scalar_one_or_none()

            if not flow:
                print(f"[SCHEDULER] Flow {flow_id} not found")
                return

            if not flow.enabled:
                print(f"[SCHEDULER] Flow {flow_id} is disabled, skipping")
                return

            secrets_result = await session.execute(select(Secret))
            secrets = {s.key: s.value for s in secrets_result.scalars().all()}

            executor = FlowExecutor(session)
            flow_data = {
                "id": flow.id,
                "nodes": flow.nodes,
                "trigger_config": flow.trigger_config,
            }

            print(f"[SCHEDULER] Running flow {flow_id}")
            result = await executor.execute_flow(flow_id, flow_data, secrets)
            await session.commit()
            print(f"[SCHEDULER] Flow {flow_id} finished: {result['status']}")

    except Exception as e:
        print(f"[SCHEDULER] Error running flow {flow_id}: {e}")
    finally:
        _running_flows.discard(flow_id)


async def run_event_reminder(event_id: str):
    from src.assistant.db import async_session as assistant_async_session
    
    try:
        async with assistant_async_session() as session:
            from sqlalchemy import select
            
            result = await session.execute(select(Event).where(Event.id == event_id))
            event = result.scalar_one_or_none()
            
            if not event:
                print(f"[SCHEDULER] Event {event_id} not found")
                return
            
            if event.completado:
                print(f"[SCHEDULER] Event {event_id} already completed, skipping reminder")
                return
        
        from src.models import async_session as engine_async_session
        async with engine_async_session() as engine_session:
            from sqlalchemy import select
            from src.models import Secret
            
            secrets_result = await engine_session.execute(select(Secret))
            secrets = {s.key: s.value for s in secrets_result.scalars().all()}
        
        telegram_token = secrets.get("TELEGRAM_BOT_TOKEN")
        if not telegram_token:
            print(f"[SCHEDULER] TELEGRAM_BOT_TOKEN not found")
            return
        
        import httpx
        
        fecha_obj = datetime.strptime(event.fecha, "%Y-%m-%d")
        fecha_str = fecha_obj.strftime("%d/%m")
        
        reminder_text = f"🔔 *Recordatorio*\n\n"
        reminder_text += f"'{event.titulo}'\n"
        reminder_text += f"📅 {fecha_str}"
        if event.hora:
            reminder_text += f" a las {event.hora}"
        reminder_text += f"\n\nTipo: {event.tipo}"
        
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                json={"chat_id": event.user_id, "text": reminder_text, "parse_mode": "Markdown"},
                timeout=10.0
            )
        
        print(f"[SCHEDULER] Sent reminder for event {event_id}")
        
        if event.recurrente and event.frecuencia_recurrencia:
            from src.engine.scheduler import advance_recurring_event
            async with assistant_async_session() as session:
                await advance_recurring_event(session, event)
        
    except Exception as e:
        print(f"[SCHEDULER] Error sending reminder for event {event_id}: {e}")


def schedule_event_reminder_minutes(event_id: str, event_datetime: datetime, anticipacion_minutos: int):
    scheduler = get_scheduler()
    
    now = datetime.now()
    if event_datetime <= now:
        print(f"[SCHEDULER] Event {event_id} is in the past ({event_datetime}), skipping reminder")
        return None
    
    reminder_time = event_datetime - timedelta(minutes=anticipacion_minutos)
    
    if reminder_time <= now:
        min_reminder = now + timedelta(minutes=1)
        if event_datetime <= min_reminder:
            min_reminder = event_datetime - timedelta(minutes=1)
            if min_reminder <= now:
                print(f"[SCHEDULER] Reminder time for event {event_id} is in the past, skipping")
                return None
        reminder_time = min_reminder
        anticipacion_minutos = max(1, int((event_datetime - reminder_time).total_seconds() / 60))
    
    job = scheduler.add_job(
        run_event_reminder,
        trigger=DateTrigger(run_date=reminder_time),
        args=[event_id],
        id=f"event_reminder_{event_id}",
        name=f"event_reminder_{event_id}",
        replace_existing=True
    )
    
    print(f"[SCHEDULER] Scheduled reminder for event {event_id} at {reminder_time} ({anticipacion_minutos}min before)")
    return job


def schedule_event_reminder(event_id: str, event_datetime: datetime, anticipacion_horas: int = 24):
    return schedule_event_reminder_minutes(event_id, event_datetime, anticipacion_horas * 60)


def unschedule_event_reminder(event_id: str):
    scheduler = get_scheduler()
    
    job = scheduler.get_job(f"event_reminder_{event_id}")
    if job:
        scheduler.remove_job(f"event_reminder_{event_id}")
        print(f"[SCHEDULER] Unscheduled reminder for event {event_id}")
    else:
        print(f"[SCHEDULER] No reminder job found for event {event_id}")


async def load_pending_event_reminders():
    from src.assistant.db import async_session as assistant_async_session
    
    async with assistant_async_session() as session:
        from sqlalchemy import select
        from src.assistant.models import Event
        
        hoy = datetime.now().strftime("%Y-%m-%d")
        
        result = await session.execute(
            select(Event).where(
                Event.completado == 0,
                Event.fecha >= hoy
            )
        )
        events = result.scalars().all()
        
        scheduled_count = 0
        for event in events:
            if event.fecha:
                fecha_parts = event.fecha.split("-")
                year, month, day = int(fecha_parts[0]), int(fecha_parts[1]), int(fecha_parts[2])
                
                hour, minute = 0, 0
                if event.hora:
                    time_parts = event.hora.split(":")
                    hour, minute = int(time_parts[0]), int(time_parts[1])
                
                event_datetime = datetime(year, month, day, hour, minute)
                
                schedule_event_reminder(event.id, event_datetime, event.anticipacion_aviso_horas)
                scheduled_count += 1
        
        print(f"[SCHEDULER] Loaded {scheduled_count} pending event reminders")


def _parse_cron_expr(cron_expr: str) -> dict:
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expr: {cron_expr}")
    return dict(minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4])


def schedule_flow(flow_id: str, cron_expr: str):
    scheduler = get_scheduler()

    trigger = CronTrigger(**_parse_cron_expr(cron_expr))

    job = scheduler.add_job(
        run_flow_job,
        trigger,
        args=[flow_id],
        id=f"flow_{flow_id}",
        name=f"flow_{flow_id}",
        replace_existing=True
    )

    print(f"[SCHEDULER] Scheduled flow {flow_id} with cron: {cron_expr}")
    return job


def unschedule_flow(flow_id: str):
    scheduler = get_scheduler()

    job = scheduler.get_job(f"flow_{flow_id}")
    if job:
        scheduler.remove_job(f"flow_{flow_id}")
        print(f"[SCHEDULER] Unscheduled flow {flow_id}")
    else:
        print(f"[SCHEDULER] No job found for flow {flow_id}")


async def load_scheduled_flows():
    async with async_session() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(Flow).where(Flow.enabled == True)
        )
        flows = result.scalars().all()

        for flow in flows:
            if flow.trigger_type == "cron" and flow.trigger_config:
                try:
                    config = json.loads(flow.trigger_config)
                    schedule = config.get("schedule")
                    if schedule:
                        schedule_flow(flow.id, schedule)
                except Exception as e:
                    print(f"[SCHEDULER] Error loading flow {flow.id}: {e}")

        print(f"[SCHEDULER] Loaded {len(flows)} scheduled flows")


async def advance_recurring_event(session, event: Event):
    from dateutil.relativedelta import relativedelta
    current_date = datetime.strptime(event.fecha, "%Y-%m-%d")
    freq = event.frecuencia_recurrencia

    if freq == "semanal":
        new_date = current_date + relativedelta(weeks=1)
    elif freq == "mensual":
        new_date = current_date + relativedelta(months=1)
    elif freq == "anual":
        new_date = current_date + relativedelta(years=1)
    else:
        print(f"[SCHEDULER] Unknown frequency '{freq}' for event {event.id}")
        return

    event.fecha = new_date.strftime("%Y-%m-%d")
    event.completado = 0
    await session.commit()

    event_datetime = datetime.combine(new_date.date(), datetime.strptime(event.hora or "00:00", "%H:%M").time())
    schedule_event_reminder(event.id, event_datetime, event.anticipacion_aviso_horas)
    print(f"[SCHEDULER] Advanced recurring event {event.id} to {event.fecha}")


async def handle_expired_events():
    from src.assistant.db import async_session as assistant_async_session

    async with assistant_async_session() as session:
        from sqlalchemy import select
        from src.assistant.models import Event

        hoy = datetime.now().strftime("%Y-%m-%d")
        ahora = datetime.now().strftime("%H:%M")

        result = await session.execute(
            select(Event).where(
                Event.completado == 0,
                Event.fecha < hoy
            )
        )
        events = result.scalars().all()

        for event in events:
            if event.hora and event.hora < ahora:
                event.completado = 1
                if event.recurrente and event.frecuencia_recurrencia:
                    await advance_recurring_event(session, event)
                else:
                    unschedule_event_reminder(event.id)

        if events:
            await session.commit()
            print(f"[SCHEDULER] Marked {len(events)} expired events as completed")


async def start_scheduler():
    scheduler = get_scheduler()

    await load_scheduled_flows()
    await load_pending_event_reminders()
    await load_scheduled_questions()
    await load_scheduled_routines()
    await handle_expired_events()

    if not scheduler.running:
        scheduler.start()
        print("[SCHEDULER] Started")


async def stop_scheduler():
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown()
        print("[SCHEDULER] Stopped")


async def update_flow_schedule(flow_id: str, enabled: bool, trigger_type: str, trigger_config: Optional[dict]):
    if trigger_type != "cron":
        unschedule_flow(flow_id)
        return

    if not enabled:
        unschedule_flow(flow_id)
        return

    schedule = trigger_config.get("schedule") if trigger_config else None
    if not schedule:
        unschedule_flow(flow_id)
        return

    schedule_flow(flow_id, schedule)


async def run_scheduled_question(question_id: str):
    from src.assistant.db import async_session as assistant_async_session
    from sqlalchemy import select
    from src.assistant.models import ScheduledQuestion

    try:
        async with assistant_async_session() as session:
            result = await session.execute(select(ScheduledQuestion).where(ScheduledQuestion.id == question_id))
            question = result.scalar_one_or_none()

            if not question or not question.activo:
                print(f"[SCHEDULER] Question {question_id} not found or inactive")
                return

            from src.models import Secret
            async with async_session() as engine_session:
                secrets_result = await engine_session.execute(select(Secret))
                secrets = {s.key: s.value for s in secrets_result.scalars().all()}

            telegram_token = secrets.get("TELEGRAM_BOT_TOKEN")
            if not telegram_token:
                print(f"[SCHEDULER] TELEGRAM_BOT_TOKEN not found")
                return

            import httpx
            from datetime import datetime as dt

            question_text = (
                f"❓ *Pregunta programada*\n\n"
                f"{question.pregunta}\n\n"
                f"_Respondé a esta pregunta y lo guardo._"
            )

            async with httpx.AsyncClient() as client:
                await client.post(
                    f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                    json={"chat_id": question.user_id, "text": question_text, "parse_mode": "Markdown"},
                    timeout=10.0
                )

            question.ultimo_envio = dt.now(timezone.utc).isoformat()
            await session.commit()
            print(f"[SCHEDULER] Sent scheduled question {question_id}")

    except Exception as e:
        print(f"[SCHEDULER] Error running scheduled question {question_id}: {e}")


def schedule_question(question_id: str, cron_expr: str):
    scheduler = get_scheduler()
    trigger = CronTrigger(**_parse_cron_expr(cron_expr))

    job = scheduler.add_job(
        run_scheduled_question,
        trigger,
        args=[question_id],
        id=f"question_{question_id}",
        name=f"question_{question_id}",
        replace_existing=True
    )

    print(f"[SCHEDULER] Scheduled question {question_id} with cron: {cron_expr}")
    return job


def unschedule_question(question_id: str):
    scheduler = get_scheduler()
    job = scheduler.get_job(f"question_{question_id}")
    if job:
        scheduler.remove_job(f"question_{question_id}")
        print(f"[SCHEDULER] Unscheduled question {question_id}")
    else:
        print(f"[SCHEDULER] No job found for question {question_id}")


async def load_scheduled_questions():
    from src.assistant.db import async_session as assistant_async_session
    from sqlalchemy import select
    from src.assistant.models import ScheduledQuestion

    async with assistant_async_session() as session:
        result = await session.execute(
            select(ScheduledQuestion).where(ScheduledQuestion.activo == 1)
        )
        questions = result.scalars().all()

        for question in questions:
            if question.cron_expr:
                schedule_question(question.id, question.cron_expr)

        print(f"[SCHEDULER] Loaded {len(questions)} scheduled questions")


async def run_routine_reminder(routine_id: str):
    from src.assistant.db import async_session as assistant_async_session
    from sqlalchemy import select
    from src.assistant.models import Routine, RoutineBlock

    try:
        async with assistant_async_session() as session:
            result = await session.execute(select(Routine).where(Routine.id == routine_id))
            routine = result.scalar_one_or_none()

            if not routine or not routine.activa:
                print(f"[SCHEDULER] Routine {routine_id} not found or inactive")
                return

            blocks_result = await session.execute(
                select(RoutineBlock).where(RoutineBlock.routine_id == routine_id)
            )
            blocks = blocks_result.scalars().all()

            from src.models import Secret
            async with async_session() as engine_session:
                secrets_result = await engine_session.execute(select(Secret))
                secrets = {s.key: s.value for s in secrets_result.scalars().all()}

            telegram_token = secrets.get("TELEGRAM_BOT_TOKEN")
            if not telegram_token:
                print(f"[SCHEDULER] TELEGRAM_BOT_TOKEN not found")
                return

            import httpx

            blocks_text = "\n".join(
                f"  • {b.hora_inicio}-{b.hora_fin} [{b.categoria or 'sin categoría'}] {b.nombre}"
                for b in blocks
            )

            message = (
                f"📋 *Tu rutina '{routine.nombre}'*\n\n"
                f"Hoy tenés programado:\n{blocks_text}\n\n"
                f"¡Manos a la obra! 💪"
            )

            async with httpx.AsyncClient() as client:
                await client.post(
                    f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                    json={"chat_id": routine.user_id, "text": message, "parse_mode": "Markdown"},
                    timeout=10.0
                )

            print(f"[SCHEDULER] Sent routine reminder for {routine_id}")

    except Exception as e:
        print(f"[SCHEDULER] Error running routine reminder {routine_id}: {e}")


def schedule_routine_reminder(routine_id: str, cron_expr: str):
    scheduler = get_scheduler()
    trigger = CronTrigger(**_parse_cron_expr(cron_expr))

    job = scheduler.add_job(
        run_routine_reminder,
        trigger,
        args=[routine_id],
        id=f"routine_{routine_id}",
        name=f"routine_{routine_id}",
        replace_existing=True
    )

    print(f"[SCHEDULER] Scheduled routine reminder {routine_id} with cron: {cron_expr}")
    return job


def unschedule_routine_reminder(routine_id: str):
    scheduler = get_scheduler()
    job = scheduler.get_job(f"routine_{routine_id}")
    if job:
        scheduler.remove_job(f"routine_{routine_id}")
        print(f"[SCHEDULER] Unscheduled routine reminder {routine_id}")
    else:
        print(f"[SCHEDULER] No job found for routine {routine_id}")


async def load_scheduled_routines():
    from src.assistant.db import async_session as assistant_async_session
    from sqlalchemy import select
    from src.assistant.models import Routine

    async with assistant_async_session() as session:
        result = await session.execute(
            select(Routine).where(Routine.activa == 1, Routine.hora_recordatorio.isnot(None))
        )
        routines = result.scalars().all()

        for routine in routines:
            if routine.hora_recordatorio:
                schedule_routine_reminder(routine.id, f"0 {routine.hora_recordatorio} * * *")

        print(f"[SCHEDULER] Loaded {len(routines)} scheduled routines")