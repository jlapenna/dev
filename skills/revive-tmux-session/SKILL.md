---
name: revive-tmux-session
description: Find `claude` or `codex` CLI processes still running after their tmux pane was closed (orphaned but alive), and give one a fresh interactive home in a new tmux window with its exact original cwd and CLI flags. Also finds sessions of the OTHER kind -- process fully exited, not just pane-less -- by scanning recent transcripts directly, and resumes those from their saved session id. Use when a tmux pane/window disappeared while Claude or Codex was working in it, when checking for orphaned processes before git-mutating work in a shared checkout, or when the user asks to "resume"/"revive"/"restore" a killed pane's session -- including when the process itself is confirmed gone, not just orphaned.
---

# Revive Tmux Session

Requires Linux `/proc`, tmux, Bash 4+, GNU core utilities, Python 3, and the
corresponding installed CLI. It reads the standard per-user transcript stores.

## Why this exists

Closing a tmux pane/window does not reliably kill the process tree under it.
If `bash` (and its `claude` or `codex` child) survive the pane's teardown —
observed in practice, root cause not fully pinned down, but the surviving
processes stay children of the same tmux server — the process keeps running
with a valid pty, just with no tmux pane pointing at it anymore. `tmux
list-panes -a` cannot see it: that command only enumerates *current* panes.

Both CLIs are supported. The two process shapes differ:

- **claude**: a single process, argv[0] `claude`.
- **codex**: a two-hop tree — `node <path>/bin/codex[.js] <args...>` (the
  launcher, the shell's direct child, argv[0] `node`) execs a native binary
  child with the same args, which itself spawns a `codex-code-mode-host`
  helper *in its own detached process group*. The scripts track the
  launcher (same role `claude` plays), but see the process-group caveat
  below — a single `kill -- -<pgid>` will not reach that helper.

## Two ways a session ends up needing revival

1. **Orphaned but alive** (the original case above): the pane closed, the
   process didn't. `find-orphans.sh` + `revive.sh`, driven off `/proc/<pid>`.
2. **Fully dead**: the process itself exited too, so there's no `/proc`
   entry left at all — only the transcript file on disk. This happens more
   than you'd expect: if a pane's shell was wrapping a single one-shot
   invocation (e.g. `codex --dangerously-bypass-approvals-and-sandbox
   "<task>"`), the process finishing its task ends the shell too, and since
   tmux has no `remain-on-exit` by default the window just vanishes at that
   instant — taking any final answer with it if you weren't watching. It
   also happens after a plain interrupt (Esc/Ctrl-C mid-turn) if the pane
   gets closed afterward without resuming first. `find-dead-sessions.sh` +
   `revive-dead.sh` handle this case, working backwards from transcripts
   instead of forwards from a live pid.

## Quick start

```bash
# 1. Find orphans (optionally scoped to a path substring, e.g. a repo) —
#    scans for both claude and codex processes.
scripts/find-orphans.sh "/path/to/repository"

# 2. Give one a new home (auto-detects which CLI the pid belongs to)
scripts/revive.sh <pid> [window-name]

# 1b. Or: find sessions whose process is fully gone (last N hours, default 4;
#     optional cwd-substring filter, same as find-orphans.sh)
scripts/find-dead-sessions.sh 4 "/path/to/repository"

# 2b. Resume one by session id (recorded cwd and id come straight from the listing above)
scripts/revive-dead.sh <claude|codex> <session-id> <cwd> [window-name] [flags...]
```

`revive.sh` reads the orphan's exact `cwd` and `argv` from `/proc/<pid>`,
detects whether it's `claude` or `codex`, opens a new tmux window there via
`tmux new-window`, and launches the same CLI with equivalent flags. When a
specific session id is available, it applies the same safe linked-worktree
inference as `revive-dead.sh`; `REVIVE_WORKTREE` explicitly overrides either
script's target. It must be run from inside a tmux client (checks `$TMUX`).

`revive-dead.sh` does the analogous thing for a session with no process left
at all. It treats its cwd argument as the **recorded** cwd, then, when that
is a primary checkout, scans the transcript's task text against linked Git
worktree branch/path names. A unique issue-number or task-term match becomes
the launch cwd; an ambiguous/no-match result safely stays in the recorded
cwd. Set `REVIVE_WORKTREE=/absolute/path` to force a target. It then runs
`claude --resume <id>` / `codex resume <id>` in the selected tmux window.
No `/proc` is involved, so no argv can be replayed.

## What "revive" actually does — and doesn't

- If the orphan's original argv already resumes a specific session —
  claude: `--resume <session-id>`; codex: a `resume <session-id>`
  subcommand — relaunching with the same argv **continues that exact
  transcript**.
- If it didn't (claude: a plain `claude --dangerously-skip-permissions` or
  similar; codex: a plain `codex --dangerously-bypass-approvals-and-sandbox`
  or similar, no `resume` subcommand), `revive.sh` calls
  `scripts/find-session-id.sh <pid> [claude|codex]` to correlate the
  orphan's `cwd` + process start time against its transcript store —
  claude: `.jsonl` files under `~/.claude/projects/<project-dir>/`; codex:
  `rollout-*.jsonl` files under `~/.codex/sessions/YYYY/MM/DD/` — and
  resumes that specific id directly if the match is confident. Only if
  correlation fails does it fall back to a bare resume (interactive picker)
  and make the user pick. See [script internals](references/script-internals.md) for how the
  correlation works and its known sharp edges. For codex specifically, any
  flag-shaped args from the original invocation (e.g.
  `--dangerously-bypass-approvals-and-sandbox`) are carried over after the
  `resume <id>`; a bare positional (an initial prompt) is dropped since
  resuming already replays that history.
