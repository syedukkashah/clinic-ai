import asyncio
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="ops.run_scheduled_check", bind=True, max_retries=2)
def run_scheduled_ops_check(self):
    from db.session import async_session_factory
    from agents.orchestrator import orchestrator

    async def _run():
        async with async_session_factory() as db:
            try:
                return await orchestrator.run_ops_monitor(
                    trigger="scheduled", context={}, db=db
                )
            except Exception as exc:
                raise self.retry(exc=exc, countdown=60)

    return asyncio.run(_run())