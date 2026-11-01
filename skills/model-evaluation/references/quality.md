# Quality and actual-client qualification

Choose evals for the user's workload before seeing candidate scores. Tool-use
quality, code correctness, long-context retrieval, and real agent completion
answer different questions. Run the relevant ones against the baseline and
every serious candidate; throughput alone does not establish intelligence.

## Use upstream evaluators

For tool calling, start with
[tool-eval-bench](https://github.com/SeraphimSerapis/tool-eval-bench). For coding,
use [EvalPlus](https://github.com/evalplus/evalplus) or another established suite
that exercises the requested languages and tasks. Discover each pinned tool's
CLI and dataset versions rather than copying commands from a different release.
A minimal API adapter may translate transport or sampling fields; preserve the
suite's prompts, tool semantics, stopping rules, and graders. Do not replace an
available evaluator with a few hand-written questions and call that qualification.

Record dataset/split/version, task count, hard-mode variants, seed list,
sampling, reasoning mode, output and turn budgets, tokenizer/model revision,
endpoint/backend, evaluator revision, and error policy. Keep them matched
between candidates, or explicitly label a comparison that intentionally uses
each candidate's production recipe. Never silently use different reasoning
budgets or default sampling. Follow the model's supported tool-use sampling;
inspect the model card, chat template, and serving recipe for supported settings.

Use repeated runs or samples sufficient for the decision's uncertainty and
cost. A fast core suite is useful screening; broad claims need broader coverage.
Choose targeted follow-ups from observed consequential differences, while
retaining the original matched comparison. Report scores with denominators,
per-run results/spread, API failures, timeouts, truncations, and tool-turn
exhaustion. Evaluator errors are not valid quality scores or automatic passes.

Execute generated code in the evaluator's supported isolation or a disposable
sandbox with no credentials or external network access. Benchmark tool actions
should use the suite's mock tools or disposable fixtures. These checks do not
authorize real email, messages, deletion, or other external side effects.
Bound bulk eval traffic according to the endpoint's admission policy; use the
[performance isolation procedure](benchmarks.md) for dedicated load tests.

## Inspect differences without changing the grading contract

Keep raw outputs, tool calls/results, scorer output, and complete failure traces.
Distinguish model mistakes from parser incompatibility, infrastructure errors,
output caps, and grader defects. Replay disputed traces with the pinned upstream
scorer where possible. Publish its original score separately from any manually
adjudicated result, with the trace and rationale. Do not patch a grader mid-run
or count a questionable case as a confirmed regression.

Compare paired cases as well as aggregates. A repeated failure on authorization,
tool dependencies, or destructive-action prerequisites may matter more to the
requested use than a small average score difference. Apply the same inspection
to the baseline; its prior deployment is not proof of quality or safety. Do not
invent a universal zero-regression gate after seeing the results.

## Validate the real clients

After the candidate responds, send a completion through the actual authenticated
client route or gateway default. Exercise supported thinking and non-thinking modes,
streaming, and a tool-call/tool-result round trip. Use the actual configured agent defaults for turns, not only a direct engine API substitute.
Record client/provider/model/variant and configuration provenance. Disable
outbound delivery and use harmless local fixtures. Client checks prove routing,
capability declarations, and parsing; a single file-read turn does not prove
coding quality.

For a long-context requirement, include retrieval/correctness checks at the
relevant depths and combined concurrency, not just successful token generation.
Record actual token counts and misses. Use a workload-level task when claiming
that an agent finishes sooner: sum of decode rates does not measure tool wait,
reasoning overhead, retries, or task correctness.

Report the quality and client evidence beside the performance results in the
same candidate decision. Keep unmeasured capabilities explicit and complete
follow-ups that can change the recommendation within the authorized scope.
