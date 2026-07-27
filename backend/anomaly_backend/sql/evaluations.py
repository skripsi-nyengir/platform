from sqlalchemy import bindparam, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.tables import model_evaluations


_SUMMARY_COLUMNS = (
    model_evaluations.c.version,
    model_evaluations.c.model,
    model_evaluations.c.track,
    model_evaluations.c.label,
    model_evaluations.c.score_key,
    model_evaluations.c.score_semantics,
    model_evaluations.c.evaluation_period,
    model_evaluations.c.validation_only,
    model_evaluations.c.test_evaluated,
    model_evaluations.c.n_val_windows,
    model_evaluations.c.threshold,
    model_evaluations.c.threshold_policy,
    model_evaluations.c.has_labeled_ground_truth,
    model_evaluations.c.available_metrics,
    model_evaluations.c.summary,
    model_evaluations.c.model_key,
    model_evaluations.c.report_source,
    model_evaluations.c.label_source,
    model_evaluations.c.evaluation_kind,
    model_evaluations.c.test_observed,
    model_evaluations.c.independent_final,
    model_evaluations.c.source_commit,
    model_evaluations.c.source_path,
    model_evaluations.c.source_sha256,
)
_LIST_BY_VERSION_ASC = (
    select(*_SUMMARY_COLUMNS)
    .where(model_evaluations.c.is_public)
    .order_by(model_evaluations.c.version.asc())
)
_DETAIL_BY_VERSION = select(
    *_SUMMARY_COLUMNS,
    model_evaluations.c.model_hash,
    model_evaluations.c.preprocessing_hash,
    model_evaluations.c.threshold_hash,
    model_evaluations.c.metrics,
    model_evaluations.c.notes,
).where(
    model_evaluations.c.version == bindparam("version"),
    model_evaluations.c.is_public,
)


async def evaluation_rows(connection: AsyncConnection) -> list[RowMapping]:
    result = await connection.execute(_LIST_BY_VERSION_ASC)
    return list(result.mappings())


async def evaluation_row(
    connection: AsyncConnection, *, version: str
) -> RowMapping | None:
    result = await connection.execute(_DETAIL_BY_VERSION, {"version": version})
    return result.mappings().one_or_none()
