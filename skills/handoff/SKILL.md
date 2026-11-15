---
name: handoff
description: Compact the current conversation into a handoff document a fresh agent can continue from. Use when the user invokes /handoff, optionally naming the next session's focus.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
---

Write a handoff document summarising the current conversation so a fresh agent can continue the work. Save it in the session scratchpad directory (or the OS temp directory when there is none), not the current workspace, and give the user its absolute path.

The next agent starts with no memory of this conversation, so give it what it
cannot rediscover cheaply:

- the goal and the user's decisions and corrections, in their words where it
  matters;
- the current state: branch, worktree, PR, what passed or failed;
- the remaining work as numbered next steps, and open questions;
- a "Suggested skills" section naming the skills the next agent should
  invoke: those this session relied on and any that fit the remaining work.

If the harness cannot write files, show the document inline with the absolute
path it belongs at, so the user can save it.

Do not duplicate content already captured in other artifacts (specs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.
