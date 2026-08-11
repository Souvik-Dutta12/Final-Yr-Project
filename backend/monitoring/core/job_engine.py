"""
Job Engine — submits, tracks, and cancels Celery tasks.

The FastAPI request handler calls submit_job() and returns immediately.
The Celery task runs in a worker process.
Status is polled via get_job_status().
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from celery.result import AsyncResult
from celery_app import celery_app
from monitoring.models.job_models import JobStatus, MonitoringJobConfig, MonitoringJobResult

logger = logging.getLogger(__name__)

class JobEngine:
    def submit_monitoring_job(
        self,
        config: MonitoringJobConfig
    )->str:
        """
        Submit a monitoring pipeline task to Celery.
        Returns the Celery task ID (used as job_id everywhere).
        """
        from monitoring.core.tasks import run_monitoring_pipeline

        task = run_monitoring_pipeline.apply_async(
            kwargs={
                "farm_id": config.farm_id,
                "polygon": config.polygon,
                "days_back": config.days_back,
                "include_soil": config.include_soil,
                "include_crop_analysis": config.include_crop_analysis,
                "triggered_by": config.triggered_by,
            },
            queue="monitoring",
        )

        logger.info("Submitted monitoring job | farm=%s | task_id=%s", config.farm_id, task.id)
        return task.id
    
    def submit_test_job(
        self,
        farm_id: str,
        message: str
    )-> str:
        """Submit a no-op echo task for connectivity testing."""
        from monitoring.core.tasks import test_echo_task

        task = test_echo_task.apply_async(
            kwargs={
                "farm_id": 
                farm_id, "message": message
            },
            queue="monitoring",
        )
        return task.id
    
    def get_job_status(
        self,
        job_id: str
    )->MonitoringJobResult:
        """
        Poll Celery for job status and map to our JobStatus enum.
        Result is available once status == COMPLETED.
        """

        result: AsyncResult = AsyncResult(job_id, app=celery_app)

        status_map = {
            "PENDING": JobStatus.QUEUED,
            "STARTED": JobStatus.RUNNING,
            "SUCCESS": JobStatus.COMPLETED,
            "FAILURE": JobStatus.FAILED,
            "REVOKED": JobStatus.CANCELLED,
            "RETRY": JobStatus.RUNNING,
        }
        celery_status = result.status
        our_status = status_map.get(celery_status, JobStatus.QUEUED)
        job_result = MonitoringJobResult(
            job_id=job_id,
            farm_id="",
            status=our_status,
        )
        if our_status == JobStatus.COMPLETED and result.result:
            res = result.result
            job_result.farm_id = res.get("farm_id", "")
            job_result.snapshot_id = res.get("snapshot_id")
            job_result.alert_count = res.get("alert_count", 0)
            job_result.critical_alerts = res.get("critical_alerts", 0)
            job_result.duration_seconds = res.get("duration_seconds")
        elif our_status == JobStatus.FAILED:
            job_result.error_message = str(result.result) if result.result else "Unknown error"

        return job_result
    
    def cancel_job(
        self,
        job_id: str
    ) -> bool:
        """Revoke a queued or running task."""
        try:
            celery_app.control.revoke(job_id, terminate=True, signal="SIGTERM")
            return True
        except Exception as exc:
            logger.error("Failed to cancel job %s: %s", job_id, exc)
            return False
        
    def ping_workers(
        self,
        timeout: float = 5.0
    )->Dict[str,Any]:
        """Check if any Celery workers are online."""
        start = datetime.utcnow()
        from monitoring.core.tasks import ping_task

        try:
            ar = ping_task.apply_async(queue="monitoring", retry = True)
            logger.info(
                "Ping task published | task_id=%s | broker=%s",
                ar.id, celery_app.conf.broker_url,
            )
            res = ar.get(timeout=timeout, propagate=True)
            elapsed_ms = (datetime.utcnow() - start).total_seconds() * 1000
            return{
                "worker_online": True,
                "response_time_ms": round(elapsed_ms, 1),
                "worker_id": res.get("worker_id"),
            }
        except Exception as exc:
            logger.error(
                "Ping failed | type=%s | msg=%s | broker=%s",
                type(exc).__name__, exc, celery_app.conf.broker_url,
                exc_info=True,
            )
            return {
                "worker_online": False, 
                "error": f"{type(exc).__name__}: {exc}",
            }
        
#Singleton
job_engine = JobEngine()