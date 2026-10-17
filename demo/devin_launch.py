"""Start and follow a live Devin session that runs the migration Playbook (Devin API v3).

The API key is read from DEVIN_API_KEY on the server and is never sent to the browser.
State for the latest launched session is kept in build/devin-runs/latest.json.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

import evidence

API = os.environ.get("DEVIN_API_BASE", "https://api.devin.ai/v3")
ORG_ID = os.environ.get("DEVIN_ORG_ID", "org-3c6501402dcf4b9190f5cdf0fc60b67c")
PLAYBOOK_ID = "playbook-f242f29f76f8440ea96928dfeec1d441"
REPO = "wstomber/devinexecdemo"
START_BRANCH = "demo/starter-37ceca1"
TITLE = "Live demo: MSP COBOL to Python from the COBOL-only starter"
PROMPT = (f"Run this Playbook on {REPO} starting from branch {START_BRANCH}. "
          f"This is a live demo run: open the pull request into {START_BRANCH}, never into main.")
STATE = evidence.ROOT / "build" / "devin-runs" / "latest.json"
ACTIVE = {"new", "claimed", "running", "resuming"}
FINAL = {"exit", "error"}
LOCK = threading.Lock()
_checked = {"at": 0.0}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def configured():
    return bool(os.environ.get("DEVIN_API_KEY"))


def call(method, path, body=None):
    req = urllib.request.Request(
        f"{API}/organizations/{ORG_ID}{path}", method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {os.environ['DEVIN_API_KEY']}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read() or b"{}")


def problem(exc):
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body = json.loads(exc.read() or b"{}")
            detail = body.get("detail") or body.get("title")
        except ValueError:
            detail = None
        return f"Devin API answered {exc.code}" + (f": {detail}" if isinstance(detail, str) else "")
    if isinstance(exc, urllib.error.URLError):
        return f"Could not reach the Devin API ({exc.reason})"
    return f"Devin API call failed ({type(exc).__name__})"


def load():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return None


def save(session):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(session, indent=2) + "\n")
    tmp.replace(STATE)


def merge(session, data):
    session.update({
        "status": data.get("status"),
        "status_detail": data.get("status_detail"),
        "pull_requests": [{"url": p.get("pr_url"), "state": p.get("pr_state")}
                          for p in data.get("pull_requests") or [] if p.get("pr_url")],
        "checked_at": now(),
    })
    session.pop("problem", None)
    return session


def is_active(session):
    return bool(session) and session.get("status") in ACTIVE and session.get("status_detail") != "finished"


def state(max_age=8):
    """Latest launched session, refreshed from the API at most every max_age seconds."""
    session = load()
    if session and configured() and session.get("status") not in FINAL and \
            time.monotonic() - _checked["at"] >= max_age:
        _checked["at"] = time.monotonic()
        sid = session["session_id"]
        try:
            merge(session, call("GET", f"/sessions/{sid if sid.startswith('devin-') else 'devin-' + sid}"))
        except Exception as exc:  # noqa: BLE001 - shown on screen, never fatal
            session["problem"] = problem(exc)
        save(session)
    return {"configured": configured(), "playbook_id": PLAYBOOK_ID, "start_branch": START_BRANCH,
            "session": session}


def start():
    """Create the session. Returns (http_code, payload). One active launch at a time."""
    if not configured():
        return 503, {**state(), "error": "This server has no DEVIN_API_KEY, so it cannot start Devin. "
                                         "Use the manual steps instead."}
    with LOCK:
        current = load()
        if is_active(current):
            return 409, {**state(max_age=0), "error": "A live Devin session is already running."}
        try:
            data = call("POST", "/sessions", {"prompt": PROMPT, "playbook_id": PLAYBOOK_ID,
                                              "repos": [REPO], "title": TITLE,
                                              "tags": ["devinexecdemo-live"]})
        except Exception as exc:  # noqa: BLE001
            return 502, {**state(), "error": problem(exc)}
        session = merge({"session_id": data["session_id"], "url": data["url"], "title": TITLE,
                         "started_at": now(), "playbook_id": PLAYBOOK_ID}, data)
        save(session)
        _checked["at"] = time.monotonic()
        return 201, state()
