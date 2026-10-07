"""Run: python3 -m unittest discover -s tests"""
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import eval_intake  # noqa: E402
import main  # noqa: E402
from agents import validation  # noqa: E402
from agents.common import FIELDS, UNKNOWN, Request  # noqa: E402

TODAY = dt.date(2026, 10, 7)


def sample(case_id: str) -> Request:
    return Request(case_id, (ROOT / "samples" / "requests" / f"{case_id}.txt").read_text())


def fields(**overrides) -> dict:
    base = {f: UNKNOWN for f in FIELDS}
    base.update(overrides)
    return base


class ValidationCatchesRealModelFailures(unittest.TestCase):
    """These are the actual mistakes a model made in the first briefing-evals run."""

    def test_last_years_audience_is_blocked(self):
        req = sample("05-virtual")
        v = validation.run(req, fields(event_name="Open Classroom livestream", date="September 22, 2027",
                                       requestor_org="Open Classroom Foundation", ask="Q&A",
                                       audience_size="40,000 (based on last year's stream)"), TODAY)
        self.assertEqual(v["status"], "blocked")
        self.assertTrue(any("past or different event" in e for e in v["errors"]))

    def test_invented_moderator_is_blocked(self):
        req = sample("01-no-moderator")
        v = validation.run(req, fields(event_name="Lakeshore Health Innovation Forum", date="March 11, 2027",
                                       requestor_org="Lakeshore Health Institute", ask="fireside chat",
                                       moderator="Jordan Lee"), TODAY)
        self.assertEqual(v["status"], "blocked")

    def test_invented_number_is_blocked(self):
        req = sample("02-vague-crowd")
        v = validation.run(req, fields(event_name="Cascade Builders Summit", date="May 4, 2027",
                                       requestor_org="Cascade Builders Alliance", ask="keynote",
                                       audience_size="500"), TODAY)
        self.assertEqual(v["status"], "blocked")

    def test_past_date_is_blocked(self):
        req = sample("03-last-years-date")
        v = validation.run(req, fields(event_name="Riverbend Leadership Dinner", date="November 6, 2025",
                                       requestor_org="Riverbend Business Council", ask="conversation"), TODAY)
        self.assertEqual(v["status"], "blocked")

    def test_missing_date_needs_info_not_blocked(self):
        req = sample("03-last-years-date")
        v = validation.run(req, fields(event_name="Riverbend Leadership Dinner",
                                       requestor_org="Riverbend Business Council", ask="conversation"), TODAY)
        self.assertEqual(v["status"], "needs_info")
        self.assertIn("date", v["gaps"])


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.items = main.main(["--today", "2026-10-07", "--out", self.tmp])

    def test_every_sample_is_processed(self):
        self.assertEqual(len(self.items), 12)

    def test_blocked_items_are_never_drafted(self):
        for i in self.items:
            if i.status == "blocked":
                self.assertEqual(i.reply_draft, "")
                self.assertEqual(i.briefing, "")

    def test_unknowns_become_questions_not_guesses(self):
        item = next(i for i in self.items if i.request.id == "03-last-years-date")
        self.assertEqual(item.status, "needs_info")
        self.assertIn("confirmed date", item.reply_draft)
        self.assertIn("UNKNOWN", item.briefing)

    def test_review_queue_says_nothing_was_sent(self):
        queue = (Path(self.tmp) / "review_queue.md").read_text()
        self.assertIn("Nothing below has been sent", queue)

    def test_no_agent_can_send(self):
        for f in (ROOT / "agents").glob("*.py"):
            src = f.read_text()
            for banned in ("smtplib", "send_message", "requests.post", "urllib.request"):
                self.assertNotIn(banned, src, f"{f.name} should not be able to send anything")


class IntakeEvalTests(unittest.TestCase):
    def test_rules_intake_never_fabricates_on_samples(self):
        r = eval_intake.score("rules")
        self.assertEqual(r["totals"]["fabricated"], 0)


if __name__ == "__main__":
    unittest.main()
