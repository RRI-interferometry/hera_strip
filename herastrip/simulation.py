import numpy as np
from astropy.coordinates import SkyCoord, AltAz
from astropy.time import TimeDelta
import astropy.units as au

from .sky_model import SkyMapGenerator, SkyH5MapGenerator, PointSourceCatalog, load_skyh5_file
from .plotting import Plotter


# HERA dish parameters
# Reference: https://reionization.org/, Fagnoni et al. 2021
HERA_DISH_DIAMETER = 14.0  # meters
SPEED_OF_LIGHT = 299.792458  # m/s per MHz (c in m/s / 1e6)

# Beam coefficient k: θ_FWHM = k × λ / D
# For uniformly illuminated circular aperture: k ≈ 1.02
# For tapered illumination (typical): k ≈ 1.15-1.22
# HERA measured: ~10° FWHM at 150 MHz → k ≈ 1.17
# Using k = 1.17 calibrated to match measured beam
HERA_BEAM_COEFFICIENT = 1.17


def calculate_hera_fov_radius(frequency_mhz, dish_diameter=HERA_DISH_DIAMETER):
    """
    Calculate HERA field of view radius based on dish diameter and frequency.

    Uses the diffraction limit for a parabolic dish antenna:
        θ_FWHM = k × λ / D

    Where:
        k = beam coefficient (~1.17 for HERA, calibrated to measured 10° at 150 MHz)
        λ = wavelength = c / frequency
        D = dish diameter (14m for HERA)

    Reference: Fagnoni et al. 2021, measured FWHM ~10° at 150 MHz

    Parameters
    ----------
    frequency_mhz : float
        Observing frequency in MHz
    dish_diameter : float, optional
        Dish diameter in meters (default: 14m for HERA)

    Returns
    -------
    float
        FOV radius in degrees (FWHM / 2)
    """
    # Calculate wavelength in meters
    wavelength_m = SPEED_OF_LIGHT / frequency_mhz

    # Calculate FWHM using diffraction limit: θ = k × λ / D
    fwhm_rad = HERA_BEAM_COEFFICIENT * wavelength_m / dish_diameter
    fwhm_deg = np.degrees(fwhm_rad)

    return fwhm_deg / 2.0


