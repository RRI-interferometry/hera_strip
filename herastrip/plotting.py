import os
import numpy as np
from bokeh.plotting import figure, show
from bokeh.models import (
    ColorBar,
    LogColorMapper,
    FixedTicker,
    HoverTool,
    ColumnDataSource,
)
from bokeh.layouts import gridplot
from bokeh.io import output_file, save, reset_output
from bokeh.resources import CDN

class Plotter:
    def __init__(self, fov_radius_deg, gleam_sources, location):
        self.fov_radius_deg = fov_radius_deg
        self.gleam_sources = gleam_sources
        self.location = location
        self.hera_dec = -30.7  # Static reference declination for HERA
    
    def _add_declination_lines(self, p):
        # Draw dotted lines indicating the FOV boundaries
        p.line(
            x=[-180, 180],
            y=[self.hera_dec + self.fov_radius_deg, self.hera_dec + self.fov_radius_deg],
            line_dash="dotted",
            color="white",
            alpha=0.7,
            line_width=2,
        )
        p.line(
            x=[-180, 180],
            y=[self.hera_dec - self.fov_radius_deg, self.hera_dec - self.fov_radius_deg],
            line_dash="dotted",
            color="white",
            alpha=0.7,
            line_width=2,
        )
    
    def create_plot(self, projected_map, obstime, ra_center):
        # Set up RA and Dec bounds for the image grid and FOV patch
        n_y, n_x = projected_map.shape
        ra_range_highlight = np.linspace(
            ra_center - self.fov_radius_deg, ra_center + self.fov_radius_deg, 100
        )
        dec_upper = self.location.lat.deg + self.fov_radius_deg
        dec_lower = self.location.lat.deg - self.fov_radius_deg
        
        # Normalize the projected map brightness for color mapping
        min_value = np.nanmin(projected_map)
        max_value = np.nanmax(projected_map)
        color_mapper = LogColorMapper(palette="Inferno256", low=min_value, high=max_value)
        
        # Create a Bokeh figure for the current observation time
        p = figure(
            title=f"Sky Model on {obstime.to_datetime().strftime('%Y-%m-%d %H:%M:%S')}",
            x_range=(-180, 180),
            y_range=(-90, 90),
            x_axis_label="RA (°)",
            y_axis_label="Dec (°)",
            aspect_ratio=2,
        )
        
        # Add the sky map image to the figure
        image = p.image(
            image=[projected_map],
            x=-180,
            y=-90,
            dw=360,
            dh=180,
            color_mapper=color_mapper,
        )
        
        # Add a hover tool for the image
        hover_tool = HoverTool(
            tooltips=[
                ("RA", "$x°"),
                ("Dec", "$y°"),
                ("Brightness", "@image"),
            ],
            formatters={"$x": "printf", "$y": "printf"},
            mode="mouse",
            renderers=[image],
            attachment="right",
        )
        p.add_tools(hover_tool)
        
        # Draw FOV declination lines
        self._add_declination_lines(p)
        
        # Highlight the observable area with a patch
        p.patch(
            x=list(ra_range_highlight) + list(ra_range_highlight[::-1]),
            y=[dec_lower] * len(ra_range_highlight) + [dec_upper] * len(ra_range_highlight),
            color="red",
            fill_alpha=0.3,
            line_alpha=1.0,
        )
        
        # Add a colorbar to the figure
        color_bar = ColorBar(
            color_mapper=color_mapper,
            label_standoff=12,
            border_line_color=None,
            location=(0, 0),
        )
        p.add_layout(color_bar, "right")
        
        # Set custom tick marks for RA and Dec
        major_ticks_ra = list(range(-180, 181, 30))
        major_ticks_dec = list(range(-90, 91, 30))
        p.xaxis.ticker = FixedTicker(ticks=major_ticks_ra)
        p.yaxis.ticker = FixedTicker(ticks=major_ticks_dec)
        p.xaxis.major_label_overrides = {tick: f"{tick}°" for tick in major_ticks_ra}
        p.yaxis.major_label_overrides = {tick: f"{tick}°" for tick in major_ticks_dec}
        
        # Optionally add GLEAM source overlays if provided
        if self.gleam_sources:
            source_data = {"ra": [], "dec": [], "flux": []}
            for source in self.gleam_sources:
                ra = source["coords"].ra.deg
                dec = source["coords"].dec.deg
                flux = source["flux"]
                if ra > 180:
                    ra -= 360
                source_data["ra"].append(ra)
                source_data["dec"].append(dec)
                source_data["flux"].append(flux)
            source_cds = ColumnDataSource(data=source_data)
            p.scatter(
                x="ra",
                y="dec",
                size=3,
                source=source_cds,
                color="#39FF14",
                alpha=0.8,
            )
            hover_tool_sources = HoverTool(
                tooltips=[
                    ("RA", "@ra°"),
                    ("Dec", "@dec°"),
                    ("Flux", "@flux Jy"),
                ],
                mode="mouse",
                renderers=[p.renderers[-1]],
                attachment="left",
            )
            p.add_tools(hover_tool_sources)
        
        return p
    
    def arrange_plots(self, plots, ncols=2):
        return gridplot(children=plots, ncols=ncols)
    
    def save_grid(self, grid, folder_path):
        file_path = os.path.join(folder_path, "gsm_plots_grid.html")
        output_file(file_path)
        save(grid, filename=file_path, resources=CDN, title="Global Sky Model Plots")
        print(f"GSM plot grid saved to {file_path}")
    
    def show_grid(self, grid):
        show(grid)
        reset_output()
