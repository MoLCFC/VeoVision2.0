"""Compatibility shim — implementation lives in `veovision.annotators_soccer`."""
from veovision.annotators_soccer import (
    draw_pitch,
    draw_points_on_pitch,
    draw_paths_on_pitch,
    draw_pitch_voronoi_diagram,
)

__all__ = [
    "draw_pitch",
    "draw_points_on_pitch",
    "draw_paths_on_pitch",
    "draw_pitch_voronoi_diagram",
]
