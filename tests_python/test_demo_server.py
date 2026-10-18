"""Reset moves live runs aside (never deletes them) and refuses while a run is in progress."""
import os
import sys
import tempfile
import time
import unittest
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
        (stale / "run.json").write_text('{"status": "RUNNING", "finished_at": null}')
        old = time.time() - evidence.STALE_AFTER - 60
        os.utime(stale / "run.json", (old, old))
        self.assertEqual(evidence.live_run(stale)["status"], "INTERRUPTED")
        self.assertTrue(server.reset_live_runs(self.runs, self.archive))
        self.assertEqual(list(self.runs.iterdir()), [])

    def test_reset_refused_while_running(self):
        server.LOCK.acquire()
        try:
            self.assertFalse(server.reset_live_runs(self.runs, self.archive))
        finally:
            server.LOCK.release()
        self.assertEqual(len(list(self.runs.iterdir())), 1)


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
