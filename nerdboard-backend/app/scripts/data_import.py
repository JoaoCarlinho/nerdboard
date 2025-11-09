"""
Data Import Script

Imports dataset from JSON file to restore database state.
Usage: python -m app.scripts.data_import --input data.json.gz --confirm
"""
import asyncio
import json
import gzip
import argparse
from datetime import datetime
from sqlalchemy import text

from app.database import AsyncSessionLocal


async def clear_table(table_name: str):
    """Clear all records from a table"""
    async with AsyncSessionLocal() as session:
        await session.execute(text(f"DELETE FROM {table_name}"))
        await session.commit()
    print(f"  Cleared {table_name}")


async def import_table(table_name: str, records: list):
    """
    Import records into a table.

    Args:
        table_name: Name of table to import into
        records: List of record dictionaries
    """
    if not records:
        print(f"  {table_name}: No records to import")
        return

    async with AsyncSessionLocal() as session:
        # Get column names from first record
        columns = list(records[0].keys())
        placeholders = ", ".join([f":{col}" for col in columns])
        columns_str = ", ".join(columns)

        insert_query = text(
            f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
        )

        # Import in batches for performance
        batch_size = 100
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            for record in batch:
                await session.execute(insert_query, record)

            await session.commit()

        print(f"  {table_name}: Imported {len(records)} records")


async def import_all_data(input_file: str, confirm: bool = False):
    """
    Import all data from JSON file (AC-2, AC-3).

    Args:
        input_file: Path to input file
        confirm: Whether user confirmed the operation
    """
    if not confirm:
        print("ERROR: Import requires --confirm flag to prevent accidental data loss")
        print("This operation will DELETE ALL existing data!")
        return

    print(f"Starting data import from {input_file}...")

    # Read file
    if input_file.endswith(".gz"):
        with gzip.open(input_file, 'rt', encoding='utf-8') as f:
            import_data = json.load(f)
    else:
        with open(input_file, 'r') as f:
            import_data = json.load(f)

    # Show metadata
    metadata = import_data.get("metadata", {})
    print(f"\nImport metadata:")
    print(f"  Export time: {metadata.get('export_time')}")
    print(f"  Version: {metadata.get('version')}")
    print(f"  Total records: {metadata.get('total_records')}")

    # Clear all tables (in reverse order to handle foreign keys)
    print("\nClearing existing data...")
    tables = metadata.get("tables", [])
    for table in reversed(tables):
        await clear_table(table)

    # Import data (in correct order for foreign keys)
    print("\nImporting data...")
    data = import_data.get("data", {})

    # Import in dependency order
    import_order = [
        "tutors",          # No dependencies
        "simulation_state", # No dependencies
        "enrollments",     # No dependencies
        "sessions",        # Depends on tutors
        "health_metrics",  # No dependencies
        "capacity_snapshots", # No dependencies
        "data_quality_log" # No dependencies
    ]

    for table in import_order:
        if table in data:
            await import_table(table, data[table])

    print(f"\n✓ Import complete!")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Import nerdboard database from JSON")
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Input file path"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm data deletion and import (REQUIRED)"
    )

    args = parser.parse_args()

    # Run async import
    asyncio.run(import_all_data(args.input, confirm=args.confirm))


if __name__ == "__main__":
    main()
