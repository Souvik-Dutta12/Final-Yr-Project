"""
Celery tasks for the monitoring pipeline.

Architecture note: Tasks here are thin wrappers.
All business logic lives in pipeline.py and analyzers.
This separation makes unit-testing the logic easy
(no Celery context needed in tests).
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from celery_app import celery_app

logger = logging.getLogger(__name__)

class MonitoringBaseTask(Task):
    """Base task class — adds structured logging and error reporting."""

    def on_failure(
            self, 
            exc, 
            task_id, 
            args, 
            kwargs, 
            einfo
            ):
        
        logger.error(
            "Task %s [%s] failed: %s",
            self.name, task_id, exc,
            exc_info=True,
        )
        # Non-blocking: report failure to TS server
        from monitoring.utils.ts_client import ts_client
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            farm_id = kwargs.get("farm_id") or (args[0] if args else "unknown")
            loop.run_until_complete(
                ts_client.update_job_status(
                    task_id,
                    "FAILED",
                    {
                        "error_message": str(exc), 
                        "farm_id": farm_id
                    },
                )
            )
        except Exception:
            pass # never fail in the failure

@celery_app.task(
    bind=True,
    base=MonitoringBaseTask,
    name="monitoring.core.tasks.ping_task",
    max_retries=1,
)
def ping_task(self) -> Dict[str, Any]:
    """Simple task to verify Celery worker is reachable."""
    return {
        "pong": True, 
        "worker_id": self.request.hostname, 
        "ts": datetime.utcnow().isoformat()
    }

@celery_app.task(
    bind=True,
    base=MonitoringBaseTask,
    name="monitoring.core.tasks.test_echo_task",
    max_retries=0,
)
def test_echo_task(
    self,
    farm_id: str,
    message: str
) -> Dict[str, Any]:
    """Echo task for development testing — no GEE calls."""
    time.sleep(1)  # simulate work
    return {
        "farm_id": farm_id,
        "echoed": message,
        "worker": self.request.hostname,
        "task_id": self.request.id,
    }

@celery_app.task(
    bind=True,
    base=MonitoringBaseTask,
    name="monitoring.core.tasks.run_monitoring_pipeline",
    max_retries=2,
    default_retry_delay=120,
)
def run_monitoring_pipeline(
    self,
    farm_id: str,
    polygon: Dict[str, Any],
    days_back: int = 60,
    include_soil: bool = True,
    include_crop_analysis: bool = True,
    triggered_by: str = "scheduler",
) -> Dict[str, Any]:
    """
    Full monitoring pipeline for one farm.
    Dispatched by the job engine; heavy lifting done in pipeline.py.
    """
    import asyncio
    from monitoring.core.pipeline import MonitoringPipeline

    logger.info("Starting monitoring pipeline | farm_id=%s | task_id=%s", farm_id, self.request.id)

    try:
        pipeline = MonitoringPipeline(task_id=self.request.id)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                pipeline.run(
                    farm_id=farm_id,
                    polygon=polygon,
                    days_back=days_back,
                    include_soil=include_soil,
                    include_crop_analysis=include_crop_analysis,
                )
            )
        finally:
            loop.close()

        logger.info(
            "Pipeline complete | farm_id=%s | alerts=%d | duration=%.1fs",
            farm_id,
            result.get("alert_count", 0),
            result.get("duration_seconds", 0),
        )
        return result
    except SoftTimeLimitExceeded:
        logger.error("Pipeline soft time limit exceeded | farm_id=%s", farm_id)
        raise self.retry(exc=SoftTimeLimitExceeded("Soft limit"), countdown=300)
    except Exception as exc:
        logger.exception("Pipeline error | farm_id=%s", farm_id)
        raise self.retry(exc=exc)