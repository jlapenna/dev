# External pull request report

This manual-only LCARS job runs the repository's `external-pr-checkin` skill in
read-only report mode. It reports the selected GitHub identity's open external
pull requests, current checks and review gates, and concrete next actions.
It makes no changes to GitHub and has no recurring schedule.

The `dev-personal-github` execution profile is supplied by the consuming LCARS
installation. Its operator must bind a credential set and grant it to this
exact repository, job, profile and invoking principal. The recipe contains no
credentials and does not obtain credentials from the host or the skill's
installation. Missing admission or credentials fail through LCARS's normal
authorization path.

Refresh the job catalog after merging, enable the admitted digest as an
authorized operator, and invoke `jlapenna/dev` → `external-pr-sweep` in LCARS
Jobs. This job defaults to the personal profile; it does not change the
credentials of any other job. LCARS retains `report.md` and `result.json` as
the run's artifacts.
