from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.contracts import (
    ModelEvaluationDetail,
    ModelEvaluationSummary,
    ModelEvaluationsQuery,
    ModelEvaluationsResponse,
)
from anomaly_backend.db import get_connection
from anomaly_backend.problems import NotFound, new_request_id
from anomaly_backend.sql.evaluations import evaluation_row, evaluation_rows


router = APIRouter()


def _summary(row: RowMapping) -> ModelEvaluationSummary:
    return ModelEvaluationSummary.model_validate(dict(row), strict=True)


@router.get("/api/model-evaluations", response_model=ModelEvaluationsResponse)
async def list_model_evaluations(
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 25,
) -> ModelEvaluationsResponse:
    query = ModelEvaluationsQuery.model_validate(
        {"page": page, "page_size": page_size}, strict=True
    )
    rows = await evaluation_rows(connection)
    start = (query.page - 1) * query.page_size
    return ModelEvaluationsResponse(
        request_id=new_request_id(),
        items=[_summary(row) for row in rows[start : start + query.page_size]],
        page=query.page,
        page_size=query.page_size,
        total=len(rows),
    )


@router.get(
    "/api/model-evaluations/{version:path}", response_model=ModelEvaluationDetail
)
async def model_evaluation(
    version: str,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> ModelEvaluationDetail:
    row = await evaluation_row(connection, version=version)
    if row is None:
        raise NotFound("The model evaluation was not found")
    return ModelEvaluationDetail.model_validate(
        {**dict(row), "request_id": new_request_id()}, strict=True
    )
