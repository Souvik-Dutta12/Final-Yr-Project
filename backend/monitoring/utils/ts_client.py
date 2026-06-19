"""
HTTP client for calling the TypeScript Orchestration Server.
All Python→TS communication is centralised here.
Never call the TS server from anywhere else directly.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from monitoring.config import monitoring_config

logger = logging.getLogger(__name__)

# Shared async client — reuse connections across requests
_client: Optional[httpx.AsyncClient] = None

def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=monitoring_config.ts_server_url,
            headers={
                "Authorization": f"Bearer {monitoring_config.ts_internal_token}",
                "Content-Type": "application/json",
                "X-Internal-Service": "python-core",
            },
            timeout=30.0,
        )
    return _client

class TSClient:
    """Typed wrapper around TS server internal API."""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_farm_config(self, farm_id: str) -> Optional[Dict]:
        """Fetch monitoring config for a farm from TS server."""
        try:
            resp = await _get_client().get(f"/internal/farms/{farm_id}/config")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_active_farms(self) -> List[Dict]:
        """Fetch all farms with active monitoring enabled."""
        resp = await _get_client().get("/internal/farms/active-monitoring")
        resp.raise_for_status()
        return resp.json().get("data", [])
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def persist_snapshot(self, snapshot_payload: Dict) -> Dict:
        """Persist snapshot to TS PostgreSQL. Returns {id, ...}."""
        resp = await _get_client().post("/internal/snapshots", json=snapshot_payload)
        resp.raise_for_status()
        return resp.json()
    
    async def get_snapshot_history(
        self, farm_id: str, limit: int = 10
    ) -> List[Dict]:
        """Fetch recent snapshots for trend analysis."""
        resp = await _get_client().get(
            f"/internal/snapshots/{farm_id}/history",
            params={"limit": limit},
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
    
    async def get_baseline_snapshot(self, farm_id: str) -> Optional[Dict]:
        """Fetch the designated baseline snapshot."""
        try:
            resp = await _get_client().get(
                f"/internal/snapshots/{farm_id}/baseline"
            )
            resp.raise_for_status()
            return resp.json().get("data")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def persist_alerts(self, alerts_payload: List[Dict]) -> List[Dict]:
        """Persist a batch of alerts. Returns list of created alert IDs."""
        resp = await _get_client().post(
            "/internal/alerts/batch", json={"alerts": alerts_payload}
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def persist_report(self, report_payload: Dict) -> Dict:
        """Persist a monitoring report."""
        resp = await _get_client().post("/internal/reports", json=report_payload)
        resp.raise_for_status()
        return resp.json()
    
    async def update_job_status(
        self, job_id: str, status: str, extra: Optional[Dict] = None
    ) -> None:
        """Notify TS of job status change."""
        payload = {"status": status, **(extra or {})}
        await _get_client().put(f"/internal/jobs/{job_id}/status", json=payload)

    async def trigger_notification(self, notification_payload: Dict) -> None:
        """Ask TS server to send push/email/SMS notification."""
        await _get_client().post("/internal/notify", json=notification_payload)

#Singleton
ts_client = TSClient()