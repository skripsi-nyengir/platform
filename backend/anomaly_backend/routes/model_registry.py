from fastapi import APIRouter

from anomaly_backend.contracts import ModelRegistryResponse
from anomaly_backend.model_registry import load_reported_models

router = APIRouter()


@router.get("/api/model-registry", response_model=ModelRegistryResponse)
async def model_registry() -> ModelRegistryResponse:
    return ModelRegistryResponse(items=load_reported_models())
