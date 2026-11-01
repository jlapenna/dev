#!/usr/bin/env bash
# Give a *dead* claude/codex session -- process fully exited, not an
# orphan -- a fresh interactive home, resuming its saved transcript by
# session id. Companion to find-dead-sessions.sh, which finds these.
#
# This is the counterpart to revive.sh for the other failure mode: revive.sh
# handles a process that's still alive with no pane (read /proc for cwd +
# argv); this handles a process that's already gone entirely, so there is
# no /proc to read -- cwd and session id both come from find-dead-sessions.sh
# having already mined them out of the transcript file itself. There is
# nothing to warn about killing afterward (unlike revive.sh) because there
# was no live orphan to begin with.
#
# Usage: revive-dead.sh <claude|codex> <session-id> <recorded-cwd> [window-name] [extra CLI flags...]
#   window-name   optional; skip it (or start flags with '-') to use the default.
#   extra flags   passed straight through to the CLI. Every revived session
#                 also receives the appropriate non-interactive permission
#                 flag by default.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

KIND="${1:?usage: revive-dead.sh <claude|codex> <session-id> <cwd> [window-name] [flags...]}"
SESSION_ID="${2:?usage: revive-dead.sh <claude|codex> <session-id> <cwd> [window-name] [flags...]}"
CWD="${3:?usage: revive-dead.sh <claude|codex> <session-id> <recorded-cwd> [window-name] [flags...]}"
shift 3

case "$KIND" in
  claude|codex) ;;
  *) echo "kind must be 'claude' or 'codex', got '$KIND'" >&2; exit 1 ;;
esac

[ -d "$CWD" ] || { echo "cwd does not exist: $CWD" >&2; exit 1; }

# A session started in a primary checkout may have been working on an issue
# whose branch lives in a linked worktree. Infer it only when the transcript
# has one clear task match. REVIVE_WORKTREE is an explicit override; use it
# to force a particular target (including the primary checkout).
TARGET_CWD="${REVIVE_WORKTREE:-$CWD}"
if [ -z "${REVIVE_WORKTREE:-}" ]; then
  if inferred=$("$SCRIPT_DIR/infer-worktree.py" "$KIND" "$SESSION_ID" "$CWD" 2> >(sed 's/^/  worktree: /' >&2)); then
    TARGET_CWD="$inferred"
  fi
fi
[ -d "$TARGET_CWD" ] || { echo "target worktree does not exist: $TARGET_CWD" >&2; exit 1; }

# Sanity-check the session id actually has a transcript before we launch an
# interactive picker by accident on a typo.
TRANSCRIPT=""
if [ "$KIND" = "claude" ]; then
  PROJDIR=$(printf '%s' "$CWD" | tr '/.' '-')
  TRANSCRIPT="$HOME/.claude/projects/$PROJDIR/$SESSION_ID.jsonl"
  [ -f "$TRANSCRIPT" ] || { echo "warning: no transcript found at $TRANSCRIPT -- session id or cwd may be wrong." >&2; TRANSCRIPT=""; }
else
  shopt -s nullglob
  matches=("$HOME/.codex/sessions"/*/*/*/"rollout-"*"-$SESSION_ID.jsonl")
  shopt -u nullglob
  if [ "${#matches[@]}" -gt 0 ]; then
    TRANSCRIPT="${matches[0]}"
  else
    echo "warning: no rollout file found ending in $SESSION_ID.jsonl -- session id may be wrong." >&2
  fi
fi

# Refuse sub-agent threads. They are recorded like sessions but are not
# driveable: codex resumes them read-only ("Viewing sub-agent -- direct input
# is disabled") and claude's belong to their parent. Reviving one yields a
# window you cannot type into -- observed live, three at once, because the
# old `originator == codex-tui` filter classed them as ordinary sessions.
if [ -n "$TRANSCRIPT" ]; then
  META="$SCRIPT_DIR/transcript-meta.py"
  if [ -x "$META" ] || [ -f "$META" ]; then
    meta_row=$(python3 "$META" --fast "$TRANSCRIPT" 2>/dev/null || true)
    if [ -n "$meta_row" ]; then
      IFS=$'\x1f' read -r _ _ _ _ meta_interactive _ _ meta_parent _ <<<"$meta_row"
      if [ "$meta_interactive" = "no" ]; then
        echo "error: $SESSION_ID is a sub-agent/non-interactive thread${meta_parent:+ spawned by $meta_parent}, not a top-level session." >&2
        echo "  Resuming it yields a read-only window with input disabled." >&2
        [ -n "$meta_parent" ] && echo "  Revive its parent instead:  revive-dead.sh $KIND $meta_parent '$CWD'" >&2
        echo "  To do it anyway, run the CLI by hand in that directory." >&2
        exit 1
      fi
    fi
  fi
fi

NAME="revived-dead-${SESSION_ID:0:8}"
if [ -n "${1:-}" ] && [[ "${1}" != -* ]]; then
  NAME="$1"
  shift
fi
FLAGS=("$@")

if [ "$KIND" = "claude" ]; then
  RELAUNCH=(claude --resume "$SESSION_ID" "${FLAGS[@]}")
  DANGEROUS_FLAG="--dangerously-skip-permissions"
else
  RELAUNCH=(codex resume "$SESSION_ID" "${FLAGS[@]}")
  DANGEROUS_FLAG="--dangerously-bypass-approvals-and-sandbox"
fi

# Revived panes run unattended often enough that prompting for permission
# defeats the purpose of restoring them. Avoid duplicating the flag when a
# caller has already supplied it explicitly.
if ! printf '%s\n' "${RELAUNCH[@]}" | grep -Fqx -- "$DANGEROUS_FLAG"; then
  RELAUNCH+=("$DANGEROUS_FLAG")
fi

echo "Reviving dead $KIND session $SESSION_ID in a new tmux window '$NAME':"
echo "  recorded cwd: $CWD"
echo "  launch cwd: $TARGET_CWD"
printf '  cmd:'; printf ' %q' "${RELAUNCH[@]}"; echo

if [ -z "${TMUX:-}" ]; then
  echo "error: not inside a tmux client session (\$TMUX unset) -- run this from within tmux, or use 'tmux new-window -t <session>' manually." >&2
  exit 1
fi

CMD=""
for a in "${RELAUNCH[@]}"; do
  printf -v q '%q' "$a"
  CMD="$CMD $q"
done

# `exec bash` keeps the window alive if the CLI exits immediately, so a bad
# session id or a startup error stays on screen. Without it the window just
# vanishes -- observed live: several codex windows launched in one loop died
# during MCP startup and disappeared before the error could be read.
tmux new-window -c "$TARGET_CWD" -n "$NAME" "$CMD; exec bash"

echo
echo "Done. This started a brand-new process resuming session $SESSION_ID's saved transcript."
echo "No orphan to kill afterward -- unlike revive.sh's case, the old process here was already gone."
