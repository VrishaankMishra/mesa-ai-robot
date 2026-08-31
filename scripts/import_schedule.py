#!/usr/bin/env python3
"""Import a prescription CSV into the medication schedule (STRETCH-001).

    python scripts/import_schedule.py examples/prescriptions.csv

Reads the CSV, generates schedule entries, and writes them to events.db.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mesa.data.database import Database
from mesa.engine.schedule_gen import load_into_db, parse_prescription_csv


def main() -> int:
    p = argparse.ArgumentParser(description="Import prescription CSV -> schedule")
    p.add_argument("csv", help="path to prescription CSV")
    p.add_argument("--db", default="events.db")
    p.add_argument("--replace", action="store_true",
                   help="clear the existing schedule first (re-import without duplicating)")
    args = p.parse_args()

    text = Path(args.csv).read_text(encoding="utf-8")
    entries = parse_prescription_csv(text)
    db = Database(args.db)
    if args.replace:
        print(f"Cleared {db.clear_schedule()} existing schedule entries.")
    n = load_into_db(db, entries)
    db.close()
    print(f"Loaded {n} schedule entries from {args.csv} into {args.db}.")
    for e in entries:
        print(f"  {e.time_of_day}  {e.med_name}  ({e.dose or '-'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
