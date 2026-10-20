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
    ("build", "Compile the original COBOL and generate the test batches and CWF reference file",
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
    ("curated-compare", "Side-by-side table (payment, CWF decision, released), curated batch",
     "python3 tools/demo_compare.py --input build/curated.dat --out {run}/curated"),
    ("synthetic-compare", "Side-by-side table (payment, CWF decision, released), 1,000-record batch",
     "python3 tools/demo_compare.py --input build/synthetic.dat --out {run}/synthetic"),
]
PLANTED = "{run}/planted-bug/msp.py"
BUGS = {
    "contract": {"title": "Forget the contract rule",
                 "what": "Ignores the provider's contract amount and always uses the full charges.",
                 "old": "    return claim.charges if claim.contract is None else claim.contract",
                 "new": "    return claim.charges"},
    "boundary": {"title": "Off by one: > instead of \u2265",
                 "what": "Medicare should pay $0 when the other insurer paid exactly the limit; this version only stops when it paid more.",
                 "old": "    if claim.primary >= cap:",
                 "new": "    if claim.primary > cap:"},
    "cents": {"title": "Drop the cents",
              "what": "Rounds every payment down to whole dollars.",
              "old": '    return Result(claim.claim_id, "PAID", cap - max(deductions, claim.primary), "SECONDARY_PAYABLE")',
              "new": '    return Result(claim.claim_id, "PAID", (cap - max(deductions, claim.primary)) // 100 * 100, "SECONDARY_PAYABLE")'},
    "cwf": {"title": "Pay a claim CWF rejected",
            "what": "Releases the payment even when the person was not entitled to Medicare on the service date.",
            "old": '        return replace(result, cwf="REJECTED", cwf_reason="NOT_ENTITLED", released_cents=0)',
            "new": '        return replace(result, cwf="REJECTED", cwf_reason="NOT_ENTITLED", released_cents=result.payment_cents)'},
}
LOCK = threading.Lock()


def bug_source(key):
    """python/msp.py with one known mistake applied, and the changed line's index."""
    bug = BUGS[key]
    lines = (ROOT / "python" / "msp.py").read_text().split("\n")
    hits = [i for i, line in enumerate(lines) if line == bug["old"]]
    if len(hits) != 1:
        raise RuntimeError(f"planted bug {key!r}: expected exactly one matching line in python/msp.py, found {len(hits)}")
    lines[hits[0]] = bug["new"]
    return lines, hits


def plant_bug(run_dir, key, source=None):
    """Write a copy of python/msp.py with one known mistake; the real file is never modified."""
    bug = BUGS[key]
    lines, hits = source or bug_source(key)
    target = run_dir / "planted-bug" / "msp.py"
    target.parent.mkdir()
    target.write_text("\n".join(lines))
    return {"key": key, "title": bug["title"], "what": bug["what"], "line": hits[0] + 1,
            "old": bug["old"].strip(), "new": bug["new"].strip(), "file": evidence.rel(target)}


def steps_for(bug):
    """With a planted bug, every Python check runs the broken copy; the unit tests import the real module, so they are skipped."""
    if not bug:
        return LIVE_STEPS
    out = []
    for key, title, cmd in LIVE_STEPS:
        if key == "python-units":
            continue
        if "python/msp.py" in cmd:
            cmd = cmd.replace("python/msp.py", PLANTED)
        elif key.endswith("-compare"):
            cmd += f" --python 'python3 {PLANTED}'"
        out.append((key, title, cmd))
    return out


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_state(run_dir, state):
    tmp = run_dir / "run.json.tmp"
    tmp.write_text(json.dumps(state, indent=2) + "\n")
    tmp.replace(run_dir / "run.json")


