"""Account management for the platform's login.

The platform deliberately exposes no registration endpoint, so accounts are created
here instead. The password is read from stdin rather than an argument, keeping it out
of shell history and out of the process list.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
import getpass
import sys

from sqlalchemy.exc import SQLAlchemyError

from anomaly_backend.auth import current_instant, upsert_user
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine


_MINIMUM_PASSWORD_LENGTH = 12


class AuthCliError(RuntimeError):
    pass


def read_password(*, confirm: bool) -> str:
    """Read a password from a terminal prompt, or from a pipe when not interactive."""
    if sys.stdin.isatty():
        password = getpass.getpass("Password: ")
        if confirm and password != getpass.getpass("Confirm password: "):
            raise AuthCliError("passwords did not match")
    else:
        password = sys.stdin.readline().rstrip("\n")
    if len(password) < _MINIMUM_PASSWORD_LENGTH:
        raise AuthCliError(
            f"password must be at least {_MINIMUM_PASSWORD_LENGTH} characters"
        )
    return password


async def _run(username: str, password: str, display_name: str) -> tuple[str, bool]:
    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as connection:
            return await upsert_user(
                connection,
                username,
                password,
                display_name,
                now=current_instant(),
            )
    finally:
        await engine.dispose()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auth-cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser(
        "create-user",
        help="create an account, or reset it if the username already exists",
    )
    _ = create.add_argument("username")
    _ = create.add_argument("--display-name", default=None)
    reset = subparsers.add_parser("set-password", help="replace an account password")
    _ = reset.add_argument("username")
    _ = reset.add_argument("--display-name", default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    username = str(arguments.username).strip()
    if not username:
        print("auth-cli: username must not be empty", file=sys.stderr)
        return 2
    display_name = arguments.display_name or username
    try:
        password = read_password(confirm=arguments.command == "create-user")
        user_id, created = asyncio.run(_run(username, password, str(display_name)))
    except (AuthCliError, KeyError, ValueError, SQLAlchemyError) as error:
        print(f"auth-cli: {error}", file=sys.stderr)
        return 2
    # Replacing a password also revokes that account's sessions, which an operator
    # needs to know; a fresh account has none to revoke.
    outcome = "created" if created else "password replaced; existing sessions revoked"
    print(f"{username} ({user_id}): {outcome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
