from hashlib import sha256

import pytest

from anomaly_worker.simulator import (
    SimulatorInputError,
    canonical_block_bytes,
    canonical_score_bytes,
    episode_block,
    is_episode_window,
    preview_score,
)


ARCHIVE_SHA = "6c5a7ee8c248931bcc490cc114a3af55add8af82f976f58015ff7225dccce01a"
MODEL = "preview-lstm-ae-v1"


def test_golden_episode_block_uses_exact_canonical_bytes() -> None:
    canonical = canonical_block_bytes(ARCHIVE_SHA, MODEL, 0, 105)
    assert canonical == (
        b"6c5a7ee8c248931bcc490cc114a3af55add8af82f976f58015ff7225dccce01a"
        b"|preview-lstm-ae-v1|0|105"
    )
    block = episode_block(ARCHIVE_SHA, MODEL, 0, 105)
    assert sha256(canonical).hexdigest() == (
        "00268fb0bc06a3193db8219354f2db01bed77359a56163604593a22a4738e8a2"
    )
    assert block.decision_integer == 38
    assert block.start_offset == 208
    assert block.has_episode
    assert [block.contains(105 * 256 + offset) for offset in (207, 208, 210, 211)] == [
        False,
        True,
        True,
        False,
    ]


def test_golden_score_and_episode_membership() -> None:
    ordinal = 27088
    ending_index = 27117
    canonical = canonical_score_bytes(ARCHIVE_SHA, MODEL, 0, ending_index)
    digest = sha256(canonical).digest()
    assert digest.hex() == (
        "c2fa81897e725fae6995d1983ca1ec7a189f0e327a0b80eb8f87a08d2e05427d"
    )
    assert int.from_bytes(digest[:8], "big") == 14049684415067611054
    assert is_episode_window(ARCHIVE_SHA, MODEL, 0, ordinal)
    assert preview_score(ARCHIVE_SHA, MODEL, 0, ordinal, ending_index) == pytest.approx(
        1.392735713224921, abs=1e-12
    )


def test_trace_is_chunk_and_replay_subrange_independent() -> None:
    windows = [(ordinal, ordinal + 29) for ordinal in range(26800, 27300)]

    def run(selected: list[tuple[int, int]], chunk_size: int) -> dict[int, float]:
        result = {}
        for offset in range(0, len(selected), chunk_size):
            for ordinal, ending_index in selected[offset : offset + chunk_size]:
                result[ordinal] = preview_score(
                    ARCHIVE_SHA, MODEL, 0, ordinal, ending_index
                )
        return result

    full = run(windows, 17)
    differently_chunked = run(windows, 113)
    subrange = run(windows[240:320], 7)
    assert full == differently_chunked
    assert subrange == {key: full[key] for key in subrange}
    assert all(
        score > 1.0 if is_episode_window(ARCHIVE_SHA, MODEL, 0, ordinal)
        else score < 1.0
        for ordinal, score in full.items()
    )
    assert any(
        full[ordinal] != preview_score(
            ARCHIVE_SHA, "preview-usad-v1", 0, ordinal, ordinal + 29
        )
        for ordinal in full
    )


@pytest.mark.parametrize(
    ("archive_sha", "model_version"),
    [
        (ARCHIVE_SHA.upper(), MODEL),
        ("0" * 63, MODEL),
        (ARCHIVE_SHA, "bad|version"),
    ],
)
def test_noncanonical_identifiers_are_rejected(
    archive_sha: str, model_version: str
) -> None:
    with pytest.raises(SimulatorInputError):
        canonical_block_bytes(archive_sha, model_version, 0, 0)
