"""
Beam loading and processing for HERA strip visualization.

This module handles loading antenna beam patterns from FITS files
and transforming them to RA/Dec coordinates for overlay on sky maps.
"""

import numpy as np
from scipy.interpolate import RegularGridInterpolator
from astropy.coordinates import SkyCoord, AltAz, EarthLocation
from astropy.time import Time
import astropy.units as u


class BeamProcessor:
    """Load and process antenna beam patterns for visualization."""

    def __init__(self, beam_path, frequency_mhz=None):
        """
        Initialize beam processor from a FITS file.

        Parameters
        ----------
        beam_path : str
            Path to beam FITS file (pyuvdata UVBeam format)
        frequency_mhz : float, optional
            Target frequency in MHz. If None, uses first available frequency.
        """
        try:
            from pyuvdata import UVBeam
        except ImportError:
            raise ImportError(
                "pyuvdata is required for beam support. "
                "Install with: pip install pyuvdata"
            )

        self.beam_path = beam_path
        self.beam = UVBeam()
        self.beam.read_beamfits(beam_path)

        # Get frequency array and select frequency
        self.freq_array_mhz = self.beam.freq_array / 1e6

        if frequency_mhz is not None:
            self.freq_idx = np.argmin(np.abs(self.freq_array_mhz - frequency_mhz))
        else:
            self.freq_idx = 0

        self.frequency = self.freq_array_mhz[self.freq_idx]

        # Extract axis arrays (azimuth and zenith angle in radians)
        self.az_array = self.beam.axis1_array  # azimuth: 0 to 2*pi
        self.za_array = self.beam.axis2_array  # zenith angle: 0 to pi

        # Pre-compute power pattern at selected frequency
        self._compute_power_pattern()

        # Handle azimuth wrap-around: append az=360° data (copy of az=0°)
        # This ensures interpolation works correctly near az=0°/360° boundary
        self.az_array = np.append(self.az_array, 2 * np.pi)  # Add 360° = 2π
        # Append first column (az=0) as last column (az=360°)
        self.power_db = np.column_stack([self.power_db, self.power_db[:, 0]])

        print(f"Loaded beam: {beam_path}")
        print(f"  Frequency: {self.frequency:.1f} MHz (index {self.freq_idx})")
        print(f"  Az range: {np.rad2deg(self.az_array.min()):.1f}° - {np.rad2deg(self.az_array.max()):.1f}°")
        print(f"  ZA range: {np.rad2deg(self.za_array.min()):.1f}° - {np.rad2deg(self.za_array.max()):.1f}°")

    def _compute_power_pattern(self):
        """Compute power pattern from E-field components."""
        # beam.data_array shape: (Naxes_vec, Nspws, Nfreqs, Naxes2, Naxes1)
        # For efield beam: Naxes_vec=2 (theta, phi components)
        # For power beam: Naxes_vec=1

        if self.beam.beam_type == "efield":
            # E-field beam: compute power from theta and phi components
            e_theta = self.beam.data_array[0, 0, self.freq_idx, :, :]
            e_phi = self.beam.data_array[1, 0, self.freq_idx, :, :]
            self.power = np.abs(e_theta)**2 + np.abs(e_phi)**2
        else:
            # Power beam: use directly
            self.power = self.beam.data_array[0, 0, self.freq_idx, :, :]

        # Normalize to peak
        self.power = self.power / np.nanmax(self.power)

        # Convert to dB
        self.power_db = 10 * np.log10(self.power + 1e-10)

    def get_power_at_za(self, max_za_deg=90):
        """
        Get power pattern up to a maximum zenith angle.

        Parameters
        ----------
        max_za_deg : float
            Maximum zenith angle in degrees (default: 90 for horizon)

        Returns
        -------
        az_deg : ndarray
            Azimuth array in degrees
        za_deg : ndarray
            Zenith angle array in degrees
        power_db : ndarray
            Power pattern in dB (normalized)
        """
        max_za_rad = np.deg2rad(max_za_deg)
        za_mask = self.za_array <= max_za_rad

        az_deg = np.rad2deg(self.az_array)
        za_deg = np.rad2deg(self.za_array[za_mask])
        power_db = self.power_db[za_mask, :]

        return az_deg, za_deg, power_db

    def transform_to_radec(self, location, obstime=None, lst_hours=None, max_za_deg=90,
                           ra_resolution=0.5, dec_resolution=0.5):
        """
        Transform beam pattern from Az/ZA to RA/Dec coordinates.

        The beam is centered at zenith, which is at RA = LST, Dec = latitude.

        Parameters
        ----------
        location : EarthLocation
            Observer location
        obstime : Time, optional
            Observation time (used to calculate LST). Either obstime or lst_hours required.
        lst_hours : float, optional
            Local Sidereal Time in hours (0-24). Alternative to obstime.
        max_za_deg : float
            Maximum zenith angle to include (default: 90)
        ra_resolution : float
            RA grid resolution in degrees
        dec_resolution : float
            Dec grid resolution in degrees

        Returns
        -------
        dict with keys:
            'ra_grid' : ndarray, RA values in degrees
            'dec_grid' : ndarray, Dec values in degrees
            'power_db' : 2D ndarray, power in dB on RA/Dec grid
            'ra_center' : float, zenith RA in degrees
            'dec_center' : float, zenith Dec in degrees
        """
        # Determine zenith position
        lat_deg = location.lat.deg

        if lst_hours is not None:
            # LST directly gives zenith RA
            zenith_ra = lst_hours * 15.0  # Convert hours to degrees
        elif obstime is not None:
            # Calculate LST from observation time
            lst = obstime.sidereal_time('apparent', longitude=location.lon)
            zenith_ra = lst.deg
        else:
            raise ValueError("Either obstime or lst_hours must be provided")

        zenith_dec = lat_deg

        # Create interpolator for the beam pattern
        # Note: beam axes are (ZA, Az), power shape is (n_za, n_az)
        interpolator = RegularGridInterpolator(
            (self.za_array, self.az_array),
            self.power_db,
            method='linear',
            bounds_error=False,
            fill_value=np.nan
        )

        # Create RA/Dec grid covering the beam extent
        # The beam extends max_za_deg from zenith in all directions
        ra_extent = max_za_deg / np.cos(np.deg2rad(zenith_dec))  # Correct for cos(dec)

        ra_min = zenith_ra - ra_extent
        ra_max = zenith_ra + ra_extent
        dec_min = zenith_dec - max_za_deg
        dec_max = zenith_dec + max_za_deg

        # Clip to valid declination range
        dec_min = max(dec_min, -90)
        dec_max = min(dec_max, 90)

        # Create grids
        ra_grid = np.arange(ra_min, ra_max + ra_resolution, ra_resolution)
        dec_grid = np.arange(dec_min, dec_max + dec_resolution, dec_resolution)

        # Create 2D meshgrid
        RA, DEC = np.meshgrid(ra_grid, dec_grid)

        # Convert RA/Dec to Az/ZA using spherical trigonometry
        # For a point at (RA, Dec), the angular distance from zenith (ZA) is:
        #   cos(ZA) = sin(Dec_z)*sin(Dec) + cos(Dec_z)*cos(Dec)*cos(RA - RA_z)
        # The azimuth (measured from North toward East) is:
        #   sin(Az) = cos(Dec)*sin(RA - RA_z) / sin(ZA)
        #   cos(Az) = (sin(Dec) - sin(Dec_z)*cos(ZA)) / (cos(Dec_z)*sin(ZA))

        dec_z_rad = np.deg2rad(zenith_dec)
        dec_rad = np.deg2rad(DEC)
        delta_ra_rad = np.deg2rad(RA - zenith_ra)

        # Calculate zenith angle
        cos_za = (np.sin(dec_z_rad) * np.sin(dec_rad) +
                  np.cos(dec_z_rad) * np.cos(dec_rad) * np.cos(delta_ra_rad))
        cos_za = np.clip(cos_za, -1, 1)
        za_rad = np.arccos(cos_za)

        # Calculate azimuth
        sin_za = np.sin(za_rad)
        # Avoid division by zero at zenith
        with np.errstate(divide='ignore', invalid='ignore'):
            sin_az = np.cos(dec_rad) * np.sin(delta_ra_rad) / sin_za
            cos_az = (np.sin(dec_rad) - np.sin(dec_z_rad) * cos_za) / (np.cos(dec_z_rad) * sin_za)

        sin_az = np.clip(sin_az, -1, 1)
        cos_az = np.clip(cos_az, -1, 1)

        az_rad = np.arctan2(sin_az, cos_az)
        # Convert to 0-2*pi range
        az_rad = az_rad % (2 * np.pi)

        # Handle zenith point (ZA = 0)
        zenith_mask = za_rad < 1e-6
        az_rad[zenith_mask] = 0

        # Interpolate beam power at these Az/ZA coordinates
        points = np.column_stack([za_rad.ravel(), az_rad.ravel()])
        power_db_grid = interpolator(points).reshape(RA.shape)

        # Mask points beyond max_za
        power_db_grid[za_rad > np.deg2rad(max_za_deg)] = np.nan

        return {
            'ra_grid': ra_grid,
            'dec_grid': dec_grid,
            'power_db': power_db_grid,
            'ra_center': zenith_ra,
            'dec_center': zenith_dec,
            'max_za_deg': max_za_deg
        }

    def create_rgba_overlay(self, beam_data, cmap='RdBu_r', vmin=-40, vmax=0, alpha_scale=0.7):
        """
        Create RGBA image for Bokeh overlay from transformed beam data.

        Parameters
        ----------
        beam_data : dict
            Output from transform_to_radec()
        cmap : str
            Matplotlib colormap name
        vmin, vmax : float
            Color scale limits in dB
        alpha_scale : float
            Maximum alpha value (0-1) for the overlay

        Returns
        -------
        dict with keys:
            'image' : 2D uint32 ndarray for image_rgba
            'x' : float, left edge in plot coordinates
            'y' : float, bottom edge in plot coordinates
            'dw' : float, width in plot coordinates
            'dh' : float, height in plot coordinates
        """
        import matplotlib.pyplot as plt

        power_db = beam_data['power_db']
        ra_grid = beam_data['ra_grid']
        dec_grid = beam_data['dec_grid']

        # Get colormap
        colormap = plt.get_cmap(cmap)

        # Normalize power to 0-1 for colormap
        power_normalized = (power_db - vmin) / (vmax - vmin)
        power_normalized = np.clip(power_normalized, 0, 1)

        # Apply colormap (returns RGBA with values 0-1)
        rgba = colormap(power_normalized)

        # Adjust alpha based on power level
        # Higher power (closer to 0 dB) = more opaque
        # Lower power (closer to vmin) = more transparent
        alpha = power_normalized * alpha_scale

        # Set alpha for NaN values to 0 (fully transparent)
        nan_mask = np.isnan(power_db)
        alpha[nan_mask] = 0

        # Set RGBA alpha channel
        rgba[:, :, 3] = alpha

        # Convert to uint8
        rgba_uint8 = (rgba * 255).astype(np.uint8)

        # Pack into uint32 for Bokeh image_rgba
        # Bokeh expects RGBA packed as: R + G*256 + B*256^2 + A*256^3
        img = np.empty((rgba_uint8.shape[0], rgba_uint8.shape[1]), dtype=np.uint32)
        view = img.view(dtype=np.uint8).reshape(rgba_uint8.shape[0], rgba_uint8.shape[1], 4)
        view[:, :, 0] = rgba_uint8[:, :, 0]  # R
        view[:, :, 1] = rgba_uint8[:, :, 1]  # G
        view[:, :, 2] = rgba_uint8[:, :, 2]  # B
        view[:, :, 3] = rgba_uint8[:, :, 3]  # A

        # Calculate image position and size
        x = ra_grid[0]
        y = dec_grid[0]
        dw = ra_grid[-1] - ra_grid[0]
        dh = dec_grid[-1] - dec_grid[0]

        return {
            'image': img,
            'x': x,
            'y': y,
            'dw': dw,
            'dh': dh,
            'ra_center': beam_data['ra_center'],
            'dec_center': beam_data['dec_center']
        }
