import argparse
import os
from astropy.coordinates import EarthLocation
from astropy.time import Time

# Fix the import to use relative import since we're in the same package
from .simulation import HeraStripSimulator

def main():
    parser = argparse.ArgumentParser(description="HERA Strip Simulation")
    parser.add_argument("--location", type=str, required=True, help="Observer location as 'lat,lon'")
    parser.add_argument("--start", type=str, required=True, help="Observation start time (ISO format, e.g., 2025-04-06T00:00:00)")
    parser.add_argument("--duration", type=float, required=True, help="Total simulation duration in seconds")
    parser.add_argument("--frequency", type=float, default=76, help="Frequency in MHz (default: 76)")
    parser.add_argument("--output", type=str, help="Output directory for saving simulation results")
    args = parser.parse_args()
    
    # Parse the observer's location
    lat, lon = map(float, args.location.split(","))
    location = EarthLocation(lat=lat, lon=lon)
    obstime_start = Time(args.start)
    
    # Initialize and run the simulation
    simulator = HeraStripSimulator(
        location=location,
        obstime_start=obstime_start,
        total_seconds=args.duration,
        frequency=args.frequency
    )
    
    save_output = args.output is not None
    if save_output:
        os.makedirs(args.output, exist_ok=True)
    
    simulator.run_simulation(save_simulation_data=save_output, folder_path=args.output)
    
    if save_output:
        print(f"Simulation results saved to {args.output}")

if __name__ == "__main__":
    main()
