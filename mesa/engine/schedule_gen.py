"""Schedule generator (STRETCH-001).

Turn a prescription list (CSV) into medication schedule entries and load them into the DB.

CSV columns (header row required):
    med_name   - medication name (required)
    dose       - free text, e.g. "1 tablet" (optional)
    times      - explicit "HH:MM" times, semicolon-separated, e.g. "08:00;20:00" (optional)
    frequency  - integer doses/day; used only when `times` is empty (optional)

If both `times` and `frequency` are empty the row is skipped. Pure parsing
(:func:`parse_prescription_csv`) is separated from DB loading so it's unit-testable.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

# Default clock slots when only a per-day frequency is given.
DEFAULT_SLOTS: dict[int, list[str]] = {
    1: ["09:00"],
    2: ["09:00", "21:00"],
    3: ["08:00", "14:00", "20:00"],
    4: ["08:00", "12:00", "16:00", "20:00"],
}

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


@dataclass(frozen=True)
class ScheduleEntry:
    med_name: str
    time_of_day: str
    dose: str | None = None


def _normalize_med(name: str) -> str:
    return re.sub(r"\s+", "_", name.strip().lower())


def _valid_time(t: str) -> bool:
    return bool(_TIME_RE.match(t.strip()))


def parse_prescription_csv(text: str) -> list[ScheduleEntry]:
    """Parse prescription CSV text into schedule entries. Raises ValueError on bad rows."""
    entries: list[ScheduleEntry] = []
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or "med_name" not in reader.fieldnames:
        raise ValueError("CSV must have a header row with a 'med_name' column")

    for i, row in enumerate(reader, start=2):  # line 2 = first data row
        name = (row.get("med_name") or "").strip()
        if not name:
            continue
        med = _normalize_med(name)
        dose = (row.get("dose") or "").strip() or None
        raw_times = (row.get("times") or "").strip()
        freq = (row.get("frequency") or "").strip()

        if raw_times:
            times = [t.strip() for t in raw_times.split(";") if t.strip()]
            for t in times:
                if not _valid_time(t):
                    raise ValueError(f"line {i}: invalid time '{t}' (use HH:MM)")
        elif freq:
            try:
                n = int(freq)
            except ValueError:
                raise ValueError(f"line {i}: frequency must be an integer, got '{freq}'")
            if n not in DEFAULT_SLOTS:
                raise ValueError(f"line {i}: unsupported frequency {n} (supported: 1-4)")
            times = DEFAULT_SLOTS[n]
        else:
            continue  # nothing to schedule for this row

        for t in times:
            entries.append(ScheduleEntry(med_name=med, time_of_day=t, dose=dose))
    return entries


def load_into_db(db, entries: list[ScheduleEntry]) -> int:
    """Register medications + schedule rows. Returns the number of schedule rows added."""
    for e in entries:
        db.add_medication(e.med_name)
        db.add_schedule(e.med_name, e.time_of_day, e.dose)
    return len(entries)
