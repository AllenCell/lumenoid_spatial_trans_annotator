"""Napari-based cell boundary annotation tool.

Produces Cellpose-compatible instance-label masks for benchmarking and
parameter optimization.
"""

from cell_annotation.viewer import launch_annotator

__all__ = ["launch_annotator", "__version__"]
__version__ = "0.1.0"
