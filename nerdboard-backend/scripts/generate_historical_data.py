#!/usr/bin/env python
"""
Historical Data Generation CLI

Generates 12 months of realistic historical data for the nerdboard platform.
Supports configuration via YAML file or command-line arguments (CLI takes precedence).
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime
import yaml

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.data_generator import DataGenerator


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Warning: Config file not found at {config_path}, using defaults")
        return {}
    except yaml.YAMLError as e:
        print(f"Error parsing config file: {e}")
        sys.exit(1)


def parse_date(date_str: str) -> datetime:
    """Parse date string in YYYY-MM-DD format"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


def parse_subjects(subjects_str: str) -> list:
    """Parse comma-separated subject list"""
    return [s.strip() for s in subjects_str.split(',') if s.strip()]


async def run_generation(args):
    """Execute data generation with given arguments"""
    # Load config file
    config_path = Path(__file__).parent.parent / "config" / "data_generator_config.yaml"
    config = load_config(str(config_path))

    # Parse dates (CLI args override config)
    start_date = parse_date(args.start_date) if args.start_date else parse_date(config.get("start_date", "2024-01-01"))
    end_date = parse_date(args.end_date) if args.end_date else parse_date(config.get("end_date", "2024-12-31"))

    # Parse numeric params (CLI args override config)
    num_tutors = args.num_tutors if args.num_tutors is not None else config.get("num_tutors", 150)
    num_students = args.num_students if args.num_students is not None else config.get("num_students", 500)

    # Parse subjects list (CLI args override config)
    subjects_list = None
    if args.subjects_list:
        subjects_list = parse_subjects(args.subjects_list)
    elif "subjects_list" in config:
        subjects_list = config["subjects_list"]

    # Validate parameters
    if start_date >= end_date:
        print("Error: start_date must be before end_date")
        sys.exit(1)

    if num_tutors < 100:
        print("Warning: num_tutors < 100 may violate AC: 5 (minimum 100 tutors required)")

    if num_students < 1:
        print("Error: num_students must be positive")
        sys.exit(1)

    # Print configuration
    print("=" * 60)
    print("Historical Data Generator")
    print("=" * 60)
    print(f"Date Range: {start_date.date()} to {end_date.date()}")
    print(f"Tutors: {num_tutors}")
    print(f"Students: {num_students}")
    print(f"Subjects: {len(subjects_list) if subjects_list else 'default (13)'}")
    print("=" * 60)

    if args.dry_run:
        print("\n[DRY RUN MODE] Would generate:")
        duration_days = (end_date - start_date).days + 1
        estimated_enrollments = duration_days * 5  # ~5 enrollments per day
        estimated_sessions = max(10000, estimated_enrollments * 8)
        print(f"  - ~{estimated_enrollments:,} enrollments")
        print(f"  - ~{estimated_sessions:,} sessions")
        print(f"  - {num_tutors} tutors")
        print(f"  - {num_students} students")
        print(f"  - Health metrics for 25 customers")
        print("\nNo database writes performed.")
        return

    # Initialize generator
    generator = DataGenerator(
        start_date=start_date,
        end_date=end_date,
        num_tutors=num_tutors,
        num_students=num_students,
        subjects_list=subjects_list,
    )

    # Execute generation
    try:
        results = await generator.generate_all_data()

        # Print summary
        print("\n" + "=" * 60)
        print("Generation Complete!")
        print("=" * 60)
        print(f"Duration: {results['duration_seconds']:.2f} seconds")
        print(f"Tutors: {results['tutors_count']:,}")
        print(f"Enrollments: {results['enrollments_count']:,}")
        print(f"Sessions: {results['sessions_count']:,}")
        print(f"Health Metrics: {results['health_metrics_count']:,}")
        print(f"Capacity Snapshots: {results['capacity_snapshots_count']:,}")
        print("=" * 60)

        # Verify acceptance criteria
        print("\nAcceptance Criteria Verification:")
        print(f"  AC: 2 (12 months in <30s): {'✓ PASS' if results['duration_seconds'] < 30 else '✗ FAIL'} ({results['duration_seconds']:.2f}s)")
        print(f"  AC: 5 (100+ tutors): {'✓ PASS' if results['tutors_count'] >= 100 else '✗ FAIL'} ({results['tutors_count']})")
        print(f"  AC: 6 (10,000+ sessions): {'✓ PASS' if results['sessions_count'] >= 10000 else '✗ FAIL'} ({results['sessions_count']:,})")

    except Exception as e:
        print(f"\nError during data generation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Generate 12 months of realistic historical data for nerdboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default configuration
  python generate_historical_data.py

  # Override specific parameters
  python generate_historical_data.py --num-tutors 200 --num-students 1000

  # Custom date range
  python generate_historical_data.py --start-date 2024-06-01 --end-date 2025-05-31

  # Dry run to preview generation plan
  python generate_historical_data.py --dry-run

  # Custom subject list
  python generate_historical_data.py --subjects-list "Math,Science,English,SAT Prep"
        """
    )

    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date in YYYY-MM-DD format (default: from config file or 2024-01-01)",
    )

    parser.add_argument(
        "--end-date",
        type=str,
        help="End date in YYYY-MM-DD format (default: from config file or 2024-12-31)",
    )

    parser.add_argument(
        "--num-tutors",
        type=int,
        help="Number of tutors to generate (default: from config file or 150, minimum 100 recommended)",
    )

    parser.add_argument(
        "--num-students",
        type=int,
        help="Number of students to generate (default: from config file or 500)",
    )

    parser.add_argument(
        "--subjects-list",
        type=str,
        help="Comma-separated list of subjects (default: from config file or built-in list)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview generation plan without writing to database",
    )

    args = parser.parse_args()

    # Run async generation
    asyncio.run(run_generation(args))


if __name__ == "__main__":
    main()
