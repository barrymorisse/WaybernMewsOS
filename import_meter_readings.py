#!/usr/bin/env python3
"""
One-off import: loads historical meter readings from Google Sheet CSV exports
into the Waybern Mews database.

Usage (from the project root):
    python import_meter_readings.py --elec path/to/electricity.csv
    python import_meter_readings.py --elec path/to/electricity.csv --water path/to/water.csv
    python import_meter_readings.py --elec path/to/electricity.csv --dry-run
"""

import argparse
import csv
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models.meter_readings import MeterReading

MONTH_NAMES = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}

ELEC_LABEL_TO_FIELD = {
    "Unit 1": "elec_unit_1",
    "Unit 2": "elec_unit_2",
    "Unit 3": "elec_unit_3",
    "Unit 4": "elec_unit_4",
    "Unit 5": "elec_unit_5",
    "Public Lighting": "elec_public_lighting",
    "Total": "elec_total",
}

WATER_LABEL_TO_FIELD = {
    "Unit 1": "water_unit_1",
    "Unit 2": "water_unit_2",
    "Unit 3": "water_unit_3",
    "Unit 4": "water_unit_4",
    "Unit 5": "water_unit_5",
    "Total": "water_total",
}


def parse_reading_date(date_str: str) -> date:
    return datetime.strptime(date_str.strip(), "%d %B %Y").date()


def parse_month_label(label: str) -> tuple[int, int]:
    parts = label.strip().split()
    return int(parts[1]), MONTH_NAMES[parts[0]]  # (year, month)


def parse_sheet(csv_path: str, label_map: dict) -> dict[tuple[int, int], dict]:
    """Returns {(year, month): {'reading_date': date, field_name: float, ...}}"""
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    # Row index 2: alternating 'Reading' / 'Usage' labels
    # Row index 3: alternating month names ('April 2025') / dates ('30 April 2025')
    type_row = rows[2]
    date_row = rows[3]

    # Build column → (year, month, reading_date) for all Reading columns.
    # Col 1 is the initial/seed reading with no date in the sheet — treated as March 2025.
    col_info: dict[int, tuple[int, int, date]] = {}
    for i, col_type in enumerate(type_row):
        if col_type.strip() != "Reading":
            continue
        if i == 1:
            # Initial reading column: assign to March 2025, date 31 March 2025
            col_info[i] = (2025, 3, date(2025, 3, 31))
            continue
        date_str = date_row[i] if i < len(date_row) else ""
        if not date_str.strip():
            continue
        month_label = date_row[i - 1] if i > 0 else ""
        if not month_label.strip():
            continue
        reading_date = parse_reading_date(date_str)
        year, month = parse_month_label(month_label)
        col_info[i] = (year, month, reading_date)

    results: dict[tuple[int, int], dict] = {}
    for row in rows[4:]:
        label = row[0].strip() if row else ""
        if label not in label_map:
            continue
        field_name = label_map[label]
        for col_idx, (year, month, reading_date) in col_info.items():
            key = (year, month)
            if key not in results:
                results[key] = {"reading_date": reading_date}
            raw = row[col_idx].strip() if col_idx < len(row) else ""
            results[key][field_name] = float(raw) if raw else None

    return results


def merge(elec: dict, water: dict) -> dict:
    merged = {}
    for key in sorted(set(elec) | set(water)):
        entry = {}
        entry.update(elec.get(key, {}))
        water_entry = water.get(key, {})
        # Don't let water overwrite the reading_date from elec
        for k, v in water_entry.items():
            if k != "reading_date" or "reading_date" not in entry:
                entry[k] = v
        merged[key] = entry
    return merged


def run(merged: dict, dry_run: bool) -> None:
    db = SessionLocal()
    inserted = skipped = 0
    try:
        for (year, month), fields in sorted(merged.items()):
            existing = db.query(MeterReading).filter_by(year=year, month=month).first()
            if existing:
                print(f"  SKIP   {year}-{month:02d} — already in database (id={existing.id})")
                skipped += 1
                continue
            reading = MeterReading(year=year, month=month, **fields)
            tag = "DRY-RUN" if dry_run else "INSERT"
            print(f"  {tag}  {year}-{month:02d}  (reading date: {fields.get('reading_date')})")
            inserted += 1
            if not dry_run:
                db.add(reading)
        if not dry_run:
            db.commit()
    finally:
        db.close()
    action = "would insert" if dry_run else "inserted"
    print(f"\nDone: {inserted} {action}, {skipped} skipped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import historical meter readings from CSV.")
    parser.add_argument("--elec", metavar="PATH", help="Electricity CSV file")
    parser.add_argument("--water", metavar="PATH", help="Water CSV file")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report without writing to the database")
    args = parser.parse_args()

    if not args.elec and not args.water:
        parser.error("Provide at least one of --elec or --water.")

    elec_data: dict = {}
    water_data: dict = {}

    if args.elec:
        print(f"Parsing electricity: {args.elec}")
        elec_data = parse_sheet(args.elec, ELEC_LABEL_TO_FIELD)
        print(f"  Found {len(elec_data)} months.")

    if args.water:
        print(f"Parsing water: {args.water}")
        water_data = parse_sheet(args.water, WATER_LABEL_TO_FIELD)
        print(f"  Found {len(water_data)} months.")

    merged = merge(elec_data, water_data)
    print(f"\n{len(merged)} month(s) to process:\n")
    run(merged, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
