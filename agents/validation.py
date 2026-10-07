"""Validation Agent: checks the Intake Agent's work before anything is drafted.

It never trusts the extraction. Every value has to trace back to the request.

  errors  Something in the extraction looks invented or stale. The item is
          BLOCKED: nothing is drafted until a person fixes the fields.
  gaps    A field the team needs isn't in the request. The item goes out as
          NEEDS INFO, with a drafted reply asking the requestor for it.
"""
from __future__ import annotations

import datetime as dt
import re

from .common import FIELDS, STALE_MARKERS, UNKNOWN, Request, norm, numbers, sentences

REQUIRED = ["event_name", "date", "requestor_org", "ask"]
NICE_TO_HAVE = ["location", "format", "audience_size", "requestor_name"]
STOPWORDS = {"the", "and", "for", "our", "with", "your", "a", "an", "of", "on", "in", "at", "to"}

MONTH_NUM = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}


def _grounded(value: str, source: str) -> bool:
    """At least 60% of the value's meaningful words must appear in the source."""
    if value == "Virtual":
        return bool(re.search(r"virtual|livestream|online", source, re.I))
    words = [w for w in norm(value).split() if w not in STOPWORDS and len(w) > 1]
    if not words:
        return True
    src = set(norm(source).split())
    return sum(w in src for w in words) / len(words) >= 0.6


def _stale_numbers(value: str, source: str) -> list[str]:
    """Numbers that only appear in sentences about another event or a past year."""
    stale = []
    for n in numbers(value):
        homes = [s for s in sentences(source) if n in numbers(s)]
        if homes and all(STALE_MARKERS.search(s) for s in homes):
            stale.append(n)
    return stale


def _parse_date(value: str) -> dt.date | None:
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2})(?:\s*[-–]\s*\d{1,2})?,\s+(\d{4})", value)
    if not m or m.group(1).lower() not in MONTH_NUM:
        return None
    try:
        return dt.date(int(m.group(3)), MONTH_NUM[m.group(1).lower()], int(m.group(2)))
    except ValueError:
        return None


def run(req: Request, fields: dict, today: dt.date) -> dict:
    errors, gaps = [], []
    source = req.text

    for f in FIELDS:
        v = fields.get(f, UNKNOWN)
        if v == UNKNOWN:
            continue
        if not _grounded(v, source):
            errors.append(f"{f}: '{v}' doesn't appear in the request. Possible fabrication.")
        invented = [n for n in numbers(v) if n not in numbers(source)]
        if invented:
            errors.append(f"{f}: number(s) {', '.join(invented)} aren't in the request.")
        stale = _stale_numbers(v, source)
        if stale:
            errors.append(f"{f}: {', '.join(stale)} comes from a past or different event.")

    d = _parse_date(fields.get("date", UNKNOWN))
    if fields.get("date", UNKNOWN) != UNKNOWN and d is None:
        errors.append(f"date: couldn't read '{fields['date']}' as a date.")
    elif d and d < today:
        errors.append(f"date: {fields['date']} is in the past.")

    for f in REQUIRED:
        if fields.get(f, UNKNOWN) == UNKNOWN:
            gaps.append(f)
    soft_gaps = [f for f in NICE_TO_HAVE if fields.get(f, UNKNOWN) == UNKNOWN]

    status = "blocked" if errors else ("needs_info" if gaps else "ready")
    return {"status": status, "errors": errors, "gaps": gaps, "soft_gaps": soft_gaps,
            "event_date": d.isoformat() if d else None}