class HeraStripSimulator:
    def __init__(
        self,
        location,
        obstime_start=None,
        total_seconds=None,
        frequency=76,
        fov_radius_deg=None,
        point_sources=None,
        model="gsm2008",
        skyh5_path=None,
        max_sources=1000,
        background_mode="gsm",
        color_scale="log",
        use_lst=False,
        lst_range=None,
        beam_path=None,
        beam_vmin=-40,
        beam_vmax=0,
        beam_lst=None,
    ):
        self.location = location
        self.obstime_start = obstime_start
        self.total_seconds = total_seconds
        self.frequency = frequency
        self.point_sources = point_sources
        self.model = model
        self.skyh5_path = skyh5_path
        self.max_sources = max_sources
        self.background_mode = background_mode  # "gsm", "none", or "reference"
        self.color_scale = color_scale
        self.use_lst = use_lst
        self.lst_range = lst_range  # Alternative to obstime_start/total_seconds
        self.sky_map_gen = None  # Will be set below if background is used
        self.beam_path = beam_path
        self.beam_vmin = beam_vmin
        self.beam_vmax = beam_vmax
        self.beam_lst = beam_lst
        self.beam_processor = None  # Will be set below if beam is used

        # Handle skyh5 file if provided
        if self.skyh5_path is not None:
            sky_model, component_type = load_skyh5_file(self.skyh5_path)

            if component_type == "healpix":
                # Use healpix map as background
                self.sky_map_gen = SkyH5MapGenerator(
                    skyh5_path=self.skyh5_path,
                    frequency=self.frequency
                )
                self.frequency = self.sky_map_gen.frequency
                print(f"Using skyh5 healpix map: {self.skyh5_path}")
                print(f"Selected frequency: {self.frequency:.2f} MHz")

            elif component_type == "point":
                # Point source catalog
                catalog = PointSourceCatalog(
                    skyh5_path=self.skyh5_path,
                    frequency=self.frequency
                )
                self.frequency = catalog.frequency

                # Get brightest sources
                self.point_sources = catalog.get_sources(max_sources=self.max_sources)
                n_displayed = len(self.point_sources)

                print(f"Using skyh5 point source catalog: {self.skyh5_path}")
                print(f"Total sources: {catalog.n_sources}, displaying brightest {n_displayed}")
                print(f"Frequency: {self.frequency:.2f} MHz")

                if self.background_mode == "none":
                    # No background - will use blank map
                    self.sky_map_gen = None
                    print("Background: None (sources only)")
                elif self.background_mode == "reference":
                    # GSM2008 background as visual reference (no hover, source colorbar)
                    self.sky_map_gen = SkyMapGenerator(
                        frequency=self.frequency,
                        model="gsm2008"
                    )
                    print("Background: GSM2008 (reference)")
                else:
                    # Full GSM background (default)
                    self.sky_map_gen = SkyMapGenerator(
                        frequency=self.frequency,
                        model=self.model
                    )
                    print(f"Background model: {self.model}")

            else:
                raise ValueError(f"Unknown skyh5 component_type: {component_type}")
        else:
            # Use pygdsm diffuse model
            self.sky_map_gen = SkyMapGenerator(
                frequency=self.frequency,
                model=self.model
            )

        # Calculate FOV radius from frequency if not provided
        if fov_radius_deg is None:
            self.fov_radius_deg = calculate_hera_fov_radius(self.frequency)
            fwhm = self.fov_radius_deg * 2
            print(f"HERA beam at {self.frequency:.1f} MHz: FWHM = {fwhm:.1f}°, radius = {self.fov_radius_deg:.1f}°")
        else:
            self.fov_radius_deg = fov_radius_deg

        # Load beam file if provided
        if self.beam_path is not None:
            from .beam import BeamProcessor
            self.beam_processor = BeamProcessor(
                beam_path=self.beam_path,
                frequency_mhz=self.frequency
            )

        self.plotter = Plotter(
            fov_radius_deg=self.fov_radius_deg,
            point_sources=self.point_sources,
            location=self.location,
            color_scale=self.color_scale,
            use_lst=self.use_lst,
            background_mode=self.background_mode,
            beam_processor=self.beam_processor,
            beam_vmin=self.beam_vmin,
            beam_vmax=self.beam_vmax,
            beam_lst=self.beam_lst,
        )

    def _get_zenith_ra(self, obstime):
        """Calculate zenith RA at a given observation time."""
        zenith = SkyCoord(
            alt=90 * au.deg,
            az=0 * au.deg,
            frame=AltAz(obstime=obstime, location=self.location)
        )
        zenith_radec = zenith.transform_to("icrs")
        return zenith_radec.ra.deg

    def _lst_to_ra(self, lst_hours):
        """Convert LST in hours to RA in degrees.

        LST (hours) * 15 = RA (degrees)
        """
        return lst_hours * 15.0

    def run_simulation(self, save_simulation_data=False, folder_path=None):
        """Run simulation and create a single plot showing the observable strip."""
        # Generate the projected sky map (or None if no background)
        if self.sky_map_gen is not None:
            projected_map = self.sky_map_gen.generate_projected_map()
        else:
            projected_map = None

        # Determine RA range based on mode
        if self.lst_range is not None:
            # LST range mode: convert LST to RA
            lst_start, lst_end = self.lst_range
            ra_start = self._lst_to_ra(lst_start)
            ra_end = self._lst_to_ra(lst_end)
            obstime_start = None
            obstime_end = None
        else:
            # Time-based mode: calculate RA from observation times
            obstime_end = self.obstime_start + TimeDelta(self.total_seconds, format="sec")
            ra_start = self._get_zenith_ra(self.obstime_start)
            ra_end = self._get_zenith_ra(obstime_end)
            obstime_start = self.obstime_start

        # Create a single plot showing the strip for the entire duration
        plot = self.plotter.create_strip_plot(
            projected_map=projected_map,
            obstime_start=obstime_start,
            obstime_end=obstime_end,
            ra_start=ra_start,
            ra_end=ra_end
        )

        # Save if requested
        if save_simulation_data and folder_path:
            self.plotter.save_plot(plot, folder_path)

        # Display the plot
        self.plotter.show_plot(plot)
