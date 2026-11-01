# Script internals

Read from [revive-tmux-session](../SKILL.md) before changing or debugging
its scripts, or when a lookup returns no match or the wrong session.

## Parsing: everything goes through `transcript-meta.py`

`scripts/transcript-meta.py` is the single parser. Given paths (argv, or `-`
for stdin) it emits one row per file:

```
path kind session_id cwd interactive mtime_epoch start_epoch parent_id classification
```

`--fast` skips `classification` and stops as soon as identity is known — use
it for correlation, which scans every candidate in a project dir. Omit it
when you need `classification`.

**Fields are separated by ASCII Unit Separator (0x1f), not tab.** Callers
must use `IFS=$'\x1f' read`. Tab is an IFS *whitespace* character in bash, so
`IFS=$'\t' read` collapses runs of tabs and drops empty fields — a row whose
`parent_id` is empty (i.e. every top-level session) silently shifts
`classification` into `parent_id` and leaves `classification` blank. That
presented as every claude row printing `ended:` with nothing after it.

**Do not reintroduce inline `grep`/heredoc parsing.** Every silent-failure
bug in this skill came from that, all found live:

1. `grep '"cwd":"…"'` also matches **nested** payloads (tool results,
   embedded system reminders) and reports a directory the session never ran
   in — that is what makes some sessions show a wrong cwd and others none.
2. `head -c 4000 | grep '"timestamp"'` finds **nothing** when a large
   `{"type":"summary","leafUuid":…}` compaction record leads the file and
   overflows the byte window; the candidate is skipped and correlation
   reports "no match" — hit against a session that was *running at the
   time*, which then made the dead-session scan list a live session as dead.
   Widening the window is not the fix; scanning records until the field
   appears is.
3. A bare `var=$(grep … | …)` under `set -euo pipefail` aborts the **whole**
   calling script when a file lacks the field, discarding a correct match
   found in an earlier loop iteration.

## Finding the session id (when argv has no resume marker)

`scripts/find-session-id.sh <pid> [claude|codex]` (kind defaults to
`claude`) automates the correlation: read the orphan's `cwd` and start time
from `/proc`, then scan its transcript store for an exact `cwd` field match
whose start time lands closest to (and not before) the process's start
time. In practice the gap is a few seconds to under a minute — a tight
match is a strong signal, not a coincidence, even across 100+ candidate
files in a busy project directory.

The two CLIs store transcripts differently:

- **claude**: map `cwd` to its project directory (`~/.claude/projects/<cwd
  with every '/' and '.' replaced by '-'>`), and scan that directory's
  `*.jsonl` files, using the **first record that carries a top-level
  `"timestamp"`** (UTC) as its start time — not literally line 1, which on a
  compaction fork is a `summary`/`leafUuid` record with no timestamp at all.
- **codex**: transcripts live at `~/.codex/sessions/YYYY/MM/DD/rollout-
  <local-timestamp>-<uuid>.jsonl` — both the directory and the filename
  timestamp are in **local** time (unlike the UTC timestamps inside the
  JSON payload itself), so the day-directory to scan is computed straight
  from the process's local start time with no UTC conversion needed. The
  session id is the UUID suffix of the filename, sliced out directly —
  never re-derived from a JSON field, since a forked/subagent-spawned
  rollout file can have a `session_id` payload field pointing at a
  *different* (parent) thread than its own filename UUID. A same-`cwd`
  match is additionally required to be a top-level interactive session on
  the first pass (excludes sub-agent/exec spawns that also write rollout
  files against the same cwd); only if that yields nothing does a second
  pass drop the filter. That test is `thread_source == "user"` on the first
  `session_meta` record — **not** `originator == "codex-tui"`, which every
  sub-agent also reports. See the sub-agent section above.

Sharp edges worth knowing before trusting a "successful" match:

- **The `date -u -d "STRING"` trap.** `ps -o lstart=` prints e.g.
  `Sun Jul 5 10:31:58 2026` with no timezone. Piping that straight into
  `date -u -d "$STRING"` does **not** convert it from local time — GNU date
  silently treats a zone-less string as if it were *already* UTC when `-u`
  is also given, and fails silently (wrong answer, no error). The fix:
  parse in local time first to get epoch seconds, then convert:
  `epoch=$(date -d "$STRING" +%s); utc=$(date -d "@$epoch" -u +...)`.
  `find-session-id.sh` does this correctly; don't reintroduce the shortcut.
- **Compaction forks share a start instant.** Two different session-id
  files can have the *identical* first-line timestamp (down to the
  millisecond) when one is a compaction/summary fork of the other. The
  real, actively-continued session is the one with the far-later `mtime`
  (still being written to hours/days later); the abandoned fork stops
  almost immediately after creation. `find-session-id.sh` breaks timestamp
  ties by preferring the later `mtime`, but if you're eyeballing candidates
  manually, check `mtime` before trusting a timestamp match alone.

