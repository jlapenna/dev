# Agent Guide

<!-- repo-tools:begin -->

## Shared repository conventions

Git safety and pull-request delivery follow two skills published by
[jlapenna/repo-tools](https://github.com/jlapenna/repo-tools):

- [worktree-hygiene](https://github.com/jlapenna/repo-tools/blob/main/plugins/repo-tools/skills/worktree-hygiene/SKILL.md) before any
  git-mutating command: author in a linked worktree, never in the primary
  checkout or on `main`.
- [land-pr](https://github.com/jlapenna/repo-tools/blob/main/plugins/repo-tools/skills/land-pr/SKILL.md) to carry a change through commit, push, CI,
  review, protected merge, and cleanup.

Do not mirror their bodies locally; load them from the plugin and use the
`repo-*` commands they describe. Repository-specific policy (check names,
deployment rules) stays in this file outside this section.

<!-- repo-tools:end -->

## Scope and checks

This repository owns portable development skills and session-fork tooling.
Keep environment-specific hosts, credentials, service state, and operating
procedures with the consumer. Do not import private repository history.

Run `make setup` in each task worktree and `make check` before publication.
Keep generated skill-evaluation runs in `.evaluation/`, outside `skills/`.
Fork tests use mock Herdr commands; do not create live panes for a source check.
Changes to skill routing or behavior should be checked with a realistic prompt
and the minimum necessary artifacts. Structural checks do not prove better
agent decisions.
