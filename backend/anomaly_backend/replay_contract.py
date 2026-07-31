from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


REPLAY_CONTRACT_LOCK_KEY = 731_113


def acquire_shared_replay_contract_lock(
    connection: Any,
) -> Any:
    if isinstance(connection, AsyncConnection):
        return connection.execute(
            text("SELECT pg_advisory_xact_lock_shared(:key)"),
            {"key": REPLAY_CONTRACT_LOCK_KEY},
        )
    return connection.execute(
        "SELECT pg_advisory_xact_lock_shared(%s)",
        (REPLAY_CONTRACT_LOCK_KEY,),
    )
