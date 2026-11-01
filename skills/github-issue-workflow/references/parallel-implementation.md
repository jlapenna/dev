# A parallel implementation already merged

Read this when the pre-PR landscape check (step 7) shows the same feature or
fix landed independently. A fresh PR that unexpectedly reports
`mergeStateStatus: DIRTY` often means this, so check for a parallel merge
first; an ordinary conflict follows `repo-tools:land-pr` instead.

On any run longer than an hour, the world has moved. Claims bind agents, not
humans: the maintainer (or another runtime) may have shipped the same change
while you built yours.

1. Stop. Do not open (or keep) a duplicate PR, and do not mechanically resolve
   its conflicts.
2. Close your duplicate with a provenance comment that names the merged
   implementation.
3. Diff your branch against the merged version for salvageable deltas: fixes
   and review findings yours carries that theirs lacks.
4. Ship only those deltas as a focused follow-up PR through the normal steps.
