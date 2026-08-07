from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from anomaly_backend.auth_middleware import install_session_guard
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.problems import install_problem_handlers
from anomaly_backend.routes.alerts import router as alerts_router
from anomaly_backend.routes.auth import router as auth_router
from anomaly_backend.routes.eda import router as eda_router
from anomaly_backend.routes.evaluations import router as evaluations_router
from anomaly_backend.routes.inference import router as inference_router
from anomaly_backend.routes.injection import router as injection_router
from anomaly_backend.routes.model_registry import router as model_registry_router
from anomaly_backend.routes.offline_evaluations import router as offline_evaluations_router
from anomaly_backend.routes.post_inference_bins import router as post_inference_bins_router
from anomaly_backend.routes.preview import router as preview_router
from anomaly_backend.routes.simulation import router as simulation_router
from anomaly_backend.routes.system import router as system_router
from anomaly_backend.routes.telemetry import router as telemetry_router


def create_app(engine: AsyncEngine, *routers: APIRouter) -> FastAPI:
    """Create an app around an engine whose lifecycle remains caller-owned."""
    app = FastAPI(
        redirect_slashes=False,
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    app.state.engine = engine
    install_problem_handlers(app)
    for router in routers:
        app.include_router(router)
    # Installed last so it wraps every router, including any added by a caller.
    install_session_guard(app)
    return app


_PRODUCTION_ROUTERS = (
    auth_router,
    preview_router,
    telemetry_router,
    inference_router,
    post_inference_bins_router,
    injection_router,
    simulation_router,
    alerts_router,
    eda_router,
    evaluations_router,
    model_registry_router,
    offline_evaluations_router,
    system_router,
)
_production_engine = create_database_engine(Settings.from_environ())


@asynccontextmanager
async def _production_lifespan(_: FastAPI) -> AsyncGenerator[None]:
    try:
        yield
    finally:
        await _production_engine.dispose()


app = create_app(_production_engine, *_PRODUCTION_ROUTERS)
app.router.lifespan_context = _production_lifespan
