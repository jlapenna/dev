#!/usr/bin/env bash
# List recently-touched claude/codex session transcripts whose process has
# fully exited -- not an orphan (find-orphans.sh's job: alive, no pane),
# but genuinely gone, e.g. because the pane's shell wrapped a single `codex
# ...`/`claude ...` invocation and closed the instant that process exited
# (tmux has no remain-on-exit by default, so the window just vanishes,
# taking any final answer with it unless you were watching).
#
# There is no /proc entry left to correlate from for these, so unlike
# find-orphans.sh this works backwards from the transcript files
# themselves: scan recently-modified ones, read each transcript's own
# embedded `cwd` field, and report it as "dead" only if no CURRENTLY LIVE,
# tmux-tracked claude/codex process is already resuming that exact session
# id. That exclusion check matters -- without it, every transcript
# belonging to a still-running interactive session would misreport as
# dead the instant its owning pane goes a few minutes without a write.
#
# Usage: find-dead-sessions.sh [hours] [cwd-substring]
#   hours          how far back to scan by mtime. Default: 4.
#   cwd-substring  optional filter, e.g. a repo path. Default: no filter.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

HOURS="${1:-4}"
FILTER="${2:-}"
MMIN=$(( HOURS * 60 ))
NOW=$(date +%s)
FRESH_GUARD=90  # skip files written within the last N seconds -- could still be a live write in flight

# ---- same tmux-tracking helpers as find-orphans.sh ----
live_panes() {
  tmux list-panes -a -F '#{pane_pid}' 2>/dev/null || true
}

is_tracked_by_tmux() {
  local pid="$1" panes="$2" cur="$1" ppid
  while [ -n "$cur" ] && [ "$cur" != "1" ]; do
    if grep -qx "$cur" <<<"$panes"; then
      return 0
    fi
    ppid=$(awk '/^PPid:/{print $2}' "/proc/$cur/status" 2>/dev/null) || return 1
    [ -n "$ppid" ] || return 1
    cur="$ppid"
  done
  return 1
}

cli_kind() {
  local -n _args="$1"
  [ "${#_args[@]}" -ge 1 ] || { echo ""; return; }
  local a0 a1
  a0=$(basename -- "${_args[0]}")
  if [ "$a0" = "claude" ]; then
    echo "claude"
  elif [ "$a0" = "node" ] && [ "${#_args[@]}" -ge 2 ]; then
    a1=$(basename -- "${_args[1]}")
    if [[ "$a1" =~ ^codex(\.js)?$ ]]; then echo "codex"; else echo ""; fi
  elif [ "$a0" = "codex" ]; then
    echo "codex"
  else
    echo ""
  fi
}

codex_offset() {
  local -n _args="$1"
  if [ "$(basename -- "${_args[0]}")" = "node" ]; then
    echo 2
  else
    echo 1
  fi
}

is_in() {
  local needle="$1"; shift
  local x
  for x in "$@"; do
    [ "$x" = "$needle" ] && return 0
  done
  return 1
}

# ---- build the exclusion set: session ids already backed by a live, tmux-tracked process ----
panes="$(live_panes)"
LIVE_CLAUDE_IDS=()
LIVE_CODEX_IDS=()

for pid_dir in /proc/[0-9]*; do
  pid="${pid_dir#/proc/}"
  cmdline_file="$pid_dir/cmdline"
  [ -r "$cmdline_file" ] || continue

  ARGS=()
  while IFS= read -r -d '' arg; do
    ARGS+=("$arg")
  done < "$cmdline_file" 2>/dev/null
  [ "${#ARGS[@]}" -gt 0 ] || continue

  kind=$(cli_kind ARGS)
  [ -n "$kind" ] || continue
  is_tracked_by_tmux "$pid" "$panes" || continue

  if [ "$kind" = "claude" ]; then
    id=""
    for i in "${!ARGS[@]}"; do
      if [ "${ARGS[$i]}" = "--resume" ] && [ $((i + 1)) -lt "${#ARGS[@]}" ]; then
        cand="${ARGS[$((i + 1))]}"
        [[ "$cand" != -* ]] && id="$cand"
      fi
    done
    if [ -z "$id" ]; then
      id=$("$SCRIPT_DIR/find-session-id.sh" "$pid" claude 2>/dev/null) || id=""
    fi
    [ -n "$id" ] && LIVE_CLAUDE_IDS+=("$id")
  else
    offset=$(codex_offset ARGS)
    id=""
    if [ "${#ARGS[@]}" -gt "$((offset + 1))" ] && [ "${ARGS[$offset]}" = "resume" ]; then
      id="${ARGS[$((offset + 1))]}"
    fi
    if [ -z "$id" ]; then
      id=$("$SCRIPT_DIR/find-session-id.sh" "$pid" codex 2>/dev/null) || id=""
    fi
    [ -n "$id" ] && LIVE_CODEX_IDS+=("$id")
  fi
