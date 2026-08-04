import json
import inspect
from typing import Any, cast

from anomaly_backend import importer, sim_importer


class RecordingConnection:
    def __init__(self) -> None:
        self.statement = ""
        self.parameters: tuple[object, ...] = ()
        self.batches: list[list[tuple[object, ...]]] = []

    def __enter__(self) -> "RecordingConnection":
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def cursor(self) -> "RecordingConnection":
        return self

    def executemany(
        self, statement: str, parameters: list[tuple[object, ...]]
    ) -> None:
        self.statement = statement
        self.batches.append(parameters)

    def execute(
        self, statement: str, parameters: tuple[object, ...]
    ) -> None:
        self.statement = statement
        self.parameters = parameters


def test_simulation_snapshot_uses_live_contract_without_changing_scaler() -> None:
    connection = RecordingConnection()

    sim_importer._upsert_snapshot(
        cast(Any, connection), "simulation-corpus", [{"segment_index": 0}]
    )

    assert "contract_status" in connection.statement
    assert "VALUES (%s, %s::jsonb, 10, 1, 'live_10'" in connection.statement
    assert json.loads(cast(str, connection.parameters[1])) == [
        "temperature_c",
        "relative_humidity_pct",
    ]
    assert json.loads(cast(str, connection.parameters[5])) == {
        "channels": ["temperature_c", "relative_humidity_pct"],
        "minimum": sim_importer.SCALER_MINIMUM,
        "maximum": sim_importer.SCALER_MAXIMUM,
        "fit_split": "train",
    }


def test_corpus_importer_explicitly_persists_live_snapshot_status() -> None:
    source = inspect.getsource(importer.import_corpus)
    snapshot_insert = source.split("INSERT INTO preprocessing_snapshots", 1)[1]

    assert "contract_status" in snapshot_insert.split("published_row =", 1)[0]


def test_artifact_thresholds_match_step7_clean_point_p995() -> None:
    connection = RecordingConnection()

    sim_importer._upsert_models(cast(Any, connection))

    expected = {
        "artifact-rnn-v3": 0.0005023972923204374,
        "artifact-gru-v3": 0.0005618056084495022,
        "artifact-transformer-v3": 0.00026567234380490805,
        "artifact-lstm-ae-v3": 0.0009487349475675721,
        "artifact-conv1d-v3": 0.0003201981883103135,
    }
    model_rows = next(
        batch
        for batch in connection.batches
        if batch and batch[0][0] == "artifact-lstm-ae-v3"
    )
    assert {
        cast(str, row[0]): cast(float, row[6])
        for row in model_rows
        if row[0] in expected
    } == expected
