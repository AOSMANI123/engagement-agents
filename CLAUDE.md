# Notes for working on this repo with Claude Code

## Architecture

`main.py` is the orchestrator. Each request goes Intake → Validation → (stop if blocked) → Triage → Drafting.
Agents live in `agents/`, one responsibility per file. Shared types are in `agents/common.py`.

## Rules that must not change

- **No send step.** Nothing in this repo sends email or posts anywhere. `tests/test_pipeline.py` checks for this.
- **Validation runs before drafting.** A blocked item must never get a briefing or reply.
- **Drafters are templates.** They may only use validated fields. Don't add an LLM to drafting without a validation pass after it.
- **Unknown stays unknown.** Missing facts are `UNKNOWN` in fields and become questions in replies.

## Before committing

```bash
python3 -m unittest discover -s tests
python3 eval_intake.py
```

Fabrication on the samples must stay at 0/12. If you add a sample request, add its answer key to `samples/answer_keys.json`.
