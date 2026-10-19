"""Regression tests for tools/demo_compare.py (presentation tooling)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "demo_compare.py"
RECORD = b"T1".ljust(12) + b"0000100000" * 2 + b"0000010000" + b"0" * 20 + b"----------N1EG4TE5MK7320250315\n"


def compare(cwd, *args):
    subprocess.run([sys.executable, str(TOOL), *args], cwd=cwd, check=False,
                   capture_output=True, text=True)


class DemoCompareTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.p = Path(self.dir.name)
        (self.p / "in.dat").write_bytes(RECORD)
        subprocess.run([sys.executable, str(ROOT / "tools" / "fixtures.py"), "--cwf-source",
                        str(ROOT / "fixtures" / "cwf.json"), "--output", str(self.p / "cwf.dat")], check=True)

    def summary(self):
        return json.loads((self.p / "out" / "summary.json").read_text())

    def test_relative_paths_resolve_from_caller_directory(self):
        python = f"{sys.executable} python/msp.py"
        compare(self.p, "--input", "in.dat", "--cwf", "cwf.dat", "--out", "out", "--cobol", python, "--python", python)
        self.assertEqual(self.summary()["verdict"], "MATCH")
        self.assertEqual(self.summary()["records_compared"], 1)

    def test_failed_runs_do_not_reuse_stale_outputs(self):
        python = f"{sys.executable} python/msp.py"
        compare(self.p, "--input", "in.dat", "--cwf", "cwf.dat", "--out", "out", "--cobol", python, "--python", python)
        compare(self.p, "--input", "in.dat", "--cwf", "cwf.dat", "--out", "out", "--cobol", "false", "--python", "false")
        self.assertEqual(self.summary()["verdict"], "MISMATCH")
        self.assertFalse((self.p / "out" / "python-results.csv").exists())


if __name__ == "__main__":
    unittest.main()
