# HERA Strip

**HERA Strip** is an interactive visualization tool for simulating and visualizing the observable sky strip for the Hydrogen Epoch of Reionization Array (HERA) radio telescope. It creates interactive Bokeh plots showing diffuse sky models, point source catalogs, and antenna beam patterns projected onto celestial coordinates.

## Features

- **Diffuse Sky Models**: Visualize Global Sky Models (GSM2008, GSM2016, LFSS, Haslam) at any frequency
- **Point Source Catalogs**: Load and display point sources from pyradiosky `.skyh5` files
- **Antenna Beam Overlay**: Project HERA beam patterns from FITS files onto the sky map with power contours
- **Observable Strip**: Highlight the region of sky visible to HERA during a given time range or LST range
- **Interactive Plots**: Zoom, pan, and hover over sources to see coordinates and flux values
- **Flexible Coordinate Systems**: Display in Right Ascension (RA) or Local Sidereal Time (LST)
- **Multiple Background Modes**: Full GSM with hover, reference-only GSM, or white background

## Installation

### From PyPI

```bash
pip install hera-strip
```

### From Source

```bash
git clone https://github.com/RRI-interferometry/hera_strip.git
cd hera_strip
pip install -e .
```

### Dependencies

Required packages:
- `numpy`
- `astropy`
- `healpy`
- `pygdsm`
- `bokeh`
- `matplotlib`
- `scipy`
- `pyradiosky` - For `.skyh5` file support (point sources and healpix maps)
- `pyuvdata` - For beam FITS file support

Install all dependencies:
```bash
pip install -r requirements.txt
```

## Quick Start

### Basic Usage with LST Range

```bash
# Visualize sky strip from LST 1.25h to 5.75h at HERA location
python -m herastrip --location="-30.7,21.4" --lst-range="1.25-5.75" --frequency=80 --use-lst
```

### With Point Source Catalog

```bash
# Overlay point sources from a skyh5 catalog
python -m herastrip --location="-30.7,21.4" --lst-range="1.25-5.75" \
    --skyh5=./catalog.skyh5 --background=reference --use-lst
```

### With Beam Overlay

```bash
# Add HERA beam pattern centered at LST 18h
python -m herastrip --location="-30.7,21.4" --lst-range="1.25-5.75" \
    --skyh5=./catalog.skyh5 --background=reference --use-lst \
    --add-beam=./beam.fits --beam-lst=18
```

## Command Line Interface

```
python -m herastrip [OPTIONS]
```

### Required Arguments

| Argument | Description |
|----------|-------------|
| `--location LAT,LON` | Observer location as latitude,longitude in degrees (e.g., `-30.7,21.4` for HERA) |

**Plus one of:**
| Argument | Description |
|----------|-------------|
| `--lst-range START-END` | LST range in hours (e.g., `1.25-5.75`) |
| `--start TIME --duration SEC` | ISO time and duration in seconds |

### Optional Arguments

#### Sky Model Options

| Argument | Default | Description |
|----------|---------|-------------|
| `--frequency FREQ` | 76 | Observing frequency in MHz |
| `--model MODEL` | gsm2008 | Sky model: `gsm2008`, `gsm2016`, `lfss`, `haslam` |
| `--skyh5 PATH` | None | Path to `.skyh5` file (overrides `--model`) |
| `--fov DEGREES` | Auto | FOV radius in degrees (auto-calculated from HERA beam if not set) |

#### Display Options

| Argument | Default | Description |
|----------|---------|-------------|
| `--background MODE` | gsm | Background mode: `gsm` (full with hover), `reference` (GSM as reference, source colorbar), `none` (white) |
| `--scale SCALE` | log | Color scale for point sources: `log` or `linear` |
| `--use-lst` | False | Display x-axis as LST (hours) instead of RA (degrees) |
| `--max-sources N` | 1000 | Maximum number of point sources to display |

#### Beam Overlay Options

| Argument | Default | Description |
|----------|---------|-------------|
| `--add-beam PATH` | None | Path to beam FITS file (pyuvdata UVBeam format) |
| `--beam-lst HOURS` | Center | LST in hours where to center the beam |
| `--beam-vmin DB` | -40 | Minimum power level in dB for beam colormap |
| `--beam-vmax DB` | 0 | Maximum power level in dB for beam colormap |

#### Output Options

| Argument | Default | Description |
|----------|---------|-------------|
| `--output DIR` | None | Output directory for saving HTML plot |

## Sky Models

