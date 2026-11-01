---
name: herdr-overview
description: "Open, inspect, and manage the herdr-overview grid: one cell per coding agent across the local Herdr session and every enabled saved machine, or a machine/workspace subset. Use when the user asks for an overview/grid/live view of all or some agents, or mentions herdr-overview. Requires running inside a Herdr pane."
---

# herdr-overview

Source: <https://github.com/jlapenna/dev/tree/main/herdr/overview> — a [Herdr plugin](https://herdr.dev/docs/plugins/). Install it with `herdr plugin install jlapenna/dev/herdr/overview` (actions + marketplace discoverable) or as a plain CLI with `install -m 0755 bin/herdr-overview ~/.local/bin/`.

`herdr-overview` opens a Herdr tab containing one pane per detected coding agent, across the local Herdr session and every enabled saved machine (`herdr machine list`). The grid auto-follows agents as they start and exit.

## Check prerequisites first

```bash
test "${HERDR_ENV:-}" = 1 && command -v herdr-overview
```

If either fails, say what is missing (inside a Herdr pane / tool installed) and stop.

## Open the grid

```bash
herdr-overview              # read-only text copies, refreshed every 2s; click/Enter jumps to the agent
herdr-overview --live       # each cell attaches to its agent and takes input
herdr-overview --no-focus   # open without switching to the new tab
```

### Scoping to a subset

Use `--machine` and/or `--workspace` (repeatable, comma lists, AND-combined) when the user wants only some agents:

```bash
herdr-overview --machine buildbox                # one saved machine only
herdr-overview --machine local,buildbox          # "local" = the local session
herdr-overview --workspace p                    # workspace id or label, case-insensitive
herdr-overview --machine buildbox --workspace p  # both filters at once
```

A workspace specifier is resolved per machine (each machine's own ids/labels). A specifier matching nothing contributes no cells — confirm the intended set from the controller log's `N agents:` line after opening.

When installed as a plugin, the same grids exist as actions; prefer invoking the action for unscoped/"this workspace" requests:

```bash
herdr plugin action invoke herdr-overview.overview       # this workspace only
herdr plugin action invoke herdr-overview.overview-all   # everything
```

The command prints the new tab id and log path. Do not re-run it to "check" it worked — read the log instead:

```bash
tail -n 5 "$(ls -t "${XDG_STATE_HOME:-$HOME/.local/state}/herdr-overview/"*.log | head -1)"
```

A healthy controller logs lines like `HH:MM:SS N agents: host=2 other=1 ...`.

## Managing it

- **Stop:** close the overview tab (`herdr tab close <tab_id>`). The controller exits and, in live mode, restores each agent's terminal size. Do not kill the controller process directly.
- **Detach a live cell:** `ctrl+b q` (twice `ctrl+b` first if the outer prefix is also `ctrl+b`).
- **Status:** the root pane of the overview tab tails the controller log.

## Caveats

- Never run `herdr agent attach` yourself while a live overview is open; cells own those attachments and an outside attach fights the grid's size restoration.
- Remote agents only update as fast as an `ssh` round-trip allows; a machine that stops answering keeps its last known agents, shown as `unreachable`.
- To tune refresh cadence, re-run with `HERDR_OVERVIEW_INTERVAL` / `HERDR_OVERVIEW_SCAN` set in the environment before launching.
