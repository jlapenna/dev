---
name: github-issue-workflow
description: Carry a GitHub issue from intake through a merged pull request. Use when beginning, resuming, implementing or finishing issue work, checking ownership, or taking an issue through a PR. Follow repository-defined ownership and worker protocols; shared repo-tools skills own worktree safety and delivery mechanics.
---

# GitHub Issue Workflow

Carry one GitHub issue from intake through a reviewed, merged change without
colliding with humans, agents, or other local sessions. This skill coordinates
the lifecycle; sibling skills own the mechanics it hands off to.

## Guardrails

- Follow the user's request and the repository's execution mode. Explicitly
  dispatched automation follows its worker protocol; generic CI, piped input,
  provider session IDs or a request to work autonomously do not establish one.
- Load the repository's configured ownership/operator guidance before
  interpreting a managed work queue. A GitHub assignee alone may not describe
  active queued runs or interactive sessions.
- Keep collision checks, worktree isolation, verification, secret protection
  and applicable operation approvals in every mode.
- Checking ownership is read-only and does not authorize claims, comments or
  routing changes. Do not claim, comment on or otherwise mutate an issue when
  the user only asked to inspect, explain, diagnose or review it. If the user
  explicitly asks for a claim or takeover, perform that scoped action, using the
  repository-defined identity, after checking for live ownership.
- Only add assignees. Never remove another assignee unless the user explicitly
  asks and repository policy permits it. Leave assignee history intact.
- Never bypass commit or push hooks with `--no-verify`.
- If a repository merely makes worktrees optional, still use one. Accept a
  repository's standing merge authorization as authorization.
- Managed configuration follows its owning tool's native authoring and
  publication workflow when repository policy defines that exception.

## Steps

1. **Reconcile policy.** Read the repository's `AGENTS.md`, contributing guide
   and relevant local skills before acting. System, developer and current user
   instructions control; repository rules own concrete semantics (claimant
   identity, labels, base branch, verification, CI, merge, deployment);
   personal skills are the cross-repository safety floor and the default where
   the repository is silent. Repository silence or "optional" never waives a
   stricter personal safety rule. A repository rule is an exception to a
   personal guardrail only when it addresses that guardrail explicitly and
   higher-level instructions permit it. Resolve conflicts from the user's
   existing authorization and explicit repository exceptions first; ask only
   when a material policy choice is still unresolved, and never re-ask about an
   already-settled exception. When rules overlap or conflict, read
   [references/policy-precedence.md](references/policy-precedence.md) before
   deciding.

2. **Inspect ownership before implementation**, without editing source:

   ```bash
   gh issue view <N> --json number,title,state,assignees,labels,author,url,body
   gh api user --jq .login
   gh repo view --json defaultBranchRef,nameWithOwner
   git status --short --branch
   git worktree list
   ```

   Also inspect recent issue comments, linked or open PRs, active automation
   runs, and existing worktrees or branches that could indicate active work.

   - A non-agent human assignee owns the issue. Do not begin unless that person
     explicitly hands it off, including through the current conversation.
   - When the repository uses a control plane, consult its configured
     ownership authority through the installed operator skill or repository
     guide. An incomplete answer means unknown, not free; do not substitute
     assignment age or old comments for current ownership.
   - An open implementation PR, active workflow or owning interactive session
     can indicate work in flight. Reconcile the evidence before starting a
     competing implementation.

   If the issue is closed, ambiguous, blocked by a human decision or outside
   the requested scope, stop before claiming and report what you found.

3. **Identify the session** using the harness's supported title controls.
   Include the issue number and a short task description. Choose a unique
   worktree path and branch, e.g. `../repo-issue-123-token-refresh` and
   `issue/123-token-refresh`.

4. **Apply the repository's ownership protocol.** A direct request from an
   owning maintainer can be the required handoff. Do not invent an assignment
   or takeover-comment requirement when the repository does not require one.
   Explicitly dispatched workers follow their dispatch protocol; do not post
   a duplicate claim or claim another issue merely because you read it.
   Keep inspection-only requests read-only.

5. **Isolate.** Load and follow `repo-tools:worktree-hygiene` completely, using
   the chosen path and branch from the fresh remote base, and finish the
   repository's worktree/bootstrap setup before diagnosing or editing source.
   It owns collision detection, creation, exclusive use, mutation safety,
   teardown and primary-checkout syncing; do not improvise them. All
   implementation and PR-related git work stays in that worktree.

6. **Implement and verify.** Keep the change focused on the issue. Follow the
   repository's definition of done: narrow tests while iterating, then the
   required final verification before opening or updating the PR.

7. **Re-check the landscape** immediately before creating or un-drafting the
   PR. On any run longer than an hour the world has moved. Claims bind agents,
   not humans; the maintainer or another runtime may have shipped the same
   change:

   ```bash
   git fetch origin
   git log HEAD..origin/<default-branch> --oneline   # did the same change land independently?
   gh pr list --state all --search "<issue-number>" --limit 10
   ```

   If a parallel implementation already merged (a surprise `DIRTY` merge state
   on a fresh PR often means this), stop: do not open or keep a duplicate PR
   and do not mechanically resolve its conflicts. Read
   [references/parallel-implementation.md](references/parallel-implementation.md)
   for the close-and-salvage procedure.

8. **Hand the PR to `repo-tools:land-pr`**, which owns committing, pushing, CI,
   review, auto-merge and cleanup. First preserve chain of custody:
   - Use `Closes #<N>` only when the PR fully completes the implementation
     issue; otherwise link it without closing syntax.
   - Link the issue in the PR. Follow the repository's attribution and worker
     deliverable requirements without inventing additional posting obligations.
   - Keep post-deploy or follow-up work on a separate linked issue when
     repository policy requires it.
   - Complete the authorized delivery lifecycle; creating a PR or arming
     auto-merge does not prove it merged. `land-pr` owns monitoring and cleanup.

   Loading `land-pr` does not grant permission to publish, merge, deploy or
   expand the task; repository policy still controls checks, merge method and
   deployment.

9. **Confirm completion.** After `land-pr` confirms the merge, verify the issue
   closed. If automatic closure failed, close it explicitly only when the
   merged PR fully completed the issue. The issue, PR and verification record
   should make the delivered change auditable.