HERA Strip supports multiple diffuse sky models via [pygdsm](https://github.com/telegraphic/pygdsm):

| Model | Frequency Range | Description |
|-------|-----------------|-------------|
| `gsm2008` | 10 MHz - 100 GHz | Global Sky Model 2008 (de Oliveira-Costa et al.) |
| `gsm2016` | 10 MHz - 5 THz | Global Sky Model 2016 (Zheng et al.) |
| `lfss` | 10 - 408 MHz | LWA1 Low Frequency Sky Survey (Dowell et al.) |
| `haslam` | 10 MHz - 100 GHz | Haslam 408 MHz map with spectral scaling |

## Python API

### Basic Usage

```python
from astropy.coordinates import EarthLocation
from herastrip import HeraStripSimulator

# HERA location
location = EarthLocation(lat=-30.7, lon=21.4)

# Create simulator with LST range
simulator = HeraStripSimulator(
    location=location,
    frequency=80,           # MHz
    lst_range=(1.25, 5.75), # LST hours
    use_lst=True,           # Display in LST
    background_mode="gsm",  # Full GSM background
)

# Run and display
simulator.run_simulation()
```

### With Point Sources

```python
from herastrip import HeraStripSimulator

simulator = HeraStripSimulator(
    location=location,
    frequency=80,
    lst_range=(1.25, 5.75),
    skyh5_path="./catalog.skyh5",  # Point source catalog
    max_sources=500,               # Show top 500 brightest
    background_mode="reference",   # GSM as visual reference
    use_lst=True,
)

simulator.run_simulation(save_simulation_data=True, folder_path="./output")
```

### With Beam Overlay

```python
from herastrip import HeraStripSimulator

simulator = HeraStripSimulator(
    location=location,
    frequency=80,
    lst_range=(1.25, 5.75),
    skyh5_path="./catalog.skyh5",
    background_mode="reference",
    use_lst=True,
    beam_path="./NF_HERA_Vivaldi_efield_beam.fits",
    beam_lst=18.0,      # Center beam at LST 18h
    beam_vmin=-40,      # dB range for colormap
    beam_vmax=0,
)

simulator.run_simulation()
```

### Using Individual Components

```python
from herastrip import (
    SkyMapGenerator,
    PointSourceCatalog,
    BeamProcessor,
    Plotter,
    calculate_hera_fov_radius,
)
from astropy.coordinates import EarthLocation

# HERA location
location = EarthLocation(lat=-30.7, lon=21.4)

# Generate sky map
sky_gen = SkyMapGenerator(frequency=80, model="gsm2008")
projected_map = sky_gen.generate_projected_map(nside=1024)

# Load point sources
catalog = PointSourceCatalog("./catalog.skyh5", frequency=80)
sources = catalog.get_sources(max_sources=500)

# Load beam
beam = BeamProcessor("./beam.fits", frequency_mhz=80)
beam_data = beam.transform_to_radec(location, lst_hours=18.0)

# Calculate FOV for a given frequency
fov_radius = calculate_hera_fov_radius(frequency_mhz=80)
print(f"FOV radius at 80 MHz: {fov_radius:.1f}°")
```

## HERA Beam Physics

The FOV radius is automatically calculated using HERA's dish parameters:

```
FWHM = k × λ / D

Where:
  k = 1.17 (beam coefficient, calibrated to HERA measurements)
  λ = c / frequency (wavelength)
  D = 14m (HERA dish diameter)

Reference: Fagnoni et al. 2021, measured FWHM ~10° at 150 MHz
```

| Frequency | FWHM | FOV Radius |
|-----------|------|------------|
| 50 MHz | 28.1° | 14.0° |
| 80 MHz | 17.6° | 8.8° |
| 100 MHz | 14.0° | 7.0° |
| 150 MHz | 9.4° | 4.7° |
| 200 MHz | 7.0° | 3.5° |

## Output Description

### Plot Elements

1. **Background**: Diffuse sky model (Inferno colormap, 40th percentile threshold)
2. **Observable Strip**: Red/blue shaded region showing HERA's FOV during the observation
3. **Declination Lines**: Dotted horizontal lines at FOV boundaries with Dec labels
4. **Strip Boundaries**: Dashed vertical lines at LST/RA start and end
5. **Point Sources**: Blue-to-white colored dots (brighter = higher flux)
6. **Top 5 Sources**: Yellow highlighted sources with rank labels (1-5)
7. **Beam Overlay** (optional): RdBu_r colored hemisphere with -3dB and -10dB contours
8. **Colorbars**: Left (beam dB), Right (flux Jy or GSM brightness)

### Interactive Features

- **Hover**: Display coordinates and flux for point sources
- **Zoom**: Scroll to zoom, double-click to reset
- **Pan**: Click and drag to pan
- **Save**: Use Bokeh toolbar to save as PNG

## File Formats

### skyh5 Files (pyradiosky)

HERA Strip supports two types of `.skyh5` files:

1. **Point Source Catalogs** (`component_type="point"`)
   - Contains RA, Dec, and Stokes I flux for each source
   - Multiple frequencies supported

2. **HEALPix Maps** (`component_type="healpix"`)
   - Full-sky diffuse maps in HEALPix format
   - Supports RING or NESTED ordering

### Beam FITS Files (pyuvdata)

Beam files should be in UVBeam format with:
- E-field or power beam data
- Azimuth/Zenith angle coordinate system
- Multiple frequencies supported

## Module Architecture

```
herastrip/
├── __init__.py      # Package exports
├── __main__.py      # Entry point for python -m herastrip
├── main.py          # CLI argument parsing and orchestration
├── simulation.py    # HeraStripSimulator class, HERA beam physics
├── sky_model.py     # SkyMapGenerator, PointSourceCatalog, SkyH5MapGenerator
├── beam.py          # BeamProcessor for antenna beam overlay
└── plotting.py      # Plotter class, Bokeh visualization
```

### Key Classes

| Class | Module | Description |
|-------|--------|-------------|
| `HeraStripSimulator` | simulation.py | Main simulation orchestrator |
| `SkyMapGenerator` | sky_model.py | Generate projected maps from pygdsm models |
| `SkyH5MapGenerator` | sky_model.py | Load HEALPix maps from skyh5 files |
| `PointSourceCatalog` | sky_model.py | Load point sources from skyh5 files |
| `BeamProcessor` | beam.py | Load and transform beam patterns |
| `Plotter` | plotting.py | Create interactive Bokeh visualizations |

## Examples

### Example 1: Galactic Center Region

```bash
# View the Galactic Center (transits at LST ~17.75h)
python -m herastrip --location="-30.7,21.4" --lst-range="16-20" \
    --frequency=150 --use-lst --model=gsm2008
```

### Example 2: Point Sources with Beam

```bash
# Overlay GLEAM catalog with beam at Galactic Center
python -m herastrip --location="-30.7,21.4" --lst-range="1-6" \
    --skyh5=./gleam.skyh5 --background=reference --max-sources=300 \
    --use-lst --add-beam=./hera_beam.fits --beam-lst=18
```

### Example 3: Time-Based Observation

```bash
# 2-hour observation starting at specific UTC time
python -m herastrip --location="-30.7,21.4" \
    --start="2024-04-06T22:00:00" --duration=7200 --frequency=80
```

### Example 4: Save Output

```bash
python -m herastrip --location="-30.7,21.4" --lst-range="1.25-5.75" \
    --frequency=80 --use-lst --output=./plots/
# Saves to ./plots/sky_strip.html
```

## Coordinate Systems

### Right Ascension (RA) Mode
- X-axis: RA in degrees (-180° to 180°)
- Centered at RA = 0° (vernal equinox)

### Local Sidereal Time (LST) Mode (`--use-lst`)
- X-axis: LST in hours (displayed as 0h-24h)
- Internally centered at LST = 0h (-12h to 12h)
- LST = RA / 15 (hours = degrees / 15)

### Declination
- Y-axis: Dec in degrees (-90° to 90°)
- HERA at latitude -30.7° sees Dec from ~-90° to ~+60°

## Troubleshooting

### "No module named 'X'"
Install all required dependencies:
```bash
pip install -r requirements.txt
```

### Beam overlay not visible
- Check `--beam-lst` is within the plot's LST range
- Increase `--beam-vmin` (e.g., -30 instead of -40) for more visibility

### Plot appears blank
- Ensure frequency is within the model's valid range
- Check that skyh5 file exists and is readable

## References

- HERA: https://reionization.org/
- Fagnoni et al. 2021 - HERA beam measurements
- de Oliveira-Costa et al. 2008 - GSM2008
- Zheng et al. 2017 - GSM2016
- Dowell et al. 2017 - LFSS
- Haslam et al. 1982 - 408 MHz all-sky survey

## Author

**Kartik Mandar**
Email: kartik4321mandar@gmail.com

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
