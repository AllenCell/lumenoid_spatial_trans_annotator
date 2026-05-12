# lumenoid_spatial_trans_annotator

A small, focused **napari**-based annotation tool for drawing cell-boundary
instance masks on DAPI microscopy tiles, producing **Cellpose-compatible**
ground-truth masks that can be used as a benchmark to optimize segmentation
parameters and to fine-tune Cellpose models.

---

## Project context

### Goal

Produce a small, high-quality set of hand-drawn cell instance masks on DAPI
images of lumenoids (spatial transcriptomics dataset) and hand them off as a
benchmark to a Cellpose-based segmentation workflow. The benchmark is used
downstream to:

1. Tune Cellpose inference parameters (`diameter`, `flow_threshold`,
   `cellprob_threshold`, model selection) by comparing predicted masks to
   these ground-truth masks (mean IoU, average precision at IoU 0.5 / 0.75 /
   0.9, panoptic quality).
2. Optionally fine-tune a Cellpose model on the masks
   (`cellpose --train --dir <dir> --mask_filter _masks`).

### Source data

- **Modality:** single-channel DAPI (nuclear stain) microscopy.
- **Source:** spatial transcriptomics acquisition (slide `MS00001747`) at the
  Allen Institute for Cell Science.
- **On-disk location (internal, read-only):**
  `/allen/aics/rep_learn/spatial_transcriptomics/dataset/dapi_selected_tiles`
- **Tile manifest:** `tile_coordinates.csv` in that directory, with columns
  `tile_id, filename, x, y, tile_size, dapi_p99, dapi_mean, cyto_p99`.
- **Tile properties:** 20 tiles cropped from a larger acquisition, each
  **512 × 512 pixels, 16-bit single-channel TIFF**. The `dapi_p99` column is
  used at viewer launch time to preset the napari contrast limits, so the
  16-bit data is immediately viewable.

### Output

For each input `MS00001747_DAPI_tileNNN_xXXXX_yYYYY_size512.tif` the tool
writes one file:

```
annotations/MS00001747_DAPI_tileNNN_xXXXX_yYYYY_size512_masks.tif
```

- 2D `uint16` (auto-promoted to `uint32` only on overflow, which will not
  happen on 512 × 512 tiles).
- `0 = background`; every positive integer is one cell instance.
- Deflate-compressed TIFF, written atomically (tempfile + `os.replace`).
- The `_masks.tif` suffix matches the **Cellpose ground-truth naming
  convention**, so files can be dropped next to the DAPI images and consumed
  directly by `cellpose --mask_filter _masks ...`.

Per-tile progress is recorded in `logs/annotation_log.csv` with columns
`tile_id, filename, status, annotator, n_cells, updated_at, notes`. Statuses
are `pending | in_progress | completed | skipped`.

---

## Installation

