"""
HERA Strip - A tool for simulating and visualizing diffuse sky models for HERA observations.
"""

__version__ = "1.0.1"

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
    SPEED_OF_LIGHT,
)
from .plotting import Plotter
from .beam import BeamProcessor

__all__ = [
    # Version
    "__version__",
    # Main simulator
    "HeraStripSimulator",
    # Sky models
    "SkyMapGenerator",
    "SkyH5MapGenerator",
    "PointSourceCatalog",
    "load_skyh5_file",
    "SKY_MODELS",
    # Beam processing
    "BeamProcessor",
    # Plotting
    "Plotter",
    # Constants
    "HERA_DISH_DIAMETER",
    "HERA_BEAM_COEFFICIENT",
    "SPEED_OF_LIGHT",
    # Utilities
    "calculate_hera_fov_radius",
]
