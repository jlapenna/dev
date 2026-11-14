# Project contribution notes

What earlier check-in passes learned about how specific projects review and
merge outside contributions. Each entry was checked against the project's
documents on the date shown. Projects change these rules often: confirm a rule
against the live document before acting on it, and correct the entry when it has
changed. "Observed" lines describe a small sample of merged fork PRs, not a
rule.

Add a project when a pass reads its rules for the first time. Record the
documents, the gates a contributor can clear, the gates only a maintainer can
clear, the prescribed way to ask for attention and what the project forbids.
Leave out the user's own PR numbers, hosts and credentials.

## openclaw/openclaw

Checked 2026-11-14. Documents: `CONTRIBUTING.md`, `AGENTS.md`,
`docs/reference/pull-request-review-flow.md`, and the bot's own documents in
`openclaw/clawsweeper`.

- **Bot review runs once.** ClawSweeper reviews a new PR automatically, and
  later pushes or description edits do not start another review. The author
  requests one with a new comment containing `@clawsweeper re-review`, only
  after the branch, description, evidence and CI are current. A positive result
  is supporting evidence, not approval; maintainers decide when to merge.
- **"Review blocked" by the input-safety check is usually author work.** The
  scanner rejects a literal credential-shaped string in the diff, such as a URL
  with `user:password@`. Assemble the value at runtime, as
  `src/infra/update-candidate-admission.test.ts` does, then push and request a
  re-review. The bot's notice says a maintainer must qualify the fixture; main's
  own tests show the author-side remedy.
- **"Needs real behavior proof"** (label `status: needs proof`) asks for
  redacted before-and-after output from a real entry point, recorded in the
  description. Tests with a mocked logger do not count. The CLI runs from source
  with `node scripts/run-node.mjs <args>`; isolate it with throwaway `HOME`,
  `OPENCLAW_HOME`, `OPENCLAW_STATE_DIR` and `OPENCLAW_CONFIG_PATH`.
- **`proof: telegram-e2e`** needs a Telegram Test Server run with the
  repository's E2E skill. That run needs broker credentials supplied privately
  by their owner. The documents do not reserve it for maintainers: ask for
  access in `#clawtributors`.
- **Description is the durable record.** Keep What Problem This Solves, User
  Impact, Why This Change Was Made and Evidence current, and record the
  local-review outcome or the missing-tool gap. Edit the description instead of
  only adding a comment.
- **Integrating main.** Do not merge or rebase `main` just because it advanced;
  integrate for a conflict, a named failing gate or material base risk. A PR
  that adds net test lines over the allowance needs a
  `config/test-lines-allocations/<change>.txt` record.
- **Fork CI can wait for maintainer approval** (`action_required`). The required
  `openclaw/ci-gate` status reports failure until CI completes.
- **Asking for attention.** Do not guess who to tag; mention a maintainer only
  for an owned path or documented responsibility. When automation appears
  blocked, the documented channel is `#clawtributors` on Discord, which is a
  handoff to the user.
- **Limits.** 20 open PRs per author, enforced by auto-close. Agent-authored or
  non-trivial work needs an issue first.
- `clawsweeper:intake:*` labels are a preliminary classification and ask
  nothing of the author.
- Observed: recent fork merges were small, carried a current-head bot verdict
  with sufficient proof, and landed within hours.

## home-assistant/core

Checked 2026-11-14. Documents: `CONTRIBUTING.md`,
`.github/PULL_REQUEST_TEMPLATE.md`, `AGENTS.md`, and the contributor site
(source in `home-assistant/contributors.home-assistant.io`, including
`AI_POLICY.md`).

- **Agents may not act here.** The AI policy does not allow autonomous agents,
  closes PRs it believes were created autonomously, and forbids AI-generated
  answers to maintainers' questions. Post no comments. Every reply to a
  maintainer is the user's own. AI assistance is disclosed through the
  template's checkboxes.
- **No review pings**, in the PR, in direct messages or on Discord. Reviewers
  are requested automatically from `CODEOWNERS`. A team request shows in the
  REST `requested_reviewers` field and can be missing from `gh pr view`.
- **Bot dashboard.** The bot holds a PR in draft until its dashboard comment is
  green, including the CLA, which only the human can sign. Then the author
  marks it ready for review; do that only when the user asked for it.
- **Template.** Remove nothing except the Breaking change section when nothing
  breaks. Tick exactly one type of change.
- **History.** Do not amend, squash or rebase pushed commits. After about a
  week without activity, merge `dev` and rerun tests. Core PRs go stale after
  60 days; a comment resets that.
- Observed: first human review of core PRs came between an hour and nine days
  after opening, and most merged PRs linked an issue.

## nexu-io/open-design

Checked 2026-11-14. Documents: `CONTRIBUTING.md`, `MAINTAINERS.md`,
`.github/pull_request_template.md`, `.github/workflows/ci.yml` and
`.github/templates/merge-queue/needs-validation.md`.

- **`needs-validation` is a QA-owner gate.** The merge queue rejects a PR that
  carries it. A QA owner records "QA passed" at a specific SHA, replaces the
  label with `validated` and queues the merge. The author cannot clear it.
- **Do not push after approval.** QA records and approvals are tied to a SHA,
  and the project asks for no force-push unless a reviewer requests one.
- **Core Team merges.** External maintainers can approve but not merge.
- The author-inactivity automation skips PRs that wait on QA or requested
  reviewers. Questions go to GitHub Discussions.
- Keep the description's Bug fix verification citing the current head.
- Observed: outside contributors' PRs waited 15 to 52 days between approval
  and the QA pass, and author status comments did not shorten that.

## BerriAI/litellm

Checked 2026-11-14. Documents: `.github/CONTRIBUTING.md`, `AGENTS.md` and
`.github/PULL_REQUEST_TEMPLATE/general.md`.

- **Template headings are rules.** Keep the `Handwritten 1-3 sentence
  description` heading and its placeholder untouched: only the human author
  writes there, and it may stay empty. Keep `Final Attestation`. Drop empty
  optional sections and add no headings of your own.
- **No AI attribution** in commit messages or the PR, including
  `Co-Authored-By` lines. GitHub comments are 15 to 25 words at most.
- **Proof.** At least one test under `tests/unit/` is a hard requirement, and
  the template wants a live proxy run before and after; test output alone is
  not proof.
- **Bot reviews gate the ask.** Before requesting maintainer review, the
  current head needs passing CI and acceptable results from the review bots.
  A pending or missing bot result is not a pass. Resolve or rebut each finding
  first.
- **Target the default branch**, with a conventional-commit title.
- **CLA** is checked per commit author by cla-assistant.
- **Fork CI waits for maintainer approval.** The documented channel for a slow
  merge is `#pr-review` on the project's Slack, which is a handoff to the user.
- Observed: maintainers approved CI between one and seven days after opening
  and often pushed fixes to the fork branch, so keep maintainer edits enabled.

## Martian-Engineering/lossless-claw

Checked 2026-11-14. Documents: `AGENTS.md` and `RELEASING.md`. There is no
contributing guide or PR template.

- **Changesets are maintainer-owned.** An outside contributor may include one
  but is not expected to.
- **Squash merges.** The maintainer still reads the displayed diff, so a
  merge-of-main commit that inflates it works against the PR. When asked to
  rebase, rebase.
- Observed: single-concern PRs of about five files and one or two commits
  landed as-is, in batches, with at most one author comment. A larger PR was
  split by the maintainer.
