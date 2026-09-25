"""Regression tests for revenue dashboard bugs (ASSIGNMENT)."""
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.cache import make_revenue_cache_key
from app.services.reservations import money_quantize, local_month_bounds
from app.api.v1.dashboard import _money_for_response


def test_cache_key_includes_tenant_isolation():
    """Client B must not share Client A's Redis key for the same property_id."""
    key_a = make_revenue_cache_key("tenant-a", "prop-001")
    key_b = make_revenue_cache_key("tenant-b", "prop-001")
    assert key_a == "revenue:tenant-a:prop-001"
    assert key_b == "revenue:tenant-b:prop-001"
    assert key_a != key_b


def test_paris_month_boundary_includes_utc_late_february_checkin():
    """
    res-tz-1: 2024-02-29 23:30 UTC == 2024-03-01 00:30 Europe/Paris
    must fall inside March in property-local bounds.
    """
    start, end = local_month_bounds(2024, 3, "Europe/Paris")
    check_in_utc = datetime(2024, 2, 29, 23, 30, tzinfo=ZoneInfo("UTC"))
    check_in_paris = check_in_utc.astimezone(ZoneInfo("Europe/Paris"))
    assert start <= check_in_paris < end

    # Naive UTC March filter (the old bug) would exclude this instant:
    naive_utc_start = datetime(2024, 3, 1)
    assert check_in_utc.replace(tzinfo=None) < naive_utc_start


def test_money_quantize_avoids_cent_drift():
    """333.333 + 333.333 + 333.334 → 1000.00 when summed then rounded once."""
    total = Decimal("333.333") + Decimal("333.333") + Decimal("333.334")
    assert money_quantize(total) == Decimal("1000.00")

    # Rounding each line then summing loses a cent (the finance bug pattern).
    rounded_each = sum(
        (money_quantize(Decimal(x)) for x in ("333.333", "333.333", "333.334")),
        Decimal("0"),
    )
    assert rounded_each == Decimal("999.99")


def test_dashboard_money_response_stable():
    assert _money_for_response("2250.000") == 2250.0
    assert _money_for_response("1000.00") == 1000.0
    assert _money_for_response(Decimal("333.333") + Decimal("333.333") + Decimal("333.334")) == 1000.0
