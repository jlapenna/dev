#!/usr/bin/env python3
"""Extract identity + end-state metadata from claude/codex transcript files.

Reads transcript paths from argv (or one-per-line on stdin when the sole
non-flag argument is "-") and writes one row per readable file, fields
separated by ASCII Unit Separator (0x1f):

  path kind session_id cwd interactive mtime_epoch start_epoch parent_id classification

The separator is 0x1f, NOT a tab, and callers must use `IFS=$'\\x1f' read`.
Tab is an IFS *whitespace* character in bash, so `IFS=$'\\t' read` silently
collapses runs of tabs and drops empty fields — a row whose parent_id is
empty (every top-level session) would shift `classification` into
`parent_id` and leave `classification` blank. 0x1f is not IFS-whitespace,
so empty fields survive, and it cannot occur inside a path or cwd.

kind            "claude" | "codex"
session_id      the id you would pass to `claude --resume` / `codex resume`
cwd             working directory the session ran in ("" if undeterminable)
interactive     "yes" for a top-level human-driven session; "no" for sub-agent
                threads and non-interactive spawns, which are not resumable in
                any useful sense (codex opens them read-only: "Viewing
                sub-agent — direct input is disabled")
mtime_epoch     file mtime, integer seconds
start_epoch     when the session started, integer seconds ("" if unknown)
parent_id       for a sub-agent thread, the parent session id ("" otherwise)
classification  how the session ended: "completed", "interrupted by user",
                "ended mid tool-call (no result) -- possibly killed", etc.
                Empty in --fast mode.

Flags:
  --fast   identity only: stop reading each file as soon as the identity
           fields are known, and skip classification. Correlating a pid
           against a busy project directory scans every candidate, so that
           early exit is the difference between fast and unusable. Callers
           that need `classification` must omit --fast.

This module is deliberately the ONE place that parses transcripts. Every
historical bug in this skill came from ad-hoc `grep` over these files:

  * `grep '"cwd":"…"'` also matches NESTED payloads (tool results, embedded
    system reminders) and reports a directory the session never ran in.
  * `head -c 4000 | grep '"timestamp"'` finds nothing when a large
    {"type":"summary","leafUuid":…} compaction record leads the file and
    overflows the byte window, so the file is silently skipped and
    correlation reports "no match" — even for a session that is running
    right now.
  * a bare `var=$(grep … | …)` under `set -euo pipefail` aborts the whole
    calling script when a file simply lacks the field, discarding a correct
    match already found in an earlier loop iteration.

Parsing per-record in Python avoids all three: fields are read from the top
level of each JSON object, scanning forward until found.

Batched deliberately: a dead-session scan touches hundreds of transcripts,
and paying python's startup cost per file made scans take minutes.

Unreadable/unparseable files are skipped silently — a partially written
transcript is normal when a session was killed mid-write.
"""

import datetime
import json
import os
import re
import sys

# A claude transcript's first line is NOT reliably the session's own header:
# compaction/summary forks start with a {"type":"summary","leafUuid":...}
# record carrying neither "cwd" nor "timestamp". Scan forward instead of
# trusting line 1 (or a fixed byte window).
CLAUDE_SCAN_LINES = 400

# codex encodes the session id in the filename; the JSON payload's
# "session_id" field can point at a *different* (parent) thread for sub-agent
# rollouts, so the filename is the authority. See SKILL.md.
CODEX_NAME_RE = re.compile(
    r"^rollout-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})-"
    r"([0-9a-fA-F]{8}-[0-9a-fA-F-]+)\.jsonl$"
)


