from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/monitoring/alerts", tags=["Monitoring Alerts"])