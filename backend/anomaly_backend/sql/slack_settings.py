from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend import tables


@dataclass(frozen=True, slots=True)
class SlackSettingsSnapshot:
    enabled: bool
    bot_token: str | None
    channel_id: str | None
    updated_at: datetime
    updated_by_username: str | None


def _snapshot(values: Mapping[Any, Any]) -> SlackSettingsSnapshot:
    return SlackSettingsSnapshot(
        enabled=values["enabled"],
        bot_token=values["bot_token"],
        channel_id=values["channel_id"],
        updated_at=values["updated_at"],
        updated_by_username=values["updated_by_username"],
    )


async def read_slack_settings(
    connection: AsyncConnection,
    *,
    for_update: bool = False,
) -> SlackSettingsSnapshot:
    statement = (
        select(
            tables.slack_settings.c.enabled,
            tables.slack_settings.c.bot_token,
            tables.slack_settings.c.channel_id,
            tables.slack_settings.c.updated_at,
            tables.users.c.username.label("updated_by_username"),
        )
        .select_from(
            tables.slack_settings.outerjoin(
                tables.users,
                tables.users.c.user_id == tables.slack_settings.c.updated_by_user_id,
            )
        )
        .where(tables.slack_settings.c.singleton.is_(True))
    )
    if for_update:
        statement = statement.with_for_update(of=tables.slack_settings)
    row = (
        await connection.execute(statement)
    ).mappings().one()
    return _snapshot(row)


async def write_slack_settings(
    connection: AsyncConnection,
    *,
    enabled: bool,
    bot_token: str | None,
    channel_id: str | None,
    updated_by_user_id: str,
    updated_by_username: str,
) -> SlackSettingsSnapshot:
    row = (
        await connection.execute(
            update(tables.slack_settings)
            .where(tables.slack_settings.c.singleton.is_(True))
            .values(
                enabled=enabled,
                bot_token=bot_token,
                channel_id=channel_id,
                updated_at=func.now(),
                updated_by_user_id=updated_by_user_id,
            )
            .returning(
                tables.slack_settings.c.enabled,
                tables.slack_settings.c.bot_token,
                tables.slack_settings.c.channel_id,
                tables.slack_settings.c.updated_at,
            )
        )
    ).mappings().one()
    await connection.commit()
    return SlackSettingsSnapshot(
        enabled=row["enabled"],
        bot_token=row["bot_token"],
        channel_id=row["channel_id"],
        updated_at=row["updated_at"],
        updated_by_username=updated_by_username,
    )
