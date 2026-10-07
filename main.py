"""Orchestrator: runs every request through the agents and builds the review queue.

    python3 main.py                       # all sample requests, offline rules mode
    python3 main.py --mode llm            # use Claude for intake (needs ANTHROPIC_API_KEY)
    python3 main.py path/to/request.txt   # your own request(s)

Pipeline per request:
    Intake -> Validation -> (blocked? stop) -> Triage -> Briefing + Reply drafts

Output:
    output/review_queue.md   what a person reviews: priorities, briefings, draft replies
    output/items.json        the same, machine-readable
    memory/runs_log.jsonl    one line per run, so you can compare runs over time

There is no send step. The human is always the final sender.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from agents import drafting, intake, triage, validation
from agents.common import Item, Request

HERE = Path(__file__).parent
STATUS_ORDER = {"ready": 0, "needs_info": 1, "blocked": 2}
STATUS_LABEL = {"ready": "Ready for review", "needs_info": "Needs info", "blocked": "Blocked: fix fields first"}


def load_requests(paths: list[str]) -> list[Request]:
    files: list[Path] = []
    for p in paths or [str(HERE / "samples" / "requests")]:
        path = Path(p)
        files += sorted(path.glob("*.txt")) if path.is_dir() else [path]
    return [Request(id=f.stem, text=f.read_text()) for f in files]


def process(req: Request, mode: str, today: dt.date) -> Item:
    item = Item(request=req)
    item.fields, item.notes = intake.run(req, mode)
    item.validation = validation.run(req, item.fields, today)
    item.status = item.validation["status"]
    if item.status == "blocked":
        return item  # never draft on top of fields that look invented
    item.triage = triage.run(item.fields, item.validation, today)
    item.briefing = drafting.briefing(item)
    item.reply_draft = drafting.reply(item)
    return item


def review_queue(items: list[Item], mode: str, today: dt.date) -> str:
    items = sorted(items, key=lambda i: (STATUS_ORDER[i.status], -i.triage.get("score", 0)))
    counts = {s: sum(i.status == s for i in items) for s in STATUS_ORDER}
    out = [
        "# Engagement review queue",
        "",
        f"Run on {today:%B} {today.day}, {today.year} · intake mode: `{mode}` · {len(items)} requests",
        "",
        "Nothing below has been sent. Every reply is a draft for a person to edit and send.",
        "",
        "| Request | Status | Priority | Score |",
        "|---|---|---|---|",
    ]
    for i in items:
        out.append(f"| {i.request.id} | {STATUS_LABEL[i.status]} | "
                   f"{i.triage.get('priority', '-')} | {i.triage.get('score', '-')} |")
    out += ["", f"**{counts['ready']} ready · {counts['needs_info']} need info · {counts['blocked']} blocked**", ""]

    for i in items:
        out += ["---", "", f"## {i.request.id} · {STATUS_LABEL[i.status]}", ""]
        if i.status == "blocked":
            out += ["Validation stopped this item before drafting:", ""]
            out += [f"- {e}" for e in i.validation["errors"]]
            out += ["", "Extracted fields, for a person to correct:", "", "```json",
                    json.dumps(i.fields, indent=2), "```", ""]
            continue
        out += [f"**Proposed priority: {i.triage['priority']} ({i.triage['score']}/100).** "
                + "; ".join(i.triage["reasons"]) + ".", "", i.briefing, "",
                "**Draft reply (not sent):**", "", "```", i.reply_draft, "```", ""]
    return "\n".join(out)


def main(argv=None) -> list[Item]:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("requests", nargs="*", help="request .txt files or folders (default: samples)")
    ap.add_argument("--mode", choices=["rules", "llm"], default="rules")
    ap.add_argument("--today", help="pretend today is YYYY-MM-DD (default: real today)")
    ap.add_argument("--out", default=str(HERE / "output"))
    args = ap.parse_args(argv)

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    items = [process(r, args.mode, today) for r in load_requests(args.requests)]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "review_queue.md").write_text(review_queue(items, args.mode, today))
    (out / "items.json").write_text(json.dumps([{
        "id": i.request.id, "status": i.status, "fields": i.fields, "notes": i.notes,
        "validation": i.validation, "triage": i.triage, "reply_draft": i.reply_draft,
    } for i in items], indent=2))

    mem = HERE / "memory"
    mem.mkdir(exist_ok=True)
    with (mem / "runs_log.jsonl").open("a") as log:
        log.write(json.dumps({"run_at": dt.datetime.now().isoformat(timespec="seconds"),
                              "mode": args.mode, "today": today.isoformat(),
                              "statuses": {i.request.id: i.status for i in items}}) + "\n")

    for s in STATUS_ORDER:
        print(f"{STATUS_LABEL[s]:<28} {sum(i.status == s for i in items)}")
    print(f"\nReview queue: {out / 'review_queue.md'}")
    return items


if __name__ == "__main__":
    main()
