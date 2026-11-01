# Resolving personal versus repository policy

Read this when a repository rule and a personal skill or user instruction
overlap or appear to conflict.

Precedence:

- System, developer, and current user instructions and permissions control.
- Repository rules own concrete repository semantics: claimant identity,
  labels, base branch, verification, CI, merge, and deployment.
- Personal skills provide the cross-repository safety floor and the defaults
  for anything the repository does not specify.

Resolve overlapping rules with this test:

1. The most specific compatible rule wins.
2. First determine whether a rule applies to this execution mode. A stricter
   autonomous-only rule is inapplicable to an interactive session.
3. When compatible shared safety requirements differ, use the stricter rule.
4. Repository silence or wording such as "optional" does not waive a stricter
   personal safety rule.
5. Treat a repository rule as an exception to a personal guardrail only when
   it addresses that guardrail explicitly and higher-level instructions permit
   the exception.
6. Resolve conflicts using the user's existing authorization and explicit
   repository exceptions first. Ask only when a material policy choice is still
   unresolved; do not repeatedly ask about an already-settled exception.

An exception for one managed-file workflow does not settle an unrelated
repository's explicit prohibition. Resolve the actual ownership boundary from
the user's instructions and the current repository's rules.