done

found_any=0
skipped_sub=0

# ---- candidate transcripts, both CLIs, newest first ----
#
# All parsing goes through transcript-meta.py (one batched invocation) rather
# than a python heredoc per file. Besides being much faster on a few hundred
# candidates, it is the only place that knows how to read these formats
# correctly -- see that script's header for the three silent-failure bugs
# that inline parsing kept reintroducing.
CANDIDATES=$(mktemp)
trap 'rm -f "$CANDIDATES"' EXIT
{
  find "$HOME/.claude/projects" -maxdepth 4 -name '*.jsonl' -mmin "-$MMIN" 2>/dev/null
  find "$HOME/.codex/sessions" -name 'rollout-*.jsonl' -mmin "-$MMIN" 2>/dev/null
} > "$CANDIDATES" || true

if [ ! -s "$CANDIDATES" ]; then
  echo "No claude/codex transcripts touched in the last ${HOURS}h."
  exit 0
fi

while IFS=$'\x1f' read -r _f kind session_id file_cwd interactive mtime _start _parent classification; do
  [ -n "$session_id" ] || continue

  age=$(( NOW - mtime ))
  [ "$age" -ge "$FRESH_GUARD" ] || continue

  # Sub-agent threads are recorded like sessions but are NOT resumable: codex
  # opens them read-only ("Viewing sub-agent -- direct input is disabled") and
  # claude's belong to their parent session.
  #
  # This used to filter on `originator == "codex-tui"`, which is WRONG --
  # sub-agent threads report that originator too, so every one of them came
  # through as a revivable session. The working discriminator is
  # thread_source (see transcript-meta.py).
  if [ "$interactive" != "yes" ]; then
    skipped_sub=$(( skipped_sub + 1 ))
    continue
  fi

  [ -n "$file_cwd" ] || continue
  [ -z "$FILTER" ] || [[ "$file_cwd" == *"$FILTER"* ]] || continue

  if [ "$kind" = "claude" ]; then
    is_in "$session_id" "${LIVE_CLAUDE_IDS[@]:-}" && continue
  else
    is_in "$session_id" "${LIVE_CODEX_IDS[@]:-}" && continue
  fi

  found_any=1
  when=$(date -d "@$mtime" '+%Y-%m-%d %H:%M:%S')
  echo "kind=$kind  session=$session_id"
  echo "  cwd: $file_cwd"
  echo "  last activity: $when ($(( age / 60 ))m ago)"
  echo "  ended: $classification"
  if [ ! -d "$file_cwd" ]; then
    echo "  revive: BLOCKED -- that cwd no longer exists (deleted worktree?)"
  else
    echo "  revive: $SCRIPT_DIR/revive-dead.sh $kind $session_id '$file_cwd' [window-name] [flags...]"
  fi
  echo
done < <(python3 "$SCRIPT_DIR/transcript-meta.py" - < "$CANDIDATES" | sort -t$'\x1f' -k6,6nr)

if [ "$found_any" -eq 0 ]; then
  echo "No dead sessions found in the last ${HOURS}h${FILTER:+ under $FILTER}."
fi
if [ "$skipped_sub" -gt 0 ]; then
  echo "($skipped_sub sub-agent/non-interactive thread(s) excluded -- they resume read-only.)"
fi
