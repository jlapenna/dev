#!/usr/bin/env bash
# Best-effort correlation of a live `claude` or `codex` process (typically
# an orphan found via find-orphans.sh, not yet killed) to its session
# transcript file, when its argv has no resume marker to read directly.
#
# claude transcripts: ~/.claude/projects/<project-dir>/<session-id>.jsonl
# codex transcripts:  ~/.codex/sessions/YYYY/MM/DD/rollout-<local-ts>-<uuid>.jsonl
#
# Matching signal: exact `cwd` + transcript start time closest to (and not
# before) the process's start time. This is inherently best-effort — there's
# no fd from a live claude process back to its own transcript file — but in
# practice the gap between process start and first transcript write is a few
# seconds to under a minute, so a tight match is a strong signal.
#
# All transcript parsing is delegated to transcript-meta.py. It used to be
# done with inline `grep`, which produced three separate silent-failure bugs
# (nested "cwd" matches, a 4000-byte window that missed the first
# "timestamp" when a large summary record led the file, and a pipefail abort
# on files lacking the field). See the header of transcript-meta.py.
#
# Gotcha this script still guards: `date -u -d "STRING"` parses STRING as if
# it were ALREADY UTC when STRING has no explicit zone (e.g. `ps -o lstart=`
# output like "Sun Jul 5 10:31:58 2026") — it does NOT convert from local
# time. Silently wrong, no error. Parse in local time first, then convert:
#   epoch=$(date -d "$lstart" +%s); utc=$(date -d "@$epoch" -u +...)
#
# Usage: find-session-id.sh <pid> [claude|codex]
#   kind defaults to "claude" for backward compatibility.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
META="$SCRIPT_DIR/transcript-meta.py"

PID="${1:?usage: find-session-id.sh <pid> [claude|codex]}"
KIND="${2:-claude}"
[ -d "/proc/$PID" ] || { echo "No such process: $PID" >&2; exit 1; }

CWD=$(readlink "/proc/$PID/cwd") || { echo "Can't read cwd for $PID" >&2; exit 1; }
LSTART=$(ps -o lstart= -p "$PID" 2>/dev/null) || { echo "Can't read start time for $PID" >&2; exit 1; }

# If argv ALREADY names a session id, return it and skip correlation entirely.
#
# This is not just an optimization -- correlation cannot work in that case and
# will confidently return the WRONG id. The match requires the transcript to
# start at-or-after the process; a resumed session's transcript started long
# before this process did, so it is structurally excluded, and any *newer*
# stale transcript sharing the cwd wins instead.
#
# Observed: pid resuming dd690c1b (transcript start 03:05:17, process start
# 06:01:10, still the actively-written file) correlated to an unrelated
# 69b01da8 that had started at 06:07:52 and since gone idle.
ARGV=()
while IFS= read -r -d '' a; do ARGV+=("$a"); done < "/proc/$PID/cmdline"
for ((i = 0; i < ${#ARGV[@]} - 1; i++)); do
  case "${ARGV[$i]}" in
    --resume|resume)
      cand="${ARGV[$((i + 1))]}"
      if [[ "$cand" != -* ]] && [ -n "$cand" ]; then
        echo "argv already names session $cand -- returning it; correlation skipped (it would be unreliable here)." >&2
        echo "$cand"
        exit 0
      fi
      ;;
  esac
done

# See the date(1) gotcha above — do not collapse this into `date -u -d "$LSTART"`.
EPOCH=$(date -d "$LSTART" +%s)
TARGET_UTC=$(date -d "@$EPOCH" -u +"%Y-%m-%dT%H:%M:%S")
echo "pid=$PID  kind=$KIND  cwd=$CWD  local_start='$LSTART'  utc_start=$TARGET_UTC" >&2

# Collect candidate transcript paths for this kind into $CANDIDATES.
CANDIDATES=$(mktemp)
trap 'rm -f "$CANDIDATES"' EXIT

if [ "$KIND" = "codex" ]; then
  # codex directories and rollout filenames both embed LOCAL time, so the
  # day-directory comes straight from the local start time. Scan the next day
  # too: a session started just before midnight lands in tomorrow's dir.
  ROOT="$HOME/.codex/sessions"
  echo "sessions root: $ROOT" >&2
  [ -d "$ROOT" ] || { echo "No codex sessions directory — can't correlate." >&2; exit 1; }

  DAY1=$(date -d "@$EPOCH" +%Y/%m/%d)
  DAY2=$(date -d "@$((EPOCH + 86400))" +%Y/%m/%d)
  for d in "$ROOT/$DAY1" "$ROOT/$DAY2"; do
    [ -d "$d" ] && find "$d" -maxdepth 1 -name 'rollout-*.jsonl' >> "$CANDIDATES"
  done
  SCOPE="$ROOT/$DAY1${DAY2:+ and $ROOT/$DAY2}"
else
  # Claude Code's project-dir encoding: cwd with every '/' and '.' -> '-'.
  PROJDIR=$(printf '%s' "$CWD" | tr '/.' '-')
  ROOT="$HOME/.claude/projects/$PROJDIR"
  echo "project dir: $ROOT" >&2
  [ -d "$ROOT" ] || { echo "No project dir found for this cwd — can't correlate." >&2; exit 1; }
  find "$ROOT" -maxdepth 1 -name '*.jsonl' >> "$CANDIDATES"
  SCOPE="$ROOT"
fi

if [ ! -s "$CANDIDATES" ]; then
  echo "No candidate transcript files under $SCOPE." >&2
  exit 1
fi

# Two passes: first consider only top-level interactive sessions (excludes
# sub-agent threads and exec spawns, which also write transcripts against the
# same cwd); only if that yields nothing, retry including them.
best_id=""
best_delta=""
best_mtime=""
for require_interactive in yes no; do
  [ -n "$best_id" ] && break
  while IFS=$'\x1f' read -r _path _kind sid cwd interactive mtime start _parent _classification; do
    [ "$cwd" = "$CWD" ] || continue
    [ -n "$start" ] || continue
    [ "$require_interactive" = "no" ] || [ "$interactive" = "yes" ] || continue

    delta=$(( start - EPOCH ))
    # A transcript can't start before its process did; allow a few seconds of
    # clock/measurement slack but discard anything clearly earlier.
    [ "$delta" -ge -5 ] || continue

    # Tie-break identical start times by later mtime: a compaction fork and
    # the session it forked from share a start instant to the millisecond,
    # and the real, actively-continued one is the one still being written to.
    if [ -z "$best_id" ] \
       || [ "$delta" -lt "$best_delta" ] \
       || { [ "$delta" -eq "$best_delta" ] && [ "$mtime" -gt "$best_mtime" ]; }; then
      best_id="$sid"
      best_delta="$delta"
      best_mtime="$mtime"
    fi
    # --fast: identity only. Correlation never needs `classification`, and
    # computing it would mean reading every candidate file end-to-end.
  done < <(python3 "$META" --fast - < "$CANDIDATES")
done

if [ -z "$best_id" ]; then
  echo "No candidate transcript matched cwd + plausible start time under $SCOPE." >&2
  exit 1
fi

echo "best match: $best_id  (started $best_delta""s after the process, mtime $(date -d "@$best_mtime" '+%Y-%m-%d %H:%M:%S'))" >&2
if [ "$best_delta" -gt 120 ]; then
  echo "warning: gap is over 2 minutes — weaker confidence, verify before trusting this." >&2
fi

# Machine-readable result on stdout; everything else above is on stderr.
echo "$best_id"
