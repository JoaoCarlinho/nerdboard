"""
Feature Extraction Script

CLI tool to extract features for ML model training.
Usage: python -m app.scripts.extract_features [--subject SUBJECT] [--all]
"""
import asyncio
import argparse
from datetime import datetime, timedelta
import sys

from app.services.feature_engineer import get_feature_engineer


async def extract_for_subject(subject: str, date: datetime = None):
    """Extract features for a single subject"""
    print(f"\n=== Extracting features for {subject} ===")

    engineer = get_feature_engineer()
    features = await engineer.extract_features_for_subject(subject, date)

    print(f"\nExtracted {len(features)} features:")
    for key, value in sorted(features.items()):
        if key not in ["subject", "reference_date"]:
            print(f"  {key}: {value}")

    print(f"\n✓ Features extracted and stored for {subject}")


async def extract_for_all_subjects(date: datetime = None):
    """Extract features for all subjects"""
    print("\n=== Extracting features for all subjects ===")

    engineer = get_feature_engineer()
    all_features = await engineer.extract_features_for_all_subjects(date)

    print(f"\n✓ Extracted features for {len(all_features)} subjects")

    # Summary
    if all_features:
        feature_count = len([k for k in all_features[0].keys()
                            if k not in ["subject", "reference_date"]])
        print(f"  Features per subject: {feature_count}")
        print(f"  Subjects: {', '.join([f['subject'] for f in all_features])}")


async def extract_historical_features(days_back: int = 30):
    """
    Extract features for historical dates to build training dataset.

    Args:
        days_back: Number of days to go back
    """
    print(f"\n=== Extracting historical features ({days_back} days) ===")

    engineer = get_feature_engineer()
    today = datetime.utcnow()

    for day_offset in range(days_back, 0, -1):
        reference_date = today - timedelta(days=day_offset)
        print(f"\nExtracting features for {reference_date.date()}...")

        all_features = await engineer.extract_features_for_all_subjects(reference_date)
        print(f"  ✓ {len(all_features)} subjects")

    print(f"\n✅ Historical feature extraction complete!")
    print(f"   {days_back} days × {len(all_features)} subjects = {days_back * len(all_features)} feature sets")


async def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Extract features for ML model")
    parser.add_argument(
        "--subject",
        "-s",
        help="Extract features for specific subject"
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Extract features for all subjects"
    )
    parser.add_argument(
        "--historical",
        "-hist",
        type=int,
        metavar="DAYS",
        help="Extract historical features for N days back"
    )
    parser.add_argument(
        "--date",
        "-d",
        help="Reference date (YYYY-MM-DD, default: today)"
    )

    args = parser.parse_args()

    # Parse date if provided
    reference_date = None
    if args.date:
        try:
            reference_date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print(f"ERROR: Invalid date format '{args.date}'. Use YYYY-MM-DD")
            sys.exit(1)

    # Execute based on args
    if args.historical:
        await extract_historical_features(args.historical)
    elif args.all:
        await extract_for_all_subjects(reference_date)
    elif args.subject:
        await extract_for_subject(args.subject, reference_date)
    else:
        print("ERROR: Specify --subject, --all, or --historical")
        parser.print_help()
        sys.exit(1)

    print("\n✅ Feature extraction complete!")


if __name__ == "__main__":
    asyncio.run(main())
