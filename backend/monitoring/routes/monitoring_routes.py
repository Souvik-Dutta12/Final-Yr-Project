"""
Monitoring routes — stub for Phase 1.
Expanded in later phases.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from monitoring.config import monitoring_config

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