"""TIFF I/O and tile listing.

Output masks follow the Cellpose ground-truth convention:
- dtype uint16 (auto-promoted to uint32 if >65535 instances, which should not
  happen on 512x512 tiles in practice).
- 0 = background, positive integers = unique cell instance IDs.
- Single 2D plane, compressed with deflate ("zlib").
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile


@dataclass(frozen=True)
class TileRecord:
    tile_id: int
    filename: str
    path: Path
    dapi_p99: float | None


def load_tile(path: Path) -> np.ndarray:
    """Load a DAPI tile as a 2D numpy array."""
    arr = tifffile.imread(str(path))
    if arr.ndim == 3 and arr.shape[0] == 1:
        arr = arr[0]
    if arr.ndim != 2:
        raise ValueError(f"Expected 2D image, got shape {arr.shape} from {path}")
    return arr


def list_tiles(csv_path: Path, input_dir: Path) -> list[TileRecord]:
    """Return tiles in CSV row order so annotation is deterministic."""
    df = pd.read_csv(csv_path)
    required = {"tile_id", "filename"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{csv_path} is missing required columns: {missing}")
    records: list[TileRecord] = []
    for _, row in df.iterrows():
        records.append(
            TileRecord(
                tile_id=int(row["tile_id"]),
                filename=str(row["filename"]),
                path=Path(input_dir) / str(row["filename"]),
                dapi_p99=float(row["dapi_p99"]) if "dapi_p99" in df.columns else None,
            )
        )
    return records


def _choose_dtype(labels: np.ndarray) -> np.dtype:
    max_val = int(labels.max()) if labels.size else 0
    if max_val <= np.iinfo(np.uint16).max:
        return np.dtype(np.uint16)
    return np.dtype(np.uint32)


def save_labels(labels: np.ndarray, path: Path) -> Path:
    """Atomically write an instance-label mask to `path`.

    Returns the final path written.
    """
    if labels.ndim != 2:
        raise ValueError(f"Expected 2D labels, got shape {labels.shape}")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dtype = _choose_dtype(labels)
    out = labels.astype(dtype, copy=False)
    # Atomic write: tmp file + os.replace.
    fd, tmp_name = tempfile.mkstemp(suffix=".tif", dir=str(path.parent))
    os.close(fd)
    try:
        tifffile.imwrite(
            tmp_name,
            out,
            compression="zlib",
            metadata={"description": "cell_annotation instance labels; 0=background"},
        )
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
    return path


def load_labels(path: Path) -> np.ndarray:
    """Load an instance-label mask from disk."""
    arr = tifffile.imread(str(path))
    if arr.ndim != 2:
        raise ValueError(f"Expected 2D labels, got shape {arr.shape}")
    return arr
