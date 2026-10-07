"""Briefing Drafter and Reply Drafter.

Both are templates on purpose. They only rearrange fields that already passed
validation, so neither can introduce a fact that isn't in the request. Anything
unknown is shown as a question for a person, never filled in.

Nothing here sends anything. Drafts land in the review queue for a human.
"""
from __future__ import annotations

from .common import UNKNOWN

LABELS = {
    "event_name": "Event", "date": "Date", "location": "Location", "format": "Format",
    "moderator": "Moderator", "audience_size": "Audience", "requestor_name": "Requested by",
    "requestor_org": "Organization", "ask": "The ask",
}
ASK_FOR = {
    "event_name": "the name of the event",
    "date": "the confirmed date",
    "location": "the city and venue",
    "format": "the format you have in mind (keynote, panel, fireside chat, etc.)",
    "audience_size": "the expected audience size",
    "requestor_name": "the best contact for logistics",
    "requestor_org": "the organization hosting",
    "ask": "what exactly you'd like the CEO to do, and for how long",
}


def briefing(item) -> str:
    f = item.fields
    lines = [f"### {f.get('event_name', UNKNOWN)}", ""]
    for key, label in LABELS.items():
        v = f.get(key, UNKNOWN)
        lines.append(f"- **{label}:** " + ("⚠️ UNKNOWN, confirm before accepting" if v == UNKNOWN else v))
    for note in item.notes:
        lines.append(f"- **Note:** {note}")
    open_qs = item.validation.get("gaps", []) + item.validation.get("soft_gaps", [])
    if open_qs:
        lines += ["", "**Open questions:** " + "; ".join(ASK_FOR[g] for g in open_qs if g in ASK_FOR)]
    return "\n".join(lines)


def reply(item) -> str:
    f = item.fields
    name = f.get("requestor_name", UNKNOWN)
    greeting = f"Hi {name.split()[0]}," if name != UNKNOWN else "Hello,"
    event = f.get("event_name", UNKNOWN)
    event_ref = f"the {event}" if event != UNKNOWN else "your event"
    missing = item.validation.get("gaps", []) + item.validation.get("soft_gaps", [])
    missing = [ASK_FOR[g] for g in missing if g in ASK_FOR and g != "requestor_name"]

    body = [greeting, "", f"Thank you for thinking of us for {event_ref}."]
    if missing:
        body.append("So we can review it properly, could you share:")
        body += [f"- {m}" for m in missing]
    else:
        body.append("We're reviewing the request and will follow up once we've had a chance to discuss it.")
    body += ["", "Best regards,", "[Your name]"]
    return "\n".join(body)
