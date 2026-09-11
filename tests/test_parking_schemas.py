"""Parking schema validation tests (no DB)."""

import pytest
from pydantic import ValidationError

from Schemas.parking import (
    AllocationListQueryParams,
    ParkingAllocateRequest,
    ParkingEntryRequest,
    ParkingExitRequest,
    ParkingRefundRequest,
    ParkingRevokeRequest,
    ParkingSlotCreate,
    ParkingTransferRequest,
    ParkingZoneCreate,
    ParkingZoneUpdate,
    VehicleCreate,
    VehicleUpdate,
    VisitorParkingCreate,
)

VALID_UUID = "00000000-0000-0000-0000-000000000001"
VALID_UUID_2 = "00000000-0000-0000-0000-000000000002"


def test_zone_create_defaults():
    body = ParkingZoneCreate(code="B1", name="Basement A")
    assert body.zoneType == "basement"
    assert body.isVisitorAllowed is True
    assert body.monthlyFeeMinor == 0


def test_zone_create_normalizes_code_and_type():
    body = ParkingZoneCreate(code=" bas-a ", name="Basement", zoneType="Open")
    assert body.code == "BAS-A"
    assert body.zoneType == "open"


def test_zone_update_invalid_type():
    with pytest.raises(ValidationError):
        ParkingZoneUpdate(zoneType="underground")


def test_slot_create_normalizes():
    body = ParkingSlotCreate(
        zoneId=VALID_UUID, slotCode=" a-01 ", vehicleTypesAllowed="Car, Bike, EV"
    )
    assert body.slotCode == "A-01"
    assert body.vehicleTypesAllowed == "car,bike,ev"
    assert body.slotCategory == "standard"


def test_slot_create_invalid_vehicle_type():
    with pytest.raises(ValidationError):
        ParkingSlotCreate(zoneId=VALID_UUID, slotCode="A-01", vehicleTypesAllowed="truck")


def test_vehicle_create_normalizes_number():
    body = VehicleCreate(vehicleNumber=" mh12ab1234 ", vehicleType="Car", residentId=VALID_UUID)
    assert body.vehicleNumber == "MH12AB1234"
    assert body.vehicleType == "car"


def test_vehicle_update_status():
    body = VehicleUpdate(status="Blocked")
    assert body.status == "blocked"
    with pytest.raises(ValidationError):
        VehicleUpdate(status="sold")


def test_allocate_temporary_requires_end_date():
    with pytest.raises(ValidationError):
        ParkingAllocateRequest(
            slotId=VALID_UUID,
            residentId=VALID_UUID,
            allocationType="temporary",
            startDate="2099-01-01",
        )


def test_allocate_date_range():
    with pytest.raises(ValidationError):
        ParkingAllocateRequest(
            slotId=VALID_UUID,
            residentId=VALID_UUID,
            startDate="2099-01-10",
            endDate="2099-01-01",
        )


def test_transfer_date_validation():
    with pytest.raises(ValidationError):
        ParkingTransferRequest(
            allocationId=VALID_UUID,
            newSlotId=VALID_UUID_2,
            startDate="2099-02-01",
            endDate="2099-01-01",
        )


def test_revoke_reason_required():
    with pytest.raises(ValidationError):
        ParkingRevokeRequest(allocationId=VALID_UUID, reason="   ")


def test_entry_requires_identifier():
    with pytest.raises(ValidationError):
        ParkingEntryRequest()


def test_entry_normalizes_code():
    body = ParkingEntryRequest(parkingCode=" abc123 ")
    assert body.parkingCode == "ABC123"


def test_exit_requires_identifier():
    with pytest.raises(ValidationError):
        ParkingExitRequest()


def test_visitor_parking_defaults():
    body = VisitorParkingCreate(vehicleNumber="MH14CD5678")
    assert body.vehicleType == "car"
    assert body.vehicleNumber == "MH14CD5678"


def test_refund_requires_target():
    with pytest.raises(ValidationError):
        ParkingRefundRequest(reason="duplicate")


def test_allocation_list_query_aliases():
    query = AllocationListQueryParams.model_validate(
        {"residentId": VALID_UUID, "slotId": VALID_UUID_2}
    )
    assert str(query.resident_id) == VALID_UUID
    assert str(query.slot_id) == VALID_UUID_2
