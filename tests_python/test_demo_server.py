"""Reset moves live runs aside (never deletes them) and refuses while a run is in progress."""
import os
import sys
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demo"))
import evidence  # noqa: E402
import server  # noqa: E402


class ResetLiveRuns(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.runs, self.archive = self.tmp / "demo-runs", self.tmp / "archive"
        (self.runs / "20261018T000000Z").mkdir(parents=True)
        (self.runs / "20261018T000000Z" / "run.json").write_text("{}")

    def test_reset_archives_runs(self):
        self.assertTrue(server.reset_live_runs(self.runs, self.archive))
        self.assertEqual(list(self.runs.iterdir()), [])
        self.assertEqual([p.name for p in self.archive.glob("*/*")], ["20261018T000000Z"])

    def test_reset_with_nothing_to_clear(self):
        server.reset_live_runs(self.runs, self.archive)
        self.assertTrue(server.reset_live_runs(self.runs, self.archive))
        self.assertEqual(len(list(self.archive.iterdir())), 1)

    def test_reset_leaves_in_progress_run(self):
        busy = self.runs / "20261018T000001Z"
        busy.mkdir()
        (busy / "run.json").write_text('{"status": "RUNNING", "finished_at": null}')
        self.assertTrue(server.reset_live_runs(self.runs, self.archive))
        self.assertEqual([p.name for p in self.runs.iterdir()], ["20261018T000001Z"])
        self.assertEqual([p.name for p in self.archive.glob("*/*")], ["20261018T000000Z"])

    def test_reset_archives_abandoned_run(self):
        stale = self.runs / "20261018T000002Z"
        stale.mkdir()
        (stale / "run.json").write_text('{"status": "RUNNING", "finished_at": null, '
                                         '"steps": [{"key": "a", "status": "PASSED"}, {"key": "b", "status": "RUNNING"}]}')
        old = time.time() - evidence.STALE_AFTER - 60
        os.utime(stale / "run.json", (old, old))
        shown = evidence.live_run(stale)
        self.assertEqual(shown["status"], "INTERRUPTED")
        self.assertEqual([st["status"] for st in shown["steps"]], ["PASSED", "INTERRUPTED"])
        self.assertFalse(evidence.abandoned(self.runs / "gone", {"status": "RUNNING"}))
        self.assertTrue(server.reset_live_runs(self.runs, self.archive))
        self.assertEqual(list(self.runs.iterdir()), [])

    def test_reset_refused_while_running(self):
        server.LOCK.acquire()
        try:
            self.assertFalse(server.reset_live_runs(self.runs, self.archive))
        finally:
            server.LOCK.release()
        self.assertEqual(len(list(self.runs.iterdir())), 1)


class PlantedBugs(unittest.TestCase):
    def test_each_bug_changes_exactly_one_line_of_a_copy(self):
        real = (server.ROOT / "python" / "msp.py").read_text()
        for key in server.BUGS:
            with self.subTest(key):
                run = Path(tempfile.mkdtemp())
                info = server.plant_bug(run, key)
                broken = (run / "planted-bug" / "msp.py").read_text().split("\n")
                diff = [i for i, (a, b) in enumerate(zip(real.split("\n"), broken)) if a != b]
                self.assertEqual(diff, [info["line"] - 1])
        self.assertEqual((server.ROOT / "python" / "msp.py").read_text(), real)

    def test_bug_steps_use_the_copy_and_skip_unit_tests(self):
        steps = server.steps_for("contract")
        keys = [k for k, _, _ in steps]
        self.assertNotIn("python-units", keys)
        for key, _, cmd in steps:
            self.assertNotIn(" python/msp.py", cmd)
            if key in ("policy-python", "curated-verify", "synthetic-verify", "curated-compare", "synthetic-compare"):
                self.assertIn(server.PLANTED, cmd)
        self.assertIs(server.steps_for(None), server.LIVE_STEPS)
        self.assertFalse(server.start_live_run("nope"))

    def test_a_bug_that_no_longer_applies_creates_no_run_folder(self):
        run = Path(tempfile.mkdtemp()) / "run"
        with mock.patch.dict(server.BUGS, {"gone": {"title": "t", "what": "w", "old": "no such line", "new": "x"}}):
            with self.assertRaises(RuntimeError):
                server.live_run(run, bug="gone")
            with self.assertRaises(RuntimeError):
                server.start_live_run("gone")
        self.assertFalse(run.exists())
        self.assertFalse(server.LOCK.locked())


if __name__ == "__main__":
    unittest.main()


class RequireDevinKey(unittest.TestCase):
    def test_refuses_to_start_without_key(self):
        from unittest import mock
        env = {k: v for k, v in os.environ.items() if k != "DEVIN_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(sys, "argv", ["server.py", "--require-devin-key"]), \
                mock.patch.object(server, "ThreadingHTTPServer") as http:
            self.assertEqual(server.main(), 2)
            http.assert_not_called()
