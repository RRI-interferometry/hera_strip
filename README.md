# HERA Strip

HERA Strip is an open source Python project that simulates and visualizes the diffuse radio sky using a global sky model. It leverages pygdsm, healpy, astropy, and Bokeh to create interactive sky maps over time from a given observer location.

## Installation

You can install HERA Strip in several ways:

### From PyPI (recommended)

```bash
pip install hera_strip
```

### From source

Clone the repository and install:

```bash
git clone https://github.com/yourusername/hera_strip.git
cd hera_strip
pip install .
```

For development:

```bash
git clone https://github.com/yourusername/hera_strip.git
cd hera_strip
pip install -e .
```

## Usage

### Command Line Interface

HERA Strip provides a command-line interface:

```bash
# Basic usage
hera-strip --location "-30.7,21.4" --start "2023-04-06T00:00:00" --duration 86400 --frequency 76

# Save output to a directory
hera-strip --location "-30.7,21.4" --start "2023-04-06T00:00:00" --duration 86400 --frequency 76 --output "./output"
```

### Python API

```python
from astropy.coordinates import EarthLocation
from astropy.time import Time
from herastrip import HeraStripSimulator

# Create a simulator instance
location = EarthLocation(lat=-30.7, lon=21.4)  # HERA location
obstime = Time("2023-04-06T00:00:00")
simulator = HeraStripSimulator(
    location=location,
    obstime_start=obstime,
    total_seconds=86400,  # 24 hours
    frequency=76  # MHz
)

# Run the simulation
simulator.run_simulation(save_simulation_data=True, folder_path="./output")
```

## Development

### Building the package

```bash
pip install build
python -m build
```

### Running tests

```bash
pip install pytest
pytest
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
