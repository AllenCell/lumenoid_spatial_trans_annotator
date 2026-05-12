from pathlib import Path

from cell_annotation import log as clog
from cell_annotation.io import TileRecord


def _tiles():
    return [
        TileRecord(tile_id=0, filename="a.tif", path=Path("a.tif"), dapi_p99=100.0),
        TileRecord(tile_id=1, filename="b.tif", path=Path("b.tif"), dapi_p99=120.0),
    ]


def test_init_and_update_status(tmp_path):
    log = tmp_path / "log.csv"
    df = clog.init_log(log, _tiles())
    assert len(df) == 2
    assert set(df["status"]) == {clog.STATUS_PENDING}

    clog.update_status(log, 0, status=clog.STATUS_IN_PROGRESS, annotator="m")
    clog.update_status(log, 0, status=clog.STATUS_COMPLETED, annotator="m", n_cells=7)
    df = clog.load_log(log)
    row0 = df.loc[df["tile_id"] == 0].iloc[0]
    assert row0["status"] == clog.STATUS_COMPLETED
    assert int(row0["n_cells"]) == 7
    assert row0["annotator"] == "m"


def test_first_pending_index(tmp_path):
    log = tmp_path / "log.csv"
    clog.init_log(log, _tiles())
    assert clog.first_pending_index(log) == 0
    clog.update_status(log, 0, status=clog.STATUS_COMPLETED)
    assert clog.first_pending_index(log) == 1
    clog.update_status(log, 1, status=clog.STATUS_COMPLETED)
    assert clog.first_pending_index(log) == 0  # nothing pending -> fall back
