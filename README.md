# dev

Reusable development skills and tools for coding agents.

| Skill | Purpose |
| --- | --- |
| [model-evaluation](skills/model-evaluation/SKILL.md) | Compare model quality, inference performance, context/concurrency, and real clients; finish with a measured recommendation. |
| [fork-pane](skills/fork-pane/SKILL.md) | Fork the current coding-agent conversation into a new Herdr pane. |
| [fork-tab](skills/fork-tab/SKILL.md) | Fork the current coding-agent conversation into a new Herdr tab. |

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

## Development

Development checks require Python 3, Bash, `jq`, `uv`, and the public
[repo-tools](https://github.com/jlapenna/repo-tools) commands on `PATH`.
Run `make setup`, then `make check` before opening a pull request. Fork tests
use a mock Herdr executable and create no live panes, agents, or model requests.
Model-evaluation behavioral prompts live beside the skill; generated evaluation
runs belong outside the discoverable `skills/` tree.

MIT licensed. The public repository starts from selected source files; private
configuration and repository history are not included.
