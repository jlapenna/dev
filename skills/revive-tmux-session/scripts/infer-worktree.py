#!/usr/bin/env python3
"""Select a linked Git worktree that matches a resumable session's task.

Only an unambiguous, task-specific match is returned.  The caller must
otherwise keep the transcript's recorded cwd: a wrong worktree is worse than
the primary checkout because it can put unrelated changes on the wrong branch.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def git(cwd: str, *args: str) -> str:
    return subprocess.check_output(["git", "-C", cwd, *args], text=True, stderr=subprocess.DEVNULL).strip()


def transcript(kind: str, session_id: str, cwd: str) -> Path | None:
    home = Path.home()
    if kind == "codex":
        matches = list((home / ".codex" / "sessions").glob(f"*/*/*/rollout-*-{session_id}.jsonl"))
        return matches[0] if matches else None
    project = cwd.replace("/", "-").replace(".", "-")
    path = home / ".claude" / "projects" / project / f"{session_id}.jsonl"
    return path if path.is_file() else None


def user_text(path: Path, kind: str) -> str:
    parts: list[str] = []
    for line in path.open(errors="replace"):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if kind == "codex":
            payload = event.get("payload", {})
            if event.get("type") != "response_item" or payload.get("type") != "message" or payload.get("role") != "user":
                continue
            for item in payload.get("content", []):
                if item.get("type") == "input_text":
                    value = item.get("text", "")
                    if not value.startswith("# AGENTS.md") and not value.startswith("<environment_context>"):
                        parts.append(value)
        elif event.get("type") == "user":
            message = event.get("message", {})
            content = message.get("content", "")
            blocks = [content] if isinstance(content, str) else [
                block.get("text", "") for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ] if isinstance(content, list) else []
            for value in blocks:
                if not value.startswith(("# AGENTS.md", "<environment_context>")):
                    parts.append(value)
    # The latest requests identify the active task; old task instructions
    # would otherwise steer a revived session onto a superseded worktree.
    return "\n".join(parts[-20:])


def worktrees(repo: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    path = branch = ""
    for line in git(repo, "worktree", "list", "--porcelain").splitlines() + [""]:
        if line.startswith("worktree "):
            path = line.removeprefix("worktree ")
        elif line.startswith("branch "):
            branch = line.removeprefix("branch refs/heads/")
        elif not line and path:
            result.append((path, branch))
            path = branch = ""
    return result


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: infer-worktree.py <claude|codex> <session-id> <recorded-cwd>", file=sys.stderr)
        return 2
    kind, session_id, recorded_cwd = sys.argv[1:]
    try:
        repo = git(recorded_cwd, "rev-parse", "--show-toplevel")
        entries = worktrees(repo)
    except subprocess.CalledProcessError:
        return 1

    # A transcript that already ran in a linked worktree is authoritative.
    primary = entries[0][0] if entries else repo
    if os.path.realpath(recorded_cwd) != os.path.realpath(primary):
        print(recorded_cwd)
        return 0

    source = transcript(kind, session_id, recorded_cwd)
    if not source:
        return 1
    text = user_text(source, kind)
    text_normalized = normalized(text)
    # Users commonly omit the '#' in a follow-up such as "you do 4322".
    # Four-or-more digit values avoid mistaking dates, counts, and versions
    # for issue numbers in ordinary task text.
    issue_ids = set(re.findall(r"(?<![A-Za-z0-9])#?(\d{4,})\b", text))

    candidates: list[tuple[int, str, str, str]] = []
    for path, branch in entries:
        if os.path.realpath(path) == os.path.realpath(repo):
            continue
        label = f"{Path(path).name} {branch}".lower()
        matched_issues = [issue for issue in issue_ids if re.search(rf"(?:^|[^0-9]){re.escape(issue)}(?:[^0-9]|$)", label)]
        if matched_issues:
            candidates.append((10_000 + len(matched_issues), path, branch, f"issue #{matched_issues[0]}"))
            continue

        # A worktree's distinctive compound name (e.g. "bikereg") can be
        # written with spaces or punctuation in a user request. Normalizing
        # both sides preserves that signal without relying on fragile grep.
        tokens = [normalized(token) for token in re.split(r"[^a-z0-9]+", label)]
        generic = {"branch", "claude", "codex", "feat", "fix", "issue", "main", "rider", "worktree"}
        hits = {token for token in tokens if len(token) >= 5 and token not in generic and token in text_normalized}
        if hits:
            # The first descriptive path component is normally the issue's
            # durable subject (e.g. `4331-bikereg-race-registrations`). It
            # is much stronger evidence than a generic later term such as
            # `rider`, which may occur in several unrelated branches.
            path_tokens = [normalized(token) for token in re.split(r"[^a-z0-9]+", Path(path).name.lower())]
            primary = next((token for token in path_tokens if len(token) >= 5 and token not in generic), "")
            score = len(hits) + (100 if primary in hits else 0)
            candidates.append((score, path, branch, f"task term {primary if primary in hits else sorted(hits)[0]}"))

    if not candidates:
        return 1
    candidates.sort(reverse=True)
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        return 1
    _, path, branch, reason = candidates[0]
    print(path)
    print(f"inferred linked worktree '{path}' ({branch}; {reason})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
