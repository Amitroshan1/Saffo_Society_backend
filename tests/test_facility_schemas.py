"""Amenities schema validation tests (no DB)."""

import pytest
from pydantic import ValidationError

from Schemas.facility import (
    FacilityBookingCreate,
    FacilityCreate,
    FacilityUpdate,
    BookingAdminUpdate,
    BookingCancelRequest,
    BookingCheckinRequest,
    BookingListQueryParams,
    BookingRejectRequest,
    MaintenanceBlockCreate,
    RefundRequest,
)

VALID_UUID = "00000000-0000-0000-0000-000000000001"


def test_amenity_create_defaults():
    body = FacilityCreate(name="Clubhouse", category="clubhouse")
    assert body.capacity == 1
    assert body.isPaid is False
    assert body.availableDays == "0123456"


def test_amenity_create_paid_requires_price():
    with pytest.raises(ValidationError):
        FacilityCreate(name="Hall", category="party_hall", isPaid=True, pricePerSlot=0)


def test_amenity_create_normalizes_category():
    body = FacilityCreate(name="Gym", category="Swimming-Pool")
    assert body.category == "swimming_pool"


def test_amenity_update_status_validation():
    body = FacilityUpdate(status="Maintenance")
    assert body.status == "maintenance"
    with pytest.raises(ValidationError):
        FacilityUpdate(status="something")


def test_booking_create_time_window():
    body = FacilityBookingCreate(
        amenityId=VALID_UUID, bookingDate="2099-01-01", startTime="10:00", endTime="11:00", guestCount=1
    )
    assert body.startTime == "10:00"
    with pytest.raises(ValidationError):
        FacilityBookingCreate(
            amenityId=VALID_UUID, bookingDate="2099-01-01", startTime="11:00", endTime="10:00"
        )


def test_booking_reject_reason_required():
    with pytest.raises(ValidationError):
        BookingRejectRequest(reason="   ")


def test_booking_cancel_reason_optional():
    body = BookingCancelRequest(reason="  Not needed  ")
    assert body.reason == "Not needed"


def test_booking_checkin_code_normalized():
    body = BookingCheckinRequest(bookingCode=" abc123 ")
    assert body.bookingCode == "ABC123"


def test_booking_admin_update_payment_status():
    body = BookingAdminUpdate(paymentStatus="Paid", notes="  ok  ")
    assert body.paymentStatus == "paid"
    assert body.notes == "ok"
    with pytest.raises(ValidationError):
        BookingAdminUpdate(paymentStatus="wrong")


def test_maintenance_block_range_validation():
    with pytest.raises(ValidationError):
        MaintenanceBlockCreate(
            amenityId=VALID_UUID, startDate="2099-01-10", endDate="2099-01-01", reason="Repair"
        )


def test_refund_request_normalizes_reason():
    body = RefundRequest(bookingId=VALID_UUID, reason="  duplicate  ")
    assert body.reason == "duplicate"


def test_booking_list_query_aliases():
    query = BookingListQueryParams.model_validate({"amenityId": VALID_UUID, "from": "2099-01-01"})
    assert str(query.amenity_id) == VALID_UUID
