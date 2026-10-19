"""Assemble presentation evidence from real artifacts. Nothing is assumed to have passed.

Status vocabulary: PASSED, FAILED, RUNNING, NOT_RUN, UNKNOWN.
Saved rehearsal evidence (evidence/rehearsal/) is read-only here; live runs live in build/demo-runs/.
"""
import csv
import hashlib
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REHEARSAL = ROOT / "evidence" / "rehearsal"
RUNS = ROOT / "build" / "demo-runs"
STARTER = "be0b00ec5a2369d50a34d351694b187ae2300fe4"
STAGE_COMMITS = [("stage1", "Stage 1: baseline + COBOL explanation"),
                 ("stage2", "Stage 2: independent tests against COBOL"),
                 ("stage3", "Stage 3: Python + unit tests"),
                 ("stage4", "Stage 4: COBOL vs Python comparison"),
                 ("docs", "Maintainer docs")]
DATASETS = {"curated": "Curated 33-record policy batch",
            "synthetic": "Deterministic 1,000-record synthetic batch (seed 20261017)",
            "edge": "Adversarial 33-record byte-level edge batch"}
FIELDS = ("claim_id", "status", "payment_cents", "reason", "cwf", "cwf_reason", "released_cents")


def rel(path):
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if ROOT in path.parents else str(path)


def read_json(path):
    try:
        return json.loads(Path(path).read_text()), None
    except FileNotFoundError:
        return None, "missing"
    except (OSError, ValueError) as exc:
        return None, f"malformed: {exc}"


def read_csv(path):
    try:
        with Path(path).open(newline="") as handle:
            return list(csv.DictReader(handle)), None
    except FileNotFoundError:
        return None, "missing"
    except (OSError, csv.Error) as exc:
        return None, f"malformed: {exc}"


