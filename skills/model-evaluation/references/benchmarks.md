# Performance qualification

Use [upstream llama-benchy](https://github.com/eugr/llama-benchy) for a compatible
running endpoint. Discover its current CLI and pin the chosen third-party tool
revision for the comparison. A serving-stack wrapper is optional; benchmarking
does not require redeploying the service or submitting results to a leaderboard.
Inspect upload behavior and keep local-only work local.

## Isolate load from ordinary callers

Direct engine ports can bypass gateway admission. Before depth, concurrency,
or cache sweeps, use a dedicated backend or an already-authorized idle window
with ordinary callers quiesced. Check active/queued requests and benchmark
ownership. A deployment maintenance window does not itself block inference
clients. Obtain scheduling agreement if active callers would be interrupted;
a benchmark request alone does not authorize denying them access.

Run sweeps sequentially. If client traffic resumes, gracefully stop the
task-owned benchmark, preserve its interrupted result, and repeat under
isolation before treating it as comparable. Restore task-owned traffic pauses.
Bound serial quality-eval traffic according to the environment's admission
policy; it need not monopolize the engine.

## Match the workload

Use the tokenizer from the exact model revision. Record prompt/output budgets,
sampling, thinking, MTP/draft settings, cache state, storage placement, warm-up,
and routing/load balancing. Independent replicas need observed distribution of
requests, not an assumption that both devices shared the load.

The following illustrates a short depth sweep; adapt values and supported flags
to the requested contract, installed CLI, and model limits:

```bash
llama-benchy --base-url "$BASE_URL" --model "$MODEL" \
  --tokenizer "$TOKENIZER_DIR" --pp 2048 --tg 256 \
  --depth 0 32768 --concurrency 1 --runs 3 \
  --latency-mode generation --no-cache --format json \
  --save-result "$RUN_DIR/depth.json" \
  --emit-progress "$RUN_DIR/depth-progress.jsonl"
```

Choose context depth with output space reserved. Inspect request-body overrides
for supported reasoning controls. For a fixed-output comparison, check support
for `--exact-tg` and record it. EOS can otherwise terminate before the target:
report actual counts. A compatibility rejection is a failed attempt, not valid
throughput or proof of engine deadlock. Verify a newly released binary with
the exact backend, family, cache precision and stream budget: a generic parser
accepting a flag does not prove that the selected CUDA family supports it.
Keep published upstream speedups separate from this local compatibility test
and from matched local timing. Keep necessary overrides specific to
the tested engine/version rather than accumulating permanent workarounds.

Measure workload-relevant concurrency separately, for example `--pp 4096
--depth 0 --concurrency 1 2 4 8`, with repeated runs. A short-context concurrency
sweep plus a single-request depth sweep does not prove their combined shape;
test combined long-context concurrency when required. Scheduler slots alone
are not a capacity guarantee.

For prefix reuse, measure initial context load separately from cached follow-up,
using `--enable-prefix-caching` and omitting `--no-cache` where supported. Verify
actual cache hits in metrics/logs. Do not present cached follow-up TTFT as the
initial prompt's prefill time.

Test reuse through the route the client actually uses, as well as directly when
needed to localize a miss. Use fresh prefixes per repetition, bypass gateway
response caching, and retain per-run load/follow-up durations. An average can
hide one hit and two recomputations. Inspect the installed SDK’s emitted
session header, gateway forwarding policy and backend affinity receipt; a
configured stick table is not proof that it receives a usable key. HTTP
keepalive preserves connections, not necessarily conversation affinity. Change
one material routing variable in a separately identified follow-up, retain the
primary results, and finish or explicitly discard that follow-up before
selection. Do not recommend an untested header or routing repair as qualified.

Check admission separately from decoder capacity. A controlled over-capacity
probe can verify successful queuing beyond the proxy queue deadline; record
active decoders, pending requests, observed wait and HTTP failures. Ten successful
requests with eight active and two waiting prove queue handling, not ten
concurrent decoders. A zero exported queue-duration field does not erase an
observed wait. Use only authorized load and the environment’s existing limits.

Report TTFT, prefill, per-request and aggregate decode, complete response latency
where recorded, mean/spread, actual tokens, errors, and fit/stability evidence.
Aggregate batch throughput is not each stream's speed, and a decode gain does
not establish faster correct agent-task completion. Use a workload-level task
for that claim. Keep all failed and revised runs; do not lower context or edit
benchmark state mid-run to conceal failure.
