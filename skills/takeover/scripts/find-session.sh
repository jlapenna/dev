#!/usr/bin/env bash
# Resolve a takeover descriptor to transcript source(s).
# Usage: find-session.sh <descriptor>
#   descriptor: a session/thread id (full or prefix), a herdr pane id (wE:p3),
#   a herdr agent name, an OpenCode ses_ id, a path to a brief/handoff/transcript,
#   or a free-text substring to search recent Claude/Codex transcripts for.
# Prints one line per hit: <harness>\t<id>\t<path>\t<mtime>
set -u
d=${1:?descriptor required}
emit() { printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$(date -r "$3" +%FT%T 2>/dev/null || true)"; }

# 1. literal file (brief, handoff, transcript)
if [ -f "$d" ]; then emit file "$(basename "$d")" "$d"; exit 0; fi

# 2. herdr pane or agent name -> session id (when herdr is present)
if command -v herdr >/dev/null 2>&1 && [ "${HERDR_ENV:-}" = 1 ]; then
  j=$(herdr agent get "$d" 2>/dev/null)
  sid=$(printf '%s' "$j" | jq -r '.result.agent.agent_session.value // empty' 2>/dev/null)
  kind=$(printf '%s' "$j" | jq -r '.result.agent.agent // empty' 2>/dev/null)
  if [ -n "$sid" ]; then
    printf '# herdr %s -> %s session %s (cwd %s)\n' "$d" "$kind" "$sid" "$(printf '%s' "$j" | jq -r '.result.agent.cwd')"
    d=$sid
  fi
fi

# 3. OpenCode id
case "$d" in ses_*) emit opencode "$d" "$HOME/.local/share/opencode/opencode.db"; exit 0;; esac

# 4. id or prefix in Antigravity / Claude / Codex stores
found=0
while IFS= read -r f; do
  bdir=$(dirname "$(dirname "$(dirname "$f")")")
  emit agy "$(basename "$bdir")" "$f"
  found=1
done < <(find "$HOME/.gemini/antigravity-cli/brain" -maxdepth 4 -path "*/${d}*/.system_generated/logs/transcript.jsonl" 2>/dev/null)
while IFS= read -r f; do emit claude "$(basename "$f" .jsonl)" "$f"; found=1; done < <(find "$HOME/.claude/projects" -maxdepth 2 -name "${d}*.jsonl" 2>/dev/null)
# Claude subagents: <project>/<parent-session>/subagents/agent-<hash>.jsonl (id with or without the agent- prefix)
while IFS= read -r f; do emit claude-subagent "$(basename "$f" .jsonl)" "$f"; found=1; done < <(find "$HOME/.claude/projects" -maxdepth 4 -path '*/subagents/*' \( -name "${d}*.jsonl" -o -name "agent-${d}*.jsonl" \) 2>/dev/null)
# a parent session id also lists its subagents, so a successor sees the whole tree
while IFS= read -r f; do emit claude-subagent "$(basename "$f" .jsonl)" "$f"; done < <(find "$HOME/.claude/projects" -maxdepth 4 -path "*/${d}*/subagents/agent-*.jsonl" 2>/dev/null)
while IFS= read -r f; do emit codex "$(basename "$f" .jsonl | sed 's/.*-\([0-9a-f]\{8\}-[0-9a-f-]*\)$/\1/')" "$f"; found=1; done < <(find "$HOME/.codex/sessions" -name "rollout-*${d}*.jsonl" 2>/dev/null)
[ "$found" = 1 ] && exit 0

# 5. free text: recent transcripts (7 days) mentioning it, newest first
printf '# no id match; searching recent transcripts for %q\n' "$d"
find "$HOME/.claude/projects" "$HOME/.codex/sessions" -name '*.jsonl' -mtime -7 -print0 2>/dev/null \
  | xargs -0 -r grep -lF -- "$d" 2>/dev/null \
  | while IFS= read -r f; do case "$f" in */.codex/*) h=codex;; *) h=claude;; esac; emit "$h" "$(basename "$f" .jsonl)" "$f"; done | sort -t$'\t' -k4 -r | head -15
