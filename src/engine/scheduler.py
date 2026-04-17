import json
from typing import Optional
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.models import async_session, Flow, Secret


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