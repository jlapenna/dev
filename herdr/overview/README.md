# herdr-overview

A live grid of every [Herdr](https://github.com/herdrdev/herdr) agent in one tab — local session plus every enabled saved machine. One cell per agent; the grid follows agents as they come and go.

## What you get

- **Overview mode** (default): each cell shows a read-only text copy of the agent's visible screen, refreshed every 2s. Click a cell (or press Enter) to jump to that agent. Remote agents attach in place over SSH instead.
- **Live mode** (`--live`): each cell is a real `herdr agent attach` — it takes input. Agents shrink to cell size while attached.
- A background controller rescans agents every 5s, rebuilds the grid when the set changes, and on close resets every agent's terminal to its own pane's size.
- Unreachable machines keep their last known agents, shown as `unreachable`.

## Requirements

- `herdr` 0.9.0+ in `PATH`, running inside a Herdr pane (`HERDR_ENV=1`)
- Linux, `jq`, Bash 4+, GNU `readlink`, `setsid`, `nohup`, and `timeout`; `ssh` for remote machines
- Saved machines configured via `herdr machine`

## Install as a Herdr plugin (recommended)

```bash
herdr plugin install jlapenna/dev/herdr/overview
```

The manifest registers three actions, invocable from Herdr's action UI or bound to a key:

| Action | What it opens |
| --- | --- |
| `herdr-overview.overview` | overview grid, scoped to the invoking workspace |
| `herdr-overview.overview-all` | overview grid, every workspace and machine |
| `herdr-overview.live` | live grid, scoped to the invoking workspace |

Keybinding example (`config.toml`):

```toml
[[keys.command]]
key = "prefix+o"
type = "plugin_action"
command = "herdr-overview.overview"
description = "agent overview"
```

## Install as a plain CLI

```bash
curl -fsSL https://raw.githubusercontent.com/jlapenna/dev/main/herdr/overview/bin/herdr-overview \
  -o ~/.local/bin/herdr-overview && chmod +x ~/.local/bin/herdr-overview
```

Or clone and link:

```bash
git clone https://github.com/jlapenna/dev && cd dev/herdr/overview
install -m 0755 bin/herdr-overview ~/.local/bin/
```

## Usage

From any Herdr pane:

```bash
herdr-overview              # overview: read-only text copies, refreshed every 2s
herdr-overview --live       # live view: cells attach and take input
herdr-overview --no-focus   # either mode, without switching to the new tab
```

### Subsets: `--machine` and `--workspace`

```bash
herdr-overview --machine buildbox              # one machine's agents
herdr-overview --machine local,buildbox        # comma lists, repeatable
herdr-overview --workspace p                  # agents in workspace id or label "p"
herdr-overview --machine buildbox --workspace p   # filters combine as AND
```

- `local` (or your `hostname -s`) always means the local session.
- A workspace specifier matches each machine's workspace **id or label**, case-insensitively.
- Unmatched machines/workspaces simply contribute no cells; the controller log shows the active filters.

- **Close the tab to stop.** The controller notices and cleans up (live mode restores agent sizes).
- **Detach from an attached cell:** `ctrl+b q` (attach's fixed detach key). If your outer Herdr prefix is also `ctrl+b`, press it twice to pass one through — the tool detects this and shows the right hint.
- The root pane of the new tab tails the controller log; per-tab logs live under `${XDG_STATE_HOME:-~/.local/state}/herdr-overview/`.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `HERDR_MAIN_SOCKET` | `~/.config/herdr/herdr.sock` | local main session socket |
| `HERDR_OVERVIEW_INTERVAL` | `2` | overview cell refresh (seconds) |
| `HERDR_OVERVIEW_SCAN` | `5` | controller agent rescan interval (seconds) |

## How it works

`herdr-overview` is one bash script with four modes, dispatching on its first argument:

1. **launcher** — creates a labeled tab, starts the controller detached (`setsid nohup`).
2. **`--controller`** — polls `herdr agent list` on the local socket and every enabled machine, computes a near-square grid, splits panes, and `herdr pane run`s a cell per agent. Rebuilds only when the agent set changes.
3. **`--cell`** — one overview cell: polls `herdr agent read --source visible`, repaints in place (no flicker), enables SGR mouse reporting so a left click focuses the agent.
4. **`--view`** — one live cell: runs `herdr agent attach` (over `ssh -t` for remote machines), restores the agent's own pane size on detach, reattaches on Enter.

The [herdr-overview skill](../../skills/herdr-overview/SKILL.md) teaches coding agents to run and reason about the tool, and `herdr-plugin.toml` is the Herdr plugin manifest that registers the actions above (repo topic `herdr-plugin` lists it on the Herdr marketplace).

## License

MIT