def live_run(run_dir=None, bug=None):
    """Execute every step for real; record command, exit code, timing, and full output."""
    source = bug_source(bug) if bug else None
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = run_dir or evidence.RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    rel_run = evidence.rel(run_dir)
    planted = plant_bug(run_dir, bug, source) if bug else None
    state = {"bug": planted, "id": run_dir.name, "folder": rel_run, "status": "RUNNING", "started_at": now(),
             "finished_at": None, "commit": evidence.git("rev-parse", "HEAD"),
             "dirty": bool(evidence.git("status", "--porcelain")),
             "steps": [{"key": k, "title": t, "command": c.format(run=rel_run), "status": "NOT_RUN",
                        "exit_code": None, "log": f"{rel_run}/{k}.log"} for k, t, c in steps_for(bug)]}
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


def start_live_run(bug=None):
    if bug is not None and bug not in BUGS:
        return False
    if bug:
        bug_source(bug)
    if not LOCK.acquire(blocking=False):
        return False

    def worker():
        try:
            live_run(bug=bug)
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
            data["bugs"] = {k: {"title": b["title"], "what": b["what"]} for k, b in BUGS.items()}
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
        data = target.read_bytes()
        rng = self.headers.get("Range", "")
        if rng.startswith("bytes="):
            return self.send_range(data, ctype, rng[len("bytes="):])
        return self.send(200, data, ctype)

    def send_range(self, data, ctype, spec):
        size = len(data)
        start_s, _, end_s = spec.split(",")[0].strip().partition("-")
        try:
            if start_s:
                start, end = int(start_s), int(end_s) if end_s else size - 1
            else:
                start, end = max(size - int(end_s), 0), size - 1
        except ValueError:
            return self.send(200, data, ctype)
        end = min(end, size - 1)
        if start > end or start >= size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        part = data[start:end + 1]
        self.send_response(206)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(len(part)))
        self.end_headers()
        self.wfile.write(part)
        return None

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
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 <= length <= 1024:
                return self.send(413, json.dumps({"started": False, "error": "request body too large"}))
            self.connection.settimeout(5)
            bug = json.loads(self.rfile.read(length) or b"{}").get("bug") if length else None
        except TimeoutError:
            self.close_connection = True
            return self.send(408, json.dumps({"started": False, "error": "request body timed out"}))
        except (ValueError, AttributeError):
            return self.send(400, json.dumps({"started": False, "error": "bad request body"}))
        if bug is not None and bug not in BUGS:
            return self.send(400, json.dumps({"started": False, "error": "unknown bug"}))
        try:
            started = start_live_run(bug)
        except RuntimeError as e:
            return self.send(500, json.dumps({"started": False, "error": str(e)}))
        return self.send(202 if started else 409, json.dumps({"started": started}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--run-once", action="store_true", help="run the live evidence steps and exit")
    parser.add_argument("--plant-bug", choices=sorted(BUGS), help="with --run-once: run the checks against a broken copy of the Python")
    parser.add_argument("--require-devin-key", action="store_true",
                        help="refuse to start unless DEVIN_API_KEY is set, so Start Devin live can't silently fall back")
    args = parser.parse_args()
    if args.require_devin_key and not devin_launch.configured():
        print("DEVIN_API_KEY is not set in this shell, so Start Devin live would not work. "
              "Open a new shell (secrets load only in new shells) and try again.", file=sys.stderr)
        return 2
    if args.run_once:
        state = live_run(bug=args.plant_bug)
        print(f"{state['status']}: {state['folder']}" + (f" (planted bug: {state['bug']['title']})" if state["bug"] else ""))
        for step in state["steps"]:
            print(f"  {step['status']:7} exit={step['exit_code']} {step['command']}")
        return 0 if state["status"] == "PASSED" else 1
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Migration Evidence app: http://localhost:{args.port}  (Ctrl+C to stop)")
    print(f"Start Devin live: {'ready (DEVIN_API_KEY set)' if devin_launch.configured() else 'NOT available: DEVIN_API_KEY is not set'}",
          flush=True)
    server.serve_forever()


if __name__ == "__main__":
    sys.exit(main())