```bash
git clone https://github.com/AllenCell/lumenoid_spatial_trans_annotator.git
cd lumenoid_spatial_trans_annotator
python3.12 -m venv .venv      # 3.10–3.12 all work
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

Verify the install (no GUI, just resolves config and lists tiles):

```bash
cell-annotate --dry-run
```

You should see the four resolved paths and `tiles : 20 discovered`.

---

## Annotating

```bash
cell-annotate --annotator "<your name>"
```

This opens napari with the first un-completed tile (resumes from the log
automatically) and a dock widget on the right.

### Workflow inside napari

1. Press **C** (or click *New cell label*) → `selected label` jumps to
   `max(existing) + 1`. Always do this before starting a new cell.
2. With the **paintbrush** active (default), draw a **closed** boundary
   around the cell.
3. Move the cursor inside the boundary and press **G** (or click *Fill at
   cursor*) → the interior is flood-filled with the current label.
   - Refused with a status-bar message if the flooded region touches the
     image border (boundary is not closed).
4. Repeat for every cell on the tile.
5. Press **N** (Save & next) to commit and advance, or **S** to save without
   advancing.

Alternative paths:

- napari's built-in **fill mode** (press **5** to switch the Labels layer
  into fill mode, then single-click inside a boundary) is fully supported.
- A **double-click** in paint mode also attempts the same flood-fill (this
  is best-effort — paint mode also paints on click, so prefer **G**).
- The eraser (**6**) corrects mistakes. Leave a 1-pixel gap between
  touching cells so they remain separate instances.

### Dock widget / shortcuts

| Action                                | Button                | Key |
| ------------------------------------- | --------------------- | --- |
| New cell label (= max + 1)            | New cell label (C)    |  C  |
| Decrement selected label              | Prev label (V)        |  V  |
| Fill background region at cursor      | Fill at cursor (G)    |  G  |
| Save current tile (status = in\_progress) | Save (S)          |  S  |
| Save current tile + advance (completed)   | Save & Next (N)   |  N  |
| Mark current tile completed (no advance)  | Mark complete     |  —  |
| Previous tile                         | Prev tile (P)         |  P  |
| Next tile (no save)                   | Next tile (no save)   |  —  |
| Skip current tile (status = skipped)  | Skip (K)              |  K  |

Progress is written to `logs/annotation_log.csv` after every save.

### CLI flags

```
--annotator NAME       Recorded in the log.
--start-index N        Force start at row N of tile_coordinates.csv.
--input-dir PATH       Override DAPI tile location.
--tile-csv PATH        Override tile manifest CSV.
--output-dir PATH      Override mask output dir (default: ./annotations).
--log-path PATH        Override annotation log CSV (default: ./logs/annotation_log.csv).
--dry-run              Print resolved config and exit (no GUI).
```

---

## QC

Before handing off, run:

```bash
cell-annotate-qc
```

Prints per-mask instance count and area range, and flags:

- non-contiguous label IDs (same ID used on two disconnected blobs),
- tiny labels (< 4 px, likely paint slips).

Exit code is non-zero if any issue is found.

---

## Handoff to the segmentation developer

The masks under `annotations/` constitute the benchmark.

1. Copy or symlink each `*_masks.tif` next to its matching DAPI tile, **or**
   pass `--dir <dir> --mask_filter _masks` directly to the Cellpose CLI.
2. For parameter optimization, run inference with candidate parameters and
   compare to ground-truth masks using
   `cellpose.metrics.aggregated_jaccard_index` and
   `cellpose.metrics.average_precision` at IoU thresholds
   `[0.5, 0.75, 0.9]`.
3. For fine-tuning, the same files work as training labels:
   `python -m cellpose --train --dir <dir> --mask_filter _masks ...`.

Use the `dapi_p99` / `cyto_p99` columns of `tile_coordinates.csv` if
intensity normalization at eval time needs to match what was used during
annotation.

---

## Reproducibility

- Python: 3.10–3.12 (tested on 3.12.5 on macOS arm64).
- Pinned runtime deps: `requirements.txt`.
- Annotation log captures annotator + UTC timestamp for every saved tile.
- All mask writes are atomic (tempfile + `os.replace`).

---

## Tests

```bash
pytest
```

Covers I/O round-trip (including uint16 → uint32 promotion), log state
transitions, and config defaults. The napari GUI is not exercised in tests.

---

## Project layout

```
.
├── pyproject.toml
├── requirements.txt
├── README.md
├── LICENSE
├── src/cell_annotation/
│   ├── __init__.py
│   ├── config.py        # paths, MASK_SUFFIX, Config dataclass
│   ├── io.py            # tile/mask TIFF I/O, atomic writes
│   ├── log.py           # CSV annotation log
│   ├── viewer.py        # napari viewer + dock widget
│   ├── cli.py           # `cell-annotate` entry point
│   └── qc.py            # `cell-annotate-qc` entry point
├── tests/
│   ├── test_io.py
│   ├── test_log.py
│   └── test_config.py
├── annotations/         # outputs (gitignored)
└── logs/                # annotation log CSV (gitignored)
```

`annotations/` and `logs/` are produced by the tool and are intentionally
gitignored — annotation outputs live on shared storage, not in the
repository.
