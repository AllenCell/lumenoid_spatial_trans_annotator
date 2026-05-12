"""Command-line entry point for the annotation tool."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cell_annotation.config import Config
from cell_annotation import io as cio
from cell_annotation import log as clog


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cell-annotate",
        description="Launch napari to annotate cell boundaries on DAPI tiles. "
        "Outputs Cellpose-compatible *_masks.tif files.",
    )
    p.add_argument("--input-dir", type=Path, default=None, help="Override input dir.")
    p.add_argument("--tile-csv", type=Path, default=None, help="Override tile CSV path.")
    p.add_argument("--output-dir", type=Path, default=None, help="Override output dir.")
    p.add_argument("--log-path", type=Path, default=None, help="Override log CSV path.")
    p.add_argument(
        "--start-index",
        type=int,
        default=None,
        help="Tile row index to start from (default: first pending in log).",
    )
    p.add_argument("--annotator", type=str, default=None, help="Annotator name to record.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved config and tile count, then exit.",
    )
    return p


def _resolve_config(args: argparse.Namespace) -> Config:
    kwargs = {}
    if args.input_dir is not None:
        kwargs["input_dir"] = args.input_dir
    if args.tile_csv is not None:
        kwargs["tile_csv"] = args.tile_csv
    if args.output_dir is not None:
        kwargs["output_dir"] = args.output_dir
    if args.log_path is not None:
        kwargs["log_path"] = args.log_path
    return Config(**kwargs)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    cfg = _resolve_config(args)

    print(f"input_dir : {cfg.input_dir}")
    print(f"tile_csv  : {cfg.tile_csv}")
    print(f"output_dir: {cfg.output_dir}")
    print(f"log_path  : {cfg.log_path}")

    if not cfg.tile_csv.exists():
        print(f"ERROR: tile CSV not found: {cfg.tile_csv}", file=sys.stderr)
        return 2

    tiles = cio.list_tiles(cfg.tile_csv, cfg.input_dir)
    print(f"tiles     : {len(tiles)} discovered")

    if args.dry_run:
        for t in tiles[:5]:
            print(f"  - id={t.tile_id} file={t.filename}")
        if len(tiles) > 5:
            print(f"  ... (+{len(tiles) - 5} more)")
        return 0

    cfg.ensure_dirs()
    clog.init_log(cfg.log_path, tiles)

    # Lazy import napari only for the actual launch path.
    from cell_annotation.viewer import launch_annotator

    launch_annotator(cfg, start_index=args.start_index, annotator=args.annotator)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
