# a2a-task-state-audit

**Audit A2A task lifecycle transitions from a recorded stream. Dumb math, honest numbers, zero dependencies.**

[![Tests](https://img.shields.io/badge/tests-21%20passed-brightgreen)]() [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)]()

Fifth in the a2a family: [a2a-tax](https://github.com/ZidoCode/a2a-tax) (polling), [a2a-stream-tax](https://github.com/ZidoCode/a2a-stream-tax) (streaming), [a2a-reconnect-tax](https://github.com/ZidoCode/a2a-reconnect-tax) (reconnects), [a2a-artifact-audit](https://github.com/ZidoCode/a2a-artifact-audit) (artifacts), and now the task state machine itself.

The A2A spec ([life-of-a-task](https://github.com/a2aproject/A2A/blob/main/docs/topics/life-of-a-task.md)) defines a strict state machine: `submitted → working → input-required/… → completed/failed/canceled/rejected`, and **terminal states are final**. But nothing forces a buggy server to respect that. Tasks get *resurrected* after `failed`, content arrives after `completed`, servers invent state values that don't exist in the spec, and tasks sit in `working` forever.

a2a-task-state-audit replays a recorded `message/stream` session (JSONL) and reports every lifecycle violation.

## Install

```bash
pip install a2a-task-state-audit   # or: copy the .py file
```

## Usage

```bash
$ a2a-task-state-audit report stream.jsonl
a2a-task-state-audit report — 6 task(s), 7 finding(s)

  good-task      3 states   46 tok  submitted -> working -> completed
  zombie-task    3 states   45 tok  submitted -> failed -> working
  ...

  [CRITICAL] line 7: task 'zombie-task' resumed after terminal state 'failed' -> 'working' (terminal states are final)
  [CRITICAL] line 9: unknown state 'vibrating' for task 'weird-task' (not in the A2A TaskState enum)
  [WARNING ] task 'open-task' never reached a terminal state (last: 'working')

  verdict: 5 CRITICAL — task lifecycle violated (terminal state not respected).
$ a2a-task-state-audit audit stream.jsonl && echo ok   # CI gate: exit 2 on critical
```

## What it catches

| Finding | Severity | The bug class |
|---|---|---|
| Task resumed after terminal state | **CRITICAL** | resurrection — `failed`/`completed`/`canceled`/`rejected` must be final |
| Unknown state value | **CRITICAL** | not in the A2A `TaskState` enum — client falls over |
| Artifact after terminal | **CRITICAL** | content delivered after the task closed |
| Illegal transition | WARNING | e.g. `input-required → auth-required` skips `working` |
| Task never terminal | WARNING | stuck in `working` — client waits forever |
| Missing taskId/state | WARNING | malformed events |

`report` is informational (always exit 0 unless findings). `audit` is the CI gate: exit 0 clean, 1 warnings-only, 2 critical.

## Stream format

One JSON event per line (same as [a2a-stream-tax](https://github.com/ZidoCode/a2a-stream-tax)):

```
{"jsonrpc":"2.0","id":1,"result":{"kind":"status-update","taskId":"t1","contextId":"c1","status":{"state":"working"}}}
```

Record your client's session, replay it, ship the fix. Deterministic — same stream, same findings, byte for byte. MIT license.
