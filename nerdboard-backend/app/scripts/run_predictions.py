"""
Prediction Runner Script

Manually trigger prediction generation for testing and demo purposes.
Usage: python -m app.scripts.run_predictions [--subject SUBJECT] [--horizon HORIZON]
"""
import asyncio
import argparse
import sys

from app.services.prediction_service import get_prediction_service


async def run_predictions_for_subject(subject: str, horizon: str = "2week"):
    """Run predictions for a specific subject and horizon"""
    print(f"\n=== Generating {horizon} prediction for {subject} ===")

    service = get_prediction_service()
    prediction = await service.generate_prediction_for_subject(subject, horizon)

    if prediction:
        print(f"\n✓ Prediction created: {prediction['prediction_id']}")
        print(f"  Shortage probability: {prediction['shortage_probability']*100:.1f}%")
        print(f"  Days until shortage: {prediction['days_until_shortage']}")
        print(f"  Severity: {prediction['severity']}")
        print(f"  Confidence: {prediction['confidence_score']:.0f}% ({prediction['confidence_level']})")
        print(f"  Priority score: {prediction['priority_score']:.1f}")
        print(f"  Critical: {'YES' if prediction['is_critical'] else 'no'}")

        print(f"\n  Top contributing factors:")
        for i, feature in enumerate(prediction['top_features'][:3], 1):
            print(f"    {i}. {feature['readable_description']}")

        print(f"\n  Explanation:")
        print(f"  {prediction['explanation_text'][:200]}...")
    else:
        print("\n  No prediction created (no significant change detected)")


async def run_predictions_for_all():
    """Run predictions for all subjects and all horizons"""
    print("\n=== Generating predictions for all subjects ===")

    service = get_prediction_service()
    summary = await service.generate_predictions_for_all_subjects()

    print(f"\n✅ Prediction generation complete!")
    print(f"  Subjects analyzed: {summary['subjects_analyzed']}")
    print(f"  Predictions created: {summary['predictions_created']}")
    print(f"  Duration: {summary['duration_seconds']:.1f}s")

    print(f"\n  Predictions by subject:")
    for subject, count in summary['predictions_by_subject'].items():
        print(f"    {subject}: {count} predictions")


async def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Generate capacity shortage predictions")
    parser.add_argument(
        "--subject",
        "-s",
        help="Generate predictions for specific subject"
    )
    parser.add_argument(
        "--horizon",
        "-h",
        choices=["2week", "4week", "6week", "8week"],
        default="2week",
        help="Prediction horizon (default: 2week)"
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Generate predictions for all subjects and all horizons"
    )

    args = parser.parse_args()

    if args.all:
        await run_predictions_for_all()
    elif args.subject:
        await run_predictions_for_subject(args.subject, args.horizon)
    else:
        print("ERROR: Specify --subject or --all")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
