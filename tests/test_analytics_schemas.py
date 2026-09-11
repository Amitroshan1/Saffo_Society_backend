"""Schema tests for Phase 16 analytics."""

from Schemas.analytics import (
    ExportCreateRequest,
    PreferencesUpdateRequest,
    RebuildRequest,
    ScheduleCreateRequest,
)


def test_export_create_defaults():
    body = ExportCreateRequest(reportKey="billing.outstanding")
    assert body.format == "csv"
    assert body.filters == {}


def test_schedule_create():
    body = ScheduleCreateRequest(
        name="Monthly outstanding",
        reportKey="billing.outstanding",
        frequency="monthly",
        recipientRoles=["finance"],
    )
    assert body.format == "csv"
    assert body.frequency == "monthly"


def test_preferences_partial():
    body = PreferencesUpdateRequest(favoriteReportKeys=["billing.collections"])
    assert body.favoriteReportKeys == ["billing.collections"]
    assert body.defaultFilters is None


def test_rebuild_optional_dates():
    body = RebuildRequest()
    assert body.fromDate is None
    assert body.toDate is None
