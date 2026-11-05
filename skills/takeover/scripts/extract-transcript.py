#!/usr/bin/env python3
"""Condense an agent transcript into what a successor needs to read.

Supports:
  - Antigravity:  ~/.gemini/antigravity-cli/brain/<id>/.system_generated/logs/transcript.jsonl
  - Claude Code:  ~/.claude/projects/<cwd-slug>/<session-id>.jsonl
  - Codex CLI:    ~/.codex/sessions/YYYY/MM/DD/rollout-*-<thread-id>.jsonl
  - OpenCode:     ~/.local/share/opencode/opencode.db (pass ses_... id)

Output (stdout or --out FILE):
  META line, every user-role message (truncated), then the last N items
  (assistant text + tool calls) so the successor sees intent and the exact
  point where the predecessor stopped. Harness-injected noise (environment
  context, AGENTS.md, memory refresh banners) is dropped.

Usage:
  extract-transcript.py <transcript.jsonl|ses_id> [--out FILE] [--last 25]
                        [--user-max 600] [--item-max 3000] [--since ISO]
"""
import argparse, datetime, json, os, sqlite3, sys

NOISE_PREFIXES = ("<environment_context>", "# AGENTS.md", "<hindsight", "<system-reminder>",
                  "<command-message>", "<local-command")

def clean(txt):
    return not txt.startswith(NOISE_PREFIXES)

def load_claude(path):
    meta, rows = {}, []
    for line in open(path, encoding="utf-8", errors="replace"):
        try: o = json.loads(line)
        except ValueError: continue
        if o.get("sessionId") and (not meta or not meta.get("cwd")):
            meta = {"id": o.get("sessionId"), "cwd": o.get("cwd"), "timestamp": meta.get("timestamp") or o.get("timestamp"), "harness": "claude"}
            # Subagent transcripts live at <project>/<parent>/subagents/agent-<hash>.jsonl and
            # carry the PARENT's sessionId; identify the subagent by its agentId / filename.
            base = os.path.basename(path)
            if os.path.basename(os.path.dirname(path)) == "subagents" or base.startswith("agent-"):
                meta["parent_session"] = o.get("sessionId")
                meta["id"] = o.get("agentId") or base[len("agent-"):-len(".jsonl")]
                meta["harness"] = "claude-subagent"
        ts, t, m = o.get("timestamp", ""), o.get("type"), o.get("message") or {}
        c = m.get("content")
        if t == "user":
            if isinstance(c, str):
                if clean(c): rows.append((ts, "user", c))
            elif isinstance(c, list):
                for b in c:
                    if b.get("type") == "text" and clean(b.get("text", "")): rows.append((ts, "user", b["text"]))
                    elif b.get("type") == "tool_result":
                        cc = b.get("content"); s = cc if isinstance(cc, str) else json.dumps(cc)
                        rows.append((ts, "RESULT", s))
        elif t == "assistant" and isinstance(c, list):
            for b in c:
                if b.get("type") == "text": rows.append((ts, "assistant", b["text"]))
                elif b.get("type") == "tool_use": rows.append((ts, "CALL " + str(b.get("name")), json.dumps(b.get("input"))))
    return meta, rows

def load_codex(path):
    meta, rows = {}, []
    for line in open(path, encoding="utf-8", errors="replace"):
        try: o = json.loads(line)
        except ValueError: continue
        t, p, ts = o.get("type"), o.get("payload", {}), o.get("timestamp", "")
        if t == "session_meta" and not meta:
            meta = {k: p.get(k) for k in ("id", "cwd", "timestamp")}; meta["harness"] = "codex"
        if t != "response_item": continue
        pt = p.get("type")
        if pt == "message":
            role = p.get("role")
            txt = "".join(x.get("text", "") for x in p.get("content", []) if isinstance(x, dict))
            if role == "developer" or not clean(txt): continue
            rows.append((ts, role, txt))
        elif pt in ("function_call", "custom_tool_call"):
            rows.append((ts, "CALL " + str(p.get("name")), str(p.get("arguments") or p.get("input"))))
        elif pt in ("function_call_output", "custom_tool_call_output"):
            rows.append((ts, "RESULT", str(p.get("output"))))
    return meta, rows

