import numpy as np
from astropy.coordinates import SkyCoord, AltAz
from astropy.time import TimeDelta
import astropy.units as au

from .sky_model import SkyMapGenerator
from .plotting import Plotter

class HeraStripSimulator:
    def __init__(
        self,
        location,
        obstime_start,
        total_seconds,
        frequency=76,
        fov_radius_deg=5,
        gleam_sources=None,
    ):
        self.location = location
        self.obstime_start = obstime_start
        self.total_seconds = total_seconds
        self.frequency = frequency
        self.fov_radius_deg = fov_radius_deg
        self.gleam_sources = gleam_sources

        self.sky_map_gen = SkyMapGenerator(frequency=self.frequency)
        self.plotter = Plotter(
            fov_radius_deg=self.fov_radius_deg,
            gleam_sources=self.gleam_sources,
            location=self.location,
        )
    
    def run_simulation(self, save_simulation_data=False, folder_path=None):
        # Generate the projected sky map from the Global Sky Model
        projected_map = self.sky_map_gen.generate_projected_map()
        
        # Create time points at one-hour intervals
        time_points = np.arange(0, self.total_seconds, 3600)
        plots = []
        
        for current_time in time_points:
            # Update observation time
            obstime = self.obstime_start + TimeDelta(current_time, format="sec")
            
            # Determine the observer's zenith RA center
            zenith = SkyCoord(
                alt=90 * au.deg,
                az=0 * au.deg,
                frame=AltAz(obstime=obstime, location=self.location)
            )
            zenith_radec = zenith.transform_to("icrs")
            ra_center = zenith_radec.ra.deg % 360
            if ra_center > 180:
                ra_center -= 360
            
            # Create the plot for this observation time
            plot = self.plotter.create_plot(projected_map, obstime, ra_center)
            plots.append(plot)
        
        # Arrange all plots into a grid layout
        grid = self.plotter.arrange_plots(plots)
        
        # Save the grid to an HTML file if requested
        if save_simulation_data and folder_path:
            self.plotter.save_grid(grid, folder_path)
        
        # Display the grid of plots
        self.plotter.show_grid(grid)
