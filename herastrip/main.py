import argparse
import os
from astropy.coordinates import EarthLocation
from astropy.time import Time

# Fix the import to use relative import since we're in the same package
from .simulation import HeraStripSimulator

def main():
    parser = argparse.ArgumentParser(description="HERA Strip Simulation")
    parser.add_argument("--location", type=str, required=True, help="Observer location as 'lat,lon'")
    parser.add_argument("--start", type=str, help="Observation start time (ISO format, e.g., 2025-04-06T00:00:00)")
    parser.add_argument("--duration", type=float, help="Total simulation duration in seconds")
    parser.add_argument(
        "--lst-range",
        type=str,
        help="LST range as 'start-end' in hours (e.g., '1.25-5.75' or '17.5-22.3'). Alternative to --start/--duration"
    )
    parser.add_argument("--frequency", type=float, default=76, help="Frequency in MHz (default: 76)")
    parser.add_argument(
        "--model",
        type=str,
        default="gsm2008",
        choices=["gsm2008", "gsm2016", "lfss", "haslam"],
        help="Sky model to use: gsm2008 (10MHz-100GHz), gsm2016 (10MHz-5THz), lfss (10-408MHz), haslam (408MHz scaled). Default: gsm2008"
    )
    parser.add_argument(
        "--skyh5",
        type=str,
        help="Path to a .skyh5 file (pyradiosky format). If provided, overrides --model"
    )
    parser.add_argument(
        "--fov",
        type=float,
        default=None,
        help="FOV radius in degrees. If not provided, calculated from HERA beam (~10° FWHM at 150 MHz, scales with frequency)"
    )
    parser.add_argument(
        "--max-sources",
        type=int,
        default=1000,
        help="Maximum number of point sources to display (brightest first). Default: 1000"
    )
    parser.add_argument(
        "--no-background",
        action="store_true",
        help="(Deprecated) Use --background=none instead. Show sources only without diffuse background"
    )
    parser.add_argument(
        "--background",
        type=str,
        default="gsm",
        choices=["gsm", "none", "reference"],
        help="Background mode: 'gsm' (full GSM map with hover), 'none' (white, sources only), 'reference' (GSM as visual reference, source colorbar). Default: gsm"
    )
    parser.add_argument(
        "--scale",
        type=str,
        default="log",
        choices=["log", "linear"],
        help="Color scale for point sources: 'log' (logarithmic) or 'linear'. Default: log"
    )
    parser.add_argument(
        "--use-lst",
        action="store_true",
        help="Display x-axis as LST (Local Sidereal Time) in hours instead of RA in degrees"
    )
    parser.add_argument("--output", type=str, help="Output directory for saving simulation results")
    parser.add_argument(
        "--add-beam",
        type=str,
        help="Path to a beam FITS file (pyuvdata UVBeam format) to overlay on the sky map"
    )
    parser.add_argument(
        "--beam-vmin",
        type=float,
        default=-40,
        help="Minimum power level in dB for beam colormap (default: -40)"
    )
    parser.add_argument(
        "--beam-vmax",
        type=float,
        default=0,
        help="Maximum power level in dB for beam colormap (default: 0)"
    )
    parser.add_argument(
        "--beam-lst",
        type=float,
        default=None,
        help="LST in hours where to center the beam (default: center of strip)"
    )
    args = parser.parse_args()

    # Parse the observer's location
    lat, lon = map(float, args.location.split(","))
    location = EarthLocation(lat=lat, lon=lon)

    # Handle deprecated --no-background flag
    background_mode = args.background
    if args.no_background:
        background_mode = "none"

    # Determine mode: LST range or time-based
    lst_range = None
    obstime_start = None
    total_seconds = None

    if args.lst_range:
        # Parse LST range (e.g., "1.25-5.75")
        try:
            lst_start_str, lst_end_str = args.lst_range.split("-", 1)
            # Handle negative numbers (e.g., "-1.5-5.75" means start=-1.5, end=5.75)
            if args.lst_range.startswith("-"):
                # First number is negative
                parts = args.lst_range[1:].split("-", 1)
                lst_start = -float(parts[0])
                lst_end = float(parts[1])
            else:
                lst_start = float(lst_start_str)
                lst_end = float(lst_end_str)
            lst_range = (lst_start, lst_end)
            print(f"Using LST range: {lst_start:.2f}h to {lst_end:.2f}h")
        except ValueError:
            parser.error("--lst-range must be in format 'start-end' (e.g., '1.25-5.75')")
    elif args.start and args.duration:
        obstime_start = Time(args.start)
        total_seconds = args.duration
    else:
        parser.error("Either --lst-range OR both --start and --duration are required")

    # Initialize and run the simulation
    simulator = HeraStripSimulator(
        location=location,
        obstime_start=obstime_start,
        total_seconds=total_seconds,
        frequency=args.frequency,
        fov_radius_deg=args.fov,
        model=args.model,
        skyh5_path=args.skyh5,
        max_sources=args.max_sources,
        background_mode=background_mode,
        color_scale=args.scale,
        use_lst=args.use_lst,
        lst_range=lst_range,
        beam_path=args.add_beam,
        beam_vmin=args.beam_vmin,
        beam_vmax=args.beam_vmax,
        beam_lst=args.beam_lst,
    )
    
    save_output = args.output is not None
    if save_output:
        os.makedirs(args.output, exist_ok=True)
    
    simulator.run_simulation(save_simulation_data=save_output, folder_path=args.output)
    
    if save_output:
        print(f"Simulation results saved to {args.output}")

if __name__ == "__main__":
    main()
