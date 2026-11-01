---
name: fork-tab
description: "Fork the current Claude Code, Codex, or OpenCode conversation into a new session in a new herdr tab. Use when the user asks to /fork-tab or $fork-tab, or to fork this conversation into a new tab. Only works when the calling agent is running inside a herdr pane."
---

# fork-tab

The fork task is the text the user supplied with the request, minus the part asking to fork (it may be empty).

Write a short title (3 to 8 words, no single quotes) naming the fork's task; it becomes the fork's session title and herdr agent name. If the fork task is empty, drop the title argument. Then run exactly this one shell command, with the fork task between the heredoc markers unchanged (it may be empty):

```bash
agent-fork tab '<title>' <<'FORK_TASK_EOF'
<fork task>
FORK_TASK_EOF
```

Report its output in one or two lines. If it fails, report the error output and stop; do not retry, resend, or improvise herdr commands. `agent-fork` (on `PATH`) detects this agent's kind and session from herdr, opens the tab, and starts the fork with permission prompts skipped, because nobody answers them in a background tab.
