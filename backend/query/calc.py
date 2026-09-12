"""Arithmetic the model is not allowed to do itself.

`14:30 − 2h00 − 3h25` is where a fluent 09:35 instead of 09:05 costs a client
their flight. Thinking makes that more reliable; it does not make it certain.
"""
import re

_CLOCK = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


class Unknown(Exception):
    """A required input is missing. Refusing beats assuming a plausible number."""


def _minutes(t: str) -> int:
    m = _CLOCK.match((t or "").strip())
    if not m:
        raise Unknown(f"not a 24-hour clock time: {t!r}")
    return int(m.group(1)) * 60 + int(m.group(2))


def _hm(mins: int) -> str:
    return f"{mins // 60:02d}h{mins % 60:02d}"


def compute_departure(arrive_by: str, drive_hours, buffer_hours=2.0) -> dict:
    """When to leave to catch a flight, given the drive and the reporting buffer."""
    if drive_hours is None:
        raise Unknown("no drive time is recorded for this leg — ask, do not estimate")
    if buffer_hours is None:
        raise Unknown("no airport reporting buffer was given")
    flight = _minutes(arrive_by)
    drive = round(float(drive_hours) * 60)
    buffer_ = round(float(buffer_hours) * 60)
    depart = flight - buffer_ - drive
    return {
        "depart_by": f"{depart % 1440 // 60:02d}:{depart % 1440 % 60:02d}",
        "previous_day": depart < 0,
        "breakdown": f"{arrive_by} flight − {_hm(buffer_)} reporting − {_hm(drive)} drive",
    }
