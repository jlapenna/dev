#!/usr/bin/env python3
"""Read-only discovery of open GitHub PRs using the installed gh identity."""

import argparse
from datetime import datetime, timezone
import json
import re
import subprocess
import sys


class DiscoveryError(Exception):
    pass


def github(endpoint, fields=None):
    command = ["gh", "api", "--method", "GET", endpoint]
    for key, value in (fields or {}).items():
        command += ["-f", f"{key}={value}"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DiscoveryError(f"GitHub request failed: {type(exc).__name__}") from exc
    if result.returncode:
        # Do not echo arbitrary CLI output, which can include credential details.
        raise DiscoveryError(f"gh api {endpoint} exited {result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise DiscoveryError(f"Invalid JSON from {endpoint}") from exc


def search(query, api=github):
    items, problems, total = [], [], 0
    for page in range(1, 11):  # GitHub search exposes at most 1,000 results.
        try:
            response = api("search/issues", {"q": query, "per_page": 100,
                                             "page": page, "sort": "updated",
                                             "order": "desc"})
        except DiscoveryError as exc:
            problems.append(str(exc))
            break
        total = max(total, response["total_count"])
        if response.get("incomplete_results"):
            problems.append("GitHub reported incomplete_results")
        batch = response["items"]
        items.extend(batch)
        if len(items) >= min(total, 1000) or not batch:
            break
    unique = {item["html_url"]: item for item in items}
    if total > 1000:
        problems.append(f"Search cap: {total} matches exceed GitHub's 1,000-result limit")
    if len(unique) < min(total, 1000):
        problems.append(f"Search returned {len(unique)} distinct PRs of {total} matches")
    return list(unique.values()), {"query": query, "total_count": total,
                                  "fetched": len(unique),
                                  "complete": not problems,
                                  "problems": list(dict.fromkeys(problems))}


def discover(author, exclude_owners=(), exclude_repos=(), api=github, now=None):
    now = now or datetime.now(timezone.utc)
    owners = {author.casefold(), *(owner.casefold() for owner in exclude_owners)}
    repos = {repo.casefold() for repo in exclude_repos}
    # Exclude the author's repositories before the search cap, not only after
    # fetching: a busy personal portfolio can otherwise hide upstream results.
    exclusions = f"-user:{author}" + "".join(f" -repo:{repo}" for repo in sorted(repos))
    items, metadata = search(f"is:pr author:{author} is:open {exclusions}", api)
    found, excluded = {}, set()
    for item in items:
        if item["state"] != "open":
            continue
        # repository_url is the base repository, never the contributor fork.
        repository = item["repository_url"].rsplit("/repos/", 1)[-1]
        if repository.split("/", 1)[0].casefold() in owners or repository.casefold() in repos:
            excluded.add(item["html_url"])
            continue
        found[item["html_url"]] = {
            "repository": repository, "number": item["number"],
            "title": item["title"], "url": item["html_url"],
            "search_state": item["state"], "updated_at": item["updated_at"],
            "draft": item.get("draft"),
        }
    return {"checked_at": now.isoformat(), "author": author,
            "scope": {"open": "all",
                      "excluded_owners": sorted(owners), "excluded_repos": sorted(repos)},
            "complete": metadata["complete"],
            "searches": [metadata], "excluded_in_fetched_results": len(excluded),
            "prs": sorted(found.values(), key=lambda pr: pr["updated_at"], reverse=True)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--author", help="Default: the normal gh login")
    parser.add_argument("--exclude-owner", action="append", default=[])
    parser.add_argument("--exclude-repo", action="append", default=[])
    args = parser.parse_args()
    try:
        author = args.author or github("user")["login"]
        if not re.fullmatch(r"[A-Za-z0-9-]+", author):
            parser.error("--author must be a GitHub login, not a search expression")
        if any(not re.fullmatch(r"[A-Za-z0-9-]+", owner) for owner in args.exclude_owner):
            parser.error("--exclude-owner must be a GitHub owner name")
        if any(not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+", repo)
               for repo in args.exclude_repo):
            parser.error("--exclude-repo must be owner/repository")
        report = discover(author, args.exclude_owner, args.exclude_repo)
    except (DiscoveryError, KeyError, TypeError) as exc:
        print(json.dumps({"complete": False, "error": str(exc)}))
        return 1
    print(json.dumps(report, indent=2))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    sys.exit(main())
