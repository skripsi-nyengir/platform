from collections.abc import AsyncIterator
from typing import cast

from fastapi import Request
from sqlalchemy import String, column, func, literal, select, table
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from anomaly_backend.config import Settings


def _single_migration_revision(revisions: list[str]) -> str | None:
    return revisions[0] if len(revisions) == 1 else None


def create_database_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(settings.async_database_url)


async def database_is_healthy(connection: AsyncConnection) -> bool:
    result = await connection.scalar(select(literal(1)))
    return result == 1


async def current_migration_revision(connection: AsyncConnection) -> str | None:
    table_exists = await connection.scalar(
        select(literal(True)).where(
            func.to_regclass("public.alembic_version").is_not(None)
        )
    )
    if table_exists is None:
        return None
    version_num = column("version_num", String)
    alembic_version = table("alembic_version", version_num)
    revisions = (
        await connection.scalars(select(version_num).select_from(alembic_version))
    ).all()
    # A linear Alembic history has exactly one current revision. Returning no
    # revision for a branched database makes readiness fail closed.
    return _single_migration_revision([str(revision) for revision in revisions])


async def get_connection(request: Request) -> AsyncIterator[AsyncConnection]:
    engine = cast(AsyncEngine, request.app.state.engine)
    async with engine.connect() as connection:
        yield connection
