"""Quality-control checks for completed annotation masks.

Validates that each saved mask file is a clean, Cellpose-ready ground truth:
- 2D integer array with positive instance IDs (0 = background).
- Each non-zero ID corresponds to a single connected component (otherwise the
  annotator likely reused a label across two cells).
- No zero-area or near-zero-area instances (likely paint slips).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from skimage.measure import label as cc_label

from cell_annotation.config import Config, MASK_SUFFIX
from cell_annotation import io as cio


MIN_AREA_PX = 4  # below this is almost certainly a paint slip


def check_mask(path: Path) -> dict:
    labels = cio.load_labels(path)
    issues: list[str] = []

    if labels.ndim != 2:
        issues.append(f"not 2D (shape={labels.shape})")

    ids = np.unique(labels)
    ids = ids[ids > 0]
    n_instances = int(ids.size)

    non_contiguous = []
    tiny = []
    areas = []
    for i in ids:
        mask = labels == i
        area = int(mask.sum())
        areas.append(area)
        if area < MIN_AREA_PX:
            tiny.append((int(i), area))
        cc = cc_label(mask, connectivity=1)
        if cc.max() > 1:
            non_contiguous.append(int(i))

    if non_contiguous:
        issues.append(f"non-contiguous labels: {non_contiguous}")
    if tiny:
        issues.append(f"tiny labels (<{MIN_AREA_PX}px): {tiny}")

    return {
        "path": str(path),
        "n_instances": n_instances,
        "min_area": int(min(areas)) if areas else 0,
        "max_area": int(max(areas)) if areas else 0,
        "issues": issues,
    }


def summarize_annotations(output_dir: Path) -> list[dict]:
    output_dir = Path(output_dir)
    mask_paths = sorted(output_dir.glob(f"*{MASK_SUFFIX}"))
    return [check_mask(p) for p in mask_paths]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cell-annotate-qc",
        description="Validate cell annotation masks for Cellpose handoff.",
    )
    p.add_argument("--output-dir", type=Path, default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    cfg = Config(output_dir=args.output_dir) if args.output_dir else Config()

    reports = summarize_annotations(cfg.output_dir)
    if not reports:
        print(f"No mask files found in {cfg.output_dir}")
        return 0

    any_issue = False
    for r in reports:
        flag = "FAIL" if r["issues"] else "OK"
        print(
            f"[{flag}] {Path(r['path']).name}: "
            f"{r['n_instances']} cells, area [{r['min_area']}..{r['max_area']}]"
        )
        for msg in r["issues"]:
            any_issue = True
            print(f"    - {msg}")
    return 1 if any_issue else 0


if __name__ == "__main__":
    raise SystemExit(main())
