from fastapi import APIRouter

from anomaly_backend.contracts import OfflineEvaluationsResponse
from anomaly_backend.offline_evaluations import load_offline_evaluations

router = APIRouter()


@router.get("/api/offline-evaluations", response_model=OfflineEvaluationsResponse)
async def offline_evaluations() -> OfflineEvaluationsResponse:
    return load_offline_evaluations()
