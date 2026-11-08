"""Hermetic tests; no GitHub writes or network calls."""

from datetime import datetime, timezone
import unittest

from discover_prs import DiscoveryError, admin_orgs, discover, search


def item(number, repository="outside/project", state="open"):
    return {"html_url": f"https://github.com/{repository}/pull/{number}",
            "repository_url": f"https://api.github.com/repos/{repository}",
            "number": number, "title": f"PR {number}", "state": state,
            "updated_at": "2026-10-01T00:00:00Z", "draft": False}


class DiscoveryTests(unittest.TestCase):
    def test_only_open_prs_are_queried_and_returned(self):
        calls = []

        def api(endpoint, fields):
            calls.append(fields["q"])
            # A PR may close between search indexing and the response.
            return {"total_count": 2, "items": [item(1), item(5, state="closed")]}

        result = discover("example-user", api=api)
        self.assertTrue(result["complete"])
        self.assertEqual([pr["number"] for pr in result["prs"]], [1])
        self.assertEqual(calls, ["is:pr author:example-user is:open -user:example-user"])

    def test_scope_external_organizations_and_overrides(self):
        calls = []

        def api(endpoint, fields):
            calls.append(fields["q"])
            batch = [item(1), item(2, "EXAMPLE-USER/private"),
                     item(3, "team/owned"), item(4, "another/ignored")]
            return {"total_count": len(batch), "items": batch, "incomplete_results": False}

        result = discover("example-user", exclude_owners=["team"],
                          exclude_repos=["another/ignored"], api=api,
                          now=datetime(2026, 10, 8, tzinfo=timezone.utc))
        self.assertTrue(result["complete"])
        self.assertEqual([pr["number"] for pr in result["prs"]], [1])
        self.assertEqual(result["excluded_in_fetched_results"], 3)
        self.assertEqual(calls, ["is:pr author:example-user is:open -user:example-user -repo:another/ignored"])

    def test_organization_is_included_without_explicit_exclusion(self):
        def api(endpoint, fields):
            batch = [item(1, "team/project")] if "is:open" in fields["q"] else []
            return {"total_count": len(batch), "items": batch}
        self.assertEqual(discover("example-user", api=api)["prs"][0]["repository"], "team/project")

    def test_administered_organizations_are_own_repositories(self):
        calls = []

        def api(endpoint, fields):
            calls.append(fields["q"])
            batch = [item(1), item(2, "Own-Org/site"), item(3, "member/project")]
            return {"total_count": len(batch), "items": batch}

        result = discover("example-user", own_orgs=["own-org", "Own-Org", "example-user"], api=api)
        self.assertTrue(result["complete"])
        self.assertEqual([pr["number"] for pr in result["prs"]], [1, 3])
        self.assertEqual(result["scope"]["own_admin_orgs"], ["Own-Org"])
        self.assertEqual(calls, ["is:pr author:example-user is:open -user:example-user -org:Own-Org"])

    def test_admin_orgs_keeps_only_admin_memberships(self):
        def api(endpoint, fields):
            self.assertEqual(endpoint, "user/memberships/orgs")
            return [{"organization": {"login": "zeta"}, "role": "admin"},
                    {"organization": {"login": "member"}, "role": "member"},
                    {"organization": {"login": "Alpha"}, "role": "admin"}]
        self.assertEqual(admin_orgs(api), ["Alpha", "zeta"])

    def test_unknown_own_organizations_mark_discovery_incomplete(self):
        def api(endpoint, fields):
            return {"total_count": 1, "items": [item(1, "maybe-own/site")]}
        result = discover("example-user", api=api, problems=["Could not list administered organizations"])
        self.assertFalse(result["complete"])
        self.assertEqual(result["problems"], ["Could not list administered organizations"])

    def test_paginates_beyond_first_page(self):
        pages = []
        def api(endpoint, fields):
            pages.append(fields["page"])
            start = (fields["page"] - 1) * 100
            return {"total_count": 105, "items": [item(i) for i in range(start, min(start + 100, 105))]}
        found, metadata = search("query", api)
        self.assertEqual(pages, [1, 2])
        self.assertEqual(len(found), 105)
        self.assertTrue(metadata["complete"])

    def test_search_cap_is_explicitly_incomplete(self):
        def api(endpoint, fields):
            start = (fields["page"] - 1) * 100
            return {"total_count": 1001, "items": [item(i) for i in range(start, start + 100)]}
        found, metadata = search("query", api)
        self.assertEqual(len(found), 1000)
        self.assertFalse(metadata["complete"])
        self.assertTrue(any("Search cap" in problem for problem in metadata["problems"]))

    def test_partial_api_failure_retains_results_but_not_completeness(self):
        def api(endpoint, fields):
            if fields["page"] == 2:
                raise DiscoveryError("API unavailable")
            return {"total_count": 200, "items": [item(i) for i in range(100)]}
        found, metadata = search("query", api)
        self.assertEqual(len(found), 100)
        self.assertFalse(metadata["complete"])
        self.assertIn("API unavailable", metadata["problems"])

    def test_github_incomplete_flag_and_duplicate_pages_are_not_success(self):
        def api(endpoint, fields):
            return {"total_count": 200, "items": [item(i) for i in range(100)],
                    "incomplete_results": True}
        found, metadata = search("query", api)
        self.assertEqual(len(found), 100)
        self.assertFalse(metadata["complete"])
        self.assertIn("GitHub reported incomplete_results", metadata["problems"])


if __name__ == "__main__":
    unittest.main()
