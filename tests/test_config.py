from pathlib import Path

from cell_annotation.config import Config, DEFAULT_INPUT_DIR, MASK_SUFFIX


def test_default_config_paths():
    cfg = Config()
    assert cfg.input_dir == DEFAULT_INPUT_DIR
    assert cfg.tile_csv == DEFAULT_INPUT_DIR / "tile_coordinates.csv"
    assert cfg.output_dir.name == "annotations"
    assert cfg.log_path.name == "annotation_log.csv"


def test_mask_path_for_uses_cellpose_suffix(tmp_path):
    cfg = Config(output_dir=tmp_path)
    p = cfg.mask_path_for("MS00001747_DAPI_tile000_x26496_y27648_size512.tif")
    assert p.name.endswith(MASK_SUFFIX)
    assert p.parent == tmp_path
    assert "tile000" in p.name


def test_override_paths(tmp_path):
    cfg = Config(input_dir=tmp_path, output_dir=tmp_path / "out", log_path=tmp_path / "l.csv")
    assert cfg.tile_csv == tmp_path / "tile_coordinates.csv"
    cfg.ensure_dirs()
    assert (tmp_path / "out").is_dir()
