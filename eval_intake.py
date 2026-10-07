"""Score the Intake Agent against the answer keys in samples/answer_keys.json.

    python3 eval_intake.py              # rules mode, offline
    python3 eval_intake.py --mode llm   # Claude (needs ANTHROPIC_API_KEY)

Same scoring as the briefing-evals harness, with one fix learned from its first
real run: honest blanks in any wording ("TBD", "Not specified") count as UNKNOWN,
so the fabrication number measures invention, not formatting.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from agents import intake
from agents.common import FIELDS, Request, is_blank, norm, numbers

HERE = Path(__file__).parent


def score(mode: str) -> dict:
    keys = json.loads((HERE / "samples" / "answer_keys.json").read_text())
    totals = {"correct": 0, "known": 0, "fabricated": 0, "unknown": 0, "wrong": 0, "missed": 0}
    misses = []
    for case_id, case in keys.items():
        text = (HERE / "samples" / "requests" / f"{case_id}.txt").read_text()
        got, _ = intake.run(Request(case_id, text), mode)
        for f in FIELDS:
            exp = case["expected"][f]
            val = got.get(f, "")
            blank = is_blank(val)
            if exp is None:
                totals["unknown"] += 1
                if not blank:
                    totals["fabricated"] += 1
                    misses.append(f"{case_id} {f}: filled in '{val}' (source doesn't say)")
                continue
            totals["known"] += 1
            accepted = exp if isinstance(exp, list) else [exp]
            if blank:
                totals["missed"] += 1
                misses.append(f"{case_id} {f}: said UNKNOWN, expected '{accepted[0]}'")
            elif any(norm(a) in norm(val) for a in accepted):
                totals["correct"] += 1
            else:
                totals["wrong"] += 1
                misses.append(f"{case_id} {f}: got '{val}', expected '{accepted[0]}'")
    return {"totals": totals, "misses": misses}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["rules", "llm"], default="rules")
    args = ap.parse_args(argv)
    r = score(args.mode)
    t = r["totals"]
    print(f"intake mode: {args.mode}")
    print(f"recall on stated fields : {t['correct']}/{t['known']} ({t['correct'] / t['known']:.0%})")
    print(f"fabrication             : {t['fabricated']}/{t['unknown']} unstated fields filled in")
    print(f"wrong values            : {t['wrong']}")
    print(f"missed (said UNKNOWN)   : {t['missed']}")
    for m in r["misses"]:
        print("  " + m)
    return r


if __name__ == "__main__":
    main()