def iso(ms):
    return datetime.datetime.fromtimestamp(int(ms) / 1000, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(ms) % 1000:03d}Z"

def load_opencode(session_id, db=os.path.expanduser("~/.local/share/opencode/opencode.db")):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    s = con.execute("select id, directory, title, time_created from session where id=?", (session_id,)).fetchone()
    if not s: sys.exit(f"opencode session not found: {session_id}")
    meta = {"id": s[0], "cwd": s[1], "title": s[2], "timestamp": iso(s[3]), "harness": "opencode"}
    rows = []
    for mid, tc, data in con.execute("select id, time_created, data from message where session_id=? order by time_created, id", (session_id,)):
        role = json.loads(data).get("role")
        for (pd,) in con.execute("select data from part where message_id=? order by time_created, id", (mid,)):
            part = json.loads(pd); pt = part.get("type")
            ts = iso(tc)
            if pt == "text" and part.get("text"): rows.append((ts, role, part["text"]))
            elif pt == "tool":
                state = part.get("state") or {}
                rows.append((ts, "CALL " + str(part.get("tool")), json.dumps(state.get("input"))))
                result = state.get("error") or state.get("output")
                if result: rows.append((ts, "RESULT" + (" (error)" if state.get("error") else ""), str(result)))
    return meta, rows

def load_agy(path):
    sid = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(path)))))
    meta, rows = {"id": sid, "harness": "agy"}, []
    for line in open(path, encoding="utf-8", errors="replace"):
        try: o = json.loads(line)
        except ValueError: continue
        ts, t, c = o.get("created_at", ""), o.get("type"), o.get("content", "")
        if not meta.get("timestamp") and ts: meta["timestamp"] = ts
        if t == "USER_INPUT" and c:
            rows.append((ts, "user", c))
        elif t == "PLANNER_RESPONSE":
            if c: rows.append((ts, "assistant", c))
            for tc in o.get("tool_calls") or []:
                rows.append((ts, "CALL " + str(tc.get("name")), json.dumps(tc.get("args"))))
        elif t == "GENERIC" and c:
            rows.append((ts, "RESULT", c))
    return meta, rows

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source"); ap.add_argument("--out"); ap.add_argument("--last", type=int, default=25)
    ap.add_argument("--user-max", type=int, default=600); ap.add_argument("--item-max", type=int, default=3000)
    ap.add_argument("--since", default="", help="only items with timestamp >= this ISO prefix")
    a = ap.parse_args()
    if a.source.startswith("ses_"): meta, rows = load_opencode(a.source)
    else:
        head = open(a.source, encoding="utf-8", errors="replace").readline()
        if '"step_index"' in head:
            meta, rows = load_agy(a.source)
        elif '"session_meta"' in head or "rollout-" in os.path.basename(a.source):
            meta, rows = load_codex(a.source)
        else:
            meta, rows = load_claude(a.source)
    if a.since: rows = [r for r in rows if r[0] >= a.since]
    out = open(a.out, "w") if a.out else sys.stdout
    out.write("META " + json.dumps(meta) + "\n\n=== ALL USER MESSAGES (truncated %d) ===\n" % a.user_max)
    out.write("(Verify message provenance: user-role turns can include human instructions, peer relays, or harness content. Style and length do not identify the author.)\n")
    for ts, r, m in rows:
        if r == "user": out.write(f"{ts} {m[:a.user_max]!r}\n")
    out.write(f"\n=== LAST {a.last} ITEMS ===\n")
    for ts, r, m in rows[-a.last:]:
        out.write(f"\n## {ts} {r}\n{m[:a.item_max]}\n")
    if a.out: print(f"wrote {a.out} ({len(rows)} items, {sum(1 for r in rows if r[1]=='user')} user messages)")

if __name__ == "__main__": main()
