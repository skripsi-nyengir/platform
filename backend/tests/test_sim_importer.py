import json
import inspect
from typing import Any, cast

from anomaly_backend import importer, sim_importer


class RecordingConnection:
    def __init__(self) -> None:
        self.statement = ""
        self.parameters: tuple[object, ...] = ()

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
