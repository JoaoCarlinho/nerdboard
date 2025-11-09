#!/usr/bin/env python
"""
Run Simulation CLI

Local testing tool for real-time simulation.
Supports --interval, --start-paused, --advance-days, --dry-run flags.
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime
import yaml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.data_simulator import DataSimulator


def load_config(config_path: str) -> dict:
    """Load simulation configuration from YAML"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Warning: Config file not found at {config_path}, using defaults")
        return {}
    except yaml.YAMLError as e:
        print(f"Error parsing config file: {e}")
        sys.exit(1)


async def run_simulation(args):
    """Execute simulation with given arguments"""
    # Load config
    config_path = Path(__file__).parent.parent / "config" / "simulation_config.yaml"
    config = load_config(str(config_path))

    # Parse parameters (CLI args override config)
    interval = args.interval if args.interval else config.get("event_interval_seconds", 300)
    enrollments_per_cycle = config.get("enrollments_per_cycle_base", 5)
    sessions_per_cycle = config.get("sessions_per_cycle_base", 10)

    # Print configuration
    print("=" * 60)
    print("Real-Time Simulation")
    print("=" * 60)
    print(f"Event Interval: {interval} seconds ({interval//60} minutes)")
    print(f"Enrollments per cycle: {enrollments_per_cycle}")
    print(f"Sessions per cycle: {sessions_per_cycle}")
    print(f"Start paused: {args.start_paused}")
    print("=" * 60)

    if args.dry_run:
        print("\n[DRY RUN MODE] Configuration validated. No simulation started.")
        return

    # Initialize simulator
    simulator = DataSimulator(
        event_interval_seconds=interval,
        enrollments_per_cycle=enrollments_per_cycle,
        sessions_per_cycle=sessions_per_cycle,
    )

    try:
        if args.advance_days:
            # Fast-forward mode
            print(f"\nFast-forwarding {args.advance_days} days...")
            result = await simulator.advance_simulation(days=args.advance_days)
            print("\n" + "=" * 60)
            print("Fast-Forward Complete!")
            print("=" * 60)
            print(f"Days advanced: {result['days_advanced']}")
            print(f"New time: {result['new_time']}")
            print(f"Enrollments created: {result['events_generated']['enrollments']:,}")
            print(f"Sessions created: {result['events_generated']['sessions']:,}")
            print(f"Tutors updated: {result['events_generated']['tutor_updates']}")
            print(f"Duration: {result['duration_seconds']:.2f} seconds")
            print("=" * 60)

        else:
            # Normal simulation mode
            if not args.start_paused:
                await simulator.start_simulation()
                print("\nSimulation running... Press Ctrl+C to stop.")
            else:
                print("\nSimulation initialized in paused state.")
                print("Use API endpoints to control simulation:")
                print("  POST /api/v1/simulation/start")
                print("  POST /api/v1/simulation/pause")
                print("  POST /api/v1/simulation/advance")
                print("  GET /api/v1/simulation/status")

            # Keep running until interrupted
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\n\nShutting down simulation...")
                await simulator.shutdown()
                print("Simulation stopped.")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Run real-time data simulation for nerdboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings (5-minute intervals)
  python run_simulation.py

  # Custom interval (1 minute)
  python run_simulation.py --interval 60

  # Start paused (control via API)
  python run_simulation.py --start-paused

  # Fast-forward 7 days
  python run_simulation.py --advance-days 7

  # Dry run to validate configuration
  python run_simulation.py --dry-run
        """
    )

    parser.add_argument(
        "--interval",
        type=int,
        help="Event generation interval in seconds (default: 300 / 5 minutes)",
    )

    parser.add_argument(
        "--start-paused",
        action="store_true",
        help="Start simulation in paused state (control via API)",
    )

    parser.add_argument(
        "--advance-days",
        type=int,
        help="Fast-forward simulation by N days and exit",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without starting simulation",
    )

    args = parser.parse_args()

    # Run async simulation
    asyncio.run(run_simulation(args))


if __name__ == "__main__":
    main()
