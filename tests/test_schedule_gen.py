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
