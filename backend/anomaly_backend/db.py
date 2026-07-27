from collections.abc import AsyncIterator
from typing import cast

from fastapi import Request
from sqlalchemy import String, column, func, literal, select, table
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from anomaly_backend.config import Settings


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
    revision = await connection.scalar(
        select(version_num).select_from(alembic_version)
    )
    return None if revision is None else str(revision)


async def get_connection(request: Request) -> AsyncIterator[AsyncConnection]:
    engine = cast(AsyncEngine, request.app.state.engine)
    async with engine.connect() as connection:
        yield connection
