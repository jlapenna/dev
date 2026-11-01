#!/usr/bin/env bash
# Give an orphaned `claude` or `codex` process (found via find-orphans.sh) a
# fresh, interactive home: a new tmux window, in the process's original
# working directory, running the same CLI with its exact original argv.
#
# This does NOT reattach to the orphan's live memory/conversation state —
# that isn't possible once its terminal is gone (reptyr was tried and
# abandoned for this — see SKILL.md). If the orphan's argv already resumes
# a specific session (claude: `--resume <id>`; codex: `resume <id>`), the
# new invocation continues that same transcript (the id is what matters,
# not the process). If it didn't, this tries find-session-id.sh to
# correlate the orphan's cwd + start time to its transcript file and
# resume that specific id directly; only if that correlation fails does it
# fall back to a bare resume (interactive picker) and make the user pick.
#
# Usage: revive.sh <pid> [window-name]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PID="${1:?usage: revive.sh <pid> [window-name]}"
NAME="${2:-revived-$PID}"
found_id=""

[ -d "/proc/$PID" ] || { echo "No such process: $PID" >&2; exit 1; }

CWD=$(readlink "/proc/$PID/cwd") || { echo "Can't read cwd for $PID (permission or already exited)" >&2; exit 1; }

# argv, NUL-separated -> bash array, preserving each arg exactly.
ARGS=()
while IFS= read -r -d '' arg; do
  ARGS+=("$arg")
done < "/proc/$PID/cmdline"

[ "${#ARGS[@]}" -gt 0 ] || { echo "PID $PID has an empty argv (already exited?)" >&2; exit 1; }

# Classify: claude is a single process (argv[0] "claude"). codex is
# node-wrapped (argv[0] "node", argv[1] basename codex[.js]) or, more
# rarely, a directly-invoked native binary (argv[0] basename "codex").
a0=$(basename -- "${ARGS[0]}")
KIND=""
if [ "$a0" = "claude" ]; then
  KIND="claude"
elif [ "$a0" = "node" ] && [ "${#ARGS[@]}" -ge 2 ] && [[ "$(basename -- "${ARGS[1]}")" =~ ^codex(\.js)?$ ]]; then
  KIND="codex"
elif [ "$a0" = "codex" ]; then
  KIND="codex"
fi

if [ -z "$KIND" ]; then
  echo "PID $PID is neither a claude nor a codex process (argv[0]=${ARGS[0]:-<empty>})" >&2
  exit 1
fi

if [ "$KIND" = "claude" ]; then
  RELAUNCH=("${ARGS[@]}")

  if printf '%s\n' "${RELAUNCH[@]}" | grep -qx -- '--resume'; then
    echo "Original argv includes --resume: the new pane will continue that transcript."
  else
    correlate_log=$(mktemp)
    if found_id=$("$SCRIPT_DIR/find-session-id.sh" "$PID" claude 2>"$correlate_log"); then
      echo "No --resume in original argv, but correlated it to session $found_id (see details below):"
      sed 's/^/  /' "$correlate_log"
      RELAUNCH+=("--resume" "$found_id")
    else
      echo "No --resume in original argv, and couldn't confidently correlate a transcript (see below) — appending a bare --resume so the new pane opens the interactive picker instead of starting a blank session."
      sed 's/^/  /' "$correlate_log"
      RELAUNCH+=("--resume")
    fi
    rm -f "$correlate_log"
  fi
else
  # codex: figure out where the "real" args start (past node+scriptpath).
  if [ "$a0" = "node" ]; then
    offset=2
  else
    offset=1
  fi
  REST=("${ARGS[@]:$offset}")
  RELAUNCH=("codex")

  if [ "${#REST[@]}" -ge 1 ] && [ "${REST[0]}" = "resume" ]; then
    echo "Original argv already runs 'codex resume': the new pane will continue that transcript."
    RELAUNCH+=("${REST[@]}")
  else
    correlate_log=$(mktemp)
    if found_id=$("$SCRIPT_DIR/find-session-id.sh" "$PID" codex 2>"$correlate_log"); then
      echo "No 'resume' subcommand in original argv, but correlated it to codex session $found_id (see details below):"
      sed 's/^/  /' "$correlate_log"
      # Carry over flags (leading '-') from the original invocation, e.g.
      # --dangerously-bypass-approvals-and-sandbox; drop any bare
      # positional (an initial prompt) since resume already replays history.
      FLAGS=()
      for a in "${REST[@]}"; do
        [[ "$a" == -* ]] && FLAGS+=("$a")
      done
      RELAUNCH+=(resume "$found_id" "${FLAGS[@]}")
    else
      echo "No 'resume' subcommand in original argv, and couldn't confidently correlate a saved session (see below) — appending a bare 'codex resume' so the new pane opens the interactive picker instead of starting a blank session."
      sed 's/^/  /' "$correlate_log"
      RELAUNCH+=(resume)
    fi
    rm -f "$correlate_log"
  fi
