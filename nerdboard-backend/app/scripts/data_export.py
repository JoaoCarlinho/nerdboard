"""
Data Export Script

Exports entire dataset to JSON/CSV format for backup and demo scenarios.
Usage: python -m app.scripts.data_export --output data.json.gz
"""
import asyncio
import json
import gzip
import argparse
from datetime import datetime
from pathlib import Path
from sqlalchemy import text

from app.database import AsyncSessionLocal


TABLES_TO_EXPORT = [
    "enrollments",
    "tutors",
    "sessions",
    "health_metrics",
    "capacity_snapshots",
    "simulation_state",
    "data_quality_log"
]


async def export_table(table_name: str) -> list:
    """
    Export all records from a table.

    Args:
        table_name: Name of table to export

    Returns:
        list: All records as dictionaries
    """
    async with AsyncSessionLocal() as session:
        query = text(f"SELECT * FROM {table_name}")
        result = await session.execute(query)

        # Convert rows to dictionaries
        columns = result.keys()
        records = []
        for row in result.fetchall():
            record = {}
            for col, val in zip(columns, row):
                # Convert non-JSON-serializable types
                if isinstance(val, datetime):
                    record[col] = val.isoformat()
                elif hasattr(val, '__iter__') and not isinstance(val, str):
                    # Handle arrays
                    record[col] = list(val) if val else []
                else:
                    record[col] = val
            records.append(record)

        return records


async def export_all_data(output_file: str, compress: bool = True):
    """
    Export all data to JSON file (AC-1, AC-6).

    Args:
        output_file: Path to output file
        compress: Whether to compress with gzip (default True)
    """
    print(f"Starting data export to {output_file}...")

    # Export all tables
    data = {}
    total_records = 0

    for table in TABLES_TO_EXPORT:
        print(f"Exporting {table}...", end=" ")
        records = await export_table(table)
        data[table] = records
        total_records += len(records)
        print(f"{len(records)} records")

    # Create export package
    export_data = {
        "metadata": {
            "export_time": datetime.utcnow().isoformat(),
            "version": "1.0",
            "tables": TABLES_TO_EXPORT,
            "total_records": total_records
        },
        "data": data
    }

    # Write to file
    json_str = json.dumps(export_data, indent=2)

    if compress and output_file.endswith(".gz"):
        with gzip.open(output_file, 'wt', encoding='utf-8') as f:
            f.write(json_str)
        print(f"\n✓ Export complete: {output_file} (compressed)")
    else:
        with open(output_file, 'w') as f:
            f.write(json_str)
        print(f"\n✓ Export complete: {output_file}")

    # Show file size
    file_size = Path(output_file).stat().st_size / (1024 * 1024)  # MB
    print(f"  File size: {file_size:.2f} MB")
    print(f"  Total records: {total_records}")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Export nerdboard database to JSON")
    parser.add_argument(
        "--output",
        "-o",
        default="data_export.json.gz",
        help="Output file path (default: data_export.json.gz)"
    )
    parser.add_argument(
        "--no-compress",
        action="store_true",
        help="Disable gzip compression"
    )

    args = parser.parse_args()

    # Run async export
    asyncio.run(export_all_data(args.output, compress=not args.no_compress))


if __name__ == "__main__":
    main()
