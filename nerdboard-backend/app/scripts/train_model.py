"""
Model Training Script

Trains the capacity shortage prediction model.
Usage: python -m app.scripts.train_model [--horizon DAYS] [--tune]
"""
import asyncio
import argparse
import sys

from app.ml.shortage_predictor import get_shortage_predictor


async def train_shortage_model(horizon_days: int = 14, tune: bool = False):
    """
    Train the shortage prediction model.

    Args:
        horizon_days: Prediction horizon in days
        tune: Whether to perform hyperparameter tuning
    """
    print(f"\n=== Training Shortage Prediction Model ===")
    print(f"Horizon: {horizon_days} days")
    print(f"Hyperparameter tuning: {'enabled' if tune else 'disabled'}")

    predictor = get_shortage_predictor()

    # Prepare training data
    print("\n1. Preparing training data...")
    X, y = await predictor.prepare_training_data(horizon_days)

    if len(X) == 0:
        print("\nERROR: No training data available.")
        print("Run 'python -m app.scripts.extract_features --historical 30' first")
        sys.exit(1)

    print(f"   ✓ Training samples: {len(X)}")
    print(f"   ✓ Features: {len(X.columns)}")
    print(f"   ✓ Positive cases (shortages): {y.sum()} ({y.sum()/len(y)*100:.1f}%)")

    # Train model
    print("\n2. Training model...")
    metrics = predictor.train_model(X, y, tune_hyperparameters=tune)

    print(f"\n   ✓ Model trained successfully!")
    print(f"   Accuracy:  {metrics['accuracy']:.2%}")
    print(f"   Precision: {metrics['precision']:.2%}")
    print(f"   Recall:    {metrics['recall']:.2%}")
    print(f"   F1 Score:  {metrics['f1_score']:.2%}")

    # Save model
    print("\n3. Saving model...")
    predictor.save_model()
    print(f"   ✓ Model saved to {predictor.model_path}")

    # Feature importance
    print("\n4. Top 10 important features:")
    importances = predictor.get_feature_importance()
    sorted_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:10]
    for i, (feature, importance) in enumerate(sorted_features, 1):
        print(f"   {i}. {feature}: {importance:.3f}")

    print("\n✅ Model training complete!")
    print(f"\nModel ready for predictions at {predictor.model_path}")


async def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Train capacity shortage prediction model")
    parser.add_argument(
        "--horizon",
        "-h",
        type=int,
        default=14,
        help="Prediction horizon in days (default: 14)"
    )
    parser.add_argument(
        "--tune",
        "-t",
        action="store_true",
        help="Enable hyperparameter tuning (slower but better accuracy)"
    )

    args = parser.parse_args()

    await train_shortage_model(args.horizon, args.tune)


if __name__ == "__main__":
    asyncio.run(main())
