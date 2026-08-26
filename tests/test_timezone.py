from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.services.quiz_service import current_study_date


@pytest.mark.parametrize(
    ("instant", "expected"),
    [
        (datetime(2026, 1, 1, 23, 30, tzinfo=UTC), date(2026, 1, 2)),
        (datetime(2026, 7, 1, 22, 30, tzinfo=UTC), date(2026, 7, 2)),
    ],
)
def test_prague_study_day_respects_winter_and_summer_offsets(
    instant: datetime, expected: date
) -> None:
    assert current_study_date(Settings(app_timezone="Europe/Prague"), instant) == expected


def test_study_day_uses_configured_timezone() -> None:
    instant = datetime(2026, 1, 1, 23, 30, tzinfo=UTC)
    assert current_study_date(Settings(app_timezone="UTC"), instant) == date(2026, 1, 1)


def test_unknown_timezone_is_rejected_at_startup() -> None:
    with pytest.raises(ValidationError, match="Unknown IANA timezone"):
        Settings(app_timezone="Not/A-Timezone")


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        current_study_date(Settings(), datetime(2026, 1, 1, 12, 0))
