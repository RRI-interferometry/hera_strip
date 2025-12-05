import os
import numpy as np
from bokeh.plotting import figure, show
from bokeh.models import (
    ColorBar,
    LogColorMapper,
    LinearColorMapper,
    FixedTicker,
    HoverTool,
    ColumnDataSource,
    DataTable,
    TableColumn,
    NumberFormatter,
    Div,
    Label,
    LabelSet,
)
from bokeh.layouts import gridplot, column, row as bokeh_row
from bokeh.io import output_file, save, reset_output
from bokeh.resources import CDN


def _create_blue_to_white_palette(n=256):
    """Create a palette from sky blue to white."""
    palette = []
    for i in range(n):
        # Interpolate from sky blue (0, 120, 200) to white (255, 255, 255)
        t = i / (n - 1)
        r = int(0 + t * 255)
        g = int(120 + t * (255 - 120))
        b = int(200 + t * (255 - 200))
        palette.append(f"#{r:02x}{g:02x}{b:02x}")
    return palette


# Pre-generate the blue-to-white palette
BLUE_WHITE_PALETTE = _create_blue_to_white_palette(256)


class Plotter:
    def __init__(self, fov_radius_deg, point_sources, location, color_scale="log", use_lst=False,
                 background_mode="gsm", beam_processor=None, beam_vmin=-40, beam_vmax=0, beam_lst=None):
        self.fov_radius_deg = fov_radius_deg
        self.point_sources = point_sources
        self.location = location
        self.color_scale = color_scale
        self.use_lst = use_lst
        self.background_mode = background_mode  # "gsm", "none", or "reference"
        self.beam_processor = beam_processor
        self.beam_vmin = beam_vmin
        self.beam_vmax = beam_vmax
        self.beam_lst = beam_lst  # LST in hours where to center beam (None = center of strip)

    def _ra_to_lst(self, ra_deg):
        """Convert RA in degrees to LST in hours.

        LST = RA when object is on the meridian.
        RA (degrees) / 15 = LST (hours)

        Maps [-180, 180] degrees to [-12, 12) hours (LST 0 centered).
        """
        # Normalize RA to [-180, 180)
        ra_normalized = ra_deg % 360
        if ra_normalized > 180:
            ra_normalized -= 360
        # Convert to hours [-12, 12)
        lst_hours = ra_normalized / 15.0
        return lst_hours

    def _add_declination_lines(self, p, use_light_theme=False):
        """Draw dotted lines indicating the FOV boundaries based on observer latitude."""
        observer_dec = self.location.lat.deg
        dec_upper = observer_dec + self.fov_radius_deg
        dec_lower = observer_dec - self.fov_radius_deg
        line_color = "#4a90d9" if use_light_theme else "white"  # Blue on light theme, white on dark
        text_color = "#333333" if use_light_theme else "white"

        # Set x range based on LST mode
        if self.use_lst:
            x_line = [-12, 12]
            label_x = -11.8  # Near left edge
        else:
            x_line = [-180, 180]
            label_x = -175  # Near left edge

        # Upper declination line
        p.line(
            x=x_line,
            y=[dec_upper, dec_upper],
            line_dash="dotted",
            color=line_color,
            alpha=0.7,
            line_width=2,
        )
        # Lower declination line
        p.line(
            x=x_line,
            y=[dec_lower, dec_lower],
            line_dash="dotted",
            color=line_color,
            alpha=0.7,
            line_width=2,
        )

        # Add Dec labels near y-axis
        label_upper = Label(
            x=label_x, y=dec_upper,
            text=f"{dec_upper:.1f}°",
            text_font_size="9pt",
            text_color=text_color,
            text_alpha=0.9,
            x_offset=2, y_offset=-12,
        )
        label_lower = Label(
            x=label_x, y=dec_lower,
            text=f"{dec_lower:.1f}°",
            text_font_size="9pt",
            text_color=text_color,
            text_alpha=0.9,
            x_offset=2, y_offset=2,
        )
        p.add_layout(label_upper)
        p.add_layout(label_lower)

    def _add_strip_boundary_lines(self, p, ra_start, ra_end, dec_lower, dec_upper, use_light_theme=False):
        """Draw vertical lines at the strip boundaries with LST/RA labels."""
        line_color = "#4a90d9" if use_light_theme else "yellow"
        text_color = "#333333" if use_light_theme else "yellow"

        # Convert to appropriate x-coordinates
        if self.use_lst:
            x_start = self._ra_to_lst(ra_start)
            x_end = self._ra_to_lst(ra_end)
            # Format as proper LST (0-24h)
            label_start = f"{x_start % 24:.2f}h"
            label_end = f"{x_end % 24:.2f}h"
        else:
            x_start = self._normalize_ra(ra_start)
            x_end = self._normalize_ra(ra_end)
            label_start = f"{x_start:.1f}°"
            label_end = f"{x_end:.1f}°"

        # Draw vertical lines at strip start and end
        p.line(
            x=[x_start, x_start],
            y=[dec_lower, dec_upper],
            line_dash="dashed",
            color=line_color,
            alpha=0.8,
            line_width=2,
        )
        p.line(
            x=[x_end, x_end],
            y=[dec_lower, dec_upper],
            line_dash="dashed",
            color=line_color,
            alpha=0.8,
            line_width=2,
        )

        # Add labels near x-axis for start boundary
        label_x_start = Label(
            x=x_start, y=dec_lower,
            text=label_start,
            text_font_size="9pt",
            text_color=text_color,
            text_alpha=0.9,
            x_offset=-15, y_offset=-18,
        )
        # Add label for end boundary
        label_x_end = Label(
            x=x_end, y=dec_lower,
            text=label_end,
            text_font_size="9pt",
            text_color=text_color,
            text_alpha=0.9,
            x_offset=-15, y_offset=-18,
        )
        p.add_layout(label_x_start)
        p.add_layout(label_x_end)

    def _highlight_top_sources(self, p, top_sources, use_light_theme=False):
        """Highlight top sources with yellow color and rank labels.

        Parameters
        ----------
        p : figure
            Bokeh figure
        top_sources : list
            List of top source dicts with 'ra', 'dec', 'flux' keys
        use_light_theme : bool
            Whether to use light theme colors
        """
        if not top_sources:
            return

        # Prepare data for scatter and labels
        highlight_data = {
            "x": [],
            "dec": [],
            "rank": [],
        }

        for i, source in enumerate(top_sources):
            ra = source["ra"]
            dec = source["dec"]

            # Convert to appropriate x-coordinate
            if self.use_lst:
                x = self._ra_to_lst(ra)
            else:
                x = ra

            highlight_data["x"].append(x)
            highlight_data["dec"].append(dec)
            highlight_data["rank"].append(str(i + 1))

        # Draw yellow circles for top sources
        highlight_cds = ColumnDataSource(data=highlight_data)
        p.scatter(
            x="x",
            y="dec",
            size=3,
            source=highlight_cds,
            color="yellow",
            line_color=None,
        )

        # Add rank labels (just "1", "2", etc.) next to sources
        rank_labels = LabelSet(
            x="x",
            y="dec",
            text="rank",
            source=highlight_cds,
            text_font_size="9pt",
            text_color="yellow",
            text_font_style="bold",
            x_offset=5,
            y_offset=3,
        )
        p.add_layout(rank_labels)

    def _normalize_ra(self, ra):
        """Normalize RA to [-180, 180] range."""
        ra = ra % 360
        if ra > 180:
            ra -= 360
        return ra

    def _is_in_strip(self, ra, dec, ra_start, ra_end, dec_lower, dec_upper):
        """Check if a source is within the observable strip."""
        # Check declination bounds
        if not (dec_lower <= dec <= dec_upper):
            return False

        # Normalize RA to [-180, 180]
        ra = self._normalize_ra(ra)

        # Check RA bounds (handle wrapping)
        if ra_start <= ra_end:
            # No wrapping
            return ra_start <= ra <= ra_end
        else:
            # Wrapping case: strip crosses ±180°
            return ra >= ra_start or ra <= ra_end

    def _get_top_sources_in_strip(self, ra_start, ra_end, dec_lower, dec_upper, n=5):
        """Get the top N brightest sources within the observable strip."""
        if not self.point_sources:
            return []

        sources_in_strip = []
        for source in self.point_sources:
            ra = source["coords"].ra.deg
            dec = source["coords"].dec.deg
            flux = source["flux"]

            if self._is_in_strip(ra, dec, ra_start, ra_end, dec_lower, dec_upper):
                sources_in_strip.append({
                    "ra": self._normalize_ra(ra),
                    "dec": dec,
                    "flux": flux
                })

        # Sort by flux (brightest first) and take top N
        sources_in_strip.sort(key=lambda x: x["flux"], reverse=True)
        return sources_in_strip[:n]

    def _get_nearby_sources(self, ra_start, ra_end, dec_lower, dec_upper, buffer_deg=10, n=3):
        """Get the top N brightest sources in the buffer zone around the strip.

        These are sources within buffer_deg of the strip boundary but NOT inside the strip.
        """
        if not self.point_sources:
            return []

        # Expanded region bounds (with buffer)
        expanded_dec_lower = dec_lower - buffer_deg
        expanded_dec_upper = dec_upper + buffer_deg

        # For RA, we need to handle the expansion carefully
        # Expand ra_start (go more negative/west) and ra_end (go more positive/east)
        expanded_ra_start = self._normalize_ra(ra_start - buffer_deg)
        expanded_ra_end = self._normalize_ra(ra_end + buffer_deg)

        nearby_sources = []
        for source in self.point_sources:
            ra = source["coords"].ra.deg
            dec = source["coords"].dec.deg
            flux = source["flux"]

            # Check if inside the main strip (exclude these)
            if self._is_in_strip(ra, dec, ra_start, ra_end, dec_lower, dec_upper):
                continue

            # Check if within the expanded buffer region
            if self._is_in_strip(ra, dec, expanded_ra_start, expanded_ra_end,
                                  expanded_dec_lower, expanded_dec_upper):
                nearby_sources.append({
                    "ra": self._normalize_ra(ra),
                    "dec": dec,
                    "flux": flux
                })

        # Sort by flux (brightest first) and take top N
        nearby_sources.sort(key=lambda x: x["flux"], reverse=True)
        return nearby_sources[:n]

    def _create_sources_table(self, sources, title, empty_msg="No sources found"):
        """Create a DataTable showing sources.

        Parameters
        ----------
        sources : list
            List of source dicts with 'ra', 'dec', 'flux' keys
        title : str
            Title for the table
        empty_msg : str
            Message to show if no sources
        """
        if not sources:
            return Div(text=f"<p><i>{empty_msg}</i></p>")

        # Prepare data for table
        table_data = {
            "rank": list(range(1, len(sources) + 1)),
            "ra": [f"{s['ra']:.4f}" for s in sources],
            "dec": [f"{s['dec']:.4f}" for s in sources],
            "flux": [s["flux"] for s in sources],
        }

        source = ColumnDataSource(data=table_data)

        columns = [
            TableColumn(field="rank", title="Rank", width=50),
            TableColumn(field="ra", title="RA (°)", width=100),
            TableColumn(field="dec", title="Dec (°)", width=100),
            TableColumn(
                field="flux",
                title="Flux (Jy)",
                width=120,
                formatter=NumberFormatter(format="0.000")
            ),
        ]

        # Create header
        header = Div(
            text=f"<h3 style='margin: 10px 0 5px 0;'>{title}</h3>",
            width=450
        )

        # Adjust height based on number of sources
        row_height = 28
        table_height = 30 + len(sources) * row_height

        table = DataTable(
            source=source,
            columns=columns,
            width=450,
            height=table_height,
            index_position=None,
        )

        return column(header, table)

    def _add_beam_overlay(self, p, ra_center_default, use_light_theme=False):
        """Add beam pattern overlay with contours to the plot.

        Parameters
        ----------
        p : figure
            Bokeh figure to add beam overlay to
        ra_center_default : float
            Default center RA in degrees (middle of strip, used if beam_lst not set)
        use_light_theme : bool
            Whether using light theme
        """
        if self.beam_processor is None:
            return

        import matplotlib.pyplot as plt
        from matplotlib import contour as mpl_contour

        # Determine beam center LST
        if self.beam_lst is not None:
            lst_center = self.beam_lst
        else:
            lst_center = ra_center_default / 15.0  # Convert RA to LST hours

        # Transform beam to RA/Dec coordinates
        beam_data = self.beam_processor.transform_to_radec(
            location=self.location,
            lst_hours=lst_center,
            max_za_deg=90,  # Show full hemisphere
            ra_resolution=0.25,
            dec_resolution=0.25
        )

        # Create RGBA overlay
        rgba_data = self.beam_processor.create_rgba_overlay(
            beam_data,
            cmap='RdBu_r',
            vmin=self.beam_vmin,
            vmax=self.beam_vmax,
            alpha_scale=0.7
        )

        # Convert RA grid to plot coordinates
        ra_grid = beam_data['ra_grid']
        dec_grid = beam_data['dec_grid']
        power_db = beam_data['power_db']

        if self.use_lst:
            # Convert RA to LST hours (centered at 0)
            x_grid = np.array([self._ra_to_lst(ra) for ra in ra_grid])
            dw = rgba_data['dw'] / 15.0
            center_x = self._ra_to_lst(beam_data['ra_center'])
            # Position image centered on center_x (handles wrapping correctly)
            x = center_x - dw / 2
        else:
            x_grid = np.array([self._normalize_ra(ra) for ra in ra_grid])
            dw = rgba_data['dw']
            center_x = self._normalize_ra(beam_data['ra_center'])
            x = center_x - dw / 2

        # Add the beam image overlay
        p.image_rgba(
            image=[rgba_data['image']],
            x=x,
            y=rgba_data['y'],
            dw=dw,
            dh=rgba_data['dh'],
        )

        # Add contour lines at specific dB levels
        contour_levels = [-3, -10]  # dB levels
        contour_labels = ["-3 dB (HPBW)", "-10 dB"]
        contour_colors = ["white", "yellow"]
        label_positions = [0.25, 0.75]  # Different positions along contour to avoid overlap

        # Create meshgrid for contour finding
        X, Y = np.meshgrid(x_grid, dec_grid)

        # Use matplotlib to find contours (but don't plot)
        fig_temp, ax_temp = plt.subplots()
        for level, label, color, label_pos in zip(contour_levels, contour_labels, contour_colors, label_positions):
            # Find contours at this level
            cs = ax_temp.contour(X, Y, power_db, levels=[level])

            # Extract contour paths - handle different matplotlib versions
            # Matplotlib 3.8+: ContourSet is a Collection, use get_paths() directly
            # Matplotlib < 3.8: Use collections attribute
            segments = []
            if hasattr(cs, 'get_paths'):
                # Matplotlib 3.8+: ContourSet is itself a Collection
                for path in cs.get_paths():
                    segments.append(path.vertices)
            elif hasattr(cs, 'collections'):
                # Matplotlib < 3.8: Use collections
                for collection in cs.collections:
                    for path in collection.get_paths():
                        segments.append(path.vertices)

            labeled = False
            for vertices in segments:
                if len(vertices) > 1:
                    xs = vertices[:, 0]
                    ys = vertices[:, 1]

                    # Draw contour line
                    p.line(
                        x=xs,
                        y=ys,
                        line_color=color,
                        line_width=2,
                        line_dash="solid" if level == -3 else "dashed",
                    )

                    # Add label at a point along the contour (only once per level)
                    if not labeled:
                        label_idx = int(len(xs) * label_pos)
                        if label_idx < len(xs):
                            contour_label = Label(
                                x=xs[label_idx],
                                y=ys[label_idx],
                                text=label,
                                text_font_size="8pt",
                                text_color=color,
                                text_font_style="bold",
                                background_fill_color="black",
                                background_fill_alpha=0.5,
                                x_offset=5,
                                y_offset=5,
                            )
                            p.add_layout(contour_label)
                            labeled = True

        plt.close(fig_temp)

        # Add beam colorbar
        cmap = plt.get_cmap('RdBu_r')
        beam_palette = [
            "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255))
            for r, g, b, _ in [cmap(i/255) for i in range(256)]
        ]

        beam_color_mapper = LinearColorMapper(
            palette=beam_palette,
            low=self.beam_vmin,
            high=self.beam_vmax
        )
        beam_colorbar = ColorBar(
            color_mapper=beam_color_mapper,
            label_standoff=12,
            border_line_color=None,
            location=(0, 0),
            title="Beam (dB)",
        )
        p.add_layout(beam_colorbar, "left")

    def _add_point_sources(self, p, add_colorbar=False):
        """Add point source overlays if provided.

        Parameters
        ----------
        p : figure
            Bokeh figure to add sources to
        add_colorbar : bool
            If True, add a colorbar for source flux (use when no background map)
        """
        if not self.point_sources:
            return

        source_data = {"x": [], "dec": [], "flux": [], "ra": [], "lst": []}
        for source in self.point_sources:
            ra = source["coords"].ra.deg
            dec = source["coords"].dec.deg
            flux = source["flux"]

            # Store original RA for tooltip
            source_data["ra"].append(ra if ra <= 180 else ra - 360)

            # Convert x-coordinate based on LST mode
            if self.use_lst:
                x = self._ra_to_lst(ra)
                # Store LST in 0-24h format for tooltip
                source_data["lst"].append(x % 24)
            else:
                if ra > 180:
                    ra -= 360
                x = ra
                source_data["lst"].append(0)  # Not used in RA mode

            source_data["x"].append(x)
            source_data["dec"].append(dec)
            source_data["flux"].append(flux)

        # Create color mapper for flux values
        flux_array = np.array(source_data["flux"])
        min_flux = flux_array.min()
        max_flux = flux_array.max()

        if self.color_scale == "log":
            min_flux = max(min_flux, 1e-6)  # Avoid log(0)
            source_color_mapper = LogColorMapper(
                palette=BLUE_WHITE_PALETTE,
                low=min_flux,
                high=max_flux
            )
        else:
            source_color_mapper = LinearColorMapper(
                palette=BLUE_WHITE_PALETTE,
                low=min_flux,
                high=max_flux
            )

        source_cds = ColumnDataSource(data=source_data)
        scatter = p.scatter(
            x="x",
            y="dec",
            size=3,
            source=source_cds,
            color={"field": "flux", "transform": source_color_mapper},
            line_color=None,
        )

        # Set up tooltips based on LST mode
        if self.use_lst:
            tooltips = [
                ("LST", "@lst{0.2f}h"),
                ("RA", "@ra{0.2f}°"),
                ("Dec", "@dec{0.2f}°"),
                ("Flux", "@flux Jy"),
            ]
        else:
            tooltips = [
                ("RA", "@ra{0.2f}°"),
                ("Dec", "@dec{0.2f}°"),
                ("Flux", "@flux Jy"),
            ]

        hover_tool_sources = HoverTool(
            tooltips=tooltips,
            mode="mouse",
            renderers=[scatter],
            attachment="left",
        )
        p.add_tools(hover_tool_sources)

        # Add colorbar for sources if requested
        if add_colorbar:
            source_colorbar = ColorBar(
                color_mapper=source_color_mapper,
                label_standoff=12,
                border_line_color=None,
                location=(0, 0),
                title="Flux (Jy)",
            )
            p.add_layout(source_colorbar, "right")

    def create_strip_plot(self, projected_map, obstime_start, obstime_end, ra_start, ra_end):
        """
        Create a single plot showing the observable strip over a time duration.

        Parameters
        ----------
        projected_map : ndarray or None
            2D projected sky map, or None for sources-only display
        obstime_start : Time
            Observation start time
        obstime_end : Time
            Observation end time
        ra_start : float
            Zenith RA at start time (degrees, 0-360)
        ra_end : float
            Zenith RA at end time (degrees, 0-360)
        """
        # Normalize RAs to [-180, 180] range
        ra_start = self._normalize_ra(ra_start)
        ra_end = self._normalize_ra(ra_end)

        # Declination bounds based on observer latitude
        dec_upper = self.location.lat.deg + self.fov_radius_deg
        dec_lower = self.location.lat.deg - self.fov_radius_deg

        # Determine rendering mode based on background_mode
        show_background = self.background_mode in ("gsm", "reference") and projected_map is not None
        show_source_colorbar = self.background_mode in ("none", "reference")
        use_light_theme = self.background_mode == "none"  # Blue strip/lines only for white background

        if show_background:
            # Color mapping for sky map
            # Use elevated low threshold so only brightest regions get full color
            # Everything below ~40th percentile maps to dark/black
            # Use compressed() to avoid masked array warning with percentile
            if hasattr(projected_map, 'compressed'):
                valid_data = projected_map.compressed()
            else:
                valid_data = projected_map[~np.isnan(projected_map)]
            min_value = np.percentile(valid_data, 40)
            max_value = np.nanmax(projected_map)

            color_mapper = LogColorMapper(palette="Inferno256", low=min_value, high=max_value)

        # Create title with time or LST range
        if obstime_start is not None and obstime_end is not None:
            start_str = obstime_start.to_datetime().strftime('%Y-%m-%d %H:%M')
            end_str = obstime_end.to_datetime().strftime('%Y-%m-%d %H:%M')
            title = f"Observable Strip: {start_str} to {end_str}"
        else:
            # LST range mode - show LST in title
            lst_start = ra_start / 15.0
            lst_end = ra_end / 15.0
            # Convert to 0-24h format for display
            lst_start_display = lst_start % 24
            lst_end_display = lst_end % 24
            title = f"Observable Strip: LST {lst_start_display:.2f}h to {lst_end_display:.2f}h"

        # Set up x-axis based on LST mode
        if self.use_lst:
            x_range = (-12, 12)
            x_axis_label = "LST (hours)"
        else:
            x_range = (-180, 180)
            x_axis_label = "RA (°)"

        # Create figure (white background for none and translucent modes)
        p = figure(
            title=title,
            x_range=x_range,
            y_range=(-90, 90),
            x_axis_label=x_axis_label,
            y_axis_label="Dec (°)",
            aspect_ratio=2,
            width=1000,
            height=500,
            background_fill_color="white" if use_light_theme else None,
        )

        if show_background:
            if self.use_lst:
                # For LST mode with 0h centered:
                # RA [-180, 180] maps directly to LST [-12, 12]
                # Image spans full range, no splitting needed
                image = p.image(
                    image=[projected_map],
                    x=-12,
                    y=-90,
                    dw=24,
                    dh=180,
                    color_mapper=color_mapper,
                )
            else:
                # Standard RA mode
                image = p.image(
                    image=[projected_map],
                    x=-180,
                    y=-90,
                    dw=360,
                    dh=180,
                    color_mapper=color_mapper,
                )

            # Add hover tool for sky map (only for full gsm mode, not reference)
            if self.background_mode == "gsm" and not self.use_lst:
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
        self._add_declination_lines(p, use_light_theme=use_light_theme)

        # Highlight the observable strip
        # Use different color for light theme (none/translucent) vs dark theme (gsm)
        strip_color = "#4a90d9" if use_light_theme else "red"  # Light blue on white/translucent, red on gsm
        strip_fill_alpha = 0.2 if use_light_theme else 0.15

        if self.use_lst:
            # Convert RA to LST for strip drawing (now centered at 0h)
            lst_start = self._ra_to_lst(ra_start)
            lst_end = self._ra_to_lst(ra_end)

            # Handle LST wrapping (when strip crosses ±12h boundary)
            if lst_start <= lst_end:
                # No wrapping - simple case
                lst_range = np.linspace(lst_start, lst_end, 200)
                p.patch(
                    x=list(lst_range) + list(lst_range[::-1]),
                    y=[dec_lower] * len(lst_range) + [dec_upper] * len(lst_range),
                    color=strip_color,
                    fill_alpha=strip_fill_alpha,
                    line_alpha=1.0,
                )
            else:
                # Wrapping case - strip crosses ±12h boundary
                lst_range1 = np.linspace(lst_start, 12, 100)
                lst_range2 = np.linspace(-12, lst_end, 100)

                p.patch(
                    x=list(lst_range1) + list(lst_range1[::-1]),
                    y=[dec_lower] * len(lst_range1) + [dec_upper] * len(lst_range1),
                    color=strip_color,
                    fill_alpha=strip_fill_alpha,
                    line_alpha=1.0,
                )
                p.patch(
                    x=list(lst_range2) + list(lst_range2[::-1]),
                    y=[dec_lower] * len(lst_range2) + [dec_upper] * len(lst_range2),
                    color=strip_color,
                    fill_alpha=strip_fill_alpha,
                    line_alpha=1.0,
                )
        else:
            # Handle RA wrapping (when strip crosses ±180°)
            if ra_start <= ra_end:
                # No wrapping - simple case
                ra_range = np.linspace(ra_start, ra_end, 200)
                p.patch(
                    x=list(ra_range) + list(ra_range[::-1]),
                    y=[dec_lower] * len(ra_range) + [dec_upper] * len(ra_range),
                    color=strip_color,
                    fill_alpha=strip_fill_alpha,
                    line_alpha=1.0,
                )
            else:
                # Wrapping case - strip crosses ±180° boundary
                # Draw two patches: ra_start to 180, and -180 to ra_end
                ra_range1 = np.linspace(ra_start, 180, 100)
                ra_range2 = np.linspace(-180, ra_end, 100)

                p.patch(
                    x=list(ra_range1) + list(ra_range1[::-1]),
                    y=[dec_lower] * len(ra_range1) + [dec_upper] * len(ra_range1),
                    color=strip_color,
                    fill_alpha=strip_fill_alpha,
                    line_alpha=1.0,
                )
                p.patch(
                    x=list(ra_range2) + list(ra_range2[::-1]),
                    y=[dec_lower] * len(ra_range2) + [dec_upper] * len(ra_range2),
                    color=strip_color,
                    fill_alpha=strip_fill_alpha,
                    line_alpha=1.0,
                )

        # Add vertical boundary lines with LST/RA labels
        self._add_strip_boundary_lines(p, ra_start, ra_end, dec_lower, dec_upper, use_light_theme)

        # Add beam overlay if beam processor is available
        if self.beam_processor is not None:
            # Calculate center RA for beam placement (middle of strip)
            if ra_start <= ra_end:
                ra_center = (ra_start + ra_end) / 2
            else:
                # Wrapping case - need to handle carefully
                # Convert to [0, 360] for averaging, then back
                ra_start_360 = ra_start if ra_start >= 0 else ra_start + 360
                ra_end_360 = ra_end if ra_end >= 0 else ra_end + 360
                if ra_end_360 < ra_start_360:
                    ra_end_360 += 360
                ra_center = (ra_start_360 + ra_end_360) / 2
                if ra_center > 180:
                    ra_center -= 360
            self._add_beam_overlay(p, ra_center, use_light_theme)

        # Add colorbar for GSM background (only for full gsm mode, not reference)
        if self.background_mode == "gsm" and show_background:
            color_bar = ColorBar(
                color_mapper=color_mapper,
                label_standoff=12,
                border_line_color=None,
                location=(0, 0),
            )
            p.add_layout(color_bar, "right")

        # Set tick marks
        if self.use_lst:
            # Every hour from -12 to 12, displayed as proper LST (0-24h)
            major_ticks_x = list(range(-12, 13, 1))
            p.xaxis.ticker = FixedTicker(ticks=major_ticks_x)
            # Convert negative hours to 24h format: -12 → 12h, -6 → 18h, 0 → 0h, 6 → 6h, 12 → 12h
            p.xaxis.major_label_overrides = {
                tick: f"{tick % 24}h" for tick in major_ticks_x
            }
        else:
            major_ticks_x = list(range(-180, 181, 30))
            p.xaxis.ticker = FixedTicker(ticks=major_ticks_x)
            p.xaxis.major_label_overrides = {tick: f"{tick}°" for tick in major_ticks_x}

        # Dec ticks every 15 degrees
        major_ticks_dec = list(range(-90, 91, 15))
        p.yaxis.ticker = FixedTicker(ticks=major_ticks_dec)
        p.yaxis.major_label_overrides = {tick: f"{tick}°" for tick in major_ticks_dec}

        # Add point sources if provided (with colorbar for none/reference modes)
        self._add_point_sources(p, add_colorbar=show_source_colorbar)

        # For point source plots (none/reference), add tables of top sources
        if show_source_colorbar and self.point_sources:
            # Top 5 brightest in the observable strip
            top_sources = self._get_top_sources_in_strip(
                ra_start, ra_end, dec_lower, dec_upper, n=5
            )

            # Highlight top 5 sources with yellow and labels
            self._highlight_top_sources(p, top_sources, use_light_theme)

            strip_table = self._create_sources_table(
                top_sources,
                title="Top 5 Brightest Sources in Observable Strip",
                empty_msg="No sources in observable strip"
            )

            # Top 3 brightest nearby (within 10° buffer, excluding inside)
            nearby_sources = self._get_nearby_sources(
                ra_start, ra_end, dec_lower, dec_upper, buffer_deg=10, n=3
            )
            nearby_table = self._create_sources_table(
                nearby_sources,
                title="Top 3 Brightest Sources Nearby (10° buffer)",
                empty_msg="No nearby sources in buffer zone"
            )

            tables_row = bokeh_row(strip_table, nearby_table)
            return column(p, tables_row)

        return p

    def save_plot(self, plot, folder_path):
        """Save a single plot to HTML file."""
        file_path = os.path.join(folder_path, "sky_strip.html")
        output_file(file_path)
        save(plot, filename=file_path, resources=CDN, title="Sky Strip Visualization")
        print(f"Sky strip plot saved to {file_path}")

    def show_plot(self, plot):
        """Display a single plot in browser."""
        show(plot)
        reset_output()

    # Keep old methods for backward compatibility
    def create_plot(self, projected_map, obstime, ra_center):
        """Create a single time-snapshot plot (legacy method)."""
        ra_range_highlight = np.linspace(
            ra_center - self.fov_radius_deg, ra_center + self.fov_radius_deg, 100
        )
        dec_upper = self.location.lat.deg + self.fov_radius_deg
        dec_lower = self.location.lat.deg - self.fov_radius_deg

        # Use elevated low threshold so only brightest regions get full color
        if hasattr(projected_map, 'compressed'):
            valid_data = projected_map.compressed()
        else:
            valid_data = projected_map[~np.isnan(projected_map)]
        min_value = np.percentile(valid_data, 40)
        max_value = np.nanmax(projected_map)
        color_mapper = LogColorMapper(palette="Inferno256", low=min_value, high=max_value)

        p = figure(
            title=f"Sky Model on {obstime.to_datetime().strftime('%Y-%m-%d %H:%M:%S')}",
            x_range=(-180, 180),
            y_range=(-90, 90),
            x_axis_label="RA (°)",
            y_axis_label="Dec (°)",
            aspect_ratio=2,
        )

        image = p.image(
            image=[projected_map],
            x=-180,
            y=-90,
            dw=360,
            dh=180,
            color_mapper=color_mapper,
        )

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

        self._add_declination_lines(p)

        p.patch(
            x=list(ra_range_highlight) + list(ra_range_highlight[::-1]),
            y=[dec_lower] * len(ra_range_highlight) + [dec_upper] * len(ra_range_highlight),
            color="red",
            fill_alpha=0.3,
            line_alpha=1.0,
        )

        color_bar = ColorBar(
            color_mapper=color_mapper,
            label_standoff=12,
            border_line_color=None,
            location=(0, 0),
        )
        p.add_layout(color_bar, "right")

        major_ticks_ra = list(range(-180, 181, 30))
        major_ticks_dec = list(range(-90, 91, 30))
        p.xaxis.ticker = FixedTicker(ticks=major_ticks_ra)
        p.yaxis.ticker = FixedTicker(ticks=major_ticks_dec)
        p.xaxis.major_label_overrides = {tick: f"{tick}°" for tick in major_ticks_ra}
        p.yaxis.major_label_overrides = {tick: f"{tick}°" for tick in major_ticks_dec}

        self._add_point_sources(p, add_colorbar=False)

        return p

    def arrange_plots(self, plots, ncols=2):
        """Arrange multiple plots in a grid (legacy method)."""
        return gridplot(children=plots, ncols=ncols)

    def save_grid(self, grid, folder_path):
        """Save grid of plots (legacy method)."""
        file_path = os.path.join(folder_path, "gsm_plots_grid.html")
        output_file(file_path)
        save(grid, filename=file_path, resources=CDN, title="Global Sky Model Plots")
        print(f"GSM plot grid saved to {file_path}")

    def show_grid(self, grid):
        """Show grid of plots (legacy method)."""
        show(grid)
        reset_output()
