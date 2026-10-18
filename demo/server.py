"""Migration Evidence app: `make demo` -> http://localhost:8765

Serves the frontend, evidence assembled from real artifacts (demo/evidence.py), read-only
raw files, and a "Run COBOL vs Python now" action that executes the real COBOL and Python commands into a
new build/demo-runs/<UTC> folder. Saved rehearsal evidence is never written. "Start Devin live"
launches the migration Playbook through the Devin API (demo/devin_launch.py) when DEVIN_API_KEY is set.
"""
import argparse
import json
import mimetypes
import os
import signal
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import devin_launch  # noqa: E402
import evidence  # noqa: E402

ROOT = evidence.ROOT
STATIC = ROOT / "demo" / "static"
RAW_PREFIXES = ("cobol/", "python/", "tests_policy/", "tests_python/", "tests/", "tools/", "fixtures/",
                "docs/", "evidence/", "build/demo-runs/", "README.md", "DEVIN_TASK.md", "Makefile")
LIVE_STEPS = [
    ("doctor", "Check the toolchain (GnuCOBOL, Python)", "make doctor"),
    ("build", "Compile the original COBOL and generate the test batches",
     "make build generate"),
    ("baseline", "Run the original COBOL against the retained expected results",
     "python3 tools/verify.py baseline --command build/msp-batch --report {run}/baseline-report.json"),
    ("starter-tests", "Starter infrastructure tests", "python3 -m unittest discover -s tests -v"),
    ("policy-cobol", "Independent policy tests against COBOL",
     "python3 -m unittest discover -s tests_policy -v"),
    ("policy-python", "The same independent tests against Python",
     "MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v"),
    ("python-units", "Python unit tests", "python3 -m unittest discover -s tests_python -v"),
    ("curated-verify", "Strict verifier: COBOL vs Python, curated batch",
     "python3 tools/verify.py compare --candidate 'python3 python/msp.py' --input build/curated.dat --report {run}/curated-verifier.json"),
    ("synthetic-verify", "Strict verifier: COBOL vs Python, 1,000-record batch",
     "python3 tools/verify.py compare --candidate 'python3 python/msp.py' --input build/synthetic.dat --report {run}/synthetic-verifier.json"),
    ("curated-compare", "Side-by-side table, curated batch",
     "python3 tools/demo_compare.py --input build/curated.dat --out {run}/curated"),
    ("synthetic-compare", "Side-by-side table, 1,000-record batch",
     "python3 tools/demo_compare.py --input build/synthetic.dat --out {run}/synthetic"),
]
LOCK = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_state(run_dir, state):
    tmp = run_dir / "run.json.tmp"
    tmp.write_text(json.dumps(state, indent=2) + "\n")
    tmp.replace(run_dir / "run.json")


def live_run(run_dir=None):
    """Execute every step for real; record command, exit code, timing, and full output."""
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = run_dir or evidence.RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    rel_run = evidence.rel(run_dir)
    state = {"id": run_dir.name, "folder": rel_run, "status": "RUNNING", "started_at": now(),
             "finished_at": None, "commit": evidence.git("rev-parse", "HEAD"),
             "dirty": bool(evidence.git("status", "--porcelain")),
             "steps": [{"key": k, "title": t, "command": c.format(run=rel_run), "status": "NOT_RUN",
                        "exit_code": None, "log": f"{rel_run}/{k}.log"} for k, t, c in LIVE_STEPS]}
    write_state(run_dir, state)
    for step in state["steps"]:
        step["status"], step["started_at"] = "RUNNING", now()
        write_state(run_dir, state)
        with (ROOT / step["log"]).open("w") as log:
            log.write(f"$ {step['command']}\n")
            log.flush()
            proc = subprocess.Popen(step["command"], shell=True, cwd=ROOT, stdout=log,
                                    stderr=subprocess.STDOUT, start_new_session=True)
            try:
                step["exit_code"] = proc.wait(timeout=600)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                log.write("\n[timed out after 600 s; the whole process group was stopped]\n")
                step["exit_code"] = None
        step["finished_at"] = now()
        step["status"] = "PASSED" if step["exit_code"] == 0 else "FAILED"
        write_state(run_dir, state)
    state["finished_at"] = now()
    state["status"] = "PASSED" if all(s["status"] == "PASSED" for s in state["steps"]) else "FAILED"
    write_state(run_dir, state)
    return state


def raw_allowed(name):
    """Only files git tracks (or this app's own live-run output) are served."""
    if name.startswith("build/demo-runs/"):
        return True
    out = subprocess.run(["git", "ls-files", "--error-unmatch", "--", name], cwd=ROOT,
                         capture_output=True)
    return out.returncode == 0


def run_in_progress(run_dir):
    """A run started outside this server (`--run-once`) still says RUNNING until it finishes."""
    state, err = evidence.read_json(run_dir / "run.json")
    return (not err and state.get("status") == "RUNNING" and not state.get("finished_at")
            and not evidence.abandoned(run_dir, state))


def reset_live_runs(runs=None, archive=None):
    """Move every live run aside (never deleted) so the app shows only saved evidence again."""
    runs = runs or evidence.RUNS
    archive = archive or runs.parent / "demo-runs-archive"
    if not LOCK.acquire(blocking=False):
        return False
    try:
        done = [p for p in runs.iterdir() if not run_in_progress(p)] if runs.exists() else []
        if done:
            dest = archive / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            dest.mkdir(parents=True)
            for p in done:
                shutil.move(str(p), str(dest / p.name))
        return True
    finally:
        LOCK.release()


def start_live_run():
    if not LOCK.acquire(blocking=False):
        return False

    def worker():
        try:
            live_run()
        finally:
            LOCK.release()
    threading.Thread(target=worker, daemon=True).start()
    return True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/evidence":
            data = evidence.build()
            data["live_running"] = LOCK.locked()
            return self.send(200, json.dumps(data))
        if path == "/api/devin-run":
            return self.send(200, json.dumps(devin_launch.state()))
        if path.startswith("/raw/"):
            name = path[len("/raw/"):]
            target = (ROOT / name).resolve()
            if (not name.startswith(RAW_PREFIXES) or ROOT not in target.parents or not target.is_file()
                    or not raw_allowed(name)):
                return self.send(404, "not found", "text/plain")
            ctype = "text/plain; charset=utf-8"
            if target.suffix == ".json":
                ctype = "application/json"
            return self.send(200, target.read_bytes(), ctype)
        name = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (STATIC / name).resolve()
        if STATIC not in target.parents or not target.is_file():
            return self.send(404, "not found", "text/plain")
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        return self.send(200, target.read_bytes(), ctype)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/devin-run":
            code, payload = devin_launch.start()
            return self.send(code, json.dumps(payload))
        if path == "/api/devin-reset":
            code, payload = devin_launch.reset()
            return self.send(code, json.dumps(payload))
        if path == "/api/live-reset":
            reset = reset_live_runs()
            return self.send(200 if reset else 409, json.dumps({"reset": reset}))
        if path != "/api/live-run":
            return self.send(404, "not found", "text/plain")
        started = start_live_run()
        return self.send(202 if started else 409, json.dumps({"started": started}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--run-once", action="store_true", help="run the live evidence steps and exit")
    args = parser.parse_args()
    if args.run_once:
        state = live_run()
        print(f"{state['status']}: {state['folder']}")
        for step in state["steps"]:
            print(f"  {step['status']:7} exit={step['exit_code']} {step['command']}")
        return 0 if state["status"] == "PASSED" else 1
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Migration Evidence app: http://localhost:{args.port}  (Ctrl+C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    sys.exit(main())
