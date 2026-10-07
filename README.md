# Engagement Agents

A multi-agent pipeline that turns incoming requests for an executive's time (speaking invitations, panels, interviews) into a prioritized review queue, with a fact-checked briefing and a draft reply for each one.

It runs offline in seconds with no API key. Switch one flag to use Claude for the reading step.

> This is a public, simplified version of a system I built and run at work. It uses 12 fictional requests and contains no company data.

---

## What it does

Point it at a folder of request emails. For each one it:

1. **Extracts** the nine facts a briefing needs: event, date, location, format, moderator, audience, requestor, organization and the ask.
2. **Checks** every extracted fact against the original email, and stops anything that looks invented or borrowed from another event.
3. **Scores** the request with an explicit rubric and proposes a priority.
4. **Drafts** a one-page briefing and a reply. When something is missing, the reply asks for it instead of guessing.
5. **Queues** everything for a person to review. Nothing is ever sent.

**The one rule: the human is always the final sender.** There is no send step anywhere in the code, and a test fails if one is added.

---

## How it works

```
 request emails (.txt)
        │
        ▼
 ┌───────────────┐
 │ Intake Agent  │  extracts 9 fields · rules or Claude
 └──────┬────────┘
        ▼
 ┌──────────────────┐
 │ Validation Agent │  is every value in the email? any stale or invented numbers?
 └──────┬───────────┘
        │
   errors? ──yes──► BLOCKED: nothing drafted, fields shown for a person to fix
        │
   missing required info? ──yes──► NEEDS INFO: draft reply asks for it
        │
        ▼
 ┌───────────────┐
 │ Triage Agent  │  0–100 score from a readable rubric, with reasons
 └──────┬────────┘
        ▼
 ┌──────────────────────────────┐
 │ Briefing + Reply Drafters    │  templates only, so they can't add facts
 └──────┬───────────────────────┘
        ▼
 output/review_queue.md  ◄── a person reviews, edits and sends
```

### The agents

| Agent | File | Job |
|---|---|---|
| **Orchestrator** | `main.py` | Runs each request through the pipeline, routes blocked items away from drafting, writes the queue and a run log. |
| **Intake** | `agents/intake.py` | Extracts the nine fields. `rules` mode is deterministic pattern matching; `llm` mode uses Claude with [`prompts/intake.md`](prompts/intake.md). |
| **Validation** | `agents/validation.py` | Checks each value appears in the email, numbers aren't invented, numbers don't come from "last year's" event, and the date isn't in the past. |
| **Triage** | `agents/triage.py` | Scores audience, format, lead time and completeness. Every point comes with a reason a person can disagree with. |
| **Briefing + Reply** | `agents/drafting.py` | Fills templates from validated fields only. Unknowns become questions. |

---

## What this demonstrates

| Idea | How it shows up |
|---|---|
| **One job per agent** | Each agent is a small file with one responsibility and a plain-English docstring. |
| **Guardrails before generation** | Validation runs before drafting. A blocked item is never drafted on top of. |
| **A blank beats a guess** | Missing facts become `UNKNOWN` in the briefing and a question in the reply. |
| **Learning from real failures** | The validator's stale-number check exists because a model carried last year's 40,000-viewer figure into this year's briefing during [my eval run](https://aosmani123.github.io/projects/briefing-evals/). The tests replay that failure. |
| **Auditable decisions** | Triage is a rubric, not a model, so every priority can be explained in one line. |
| **Human in the loop** | Output is a review queue. Replies are drafts. There is no send step. |
| **Memory** | Each run appends to `memory/runs_log.jsonl`, so you can compare runs over time. |

---

## Repo contents

```
engagement-agents/
├── main.py                  # Orchestrator
├── agents/
│   ├── common.py            # Shared types and text helpers
│   ├── intake.py            # Intake Agent (rules + Claude)
│   ├── validation.py        # Validation Agent
│   ├── triage.py            # Triage Agent
│   └── drafting.py          # Briefing and Reply Drafters
├── prompts/
│   └── intake.md            # System prompt for Claude mode
├── samples/
│   ├── requests/            # 12 fictional requests, each with a trap
│   └── answer_keys.json     # What a careful reader would extract
├── eval_intake.py           # Scores the Intake Agent against the answer keys
├── tests/                   # Pipeline and validation tests
└── CLAUDE.md                # Architecture notes for working on this with Claude Code
```

---

## Prerequisites

- Python 3.10 or newer. No packages needed for the default offline mode.
- For Claude mode only: `pip install anthropic` and an [Anthropic API key](https://console.anthropic.com).

---

## Setup and run

### 1. Run it offline

```bash
git clone https://github.com/AOSMANI123/engagement-agents.git
cd engagement-agents
python3 main.py
```

Open `output/review_queue.md` to see the queue.

### 2. Run it with Claude

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install anthropic
export ANTHROPIC_API_KEY=...        # never commit this
python3 main.py --mode llm
```

### 3. Use your own requests

Save each email as a `.txt` file, with a `Subject:` line at the top, then:

```bash
python3 main.py path/to/your/requests/
```

### 4. Check the work

```bash
python3 -m unittest discover -s tests   # 11 tests
python3 eval_intake.py                  # score the Intake Agent
python3 eval_intake.py --mode llm       # score Claude on the same requests
```

---

## Results

Offline rules mode, October 7, 2026:

| Measure | Result |
|---|---|
| Recall on stated fields | 95/96 (99%) |
| Unstated fields filled in | 0/12 |
| Wrong values | 0 |
| Pipeline outcome | 11 ready for review, 1 needs info (no date set) |

**Read that 99% with caution.** I wrote the rules while looking at these same 12 requests, so they fit them well. New phrasings will break them. That's what Claude mode is for, and why the Validation Agent sits after Intake no matter which mode runs.

The one miss is worth a note. The answer key counts "President Maria Gonzalez will introduce the speaker" as a moderator, but not an emcee who "would introduce the session" in another request. The Intake Agent treats both as introducers and records them as a note, which I think is right. It means the answer key needs a decision, not the agent.

---

## Prompts

[`prompts/intake.md`](prompts/intake.md) is the system prompt for Claude mode. It's the same "flag the gaps" prompt that cut fabrication in my eval harness: use only facts about this event, write `UNKNOWN` for anything not stated, and copy numbers exactly.

The drafters don't use a prompt. They're templates by design, so the only facts in a briefing are ones that passed validation.

---

## Related

- [LLM prompt eval harness](https://aosmani123.github.io/projects/briefing-evals/): where the 12 requests and the stale-number lesson come from
- [Engagement tracker template](https://aosmani123.github.io/projects/engagement-triage/): a no-code version of the same workflow
- [Portfolio](https://aosmani123.github.io)
