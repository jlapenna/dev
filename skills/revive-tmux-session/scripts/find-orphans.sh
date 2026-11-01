#!/usr/bin/env bash
# List `claude` and `codex` CLI processes that are still running but no
# longer belong to any live tmux pane (the pane was closed/killed but the
# process tree under it survived — seen in practice when the child ignores/
# outlives SIGHUP).
#
# claude is a single process: argv[0] basename "claude".
#
# codex is a two-hop tree: `node <path>/bin/codex[.js] <args...>` (the
# launcher, invoked directly by the shell — argv[0] "node", argv[1] the
# codex entry script) execs a native binary child with the same args, which
# in turn spawns a `codex-code-mode-host` helper *in its own new process
# group*. This script tracks the launcher (it's the shell's direct child,
# same role as `claude` itself) — but a later `kill -- -<pgid>` on that
# launcher's group will NOT reach the code-mode-host helper, since it
# detaches into its own group. Same story as claude's chrome-devtools MCP
# subprocess, which also runs in its own group. See SKILL.md.
#
# Usage: find-orphans.sh [cwd-substring]
#   cwd-substring   optional filter, e.g. a repo path. Default: no filter.
set -euo pipefail

FILTER="${1:-}"

# Live tmux pane PIDs across every session on the default socket, one per
# line. Empty (not an error) if no tmux server is running.
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

# Classify a NUL-split argv array (passed by name) as "claude", "codex", or
# "" (neither). codex is recognized either as the node-wrapped launcher
# (argv[0]=node, argv[1] basename codex|codex.js) or, defensively, a
# directly-invoked native binary (argv[0] basename codex, no node parent).
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

# Index of the first "real" codex arg (past the node+scriptpath prefix, if
# any) within a NUL-split argv array passed by name.
codex_offset() {
  local -n _args="$1"
  if [ "$(basename -- "${_args[0]}")" = "node" ]; then
    echo 2
  else
    echo 1
  fi
}

panes="$(live_panes)"
found_any=0

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

  cwd=$(readlink "$pid_dir/cwd" 2>/dev/null) || continue
  [ -z "$FILTER" ] || [[ "$cwd" == *"$FILTER"* ]] || continue

  if is_tracked_by_tmux "$pid" "$panes"; then
    continue
  fi

  full_cmd=$(printf '%s ' "${ARGS[@]}")
  tty=$(readlink "$pid_dir/fd/0" 2>/dev/null || echo "?")
  started=$(ps -o lstart= -p "$pid" 2>/dev/null || echo "?")

  found_any=1
  echo "PID $pid  cli=$kind  tty=$tty  started=$started"
  echo "  cwd: $cwd"
  echo "  cmd: $full_cmd"
  if [ "$kind" = "claude" ]; then
    if printf '%s\n' "${ARGS[@]}" | grep -qx -- '--resume'; then
      echo "  note: already has --resume — reviving with the same flags will continue this transcript."
    else
      echo "  note: no --resume flag — reviving with the same flags starts a NEW session, not a continuation of this one."
    fi
  else
    offset=$(codex_offset ARGS)
    if [ "${#ARGS[@]}" -gt "$offset" ] && [ "${ARGS[$offset]}" = "resume" ]; then
      echo "  note: already running 'codex resume' — reviving with the same flags will continue this transcript."
    else
      echo "  note: no 'resume' subcommand — reviving will try to correlate this to a saved session under ~/.codex/sessions/ and resume that instead of starting blank."
    fi
  fi
  echo
done

if [ "$found_any" -eq 0 ]; then
  echo "No orphaned claude/codex processes found${FILTER:+ under $FILTER}."
fi
