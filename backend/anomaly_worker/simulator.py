"""Deterministic preview score generation.

This module deliberately knows nothing about thresholds, provenance, alerts, or
persistence.  It only implements the byte-level simulation contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re


_ARCHIVE_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_UINT16_MAX_FOR_EPISODE = 1311
_WINDOWS_PER_BLOCK = 256
_EPISODE_LENGTH = 3
_EPISODE_START_MODULUS = _WINDOWS_PER_BLOCK - _EPISODE_LENGTH + 1
_UINT64_MAX = (1 << 64) - 1


class SimulatorInputError(ValueError):
    """Raised when a value cannot be encoded canonically."""


def _canonical_text(value: str, field: str) -> str:
    if not value or "|" in value:
        raise SimulatorInputError(f"{field} must be non-empty and cannot contain '|'")
    return value


def _canonical_uint(value: int, field: str) -> str:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SimulatorInputError(f"{field} must be an unsigned integer")
    return str(value)


def _archive_sha(value: str) -> str:
    if not _ARCHIVE_SHA_RE.fullmatch(value):
        raise SimulatorInputError(
            "archive_sha256 must be lowercase 64-character hexadecimal"
        )
    return value


def canonical_block_bytes(
    archive_sha256: str,
    model_version: str,
    segment_id: int,
    block_ordinal: int,
) -> bytes:
    """Return the exact canonical UTF-8 input for an episode block digest."""

    fields = (
        _archive_sha(archive_sha256),
        _canonical_text(model_version, "model_version"),
        _canonical_uint(segment_id, "segment_id"),
        _canonical_uint(block_ordinal, "block_ordinal"),
    )
    return "|".join(fields).encode("utf-8")


def canonical_score_bytes(
    archive_sha256: str,
    model_version: str,
    segment_id: int,
    ending_corpus_index: int,
) -> bytes:
    """Return the exact canonical UTF-8 input for a score digest."""

    fields = (
        _archive_sha(archive_sha256),
        _canonical_text(model_version, "model_version"),
        _canonical_uint(segment_id, "segment_id"),
        _canonical_uint(ending_corpus_index, "ending_corpus_index"),
    )
    return "|".join(fields).encode("utf-8")


@dataclass(frozen=True, slots=True)
class EpisodeBlock:
    block_ordinal: int
    digest: bytes
    decision_integer: int
    start_offset: int

    @property
    def has_episode(self) -> bool:
        return self.decision_integer < _UINT16_MAX_FOR_EPISODE

    def contains(self, eligible_window_ordinal: int) -> bool:
        if (
            not self.has_episode
            or eligible_window_ordinal // _WINDOWS_PER_BLOCK != self.block_ordinal
        ):
            return False
        offset = eligible_window_ordinal % _WINDOWS_PER_BLOCK
        return self.start_offset <= offset < self.start_offset + _EPISODE_LENGTH


def episode_block(
    archive_sha256: str,
    model_version: str,
    segment_id: int,
    block_ordinal: int,
) -> EpisodeBlock:
    digest = hashlib.sha256(
        canonical_block_bytes(
            archive_sha256, model_version, segment_id, block_ordinal
        )
    ).digest()
    return EpisodeBlock(
        block_ordinal=block_ordinal,
        digest=digest,
        decision_integer=int.from_bytes(digest[:2], byteorder="big", signed=False),
        start_offset=int.from_bytes(digest[2:4], byteorder="big", signed=False)
        % _EPISODE_START_MODULUS,
    )


def is_episode_window(
    archive_sha256: str,
    model_version: str,
    segment_id: int,
    eligible_window_ordinal: int,
) -> bool:
    block_ordinal = eligible_window_ordinal // _WINDOWS_PER_BLOCK
    return episode_block(
        archive_sha256, model_version, segment_id, block_ordinal
    ).contains(eligible_window_ordinal)


def preview_score(
    archive_sha256: str,
    model_version: str,
    segment_id: int,
    eligible_window_ordinal: int,
    ending_corpus_index: int,
) -> float:
    """Return a deterministic finite float64-compatible Python ``float``."""

    digest = hashlib.sha256(
        canonical_score_bytes(
            archive_sha256, model_version, segment_id, ending_corpus_index
        )
    ).digest()
    integer = int.from_bytes(digest[:8], byteorder="big", signed=False)
    unit = integer / _UINT64_MAX
    if is_episode_window(
        archive_sha256, model_version, segment_id, eligible_window_ordinal
    ):
        return 1.05 + 0.45 * unit
    return 0.15 + 0.65 * unit
