"""Time helpers. Everything is stored as UTC; delivery dates and ranges are Amsterdam local time (docs 01 s.6)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

AMS = ZoneInfo("Europe/Amsterdam")


def now() -> datetime:
    return timezone.now()


def local_today(at: datetime | None = None) -> date:
    return (at or now()).astimezone(AMS).date()


def combine(day: date, at: time) -> datetime:
    """Local wall-clock date + time -> aware datetime (DST safe)."""
    return datetime.combine(day, at.replace(tzinfo=None), tzinfo=AMS)


def hhmm(at: time) -> str:
    return at.strftime("%H:%M")


def plus_days(day: date, n: int) -> date:
    return day + timedelta(days=n)
