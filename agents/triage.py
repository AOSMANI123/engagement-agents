"""Triage Agent: proposes a priority using an explicit, readable rubric.

The rubric is deliberately simple so anyone can audit why an item scored the way
it did. It proposes; a person sets the final priority.
"""
from __future__ import annotations

import datetime as dt

from .common import FIELDS, UNKNOWN, numbers

HIGH_REACH_FORMATS = {"keynote", "commencement address", "fireside chat", "interview"}
MID_REACH_FORMATS = {"panel", "roundtable", "conversation", "after-dinner conversation"}


def _audience(value: str) -> int | None:
    nums = [int(n) for n in numbers(value)]
    return max(nums) if nums else None


def run(fields: dict, validation: dict, today: dt.date) -> dict:
    score, reasons = 0, []

    size = _audience(fields.get("audience_size", UNKNOWN))
    if size is None:
        pts, why = 5, "audience size unknown"
    elif size >= 1000:
        pts, why = 30, f"large audience ({size:,})"
    elif size >= 300:
        pts, why = 20, f"mid-size audience ({size:,})"
    elif size >= 100:
        pts, why = 10, f"small audience ({size:,})"
    else:
        pts, why = 5, f"very small audience ({size:,})"
    score += pts
    reasons.append(f"+{pts} {why}")

    fmt = fields.get("format", UNKNOWN).lower()
    if fmt in HIGH_REACH_FORMATS:
        pts, why = 25, f"high-visibility format ({fmt})"
    elif fmt in MID_REACH_FORMATS:
        pts, why = 15, f"shared-stage format ({fmt})"
    elif fmt == "unknown":
        pts, why = 5, "format unknown"
    else:
        pts, why = 10, f"lighter-touch format ({fmt})"
    score += pts
    reasons.append(f"+{pts} {why}")

    if validation.get("event_date"):
        days = (dt.date.fromisoformat(validation["event_date"]) - today).days
        if days >= 90:
            pts, why = 20, f"{days} days of lead time"
        elif days >= 30:
            pts, why = 10, f"only {days} days of lead time"
        else:
            pts, why = 0, f"{days} days out, tight to prepare"
    else:
        pts, why = 5, "date not set"
    score += pts
    reasons.append(f"+{pts} {why}")

    known = sum(1 for f in FIELDS if fields.get(f, UNKNOWN) != UNKNOWN)
    pts = round(25 * known / len(FIELDS))
    score += pts
    reasons.append(f"+{pts} {known}/{len(FIELDS)} details provided")

    priority = "High" if score >= 70 else "Medium" if score >= 45 else "Low"
    return {"score": score, "priority": priority, "reasons": reasons}
