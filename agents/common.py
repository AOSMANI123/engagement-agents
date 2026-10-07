"""Shared types and text helpers used by every agent."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

FIELDS = [
    "event_name", "date", "location", "format", "moderator",
    "audience_size", "requestor_name", "requestor_org", "ask",
]
UNKNOWN = "UNKNOWN"

# Words a model might use instead of UNKNOWN. All of them mean "not stated".
BLANK_WORDS = {"unknown", "tbd", "n/a", "na", "none", "not specified", "not stated",
               "not provided", "not given", "to be confirmed", "pending", ""}

# Sentences about other events or past years. Facts in them don't belong to this request.
STALE_MARKERS = re.compile(r"\b(last year|previous year|sold out|no need to)\b", re.I)


def is_blank(value) -> bool:
    if value is None:
        return True
    v = str(value).strip().lower()
    return v in BLANK_WORDS or v.startswith(("not specified", "tbd", "unknown"))


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def numbers(s: str) -> list[str]:
    return re.findall(r"\d+", str(s).replace(",", ""))


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


@dataclass
class Request:
    id: str
    text: str

    @property
    def subject(self) -> str:
        m = re.search(r"^Subject:\s*(.+)$", self.text, re.M)
        return m.group(1).strip() if m else ""

    @property
    def body(self) -> str:
        """The request itself. For a forwarded email, only the original message."""
        marker = re.search(r"-{3,}\s*Forwarded message\s*-{3,}", self.text, re.I)
        return self.text[marker.end():] if marker else self.text


@dataclass
class Item:
    """One engagement request as it moves through the pipeline."""
    request: Request
    fields: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    validation: dict = field(default_factory=dict)
    triage: dict = field(default_factory=dict)
    briefing: str = ""
    reply_draft: str = ""
    status: str = "new"  # new -> ready | needs_info | blocked
