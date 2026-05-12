"""Per-tile annotation status log persisted as CSV.

Columns:
- tile_id
- filename
- status: pending | in_progress | completed | skipped
- annotator
- n_cells (number of unique non-zero label IDs at last save)
- updated_at (ISO8601 UTC)
- notes
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_SKIPPED = "skipped"

COLUMNS = [
    "tile_id",
    "filename",
    "status",
    "annotator",
    "n_cells",
    "updated_at",
    "notes",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_OBJECT_COLS = ("filename", "status", "annotator", "updated_at", "notes")


def _coerce_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Force string columns to object dtype so str assignments don't conflict
    with pandas' inferred float64 from all-NaN columns."""
    for col in _OBJECT_COLS:
        if col in df.columns:
            df[col] = df[col].astype(object)
    return df


def load_log(log_path: Path) -> pd.DataFrame:
    log_path = Path(log_path)
    if log_path.exists():
        df = pd.read_csv(log_path)
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = pd.NA
        return _coerce_dtypes(df[COLUMNS])
    return _coerce_dtypes(pd.DataFrame(columns=COLUMNS))


def save_log(df: pd.DataFrame, log_path: Path) -> None:
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(log_path, index=False)


def init_log(log_path: Path, tiles) -> pd.DataFrame:
    """Create or extend the log with rows for any tile not yet tracked."""
    df = load_log(log_path)
    existing = set(df["tile_id"].dropna().astype(int).tolist()) if not df.empty else set()
    new_rows = []
    for t in tiles:
        if t.tile_id in existing:
            continue
        new_rows.append(
            {
                "tile_id": t.tile_id,
                "filename": t.filename,
                "status": STATUS_PENDING,
                "annotator": pd.NA,
                "n_cells": 0,
                "updated_at": _now(),
                "notes": pd.NA,
            }
        )
    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    df = df.sort_values("tile_id").reset_index(drop=True)
    df = _coerce_dtypes(df)
    save_log(df, log_path)
    return df


def update_status(
    log_path: Path,
    tile_id: int,
    *,
    status: str,
    annotator: str | None = None,
    n_cells: int | None = None,
    notes: str | None = None,
) -> pd.DataFrame:
    df = load_log(log_path)
    mask = df["tile_id"].astype("Int64") == tile_id
    if not mask.any():
        raise ValueError(f"tile_id {tile_id} not present in log at {log_path}")
    df.loc[mask, "status"] = status
    if annotator is not None:
        df.loc[mask, "annotator"] = annotator
    if n_cells is not None:
        df.loc[mask, "n_cells"] = int(n_cells)
    if notes is not None:
        df.loc[mask, "notes"] = notes
    df.loc[mask, "updated_at"] = _now()
    save_log(df, log_path)
    return df


def first_pending_index(log_path: Path) -> int:
    """Return the position (row index) of the first non-completed tile, or 0."""
    df = load_log(log_path)
    if df.empty:
        return 0
    pending = df[~df["status"].isin([STATUS_COMPLETED, STATUS_SKIPPED])]
    if pending.empty:
        return 0
    return int(pending.index[0])
