# dev

Reusable development skills and tools for coding agents.

| Skill | Purpose |
| --- | --- |
| [model-evaluation](skills/model-evaluation/SKILL.md) | Compare model quality, inference performance, context/concurrency, and real clients; finish with a measured recommendation. |
| [fork-pane](skills/fork-pane/SKILL.md) | Fork the current coding-agent conversation into a new Herdr pane. |
| [fork-tab](skills/fork-tab/SKILL.md) | Fork the current coding-agent conversation into a new Herdr tab. |
| [handoff](skills/handoff/SKILL.md) | Write a concise handoff for a successor. |
| [takeover](skills/takeover/SKILL.md) | Reconstruct intent, verify live state, and continue another session. |
| [github-issue-workflow](skills/github-issue-workflow/SKILL.md) | Carry issue work through ownership checks, isolated implementation, and delivery. |
| [external-pr-checkin](skills/external-pr-checkin/SKILL.md) | Inspect upstream PR gates and complete authorized author follow-ups. |
| [revive-tmux-session](skills/revive-tmux-session/SKILL.md) | Recover Linux tmux sessions from live processes or saved transcripts. |
| [herdr-overview](skills/herdr-overview/SKILL.md) | Show a scoped grid of coding agents. |

Skills use the standard `SKILL.md` layout. Install the desired directories with
your coding agent's skill installer. The root `.claude-plugin` marketplace also
exposes these skills as the `dev` plugin. Environment-specific hosts, credentials,
model recipes, and deployment procedures belong to the consuming environment.

## Session-fork helper

The fork skills use [bin/agent-fork](bin/agent-fork). Put `bin` on your `PATH`,
or install that executable into a directory already on it. It requires Bash,
`jq`, Herdr, and the corresponding Claude Code, Codex, or OpenCode executable.
Run it from an existing Herdr coding-agent pane:

```bash
agent-fork tab 'Investigate cache misses' <<'TASK'
Investigate the cache misses in this repository.
TASK
```

It preserves the caller's cwd and focus, resolves the live session/pane even
after a workspace move, and starts a separate fork. Background forks launch
with the corresponding agent's unattended permission flags; use it only in
an environment where that execution mode is authorized. A failed startup leaves
the new pane open for inspection and returns the actual failure.

## Herdr integrations

[Overview](herdr/overview/README.md) is the native Herdr plugin, installed with
`herdr plugin install jlapenna/dev/herdr/overview`. Its Linux launcher requires
Bash 4+, jq, GNU readlink, setsid/nohup, and timeout (plus SSH for remote hosts).

[bin/herdr-session-titles](bin/herdr-session-titles) copies Codex's session-index
titles to matching panes in Herdr's default local session. It requires Python 3
and Herdr, reads no conversation transcripts, rechecks session identity before
updates, and leaves scheduling to the consuming environment. Its metadata
producer key remains `homegit:session-title` for existing consumers.

## Development

Development checks require Python 3, Bash, `jq`, `uv`, and the public
[repo-tools](https://github.com/jlapenna/repo-tools) commands on `PATH`.
Run `make setup`, then `make check` before opening a pull request. Fixture tests use mocked CLIs and synthetic transcripts; they create no live
panes, agents, or model requests.
Model-evaluation behavioral prompts live beside the skill; generated evaluation
runs belong outside the discoverable `skills/` tree.

MIT licensed. The public repository starts from selected source files; private
configuration and repository history are not included.
