import numpy as np
import pygdsm
import healpy as hp
import matplotlib.pyplot as plt

# Available sky models and their frequency ranges
SKY_MODELS = {
    "gsm2008": {
        "class": pygdsm.GlobalSkyModel,
        "freq_range": (10, 100000),  # 10 MHz - 100 GHz
        "description": "Global Sky Model 2008 (Oliveira-Costa et al.)"
    },
    "gsm2016": {
        "class": pygdsm.GlobalSkyModel16,
        "freq_range": (10, 5000000),  # 10 MHz - 5 THz
        "description": "Global Sky Model 2016 (Zheng et al.)"
    },
    "lfss": {
        "class": pygdsm.LowFrequencySkyModel,
        "freq_range": (10, 408),  # 10 - 408 MHz
        "description": "LWA1 Low Frequency Sky Survey (Dowell et al.)"
    },
    "haslam": {
        "class": pygdsm.HaslamSkyModel,
        "freq_range": (10, 100000),  # Scaled from 408 MHz
        "description": "Haslam 408 MHz map with spectral scaling"
    },
}


class SkyMapGenerator:
    def __init__(self, frequency=76, model="gsm2008"):
        self.frequency = frequency
        self.model_name = model.lower()

        if self.model_name not in SKY_MODELS:
            raise ValueError(
                f"Unknown model '{model}'. Available: {list(SKY_MODELS.keys())}"
            )

        model_info = SKY_MODELS[self.model_name]
        freq_min, freq_max = model_info["freq_range"]

        if not (freq_min <= frequency <= freq_max):
            raise ValueError(
                f"Frequency {frequency} MHz out of range for {model}. "
                f"Valid range: {freq_min}-{freq_max} MHz"
            )

        self.gsm = model_info["class"](freq_unit="MHz")

    def generate_projected_map(self, nside=1024):
        # Generate the Global Sky Model at the specified frequency
        sky_map = self.gsm.generate(self.frequency)

        # Resample to desired nside for consistent resolution
        current_nside = hp.npix2nside(len(sky_map))
        if current_nside != nside:
            sky_map = hp.ud_grade(sky_map, nside)

        # Convert from Galactic to Equatorial coordinates
        rotator = hp.Rotator(coord=["G", "C"])
        equatorial = rotator.rotate_map_pixel(sky_map)

        # Project the equatorial map into a 2D Cartesian grid
        # xsize controls horizontal resolution (4K for high detail)
        projected_map = hp.cartview(
            equatorial,
            xsize=4000,
            norm="hist",
            coord="C",
            flip="astro",
            title="",
            unit="Brightness",
            return_projected_map=True,
            notext=True,
        )
        plt.close()
        return projected_map


def load_skyh5_file(skyh5_path):
    """
    Load a skyh5 file and return appropriate generator based on component type.

    Parameters
    ----------
    skyh5_path : str
        Path to the .skyh5 file

    Returns
    -------
    tuple
        (sky_model, component_type) where sky_model is pyradiosky SkyModel
    """
    try:
        from pyradiosky import SkyModel
    except ImportError:
        raise ImportError(
            "pyradiosky is required for skyh5 support. "
            "Install with: pip install pyradiosky"
        )

    sky_model = SkyModel.from_file(skyh5_path)
    return sky_model, sky_model.component_type


class PointSourceCatalog:
    """Load point source catalogs from pyradiosky .skyh5 files."""

    def __init__(self, skyh5_path, frequency=None, freq_index=None):
        """
        Initialize from a skyh5 file containing point sources.

        Parameters
        ----------
        skyh5_path : str
            Path to the .skyh5 file
        frequency : float, optional
            Frequency in MHz to select (finds closest match)
        freq_index : int, optional
            Direct index into frequency array (overrides frequency)
        """
        try:
            from pyradiosky import SkyModel
        except ImportError:
            raise ImportError(
                "pyradiosky is required for skyh5 support. "
                "Install with: pip install pyradiosky"
            )

        self.skyh5_path = skyh5_path
        self.sky_model = SkyModel.from_file(skyh5_path)

        if self.sky_model.component_type != "point":
            raise ValueError(
                f"Expected point source catalog, "
                f"got component_type='{self.sky_model.component_type}'"
            )

        # Get frequency array and select frequency
        self.freq_array = self.sky_model.freq_array.to("MHz").value
        self.nfreqs = len(self.freq_array)

        if freq_index is not None:
            if not (0 <= freq_index < self.nfreqs):
                raise ValueError(
                    f"freq_index {freq_index} out of range [0, {self.nfreqs})"
                )
            self.freq_idx = freq_index
        elif frequency is not None:
            self.freq_idx = np.argmin(np.abs(self.freq_array - frequency))
        else:
            self.freq_idx = 0

        self.frequency = self.freq_array[self.freq_idx]
        self.n_sources = self.sky_model.Ncomponents

    def get_available_frequencies(self):
        """Return array of available frequencies in MHz."""
        return self.freq_array

    def get_sources(self, min_flux_jy=None, max_sources=None):
        """
        Get point sources as a list of dicts for use with Plotter.

        Parameters
        ----------
        min_flux_jy : float, optional
            Minimum flux in Jy to include. If None, auto-selects threshold
            to limit to ~1000 brightest sources.
        max_sources : int, optional
            Maximum number of sources to return (brightest first).
            Default: 1000

        Returns
        -------
        list of dict
            Each dict has 'coords' (SkyCoord) and 'flux' (float in Jy)
        """
        from astropy.coordinates import SkyCoord

        if max_sources is None:
            max_sources = 1000

        # Get all fluxes first to determine threshold
        all_fluxes = self.sky_model.stokes[0, self.freq_idx, :].to("Jy").value

        # Determine flux threshold
        if min_flux_jy is None:
            # Auto-select: get threshold for top N sources
            if self.n_sources > max_sources:
                # Sort descending and get the flux at max_sources position
                sorted_fluxes = np.sort(all_fluxes)[::-1]
                min_flux_jy = sorted_fluxes[max_sources - 1]
            else:
                min_flux_jy = 0.0

        # Filter sources by flux
        mask = all_fluxes >= min_flux_jy
        indices = np.where(mask)[0]

        # Sort by flux (brightest first) and limit
        flux_order = np.argsort(all_fluxes[indices])[::-1]
        indices = indices[flux_order][:max_sources]

        sources = []
        for i in indices:
            ra = self.sky_model.ra[i]
            dec = self.sky_model.dec[i]
            flux = all_fluxes[i]

            sources.append({
                "coords": SkyCoord(ra=ra, dec=dec),
                "flux": flux
            })

        return sources