- The orphan process itself is **never touched automatically**. `revive.sh`
  prints a `kill -- -<pgid>` reminder at the end — use the **process
  group**, not the bare pid: these orphans commonly have an MCP subprocess
  tree hanging off them that runs in its **own separate, detached process
  group** — claude's `chrome-devtools` MCP subprocess (`npm exec chrome` →
  `chrome-devtools` server) and codex's `codex-code-mode-host` helper both
  do this (verified via `ps -o pid,ppid,pgid`: the helper's pgid equals its
  own pid, not its parent's). A plain `kill <pid>` only kills the top
  process, and even `kill -- -<pgid>` on the *launcher's* group won't reach
  a helper that already detached into its own group — check for it
  separately (e.g. `pgrep -a -P <native-binary-pid>`) and kill it too if
  it's still around. If you're about to resume a specific session id
  (correlated or picker-selected) while the orphan is still alive, kill it
  **before** relying on the new pane — two processes writing the same
  transcript file risks interleaving/corrupting it.

## Sub-agent threads are NOT resumable — identify and exclude them

Both CLIs write transcripts for sub-agents that look like ordinary sessions.
Reviving one gets you a window you cannot type into: codex opens it read-only
and prints `› Viewing sub-agent — direct input is disabled`.
`find-dead-sessions.sh` excludes them and reports how many it dropped;
`revive-dead.sh` refuses one and points at the parent.

- **codex** — the discriminator is `thread_source` in the **first**
  `session_meta` record: `"user"` for a real session, `"subagent"` for a
  spawned thread, which also carries
  `source.subagent.thread_spawn.parent_thread_id`.

  **`originator` is not a discriminator:** subagent threads also report
  `codex-tui`. Only the first `session_meta` counts: later records may replay
  the parent's metadata and must not overwrite the child's identity.
- **claude** — sub-agent transcripts live at
  `<project-dir>/<parent-session-id>/subagents/agent-<hash>.jsonl`. The path
  is keyed by the **parent session id**, so the grandparent directory names
  the spawner. (Not a top-level `subagents/` project dir, which is what the
  layout looks like from `basename` alone — and note this is depth 3, so a
  `find -maxdepth 2` misses them entirely.)

**Known limitation:** a headless spawn (`claude --output-format stream-json
--system-prompt …`, e.g. a `/security-review` pass) writes a transcript
*indistinguishable* from a human session — `isSidechain: false`,
`userType: external`, its own top-level id, no parent pointer. These appear
as ordinary dead sessions. Recognize them by shape: tiny entry count, a
machine-worded first user message, and a last action of
`[tool:StructuredOutput]`. Re-running one costs less than resuming it.

## Correlation only works for sessions the process STARTED

`find-session-id.sh` matches on "transcript start time at-or-after process
start time." That premise breaks for a **resumed** session: its transcript
began long before the process that is now writing to it, so the correct
answer is structurally excluded and a *newer, stale* transcript sharing the
cwd wins instead.

**argv wins over correlation, always.** `find-session-id.sh` now returns
any `--resume <id>` / `resume <id>` found in the pid's argv and skips
correlation entirely. Correlation is strictly the fallback for a process
that started a *fresh* session, which is the only case where the transcript
can post-date the process.

Corollary worth remembering: `--resume` **continues** the original
transcript, it does not fork a new id. A project directory accumulating new
session ids next to an old one means new sessions were started there, not
that resuming rewrote anything.

## Script internals

Before changing or debugging the scripts, or when a lookup returns no match or
the wrong session, read [script internals](references/script-internals.md). It
covers the `transcript-meta.py` row format, session-id correlation and its
date and compaction traps, how `find-dead-sessions.sh` classifies sessions,
and how to test the scripts without disturbing live sessions.

## Why not `reptyr`?

Live reattachment with `reptyr` was tried and abandoned here: it needs a
system-wide `ptrace_scope=0`, refuses targets that share a process group
with MCP subprocesses, and once attached to a pty other than the visible
window. Use the disk-based resume path instead.

## Detecting orphans before git-mutating work

In a shared checkout used by multiple concurrent Claude or Codex sessions,
run `find-orphans.sh <repo-path>` before any `git checkout`/`stash`/`reset`/
`commit`/`gh pr merge` — tmux panes alone undercount live sessions. See
`repo-tools:worktree-hygiene` for the shared-checkout rules this protects.

`find-dead-sessions.sh <repo-path>` doesn't need this same pre-mutation
check — a fully-dead session has no live process to conflict with your
git command by definition — but it's the right tool right *after*, when
someone asks "did I lose work when that pane disappeared" and the answer
needs to come from disk, not from `ps`.
