import json
from typing import Optional
from datetime import datetime, timedelta
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
    try:
        async with async_session() as session:
            from sqlalchemy import select
            
            result = await session.execute(select(Event).where(Event.id == event_id))
            event = result.scalar_one_or_none()
            
            if not event:
                print(f"[SCHEDULER] Event {event_id} not found")
                return
            
            if event.completado:
                print(f"[SCHEDULER] Event {event_id} already completed, skipping reminder")
                return
            
            from src.models import Secret
            secrets_result = await session.execute(select(Secret))
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
            
    except Exception as e:
        print(f"[SCHEDULER] Error sending reminder for event {event_id}: {e}")


def schedule_event_reminder(event_id: str, event_datetime: datetime, anticipacion_horas: int = 24):
    scheduler = get_scheduler()
    
    reminder_time = event_datetime - timedelta(hours=anticipacion_horas)
    
    if reminder_time <= datetime.now():
        print(f"[SCHEDULER] Reminder time for event {event_id} is in the past, skipping")
        return None
    
    job = scheduler.add_job(
        run_event_reminder,
        trigger=DateTrigger(run_date=reminder_time),
        args=[event_id],
        id=f"event_reminder_{event_id}",
        name=f"event_reminder_{event_id}",
        replace_existing=True
    )
    
    print(f"[SCHEDULER] Scheduled reminder for event {event_id} at {reminder_time}")
    return job


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


async def start_scheduler():
    scheduler = get_scheduler()

    await load_scheduled_flows()
    await load_pending_event_reminders()

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