"""Tests for a2a-task-state-audit — deterministic, no network."""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import a2a_task_state_audit as ta


def su(tid, state):
    return {"jsonrpc": "2.0", "id": 1, "result": {
        "kind": "status-update", "taskId": tid, "contextId": "c1",
        "final": state in ("completed", "failed"),
        "status": {"state": state}}}


def au(tid, text="chunk"):
    return {"jsonrpc": "2.0", "id": 1, "result": {
        "kind": "artifact-update", "taskId": tid, "contextId": "c1",
        "append": False, "last_chunk": True,
        "artifact": {"artifactId": "a1", "parts": [{"kind": "text", "text": text}]}}}


def sev(findings, level):
    return [m for s, m in findings if s == level]


class TestAudit(unittest.TestCase):
    def test_clean_lifecycle(self):
        findings, tasks = ta.audit([su("t", "submitted"), su("t", "working"), su("t", "completed")])
        self.assertEqual(sev(findings, "CRITICAL"), [])
        self.assertTrue(tasks["t"]["final"])

    def test_resurrection_critical(self):
        findings, _ = ta.audit([su("t", "failed"), su("t", "working")])
        self.assertEqual(len(sev(findings, "CRITICAL")), 1)
        self.assertIn("resumed after terminal", sev(findings, "CRITICAL")[0])

    def test_rejected_is_terminal(self):
        findings, _ = ta.audit([su("t", "rejected"), su("t", "working")])
        self.assertEqual(len(sev(findings, "CRITICAL")), 1)

    def test_unknown_state_critical(self):
        findings, _ = ta.audit([su("t", "vibrating")])
        self.assertIn("unknown state", sev(findings, "CRITICAL")[0])

    def test_illegal_transition_warning(self):
        findings, _ = ta.audit([su("t", "completed")])  # first state completed is legal
        f2, _ = ta.audit([su("t", "input-required"), su("t", "auth-required")])
        self.assertTrue(any("illegal transition" in m for m in sev(f2, "WARNING")))

    def test_artifact_after_terminal_critical(self):
        findings, _ = ta.audit([su("t", "failed"), au("t", "late")])
        self.assertTrue(any("artifact-update for terminal" in m for m in sev(findings, "CRITICAL")))

    def test_never_terminal_warning(self):
        findings, _ = ta.audit([su("t", "working")])
        self.assertTrue(any("never reached" in m for m in sev(findings, "WARNING")))

    def test_status_without_taskid(self):
        e = su("t", "working")
        e["result"].pop("taskId")
        findings, _ = ta.audit([e])
        self.assertTrue(any("without taskId" in m for m in sev(findings, "WARNING")))

    def test_garbage_lines_skipped(self):
        findings, _ = ta.audit(["not json", [], {}, {"result": "x"}, su("t", "completed")])
        self.assertEqual(sev(findings, "CRITICAL"), [])


class TestReport(unittest.TestCase):
    def test_clean_verdict(self):
        code = ta.report([su("t", "submitted"), su("t", "completed")])
        self.assertEqual(code, 0)

    def test_dirty_verdict(self):
        code = ta.report([su("t", "failed"), su("t", "working")])
        self.assertEqual(code, 2)

    def test_warning_only_is_one(self):
        code = ta.report([su("t", "working")])
        self.assertEqual(code, 1)

    def test_state_chain_shown(self):
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ta.report([su("t", "submitted"), su("t", "completed")])
        self.assertIn("submitted -> completed", buf.getvalue())


class TestSimulate(unittest.TestCase):
    CARD = {"name": "x", "description": "y" * 30, "skills": []}

    def test_more_tasks_more_tokens(self):
        self.assertGreater(ta.simulate(self.CARD, tasks=10)["tokens_total"],
                           ta.simulate(self.CARD, tasks=2)["tokens_total"])

    def test_zero_tasks(self):
        self.assertEqual(ta.simulate(self.CARD, tasks=0)["tokens_total"], 0)

    def test_negative_clamped(self):
        self.assertEqual(ta.simulate(self.CARD, tasks=-5, steps=-1)["tokens_total"], 0)

    def test_per_update_tokens_positive(self):
        self.assertGreater(ta.simulate(self.CARD)["per_update_tokens"], 0)


class TestCLI(unittest.TestCase):
    DIR = os.path.dirname(os.path.abspath(__file__))

    def _run(self, *args):
        return subprocess.run(["python3", "a2a_task_state_audit.py", *args],
                              capture_output=True, text=True, cwd=self.DIR)

    def test_audit_dirty_exit2(self):
        p = "/tmp/tsa_t1.jsonl"
        with open(p, "w") as f:
            f.write(json.dumps(su("t", "failed")) + "\n" + json.dumps(su("t", "working")) + "\n")
        self.assertEqual(self._run("audit", p).returncode, 2)

    def test_report_dirty_exit0(self):
        self.assertEqual(self._run("report", "/tmp/tsa_t1.jsonl").returncode, 0)

    def test_missing_file_exit2(self):
        self.assertEqual(self._run("audit", "/nope.jsonl").returncode, 2)

    def test_empty_file_exit2(self):
        p = "/tmp/tsa_t2.jsonl"
        open(p, "w").write("")
        self.assertEqual(self._run("audit", p).returncode, 2)


if __name__ == "__main__":
    unittest.main()