def sha256(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def git(*args):
    try:
        out = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def unittest_summary(path):
    """Parse a unittest log. PASSED only when 'Ran N tests' and a final OK are both present."""
    try:
        text = Path(path).read_text(errors="replace")
    except FileNotFoundError:
        return {"status": "NOT_RUN", "log": None, "tests": None, "detail": "log missing"}
    ran = re.findall(r"^Ran (\d+) tests? in", text, re.M)
    ok = re.search(r"^OK\b", text, re.M)
    failed = re.search(r"^FAILED \((.*)\)", text, re.M)
    names = re.findall(r"^(test_\w+) \(([\w.]+)\) \.\.\. (ok|FAIL|ERROR|skipped.*)$", text, re.M)
    if ran and int(ran[-1]) > 0 and ok and not failed:
        status = "PASSED"
    elif failed or any(r in ("FAIL", "ERROR") for _, _, r in names):
        status = "FAILED"
    else:
        status = "UNKNOWN"
    return {"status": status, "log": rel(path), "tests": int(ran[-1]) if ran else None,
            "detail": failed.group(1) if failed else None,
            "cases": [{"name": n, "group": g, "result": r} for n, g, r in names]}


def cents_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def totals_row(path):
    rows, err = read_csv(path)
    if err or not rows:
        return None
    return {k: cents_int(v) for k, v in rows[0].items()}


def count_records(path):
    """Records in a batch input file, counted independently of either program's output."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def comparison(folder, verifier_report, label, kind):
    """Rebuild the side-by-side from both raw result files; never trust a precomputed 'MATCH' alone."""
    folder = Path(folder)
    cobol, cerr = read_csv(folder / "cobol-results.csv")
    python, perr = read_csv(folder / "python-results.csv")
    summary, serr = read_json(folder / "summary.json")
    base = {"label": label, "kind": kind, "folder": rel(folder) if folder.exists() else str(folder),
            "title": DATASETS.get(folder.name, folder.name)}
    if cerr or perr:
        return {**base, "status": "NOT_RUN" if "missing" in (cerr, perr) else "UNKNOWN",
                "problem": f"COBOL results {cerr or 'ok'}; Python results {perr or 'ok'}", "rows": []}
    try:
        by_no_c = {r["record_no"]: r for r in cobol}
        by_no_p = {r["record_no"]: r for r in python}
        for r in cobol + python:
            [r[k] for k in FIELDS]
    except (KeyError, TypeError) as exc:
        return {**base, "status": "UNKNOWN", "problem": f"result file is malformed (missing column {exc})", "rows": []}
    rows, mismatches = [], 0
    for no in sorted(set(by_no_c) | set(by_no_p)):
        c, p = by_no_c.get(no), by_no_p.get(no)
        if c is None or p is None:
            result = "MISSING_IN_COBOL" if c is None else "MISSING_IN_PYTHON"
        else:
            result = "MATCH" if all(c[k] == p[k] for k in FIELDS) else "MISMATCH"
        mismatches += result != "MATCH"
        rows.append([int(no), (c or p)["claim_id"], c and c["status"], p and p["status"],
                     c and cents_int(c["payment_cents"]), p and cents_int(p["payment_cents"]),
                     c and c["reason"], p and p["reason"], result, (p or c)["claim_id"],
                     c and c["cwf"], p and p["cwf"], c and c["cwf_reason"], p and p["cwf_reason"],
                     c and cents_int(c["released_cents"]), p and cents_int(p["released_cents"])])
    ids = [r["claim_id"] for r in python if not r["claim_id"].startswith("@")]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    ct, pt = totals_row(folder / "cobol-totals.csv"), totals_row(folder / "python-totals.csv")
    report, rerr = read_json(verifier_report) if verifier_report else (None, "not applicable")
    verifier = ("PASSED" if report and report.get("result") == "PASS" else
                "FAILED" if report and report.get("result") == "FAIL" else
                "NOT_RUN" if rerr in ("missing", "not applicable") else "UNKNOWN")
    files_identical = (sha256(folder / "cobol-results.csv") == sha256(folder / "python-results.csv")
                       and sha256(folder / "cobol-totals.csv") == sha256(folder / "python-totals.csv"))
    totals_match = ct is not None and ct == pt
    input_name = (summary or {}).get("input")
    input_records = count_records(ROOT / input_name) if input_name else None
    complete = input_records is not None and len(cobol) == len(python) == input_records
    if mismatches or duplicates or not totals_match or verifier == "FAILED" or (input_records is not None and not complete):
        status = "FAILED"
    elif not verifier_report and input_records is None:
        status = "UNKNOWN"
    elif verifier_report and verifier != "PASSED":
        status = "UNKNOWN"
    else:
        status = "PASSED"
    return {**base, "input_records": input_records, "status": status, "rows": rows, "records": {"cobol": len(cobol), "python": len(python)},
            "mismatches": mismatches, "duplicates": duplicates, "totals": {"cobol": ct, "python": pt},
            "totals_match": totals_match, "byte_identical": files_identical,
            "verifier": {"status": verifier, "report": rel(verifier_report) if report else None,
                         "detail": rerr if not report else None,
                         "differences": (report or {}).get("differences")},
            "summary": summary, "summary_problem": serr, "input": input_name,
            "input_sha256": (summary or {}).get("input_sha256"),
            "raw": {n: rel(folder / n) for n in ("cobol-results.csv", "python-results.csv", "cobol-totals.csv",
                                                  "python-totals.csv", "side-by-side.csv", "summary.json")
                    if (folder / n).exists()}}


def saved_rehearsal():
    s1, s4 = REHEARSAL / "stage1-cobol-baseline", REHEARSAL / "stage4-comparison"
    manifest, merr = read_json(s1 / "manifest.json")
    report, rerr = read_json(s1 / "baseline-report.json")
    env = (REHEARSAL / "environment.txt").read_text() if (REHEARSAL / "environment.txt").exists() else None
    return {
        "label": "SAVED REHEARSAL",
        "environment": env,
        "baseline": {"status": "PASSED" if report and report.get("result") == "PASS" else ("NOT_RUN" if rerr == "missing" else "UNKNOWN"),
                     "report": report, "manifest": manifest, "manifest_problem": merr,
                     "curated_totals": totals_row(s1 / "curated-totals.csv"),
                     "synthetic_totals": totals_row(s1 / "synthetic-totals.csv"),
                     "log": rel(REHEARSAL / "stage1-baseline.log"),
                     "raw": {n: rel(s1 / n) for n in sorted(p.name for p in s1.iterdir())} if s1.exists() else {}},
        "policy_tests_cobol": unittest_summary(REHEARSAL / "stage2-pre-migration-tests" / "cobol-run.log"),
        "policy_tests_python": unittest_summary(REHEARSAL / "stage3-python" / "policy-tests-python-first-run.log"),
        "python_unit_tests": unittest_summary(REHEARSAL / "stage3-python" / "python-unit-tests.log"),
        "comparisons": {
            "curated": comparison(s4 / "curated", s4 / "curated-comparison-report.json", "SAVED REHEARSAL", "saved"),
            "synthetic": comparison(s4 / "synthetic", s4 / "comparison-report.json", "SAVED REHEARSAL", "saved"),
            "edge": comparison(s4 / "edge", None, "SAVED REHEARSAL", "saved"),
        },
        "fatal_parity": rel(s4 / "fatal-parity.md") if (s4 / "fatal-parity.md").exists() else None,
        "corrections": rel(REHEARSAL / "stage3-python" / "corrections.md"),
    }


STALE_AFTER = 660  # longest step timeout (600 s) plus slack; run.json is rewritten at every step boundary


def abandoned(run_dir, state):
    """A run that still says RUNNING but stopped updating was killed before it could finish."""
    if state.get("status") != "RUNNING" or state.get("finished_at"):
        return False
    try:
        return time.time() - (run_dir / "run.json").stat().st_mtime > STALE_AFTER
    except OSError:  # archived by Reset since it was read
        return False


def live_run(run_dir):
    state, err = read_json(run_dir / "run.json")
    if err:
        return {"id": run_dir.name, "status": "UNKNOWN", "problem": f"run.json {err}"}
    if abandoned(run_dir, state):
        state = {**state, "status": "INTERRUPTED",
                 "steps": [{**st, "status": "INTERRUPTED"} if st.get("status") == "RUNNING" else st
                           for st in state.get("steps", [])]}
    comparisons = {}
    for name in ("curated", "synthetic"):
        if (run_dir / name).exists():
            comparisons[name] = comparison(run_dir / name, run_dir / f"{name}-verifier.json",
                                           "CURRENT LIVE EXECUTION", "live")
    return {**state, "label": "CURRENT LIVE EXECUTION", "comparisons": comparisons,
            "policy_tests_cobol": unittest_summary(run_dir / "policy-cobol.log"),
            "policy_tests_python": unittest_summary(run_dir / "policy-python.log"),
            "python_unit_tests": unittest_summary(run_dir / "python-units.log"),
            "starter_tests": unittest_summary(run_dir / "starter-tests.log")}


def latest_live():
    if not RUNS.exists():
        return None
    runs = sorted(p for p in RUNS.iterdir() if p.is_dir())
    return live_run(runs[-1]) if runs else None


def history():
    log = git("log", "--format=%H%x09%h%x09%cI%x09%s", "-n", "60") or ""
    commits = [dict(zip(("sha", "short", "date", "subject"), line.split("\t"))) for line in log.splitlines()]
    stages = {}
    for c in commits:
        for key, prefix in (("stage1", "Stage 1:"), ("stage2", "Stage 2:"), ("stage3", "Stage 3:"),
                            ("stage4", "Stage 4:"), ("docs", "Maintainer docs")):
            if c["subject"].startswith(prefix) and key not in stages:
                stages[key] = c
    proof = {"status": "UNKNOWN"}
    if "stage2" in stages and "stage3" in stages:
        no_python = git("cat-file", "-e", f"{stages['stage2']['sha']}:python/msp.py") is None
        ordered = git("merge-base", "--is-ancestor", stages["stage2"]["sha"], stages["stage3"]["sha"]) is not None
        proof = {"status": "PASSED" if no_python and ordered else "FAILED",
                 "python_absent_at_stage2": no_python, "stage2_before_stage3": ordered,
                 "stage2": stages["stage2"]["short"], "stage3": stages["stage3"]["short"]}
    return {"head": git("rev-parse", "HEAD"), "head_short": git("rev-parse", "--short", "HEAD"),
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"), "dirty": bool(git("status", "--porcelain")),
            "starter": STARTER, "stages": stages, "tests_before_python": proof, "commits": commits[:15]}


def build():
    expectations, eerr = read_json(ROOT / "tests_policy" / "expectations.json")
    links, lerr = read_json(ROOT / "demo" / "status.json")
    events, verr = read_csv(ROOT / "docs" / "templates" / "session-events.csv")
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "git": history(), "saved": saved_rehearsal(), "live": latest_live(),
            "expectations": expectations, "expectations_problem": eerr,
            "status": links, "status_problem": lerr, "session_events": events or [],
            "datasets": DATASETS}


if __name__ == "__main__":
    print(json.dumps(build(), indent=1)[:3000])
