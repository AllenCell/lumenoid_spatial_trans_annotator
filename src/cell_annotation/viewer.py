"""Napari viewer and dock widget for cell boundary annotation."""

from __future__ import annotations

import numpy as np
from skimage.segmentation import flood

from cell_annotation import io as cio
from cell_annotation import log as clog
from cell_annotation.config import Config

LABELS_LAYER_NAME = "cell_labels"
IMAGE_LAYER_NAME = "dapi"


def _contrast_limits(image: np.ndarray, p99: float | None) -> tuple[float, float]:
    lo = float(image.min())
    if p99 is not None and p99 > 0:
        hi = float(p99) * 1.1
    else:
        hi = float(np.percentile(image, 99)) * 1.1
    if hi <= lo:
        hi = lo + 1.0
    return lo, hi


def _count_instances(labels: np.ndarray) -> int:
    if labels.size == 0:
        return 0
    unique = np.unique(labels)
    return int((unique > 0).sum())


def launch_annotator(
    cfg: Config | None = None,
    *,
    start_index: int | None = None,
    annotator: str | None = None,
) -> None:
    """Launch napari with a dock widget driving the annotation workflow."""
    import napari  # imported lazily so non-GUI tests don't need Qt
    from magicgui.widgets import Container, Label, PushButton

    cfg = cfg or Config()
    cfg.ensure_dirs()
    tiles = cio.list_tiles(cfg.tile_csv, cfg.input_dir)
    if not tiles:
        raise RuntimeError(f"No tiles listed in {cfg.tile_csv}")
    clog.init_log(cfg.log_path, tiles)

    if start_index is None:
        start_index = clog.first_pending_index(cfg.log_path)
    start_index = max(0, min(start_index, len(tiles) - 1))

    state = {"idx": start_index}

    viewer = napari.Viewer(title="Cell boundary annotation")

    # --- widgets ----------------------------------------------------------
    progress_label = Label(value="")
    file_label = Label(value="")
    annotator_label = Label(value=f"Annotator: {annotator or '<unset>'}")

    btn_new_cell = PushButton(text="New cell label (C)")
    btn_dec_cell = PushButton(text="Prev label (V)")
    btn_fill = PushButton(text="Fill at cursor (G)")
    btn_prev = PushButton(text="Prev tile (P)")
    btn_save = PushButton(text="Save (S)")
    btn_save_next = PushButton(text="Save & Next (N)")
    btn_complete = PushButton(text="Mark complete")
    btn_skip = PushButton(text="Skip (K)")
    btn_next = PushButton(text="Next tile (no save)")
    selected_label_display = Label(value="Selected label: 1")
    hint = Label(
        value=(
            "Workflow:\n"
            " 1. Press C to start a new cell label.\n"
            " 2. Paint a closed boundary.\n"
            " 3. Hover the cursor inside the boundary and press G\n"
            "    (or click 'Fill at cursor') to flood-fill the interior.\n"
            "Tip: napari's built-in fill mode (press 5) also works:\n"
            " switch to fill mode then click inside the boundary."
        )
    )

    container = Container(
        widgets=[
            annotator_label,
            progress_label,
            file_label,
            selected_label_display,
            btn_new_cell,
            btn_dec_cell,
            btn_fill,
            btn_prev,
            btn_save,
            btn_save_next,
            btn_complete,
            btn_skip,
            btn_next,
            hint,
        ],
        labels=False,
    )

    def _refresh_labels() -> None:
        tile = tiles[state["idx"]]
        progress_label.value = f"Tile {state['idx'] + 1} / {len(tiles)}  (id={tile.tile_id})"
        file_label.value = tile.filename

    def _load_current() -> None:
        tile = tiles[state["idx"]]
        image = cio.load_tile(tile.path)
        clo, chi = _contrast_limits(image, tile.dapi_p99)
        mask_path = cfg.mask_path_for(tile.filename)
        if mask_path.exists():
            labels = cio.load_labels(mask_path).astype(np.uint16, copy=False)
        else:
            labels = np.zeros(image.shape, dtype=np.uint16)

        # Replace layers (clear then add to keep order predictable).
        for name in (LABELS_LAYER_NAME, IMAGE_LAYER_NAME):
            if name in viewer.layers:
                viewer.layers.remove(name)
        viewer.add_image(
            image,
            name=IMAGE_LAYER_NAME,
            colormap="gray",
            contrast_limits=(clo, chi),
        )
        labels_layer = viewer.add_labels(labels, name=LABELS_LAYER_NAME)
        # Start with brush selected and label id = next free.
        next_id = int(labels.max()) + 1 if labels.max() > 0 else 1
        labels_layer.selected_label = next_id
        labels_layer.mode = "paint"
        labels_layer.brush_size = 3
        # Attach double-click flood-fill to the new layer (bonus path).
        if _fill_on_double_click not in labels_layer.mouse_double_click_callbacks:
            labels_layer.mouse_double_click_callbacks.append(_fill_on_double_click)
        # Keep the dock display in sync whenever the user changes selected_label
        # via the layer controls.
        labels_layer.events.selected_label.connect(lambda *_: _update_label_display())
        viewer.reset_view()
        _refresh_labels()
        _update_label_display()

        # Mark in_progress on load (only if currently pending).
        df = clog.load_log(cfg.log_path)
        row = df.loc[df["tile_id"] == tile.tile_id]
        if not row.empty and row.iloc[0]["status"] == clog.STATUS_PENDING:
            clog.update_status(
                cfg.log_path,
                tile.tile_id,
                status=clog.STATUS_IN_PROGRESS,
                annotator=annotator,
            )

    def _current_labels_array() -> np.ndarray:
        layer = viewer.layers[LABELS_LAYER_NAME]
        return np.asarray(layer.data)

    def _save(mark_completed: bool = False) -> None:
        tile = tiles[state["idx"]]
        labels = _current_labels_array()
        path = cfg.mask_path_for(tile.filename)
        cio.save_labels(labels, path)
        n = _count_instances(labels)
        status = clog.STATUS_COMPLETED if mark_completed else clog.STATUS_IN_PROGRESS
        clog.update_status(
            cfg.log_path,
            tile.tile_id,
            status=status,
            annotator=annotator,
            n_cells=n,
        )
        viewer.status = f"Saved {path.name}  ({n} cells, status={status})"

    def _go(delta: int) -> None:
        new_idx = state["idx"] + delta
        if 0 <= new_idx < len(tiles):
            state["idx"] = new_idx
            _load_current()
        else:
            viewer.status = "At edge of tile list"

    def _update_label_display() -> None:
        if LABELS_LAYER_NAME in viewer.layers:
            selected_label_display.value = (
                f"Selected label: {int(viewer.layers[LABELS_LAYER_NAME].selected_label)}"
            )

    def _increment_label(delta: int = 1) -> None:
        if LABELS_LAYER_NAME not in viewer.layers:
            return
        layer = viewer.layers[LABELS_LAYER_NAME]
        new_val = max(1, int(layer.selected_label) + delta)
        layer.selected_label = new_val
        viewer.status = f"Selected label = {new_val}"
        _update_label_display()

    def _next_free_label() -> None:
        if LABELS_LAYER_NAME not in viewer.layers:
            return
        layer = viewer.layers[LABELS_LAYER_NAME]
        data = np.asarray(layer.data)
        new_val = int(data.max()) + 1 if data.size and data.max() > 0 else 1
        layer.selected_label = new_val
        viewer.status = f"New cell -> label {new_val}"
        _update_label_display()

    def _flood_fill_at(coords: tuple[int, int]) -> None:
        """Flood-fill the 0-valued region containing `coords` with the current label.

        Safety: refuses to fill if the flooded region touches the image border
        (means the drawn boundary is not closed).
        """
        if LABELS_LAYER_NAME not in viewer.layers:
            return
        layer = viewer.layers[LABELS_LAYER_NAME]
        data = np.asarray(layer.data)
        if len(coords) != 2 or any(
            c < 0 or c >= s for c, s in zip(coords, data.shape)
        ):
            viewer.status = "Fill: cursor outside image."
            return
        if int(data[coords]) != 0:
            viewer.status = (
                f"Fill: cursor is on label {int(data[coords])}, not background."
            )
            return
        region = flood(data, seed_point=coords, connectivity=1, tolerance=0)
        if (
            region[0, :].any()
            or region[-1, :].any()
            or region[:, 0].any()
            or region[:, -1].any()
        ):
            viewer.status = (
                "Fill refused: region reaches image border (boundary not closed)."
            )
            return
        new_label = int(layer.selected_label)
        new_data = data.copy()
        new_data[region] = new_label
        layer.data = new_data
        layer.refresh()
        viewer.status = f"Filled {int(region.sum())} px with label {new_label}"

    def _fill_at_cursor() -> None:
        """Use the napari cursor position to flood-fill the underlying region."""
        if LABELS_LAYER_NAME not in viewer.layers:
            return
        layer = viewer.layers[LABELS_LAYER_NAME]
        try:
            pos = layer.world_to_data(viewer.cursor.position)
        except Exception as exc:
            viewer.status = f"Fill: could not read cursor ({exc!r})."
            return
        coords = tuple(int(round(c)) for c in pos)
        if len(coords) > 2:
            coords = coords[-2:]
        _flood_fill_at(coords)

    def _fill_on_double_click(layer, event):
        """Bonus: double-click in paint/fill mode to flood-fill.

        Paint mode also paints on click, so this only succeeds when the
        double-click lands on a background pixel inside a closed boundary.
        Prefer the G shortcut, which is independent of the click pipeline.
        """
        try:
            pos = layer.world_to_data(event.position)
        except Exception:
            return
        coords = tuple(int(round(c)) for c in pos)
        if len(coords) > 2:
            coords = coords[-2:]
        _flood_fill_at(coords)

    def _skip() -> None:
        tile = tiles[state["idx"]]
        clog.update_status(
            cfg.log_path,
            tile.tile_id,
            status=clog.STATUS_SKIPPED,
            annotator=annotator,
        )
        _go(1)

    btn_new_cell.clicked.connect(_next_free_label)
    btn_dec_cell.clicked.connect(lambda: _increment_label(-1))
    btn_fill.clicked.connect(_fill_at_cursor)
    btn_prev.clicked.connect(lambda: _go(-1))
    btn_next.clicked.connect(lambda: _go(1))
    btn_save.clicked.connect(lambda: _save(False))
    btn_save_next.clicked.connect(lambda: (_save(True), _go(1)))
    btn_complete.clicked.connect(lambda: _save(True))
    btn_skip.clicked.connect(_skip)

    viewer.window.add_dock_widget(container, name="Annotation", area="right")

    # --- keyboard shortcuts ----------------------------------------------
    @viewer.bind_key("S", overwrite=True)
    def _kb_save(_v):
        _save(False)

    @viewer.bind_key("N", overwrite=True)
    def _kb_save_next(_v):
        _save(True)
        _go(1)

    @viewer.bind_key("P", overwrite=True)
    def _kb_prev(_v):
        _go(-1)

    @viewer.bind_key("K", overwrite=True)
    def _kb_skip(_v):
        _skip()

    # Label increment / new-cell / fill: letter shortcuts are reliable;
    # symbol keys (+/=/-) are unreliable in napari 0.7 due to the app-model
    # key system and OS-level modifier handling.
    @viewer.bind_key("C", overwrite=True)
    def _kb_new_cell(_v):
        _next_free_label()

    @viewer.bind_key("V", overwrite=True)
    def _kb_dec(_v):
        _increment_label(-1)

    @viewer.bind_key("G", overwrite=True)
    def _kb_fill(_v):
        _fill_at_cursor()

    _load_current()
    napari.run()
