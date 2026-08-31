"""Tests for the prescription-CSV schedule generator (STRETCH-001)."""

import pytest

from mesa.data.database import Database
from mesa.engine.schedule_gen import (
    ScheduleEntry,
    load_into_db,
    parse_prescription_csv,
)


def test_explicit_times():
    csv_text = "med_name,dose,times,frequency\nTylenol,2 tablets,08:00;20:00,\n"
    entries = parse_prescription_csv(csv_text)
    assert entries == [
        ScheduleEntry("tylenol", "08:00", "2 tablets"),
        ScheduleEntry("tylenol", "20:00", "2 tablets"),
    ]


def test_frequency_maps_to_default_slots():
    csv_text = "med_name,dose,times,frequency\nIbuprofen,1 tab,,3\n"
    entries = parse_prescription_csv(csv_text)
    assert [e.time_of_day for e in entries] == ["08:00", "14:00", "20:00"]
    assert all(e.med_name == "ibuprofen" for e in entries)


def test_explicit_times_take_priority_over_frequency():
    csv_text = "med_name,dose,times,frequency\nVitamin D,1,07:30,3\n"
    entries = parse_prescription_csv(csv_text)
    assert [e.time_of_day for e in entries] == ["07:30"]


def test_row_with_neither_times_nor_frequency_skipped():
    csv_text = "med_name,dose,times,frequency\nMystery,,,\n"
    assert parse_prescription_csv(csv_text) == []


def test_name_normalized_to_snake_case():
    csv_text = "med_name,dose,times,frequency\nVitamin D,1 tablet,20:00,\n"
    assert parse_prescription_csv(csv_text)[0].med_name == "vitamin_d"


def test_invalid_time_raises():
    with pytest.raises(ValueError, match="invalid time"):
        parse_prescription_csv("med_name,times\nTylenol,25:00\n")


def test_bad_frequency_raises():
    with pytest.raises(ValueError, match="frequency"):
        parse_prescription_csv("med_name,frequency\nTylenol,9\n")


def test_missing_header_raises():
    with pytest.raises(ValueError, match="med_name"):
        parse_prescription_csv("name,times\nTylenol,08:00\n")


def test_load_into_db():
    db = Database(":memory:")
    entries = parse_prescription_csv(
        "med_name,dose,times,frequency\nTylenol,2 tabs,08:00;20:00,\nVitamin D,1 tab,,1\n"
    )
    n = load_into_db(db, entries)
    assert n == 3
    assert len(db.get_schedule()) == 3
    assert {m["name"] for m in db.list_medications()} == {"tylenol", "vitamin_d"}
    db.close()


# The eight classes models/best.pt was trained on (v2, 2026-08-07). `tray` is a scene
# class, not a medication, so it is deliberately absent.
TRAINED_MED_CLASSES = {
    "advil", "ashwagandha", "bayer_aspirin", "cvs_allergy",
    "melatonin", "mylanta", "omeprazole", "vitamin_d3",
}


def test_station_csv_names_match_the_trained_classes():
    """Regression guard for the mismatch found 2026-08-27.

    examples/prescriptions.csv is a generic sample (Tylenol, Ibuprofen, ...) whose names
    match no trained class, so loading it leaves the schedule and the detector speaking
    different languages: a `taken` event never links to a scheduled dose and "did I take
    my advil" has nothing to match. The station CSV is the one MeSA actually runs on.
    """
    from pathlib import Path

    csv_path = Path(__file__).resolve().parent.parent / "examples" / "mesa-station.csv"
    entries = parse_prescription_csv(csv_path.read_text(encoding="utf-8"))
    names = {e.med_name for e in entries}

    assert names <= TRAINED_MED_CLASSES, f"not detectable: {sorted(names - TRAINED_MED_CLASSES)}"
    assert names == TRAINED_MED_CLASSES, f"never scheduled: {sorted(TRAINED_MED_CLASSES - names)}"


def test_station_csv_covers_the_day():
    from pathlib import Path

    csv_path = Path(__file__).resolve().parent.parent / "examples" / "mesa-station.csv"
    entries = parse_prescription_csv(csv_path.read_text(encoding="utf-8"))
    times = sorted(e.time_of_day for e in entries)
    assert times[0] < "12:00" and times[-1] > "18:00", "demo needs a next-dose most of the day"
    assert all(e.dose for e in entries), "every dose should be speakable"