class SkyH5MapGenerator:
    """Load and project sky maps from pyradiosky .skyh5 files."""

    def __init__(self, skyh5_path, frequency=None, freq_index=None):
        """
        Initialize from a skyh5 file.

        Parameters
        ----------
        skyh5_path : str
            Path to the .skyh5 file
        frequency : float, optional
            Frequency in MHz to select (finds closest match)
        freq_index : int, optional
            Direct index into frequency array (overrides frequency)
        """
        try:
            from pyradiosky import SkyModel
        except ImportError:
            raise ImportError(
                "pyradiosky is required for skyh5 support. "
                "Install with: pip install pyradiosky"
            )

        self.skyh5_path = skyh5_path
        self.sky_model = SkyModel.from_file(skyh5_path)

        # Validate it's a healpix map
        if self.sky_model.component_type != "healpix":
            raise ValueError(
                f"SkyH5 file must contain healpix data, "
                f"got component_type='{self.sky_model.component_type}'. "
                f"For point source catalogs, use PointSourceCatalog class."
            )

        # Get frequency array and select frequency
        self.freq_array = self.sky_model.freq_array.to("MHz").value
        self.nfreqs = len(self.freq_array)

        if freq_index is not None:
            if not (0 <= freq_index < self.nfreqs):
                raise ValueError(
                    f"freq_index {freq_index} out of range [0, {self.nfreqs})"
                )
            self.freq_idx = freq_index
        elif frequency is not None:
            # Find closest frequency
            self.freq_idx = np.argmin(np.abs(self.freq_array - frequency))
        else:
            # Default to first frequency
            self.freq_idx = 0

        self.frequency = self.freq_array[self.freq_idx]

        # Store healpix parameters
        self.nside = self.sky_model.nside
        self.hpx_inds = self.sky_model.hpx_inds
        self.hpx_order = self.sky_model.hpx_order
        self.frame = str(self.sky_model.frame)

    def get_available_frequencies(self):
        """Return array of available frequencies in MHz."""
        return self.freq_array

    def _reconstruct_healpix_map(self):
        """Reconstruct full healpix map from sparse skyh5 data."""
        npix = hp.nside2npix(self.nside)

        # Initialize map with NaN (or UNSEEN)
        full_map = np.full(npix, hp.UNSEEN)

        # Get Stokes I data at selected frequency
        # stokes shape is (4, Nfreqs, Ncomponents) for [I, Q, U, V]
        stokes_i = self.sky_model.stokes[0, self.freq_idx, :].value

        # Fill in the pixels we have data for
        full_map[self.hpx_inds] = stokes_i

        # Convert ordering if needed (healpy expects RING by default)
        if self.hpx_order.lower() == "nested":
            full_map = hp.reorder(full_map, n2r=True)

        return full_map

    def generate_projected_map(self):
        """Generate projected 2D map from skyh5 data."""
        # Reconstruct the full healpix map
        sky_map = self._reconstruct_healpix_map()

        # Determine if coordinate transformation is needed
        # pyradiosky skyh5 files are typically in ICRS (equatorial)
        frame_lower = self.frame.lower()

        if "galactic" in frame_lower:
            # Convert from Galactic to Equatorial
            rotator = hp.Rotator(coord=["G", "C"])
            equatorial = rotator.rotate_map_pixel(sky_map)
        elif "icrs" in frame_lower or "fk5" in frame_lower or "equatorial" in frame_lower:
            # Already in equatorial coordinates
            equatorial = sky_map
        else:
            # Unknown frame, assume equatorial
            print(f"Warning: Unknown coordinate frame '{self.frame}', assuming equatorial")
            equatorial = sky_map

        # Project the equatorial map into a 2D Cartesian grid
        # xsize controls horizontal resolution (4K for high detail)
        projected_map = hp.cartview(
            equatorial,
            xsize=4000,
            norm="hist",
            coord="C",
            flip="astro",
            title="",
            unit="Brightness",
            return_projected_map=True,
            notext=True,
        )
        plt.close()
        return projected_map