## Finding fully-dead sessions (`find-dead-sessions.sh`)

Works backwards from `find-session-id.sh`'s direction: instead of a live
pid's `cwd` + start time pointing at a transcript, it starts from recently
*modified* transcripts (`-mmin` within the requested hour window, default
4) and reads each one's own embedded `cwd` field directly (claude: a
top-level `"cwd"` key on most message lines; codex: `payload.cwd` on the
first `session_meta` line — both read with `json.loads` per line, not grep,
since grep would also match a `cwd` key nested inside a tool call's
arguments and misattribute it).

A transcript only gets reported as dead if it is NOT already backed by a
live, tmux-tracked process — otherwise every transcript belonging to a
still-open, merely-idle session would misreport as dead the moment its pane
goes a few minutes without a write. The exclusion set is built the same way
`find-orphans.sh` enumerates live CLIs, but keeping the ones that ARE
tmux-tracked (the opposite filter) instead of the ones that aren't: for each
live tracked pid, read its current session id straight from argv if it
already has `--resume <id>` / `resume <id>`, otherwise fall back to
`find-session-id.sh <pid> <kind>`. A 90-second freshness guard on top skips
any candidate file written within the last 90s regardless, since that one
might still be mid-write from a live process this pass didn't manage to
correlate.

Each candidate gets a best-effort classification of how its last turn
ended, from the last few lines of the transcript:

- **claude**: last real (`user`/`assistant`) message's shape — the literal
  marker text `"[Request interrupted by user]"` means an explicit
  Esc/Ctrl-C; an assistant message ending on an uncompleted `tool_use` block
  means it was cut off mid-action; anything else is just "idle" (a normal
  stopping point, not evidence of a crash).
- **codex**: the last event's `payload.type` — `task_complete` means a
  clean finish; an unmatched `function_call`/`local_shell_call` with no
  following `function_call_output` means cut off mid-action.

`ended: ... -- possibly killed` is a *hint*, not proof — a normal end of
turn where the user simply hasn't replied yet looks identical to one where
the pane died between the assistant's message and the user's next input.
Treat it as "worth a look," not "confirmed crash."

Candidates of both kinds are additionally required to be top-level
interactive sessions, same reasoning as `find-session-id.sh`'s first pass:
excludes sub-agent/exec transcripts that share a cwd but were never an
actual tmux pane. For codex that test is `thread_source == "user"` on the
first `session_meta` record. It was originally
`"originator":"codex-tui"`, which does **not** work — sub-agent threads
report that originator too. See the sub-agent section above.

A successful `tmux new-window` does not prove the resumed CLI stays alive.
Verify the actual pane process after launch; a transcript classified `idle`
can belong to a session that exits immediately on resume.

## Testing without live inference

Verifying `find-orphans.sh` and `find-session-id.sh` against real, currently
live processes is safe and cheap — they only read `/proc` and transcript
files. Verifying `revive.sh`'s actual launch step is where it's easy to hurt
yourself:

- **claude**: `revive.sh` replays the orphan's `argv[0]` *exactly as it was*.
  A synthetic test orphan whose `argv[0]` is the bare string `claude` (e.g.
  built via `bash -c 'exec fake-script args'`, which the kernel's shebang
  handling rewrites to `bash /path/to/fake-script args` — NOT `argv[0]=
  claude` like you asked for) will, when relaunched, resolve `claude`
  through `$PATH` to the **real installed binary**, not your fake one. This
  happened once: a test orphan's replayed argv looked like `claude
  /path/to/fake_body.sh --resume <made-up-id>`, which the real CLI
  interpreted as "read this file as a prompt", and it was mid-inference
  (real tokens, real quota) before it got caught and killed. Fix: give the
  test orphan an **absolute path** as `argv[0]` (via `exec -a
  /abs/path/to/fake-claude ...`, or simpler, run a real script file located
  exactly at that absolute path) so replay can only ever invoke your fake
  file, never something found on `$PATH`.
- **codex**: relaunch reconstructs the literal command `codex`. Use an
  isolated subprocess environment with a mock `codex` first on `PATH`, and
  mock `tmux` so no real pane or inference can launch. Remove inherited
  `BASH_ENV` and exported shell functions that can bypass executable mocks.
  Alternatively test only command reconstruction without launching it.
- Whichever CLI, always verify the actual pane process after a live test
  (`ps` on the window's `pane_pid`, or check `pane_current_command`) rather
  than trusting the printed "cmd:" line alone — that line is a correct
  preview of *what will be run*, not proof of *what actually ran*.
