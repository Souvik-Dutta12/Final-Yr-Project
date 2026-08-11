"""
Monitoring routes — stub for Phase 1.
Expanded in later phases.
"""

from pydantic import Field, BaseModel
from typing import Optional

from monitoring.core.job_engine import job_engine
from fastapi import APIRouter, Path
from fastapi.responses import JSONResponse
from monitoring.config import monitoring_config
from celery_app import celery_app
from starlette.concurrency import run_in_threadpool


import redis



router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

@router.get("/health")
async def monitoring_health():
    """
    Liveness probe for the monitoring module.
    Tests: config loaded, Celery importable.
    """
    try:
        from celery_app import celery_app
        celery_ok = True
    except Exception:
        celery_ok = False

    return JSONResponse({
        "status": "ok",
        "module": "monitoring",
        "version": "1.0.0",
        "celery_available": celery_ok,
        "ts_server_url": monitoring_config.ts_server_url,
    })

@router.get("/config")
async def monitoring_config_endpoint():
    """
    Return resolved monitoring config (non-sensitive fields).
    Useful for verifying env vars are loaded correctly.
    """
    cfg = monitoring_config
    return JSONResponse({
        "ts_server_url": cfg.ts_server_url,
        "redis_url": cfg.redis_url.replace(
            cfg.redis_url.split("@")[-1] if "@" in cfg.redis_url else "", "***"
        ) if cfg.redis_url else None,
        "job_concurrency": cfg.job_concurrency,
        "max_farms_per_batch": cfg.max_farms_per_batch,
        "alert_thresholds": {
            "deforestation_min_ha": cfg.thresholds.deforestation_min_ha,
            "ndvi_drop_threshold": cfg.thresholds.ndvi_drop_threshold,
            "soil_quality_index_drop": cfg.thresholds.soil_quality_index_drop,
        },
    })

@router.post("/jobs/ping-worker")
async def ping_worker():
    """
    Test Celery worker connectivity.
    Returns round-trip time if a worker is online.
    """
    result = await run_in_threadpool(job_engine.ping_workers, timeout=8.0)
    status_code = 200 if result.get("worker_online") else 503
    return JSONResponse(result, status_code=status_code)

class TestJobRequest(BaseModel):
    farm_id: str = Field(..., example="farm-001")
    message: str = Field(..., example="hello monitoring")

@router.post("/jobs/test-task")
async def submit_test_job(body: TestJobRequest):
    """
    Submit a no-op echo task.
    Use to verify full path: FastAPI → Celery → Worker → Result.
    """
    job_id = job_engine.submit_test_job(body.farm_id, body.message)
    return JSONResponse({
        "job_id":  job_id,
        "status":  "QUEUED",
        "message": "Echo task queued. Poll /monitoring/jobs/{job_id}/status",
    })

@router.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str = Path(..., description="Celery task ID")):
    """
    Poll job status.
    Returns QUEUED | RUNNING | COMPLETED | FAILED | CANCELLED
    plus result summary when COMPLETED.
    """
    result = job_engine.get_job_status(job_id)
    return JSONResponse(result.model_dump())





@router.get("/debug/connectivity-check")
async def connectivity_check():
    out = {}
    # 1. Raw redis ping from THIS process
    try:
        r = redis.from_url(monitoring_config.redis_url, socket_connect_timeout=3)
        out["raw_redis_ping"] = r.ping()
        out["queue_len_before"] = r.llen("monitoring")
    except Exception as e:
        out["raw_redis_error"] = str(e)

    # 2. Same celery_app instance the worker uses?
    out["broker_url_seen_by_fastapi"] = celery_app.conf.broker_url

    # 3. Can control.inspect() see the worker from THIS process?
    try:
        active = celery_app.control.inspect(timeout=3).active()
        out["workers_visible_from_fastapi"] = list(active.keys()) if active else []
    except Exception as e:
        out["inspect_error"] = str(e)

    return JSONResponse(out)