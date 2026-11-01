# Takeover brief: <slug> (<harness> session <id>)

Written <ISO timestamp> by <your harness/session id>, pane <herdr/tmux id or "n/a">.

## Source
- Predecessor: <harness> session `<id>`, ran as `<agent/pane name>` in <pane>, stopped because <quota | crash | pane closed | user asked | unknown>.
- Transcript: <absolute path>  (condensed extract: <absolute path>)
- Other inputs: <brief/handoff docs, issues, PRs, worktrees, Claude Docs>

## The user's words (authority)
- <quoted, dated, in order; include the original ask, each approval, and every correction>

## Agreed plan
<the plan the user approved, as the predecessor stated it, with a pointer to where it lives if it was written down (spec, doc, issue). Note anything the user later overrode.>

## Verified live state (checked <ISO timestamp>, not inherited from the transcript)
| Claim in transcript | Live check | Result |
| --- | --- | --- |
| "PR #N merged" | `gh pr view N` | merged at ... |
| worktree X has uncommitted work | `git -C X status --short` | 5 files, listed below |
| service Y restarted | `systemctl status Y` | ... |

## Peers and ownership
- Live peers that touch the same work: <names/panes/sessions and what each owns>
- Old agent: <name>, left idle at <pane>; do not prompt or close.
- Notified: <who, how, when>

## Immediate work
1. <first bounded step>
2. ...

## Progress log
- <ISO timestamp> <what changed, with evidence pointers>
