import numpy as np

from cell_annotation import io as cio


def test_save_and_load_labels_roundtrip(tmp_path):
    labels = np.zeros((32, 32), dtype=np.uint16)
    labels[2:10, 2:10] = 1
    labels[15:25, 15:25] = 2
    labels[28:30, 28:30] = 3
    out = cio.save_labels(labels, tmp_path / "x_masks.tif")
    assert out.exists()
    loaded = cio.load_labels(out)
    assert loaded.dtype in (np.uint16, np.uint32)
    assert loaded.shape == labels.shape
    assert set(np.unique(loaded).tolist()) == {0, 1, 2, 3}


def test_save_labels_promotes_to_uint32_on_overflow(tmp_path):
    labels = np.zeros((4, 4), dtype=np.uint32)
    labels[0, 0] = np.iinfo(np.uint16).max + 5
    out = cio.save_labels(labels, tmp_path / "big_masks.tif")
    loaded = cio.load_labels(out)
    assert int(loaded.max()) == int(labels.max())
