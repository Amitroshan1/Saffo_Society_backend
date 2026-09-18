"""Facility slot-window helpers (no DB)."""

from datetime import date
from types import SimpleNamespace
from uuid import UUID

from Services.facility_helpers import (
    count_overlapping_bookings,
    generate_time_windows,
    generated_slot_to_dict,
)

AMENITY_ID = UUID("00000000-0000-0000-0000-000000000001")
SOCIETY_ID = UUID("00000000-0000-0000-0000-000000000002")
MONDAY = date(2026, 9, 21)
TUESDAY = date(2026, 9, 22)


def _amenity(**overrides):
    data = dict(
        id=AMENITY_ID,
        society_id=SOCIETY_ID,
        operating_hours_start="06:00",
        operating_hours_end="09:00",
        slot_duration_minutes=60,
        available_days="0123456",
        capacity=2,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def test_generate_time_windows_hourly():
    windows = generate_time_windows(_amenity(), MONDAY)
    assert windows == [("06:00", "07:00"), ("07:00", "08:00"), ("08:00", "09:00")]


def test_generate_time_windows_skips_closed_weekday():
    amenity = _amenity(available_days="0")
    assert generate_time_windows(amenity, TUESDAY) == []
    assert generate_time_windows(amenity, MONDAY) == [
        ("06:00", "07:00"),
        ("07:00", "08:00"),
        ("08:00", "09:00"),
    ]


def test_count_overlapping_bookings():
    bookings = [
        SimpleNamespace(start_time="07:00", end_time="08:00"),
        SimpleNamespace(start_time="08:00", end_time="09:00"),
    ]
    assert count_overlapping_bookings(bookings, "07:00", "08:00") == 1
    assert count_overlapping_bookings(bookings, "07:30", "08:30") == 2
    assert count_overlapping_bookings(bookings, "06:00", "07:00") == 0


def test_generated_slot_to_dict_keeps_api_contract():
    slot = generated_slot_to_dict(
        _amenity(),
        query_date=MONDAY,
        start_time="06:00",
        end_time="07:00",
        booked_count=1,
    )
    assert slot["id"] is None
    assert slot["amenityId"] == str(AMENITY_ID)
    assert slot["startTime"] == "06:00"
    assert slot["endTime"] == "07:00"
    assert slot["capacity"] == 2
    assert slot["bookedCount"] == 1
    assert slot["available"] == 1
    assert slot["isBlocked"] is False


def test_generated_slot_blocked_has_zero_available():
    slot = generated_slot_to_dict(
        _amenity(),
        query_date=MONDAY,
        start_time="06:00",
        end_time="07:00",
        booked_count=0,
        is_blocked=True,
        block_reason="Floor repair",
    )
    assert slot["isBlocked"] is True
    assert slot["available"] == 0
    assert slot["blockReason"] == "Floor repair"
