"""
HERA Strip - A tool for simulating and visualizing diffuse sky models for HERA observations.
"""

__version__ = "1.0.0"

from .sky_model import (
    SkyMapGenerator,
    SkyH5MapGenerator,
    PointSourceCatalog,
    load_skyh5_file,
    SKY_MODELS,
)
from .simulation import (
    HeraStripSimulator,
    calculate_hera_fov_radius,
    HERA_DISH_DIAMETER,
    HERA_BEAM_COEFFICIENT,
)
from .plotting import Plotter
