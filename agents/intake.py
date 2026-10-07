"""Intake Agent: reads a request and extracts the nine briefing fields.

Two modes:
  rules  Deterministic pattern matching. No API key, runs anywhere. A baseline,
         not a finished product: it misses phrasings it hasn't seen.
  llm    Claude, using prompts/intake.md. Needs ANTHROPIC_API_KEY.

Both modes follow the same rule: if a field isn't stated for THIS event, it is
UNKNOWN. A blank is better than a guess.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .common import FIELDS, STALE_MARKERS, UNKNOWN, Request, is_blank, sentences

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "intake.md"

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE_RE = re.compile(rf"\b((?:{MONTHS})\s+\d{{1,2}}(?:\s*[-–]\s*\d{{1,2}})?,\s+\d{{4}})")
NAME = r"([A-Z][a-z]+(?:\s[A-Z][a-z'\-]+){1,2})"
WORD = r"[A-Z][A-Za-z'&\-]*"
EVENT_NOUNS = ("Forum|Summit|Dinner|Week|Gala|Ceremony|Podcast|Conference|Festival|"
               "Awards|Commencement|Roundtable|Retreat|Expo|Symposium|Livestream|livestream")
EVENT_RE = re.compile(
    rf"((?:{WORD}\s(?:(?:of|for|and|on)\s)?){{0,5}}(?:{EVENT_NOUNS})"
    rf"(?:\s(?:for|of)\s(?!(?:{MONTHS}|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b){WORD}(?:\s{WORD}){{0,3}})?)"
)
FORMATS = ["commencement address", "fireside chat", "video message", "keynote", "panel",
           "roundtable", "interview", "Q&A", "after-dinner conversation", "conversation",
           "workshop", "address"]
CITY_RE = re.compile(r"\bin ([A-Z][a-zA-Z.]+(?:\s[A-Z][a-zA-Z.]+)*),\s([A-Z]{2})\b")
ASK_CUTS = [" at our ", " at the ", " on ", " during ", " for our ", " in "]


# ---------- helpers ----------

def _weight(sentence: str) -> int:
    """Rank sentences: the ask is about 'your CEO'; past or cancelled events are not."""
    w = 0
    if re.search(r"\byour CEO\b", sentence, re.I):
        w += 2
    if STALE_MARKERS.search(sentence):
        w -= 5
    return w


def _ranked(text: str, include_stale: bool = False) -> list[str]:
    ss = [s for s in sentences(text) if include_stale or _weight(s) >= 0]
    return sorted(ss, key=lambda s: -_weight(s))  # stable: keeps order within a weight


def _first(pattern, ss: list[str], group: int = 1) -> str | None:
    for s in ss:
        m = re.search(pattern, s)
        if m:
            return m.group(group).strip()
    return None


# ---------- field extractors ----------

def _event_name(req: Request) -> str:
    for pool in (_ranked(req.body), [req.subject], _ranked(req.body, include_stale=True)):
        for s in pool:
            m = EVENT_RE.search(s)
            if m:
                return re.sub(r"^(The|Our|Your)\s", "", m.group(1)).strip()
    return UNKNOWN


def _date(req: Request) -> str:
    return _first(DATE_RE, _ranked(req.body)) or UNKNOWN


def _location(req: Request) -> str:
    ss = _ranked(req.body)
    if any(re.search(r"\b(fully virtual|virtual|livestream(ed)?|online)\b", s, re.I) for s in ss):
        return "Virtual"
    for s in ss:
        m = CITY_RE.search(s)
        if m:
            return f"{m.group(1)}, {m.group(2)}"
    return UNKNOWN


def _format(req: Request) -> str:
    for s in _ranked(req.body):
        for f in FORMATS:
            if re.search(rf"\b{re.escape(f)}\b", s, re.I):
                return f
    return UNKNOWN


def _moderator(req: Request) -> tuple[str, list[str]]:
    ss = _ranked(req.body)
    notes = []
    patterns = [
        rf"[Mm]oderated by (?:journalist\s+)?{NAME}",
        rf"[Mm]oderator:\s*{NAME}",
        rf"\b[Hh]ost,?\s{NAME}",
        rf"\bboard chair,?\s{NAME}",
        rf"{NAME},? (?:would|will) (?:host|moderate|ask the questions)",
    ]
    for p in patterns:
        found = _first(p, ss)
        if found:
            return found, notes
    # Someone who only introduces the CEO is not a moderator. Keep it as a note.
    intro = _first(rf"(?:[Pp]resident|[Ee]mcee,?|[Hh]ost,?)?\s?{NAME},? (?:would|will) introduce", ss)
    if intro:
        notes.append(f"{intro} will introduce the CEO (introducer, not a moderator).")
    return UNKNOWN, notes


def _audience(req: Request) -> str:
    ss = _ranked(req.body)
    patterns = [
        r"(\d[\d,]*\s*[-–]\s*\d[\d,]*)\s+(?:people|attendees|guests|in the room)",
        r"\b(?i:about|roughly|approximately|around|nearly)\s+(\d[\d,]*)",
        r"\bfor (\d[\d,]*)\s+(?:[a-z\-]+\s){0,3}?(?:executives|attendees|guests|people|"
        r"recipients|students|graduates|members|leaders)",
        r"(\d[\d,]*)\s+attendees",
    ]
    for p in patterns:
        found = _first(p, ss)
        if found:
            return found
    return UNKNOWN


def _requestor(req: Request) -> tuple[str, str]:
    body = req.body
    m = re.search(r"^From:\s*([^,\n]+),\s*[^,\n]+,\s*(.+)$", body, re.M)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    lines = [l.strip() for l in body.strip().splitlines() if l.strip()]
    for i in range(len(lines) - 1, 0, -1):
        title_org = re.match(r"^[A-Z][^,]{1,60},\s(.+)$", lines[i])
        if title_org and re.fullmatch(NAME, lines[i - 1]):
            return lines[i - 1], title_org.group(1).strip()
    team = re.match(r"^(.+?)\s+(?:events\s+)?team$", lines[-1], re.I) if lines else None
    if team:
        return UNKNOWN, team.group(1).strip()
    return UNKNOWN, UNKNOWN


def _ask(req: Request) -> str:
    for s in _ranked(req.body):
        m = re.search(r"\byour CEO\b\s*(?:to\s)?(.+)", s, re.I)
        if not m:
            continue
        ask = m.group(1).rstrip(".?! ")
        cuts = [ask.find(c) for c in ASK_CUTS if ask.find(c) > 0]
        return ask[: min(cuts)] if cuts else ask
    return UNKNOWN


# ---------- modes ----------

def extract_rules(req: Request) -> tuple[dict, list[str]]:
    moderator, notes = _moderator(req)
    name, org = _requestor(req)
    fields = {
        "event_name": _event_name(req),
        "date": _date(req),
        "location": _location(req),
        "format": _format(req),
        "moderator": moderator,
        "audience_size": _audience(req),
        "requestor_name": name,
        "requestor_org": org,
        "ask": _ask(req),
    }
    return fields, notes


def extract_llm(req: Request, model: str | None = None) -> tuple[dict, list[str]]:
    import anthropic  # pip install anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=model or os.environ.get("ENGAGEMENT_MODEL", "claude-sonnet-5"),
        max_tokens=800,
        system=PROMPT_PATH.read_text(),
        messages=[{"role": "user", "content": req.text}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    match = re.search(r"\{.*\}", text, re.S)
    raw = json.loads(match.group(0)) if match else {}
    fields = {f: (UNKNOWN if is_blank(raw.get(f)) else str(raw[f]).strip()) for f in FIELDS}
    return fields, []


def run(req: Request, mode: str = "rules") -> tuple[dict, list[str]]:
    if mode == "llm":
        return extract_llm(req)
    return extract_rules(req)
