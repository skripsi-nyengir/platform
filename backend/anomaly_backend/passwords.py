"""Password hashing built on the standard library.

scrypt is a memory-hard key derivation function available from ``hashlib``, so the
platform gains password storage without a new dependency. The cost parameters travel
with the digest, which lets them be raised later without a data migration: an existing
hash keeps verifying under the parameters it was written with.
"""

from base64 import b64decode, b64encode
import hashlib
import hmac
import secrets


_SCHEME = "scrypt"
_COST = 2**14
_BLOCK_SIZE = 8
_PARALLELISM = 1
_SALT_BYTES = 16
_DERIVED_BYTES = 32
_FIELD_COUNT = 6

# 128 * cost * block_size, the working set scrypt needs, plus room for OpenSSL's own
# bookkeeping. Left implicit, OpenSSL refuses parameters this large.
_MAX_MEMORY = 128 * _COST * _BLOCK_SIZE * 2


def _derive(password: str, salt: bytes, *, cost: int, block_size: int, parallelism: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=cost,
        r=block_size,
        p=parallelism,
        dklen=_DERIVED_BYTES,
        maxmem=128 * cost * block_size * 2,
    )


def hash_password(password: str) -> str:
    """Encode ``password`` as ``scrypt$cost$block$parallel$salt$digest``."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = _derive(
        password,
        salt,
        cost=_COST,
        block_size=_BLOCK_SIZE,
        parallelism=_PARALLELISM,
    )
    return "$".join(
        (
            _SCHEME,
            str(_COST),
            str(_BLOCK_SIZE),
            str(_PARALLELISM),
            b64encode(salt).decode("ascii"),
            b64encode(digest).decode("ascii"),
        )
    )


def verify_password(password: str, encoded: str) -> bool:
    """Report whether ``password`` matches ``encoded``.

    A malformed or unknown-scheme hash verifies as False rather than raising, so a
    corrupted row cannot turn a failed login into a 500.
    """
    fields = encoded.split("$")
    if len(fields) != _FIELD_COUNT:
        return False
    scheme, raw_cost, raw_block_size, raw_parallelism, raw_salt, raw_digest = fields
    if scheme != _SCHEME:
        return False
    try:
        cost = int(raw_cost)
        block_size = int(raw_block_size)
        parallelism = int(raw_parallelism)
        salt = b64decode(raw_salt, validate=True)
        expected = b64decode(raw_digest, validate=True)
    except ValueError:
        return False
    if cost < 2 or cost & (cost - 1) or block_size < 1 or parallelism < 1:
        return False
    if 128 * cost * block_size > _MAX_MEMORY:
        return False
    try:
        candidate = _derive(
            password,
            salt,
            cost=cost,
            block_size=block_size,
            parallelism=parallelism,
        )
    except ValueError:
        return False
    return hmac.compare_digest(candidate, expected)


# Verified against this when the username is unknown, so a missing account costs the
# same time as a wrong password and cannot be distinguished by response latency.
DUMMY_HASH = hash_password(secrets.token_urlsafe(32))
