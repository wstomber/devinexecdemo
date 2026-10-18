"""The live-Devin launcher: never leaks the key, never double-starts, and reports failures honestly."""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demo"))
import devin_launch  # noqa: E402

KEY = "cog_test_key_never_shown"
CREATED = {"session_id": "abc123", "url": "https://app.devin.ai/sessions/abc123", "status": "claimed",
           "pull_requests": []}


class Launcher(unittest.TestCase):
    def setUp(self):
        self.state = Path(tempfile.mkdtemp()) / "latest.json"
        self.patches = [mock.patch.object(devin_launch, "STATE", self.state),
                        mock.patch.dict(os.environ, {"DEVIN_API_KEY": KEY})]
        for p in self.patches:
            p.start()
        devin_launch._checked["at"] = 0.0

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_without_key_nothing_is_called(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(devin_launch, "call") as call:
            code, payload = devin_launch.start()
        self.assertEqual(code, 503)
        self.assertFalse(payload["configured"])
        call.assert_not_called()

    def test_start_creates_session_with_playbook_and_starter_branch(self):
        with mock.patch.object(devin_launch, "call", return_value=CREATED) as call:
            code, payload = devin_launch.start()
        self.assertEqual(code, 201)
        method, path, body = call.call_args.args
        self.assertEqual((method, path), ("POST", "/sessions"))
        self.assertEqual(body["playbook_id"], devin_launch.PLAYBOOK_ID)
        self.assertIn("demo/starter-37ceca1", body["prompt"])
        self.assertEqual(payload["session"]["url"], CREATED["url"])
        self.assertNotIn(KEY, json.dumps(payload) + self.state.read_text())

    def test_second_start_while_running_is_refused(self):
        running = {**CREATED, "status": "running", "status_detail": "working"}
        with mock.patch.object(devin_launch, "call", side_effect=[CREATED, running]) as call:
            devin_launch.start()
            code, payload = devin_launch.start()
        self.assertEqual(code, 409)
        self.assertEqual(call.call_count, 2)
        self.assertEqual(call.call_args.args[0], "GET")
        self.assertEqual(payload["session"]["status_detail"], "working")

    def test_finished_session_allows_a_new_start(self):
        finished = {**CREATED, "status": "running", "status_detail": "finished"}
        with mock.patch.object(devin_launch, "call", return_value=CREATED):
            devin_launch.start()
        devin_launch.save({**devin_launch.load(), **finished})
        with mock.patch.object(devin_launch, "call", side_effect=[finished, {**CREATED, "session_id": "new1"}]):
            code, payload = devin_launch.start()
        self.assertEqual(code, 201)
        self.assertEqual(payload["session"]["session_id"], "new1")

    def test_one_click_starts_when_saved_status_is_stale_but_devin_finished(self):
        with mock.patch.object(devin_launch, "call", return_value=CREATED):
            devin_launch.start()
        devin_launch.save({**devin_launch.load(), "status": "running", "status_detail": "working"})
        exited = {**CREATED, "status": "exit"}
        with mock.patch.object(devin_launch, "call", side_effect=[exited, {**CREATED, "session_id": "new2"}]) as call:
            code, payload = devin_launch.start()
        self.assertEqual(code, 201)
        self.assertEqual([c.args[0] for c in call.call_args_list], ["GET", "POST"])
        self.assertEqual(payload["session"]["session_id"], "new2")

    def test_poll_does_not_queue_behind_a_slow_refresh(self):
        import threading
        with mock.patch.object(devin_launch, "call", return_value=CREATED):
            devin_launch.start()
        devin_launch._checked["at"] = 0.0
        held, release = threading.Event(), threading.Event()
        holder = threading.Thread(target=lambda: (devin_launch.LOCK.acquire(), held.set(), release.wait(),
                                                  devin_launch.LOCK.release()))
        holder.start(); held.wait()
        try:
            with mock.patch.object(devin_launch, "call") as call:
                payload = devin_launch.state()
            call.assert_not_called()
            self.assertEqual(payload["session"]["session_id"], "abc123")
        finally:
            release.set(); holder.join()

    def test_paused_session_is_kept_not_replaced(self):
        with mock.patch.object(devin_launch, "call", return_value=CREATED):
            devin_launch.start()
        with mock.patch.object(devin_launch, "call", return_value={**CREATED, "status": "suspended"}) as call:
            code, payload = devin_launch.start()
        self.assertEqual(code, 409)
        self.assertNotIn("POST", [c.args[0] for c in call.call_args_list])
        self.assertEqual(payload["session"]["session_id"], "abc123")

    def test_status_refresh_picks_up_pull_request(self):
        with mock.patch.object(devin_launch, "call", return_value=CREATED):
            devin_launch.start()
        devin_launch._checked["at"] = 0.0
        later = {**CREATED, "status": "running", "status_detail": "working",
                 "pull_requests": [{"pr_url": "https://github.com/wstomber/devinexecdemo/pull/9", "pr_state": "open"}]}
        with mock.patch.object(devin_launch, "call", return_value=later) as call:
            payload = devin_launch.state()
        self.assertEqual(call.call_args.args, ("GET", "/sessions/devin-abc123"))
        self.assertEqual(payload["session"]["pull_requests"][0]["state"], "open")

    def test_api_error_is_reported_without_the_key(self):
        err = urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(b'{"detail": "missing UseDevinSessions"}'))
        with mock.patch.object(devin_launch, "call", side_effect=err):
            code, payload = devin_launch.start()
        self.assertEqual(code, 502)
        self.assertIn("403", payload["error"])
        self.assertIn("UseDevinSessions", payload["error"])
        self.assertNotIn(KEY, json.dumps(payload))
        self.assertIsNone(payload["session"])


if __name__ == "__main__":
    unittest.main()


class Reset(unittest.TestCase):
    tearDown = Launcher.tearDown

    def setUp(self):
        self.state = Path(tempfile.mkdtemp()) / "devin-runs" / "latest.json"
        self.patches = [mock.patch.object(devin_launch, "STATE", self.state),
                        mock.patch.dict(os.environ, {"DEVIN_API_KEY": KEY})]
        for p in self.patches:
            p.start()

    def archived(self):
        return sorted(self.state.parent.with_name("devin-runs-archive").glob("*.json"))

    def test_reset_stops_a_live_session_and_clears_the_card(self):
        devin_launch.save({**CREATED, "status": "suspended"})
        with mock.patch.object(devin_launch, "call", return_value={}) as call:
            code, payload = devin_launch.reset()
        self.assertEqual(code, 200)
        self.assertEqual(call.call_args.args[:2], ("DELETE", "/sessions/devin-abc123"))
        self.assertIsNone(payload["session"])
        self.assertFalse(self.state.exists())
        self.assertEqual(len(self.archived()), 1)

    def test_reset_of_a_finished_session_only_clears_the_card(self):
        devin_launch.save({**CREATED, "status": "exit"})
        with mock.patch.object(devin_launch, "call") as call:
            code, payload = devin_launch.reset()
        self.assertEqual(code, 200)
        call.assert_not_called()
        self.assertIsNone(payload["session"])

    def test_failed_stop_keeps_the_card(self):
        devin_launch.save({**CREATED, "status": "running", "status_detail": "working"})
        err = urllib.error.HTTPError("u", 500, "boom", {}, io.BytesIO(b"{}"))
        with mock.patch.object(devin_launch, "call", side_effect=err):
            code, payload = devin_launch.reset()
        self.assertEqual(code, 502)
        self.assertTrue(self.state.exists())
        self.assertIn("Could not stop", payload["error"])
