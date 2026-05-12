"""Centralized configuration for paths and conventions.

All environment-specific paths live here so they can be overridden by the CLI
or by the downstream segmentation developer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Project root = parent of the `annotation/` directory.
_PKG_DIR = Path(__file__).resolve().parent
_ANNOTATION_DIR = _PKG_DIR.parents[1]  # .../annotation/

DEFAULT_INPUT_DIR = Path(
    "/allen/aics/rep_learn/spatial_transcriptomics/dataset/dapi_selected_tiles"
)
DEFAULT_TILE_CSV_NAME = "tile_coordinates.csv"
DEFAULT_OUTPUT_DIR = _ANNOTATION_DIR / "annotations"
DEFAULT_LOG_PATH = _ANNOTATION_DIR / "logs" / "annotation_log.csv"

# Cellpose convention: ground-truth masks are named "<image_stem>_masks.tif"
# and placed alongside (or referenced relative to) the source image. We keep
# that suffix so the coworker can drop the files next to the DAPI tiles and
# run `cellpose` training/eval without renaming.
MASK_SUFFIX = "_masks.tif"


@dataclass
class Config:
    input_dir: Path = DEFAULT_INPUT_DIR
    tile_csv: Path | None = None
    output_dir: Path = DEFAULT_OUTPUT_DIR
    log_path: Path = DEFAULT_LOG_PATH

    def __post_init__(self) -> None:
        self.input_dir = Path(self.input_dir)
        self.output_dir = Path(self.output_dir)
        self.log_path = Path(self.log_path)
        if self.tile_csv is None:
            self.tile_csv = self.input_dir / DEFAULT_TILE_CSV_NAME
        else:
            self.tile_csv = Path(self.tile_csv)

    def ensure_dirs(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def mask_path_for(self, image_filename: str) -> Path:
        stem = Path(image_filename).stem
        return self.output_dir / f"{stem}{MASK_SUFFIX}"
