"""Reset moves live runs aside (never deletes them) and refuses while a run is in progress."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demo"))
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

    def test_reset_refused_while_running(self):
        server.LOCK.acquire()
        try:
            self.assertFalse(server.reset_live_runs(self.runs, self.archive))
        finally:
            server.LOCK.release()
        self.assertEqual(len(list(self.runs.iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