fi

# A revived agent has no reliable original terminal to receive approvals.
# Always restore it with the CLI's explicit bypass flag, while preserving an
# identical flag from the original argv if it was already present.
if [ "$KIND" = "claude" ]; then
  DANGEROUS_FLAG="--dangerously-skip-permissions"
else
  DANGEROUS_FLAG="--dangerously-bypass-approvals-and-sandbox"
fi
if ! printf '%s\n' "${RELAUNCH[@]}" | grep -Fqx -- "$DANGEROUS_FLAG"; then
  RELAUNCH+=("$DANGEROUS_FLAG")
fi

# A resumed session can be recorded from a primary checkout even though its
# task has an issue-specific linked worktree. Prefer an explicit override;
# otherwise switch only when transcript task context identifies one unique
# linked worktree. A failed/ambiguous inference deliberately keeps CWD.
TARGET_CWD="${REVIVE_WORKTREE:-$CWD}"
if [ -z "${REVIVE_WORKTREE:-}" ]; then
  SESSION_ID=""
  for ((i = 0; i < ${#RELAUNCH[@]}; i++)); do
    if { [ "$KIND" = "claude" ] && [ "${RELAUNCH[i]}" = "--resume" ]; } || \
       { [ "$KIND" = "codex" ] && [ "${RELAUNCH[i]}" = "resume" ]; }; then
      SESSION_ID="${RELAUNCH[i + 1]:-}"
      break
    fi
  done
  if [ -n "$SESSION_ID" ] && inferred=$("$SCRIPT_DIR/infer-worktree.py" "$KIND" "$SESSION_ID" "$CWD" 2> >(sed 's/^/  worktree: /' >&2)); then
    TARGET_CWD="$inferred"
  fi
fi
[ -d "$TARGET_CWD" ] || { echo "target worktree does not exist: $TARGET_CWD" >&2; exit 1; }

echo "Reviving PID $PID ($KIND) in a new tmux window '$NAME':"
echo "  recorded cwd: $CWD"
echo "  launch cwd: $TARGET_CWD"
printf '  cmd:'; printf ' %q' "${RELAUNCH[@]}"; echo

if [ -z "${TMUX:-}" ]; then
  echo "error: not inside a tmux client session (\$TMUX unset) — run this from within tmux, or use 'tmux new-window -t <session>' manually." >&2
  exit 1
fi

# tmux's shell-command argument is always run through a shell, so quote
# each arg defensively even though these CLIs' own flags are normally simple.
CMD=""
for a in "${RELAUNCH[@]}"; do
  printf -v q '%q' "$a"
  CMD="$CMD $q"
done

tmux new-window -c "$TARGET_CWD" -n "$NAME" "$CMD"

pgid=$(ps -o pgid= -p "$PID" 2>/dev/null | tr -d ' ')

echo
echo "Done. The orphan (PID $PID) is still running untouched — it is not part of any tmux pane."
echo "warning: the new pane is resuming a specific session id (picker selection or $([ -n "$found_id" ] && echo "the correlated $found_id" || echo "the original resume id")) while the orphan is still alive."
echo "  If both end up writing to that transcript at once it can interleave/corrupt it — kill the"
echo "  orphan soon. Use its whole process group, not just the pid:"
echo "    kill -- -${pgid:-$PID}"
if [ "$KIND" = "codex" ]; then
  echo "  codex's code-mode-host MCP helper runs in its OWN detached process group, so the above"
  echo "  will NOT reach it. Check for a lingering 'codex-code-mode-host' child of the native"
  echo "  binary pid and kill it separately if it's still around after the kill above."
else
  echo "  claude sessions with an active chrome-devtools (or similar) MCP subprocess have the same"
  echo "  issue — those also detach into their own process group and won't be reached by the kill above."
fi