def parse_iso(ts):
    """'2026-08-11T04:24:02.203Z' -> epoch seconds, or None."""
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return int(datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def claude_meta(path, fast):
    session_id = os.path.basename(path)[: -len(".jsonl")]
    cwd = ""
    start = None
    last = None  # (role, text, has_tool_use, has_tool_result)

    with open(path, errors="replace") as fh:
        for i, line in enumerate(fh):
            if fast and (i >= CLAUDE_SCAN_LINES or (cwd and start is not None)):
                break
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            # Top-level fields only — nested payloads carry the same key names.
            if not cwd:
                v = d.get("cwd")
                if isinstance(v, str) and v.startswith("/"):
                    cwd = v
            if start is None:
                start = parse_iso(d.get("timestamp"))

            if fast or d.get("type") not in ("user", "assistant"):
                continue
            msg = d.get("message") or {}
            content = msg.get("content")
            text = None
            has_tool_use = has_tool_result = False
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    bt = block.get("type")
                    if bt == "tool_use":
                        has_tool_use = True
                    elif bt == "tool_result":
                        has_tool_result = True
                    elif bt == "text" and text is None:
                        text = block.get("text")
            last = (msg.get("role"), text, has_tool_use, has_tool_result)

    classification = ""
    if not fast:
        classification = "unknown"
        if last:
            role, text, has_tool_use, has_tool_result = last
            if role == "user" and text and "Request interrupted by user" in text:
                classification = "interrupted by user"
            elif role == "assistant" and has_tool_use:
                classification = "ended mid tool-call (no result) -- possibly killed"
            elif role == "assistant":
                classification = "idle (assistant replied, nothing pending)"
            elif role == "user" and has_tool_result:
                classification = "idle (tool result delivered, no reply yet) -- possibly killed"
            elif role == "user":
                classification = "idle (user prompt sent, no reply yet) -- possibly killed"

    # Sub-agent transcripts live at
    #   <project>/<parent-session-id>/subagents/agent-<hash>.jsonl
    # keyed by the PARENT session id, so the grandparent directory names the
    # session that spawned them.
    base = os.path.basename(path)
    parent_dir = os.path.basename(os.path.dirname(path))
    is_sub = base.startswith("agent-") or parent_dir == "subagents"
    parent_id = ""
    if parent_dir == "subagents":
        parent_id = os.path.basename(os.path.dirname(os.path.dirname(path)))

    return session_id, cwd, not is_sub, start, parent_id, classification


def codex_meta(path, fast):
    m = CODEX_NAME_RE.match(os.path.basename(path))
    if not m:
        return None
    file_ts, session_id = m.group(1), m.group(2)

    # Both the day-directory and the filename timestamp are LOCAL time
    # (unlike the UTC timestamps inside the JSON payload), so parse naive.
    try:
        start = int(datetime.datetime.strptime(file_ts, "%Y-%m-%dT%H-%M-%S").timestamp())
    except ValueError:
        start = None

    cwd = ""
    interactive = False
    parent_id = ""
    last_type = last_payload_type = None
    open_calls = set()
    # A sub-agent rollout contains MORE THAN ONE session_meta record: the
    # first is this thread's own (thread_source "subagent"), and a later one
    # replays the PARENT's (thread_source "user"). Only the first is this
    # file's identity — honoring a later one flips a sub-agent to "top-level
    # session" and hands you a read-only window.
    meta_seen = False

    with open(path, errors="replace") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            payload = d.get("payload") if isinstance(d.get("payload"), dict) else {}

            if d.get("type") == "session_meta" and not meta_seen:
                meta_seen = True
                cwd = payload.get("cwd") or ""
                # `originator` is NOT a usable discriminator: sub-agent
                # threads also report "codex-tui". The real signal is
                # thread_source, corroborated by session_id pointing at a
                # different (parent) thread than this file's own id.
                thread_source = payload.get("thread_source")
                interactive = thread_source == "user"
                src = payload.get("source")
                if isinstance(src, dict):
                    spawn = (src.get("subagent") or {}).get("thread_spawn") or {}
                    parent_id = spawn.get("parent_thread_id") or ""
                if not parent_id:
                    sid = payload.get("session_id")
                    if isinstance(sid, str) and sid and sid != session_id:
                        parent_id = sid
                if thread_source is None:
                    # Older rollouts predate thread_source; fall back to the
                    # id-mismatch signal alone.
                    interactive = not parent_id
                if fast:
                    break
                continue

            pt = payload.get("type")
            if d.get("type") == "response_item":
                if pt in ("function_call", "local_shell_call", "custom_tool_call"):
                    cid = payload.get("call_id") or payload.get("id")
                    if cid:
                        open_calls.add(cid)
                elif pt in ("function_call_output", "custom_tool_call_output", "local_shell_call_output"):
                    open_calls.discard(payload.get("call_id"))
            last_type = d.get("type")
            last_payload_type = pt

    classification = ""
    if not fast:
        classification = "unknown"
        if last_payload_type == "task_complete":
            classification = "completed"
        elif open_calls:
            classification = "ended mid tool-call (no result) -- possibly killed"
        elif last_payload_type in ("error", "stream_error"):
            classification = "error"
        elif last_type == "response_item" and last_payload_type == "message":
            classification = "idle (assistant message sent, turn state unclear)"

    return session_id, cwd, interactive, start, parent_id, classification


def main():
    args = [a for a in sys.argv[1:] if a != "--fast"]
    fast = "--fast" in sys.argv[1:]
    paths = [ln.strip() for ln in sys.stdin if ln.strip()] if args == ["-"] else args

    for path in paths:
        try:
            mtime = int(os.path.getmtime(path))
            if os.path.basename(path).startswith("rollout-"):
                got = codex_meta(path, fast)
                if got is None:
                    continue
                kind = "codex"
            else:
                got = claude_meta(path, fast)
                kind = "claude"
        except OSError:
            continue
        except Exception:
            continue

        session_id, cwd, interactive, start, parent_id, classification = got
        if not session_id:
            continue
        print(
            "\x1f".join(
                [
                    path,
                    kind,
                    session_id,
                    cwd,
                    "yes" if interactive else "no",
                    str(mtime),
                    "" if start is None else str(start),
                    parent_id,
                    classification,
                ]
            )
        )


if __name__ == "__main__":
    main()
