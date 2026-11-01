---
name: model-evaluation
description: Research, benchmark, and qualify models and inference configurations; compare quality, latency, context, concurrency, and actual client behavior and recommend what to use. Includes authorized temporary trials and retuning. Routine inference calls use the environment's request guide.
---

# Evaluate models and serving configurations

Carry the comparison from candidate research through measured performance and
quality to a recommendation for the requested workload. Throughput screenshots
and smoke tests alone do not establish a better model.

## Define the comparison

Inspect the live baseline, source recipe, and environment's operating guide.
Record workload, clients, context/output budget, concurrency, quality priorities,
research window, and operational authorization using the
[run record](assets/model-status.md). Reconcile recorded processes and artifacts
when resuming; an observer timeout does not prove that a load or test died.

Identify each configuration by model/tokenizer revision, engine/version,
weight quantization, KV-cache precision, topology, and material flags. Distinguish
cooperating tensor-parallel ranks from independent replicas of a complete model.
Report total and active parameters separately from auxiliary embeddings and
draft models. A topology change proves neither a smaller model nor equal quality.
Give each candidate and routing variant one stable identifier. Verify material
flag meanings and runtime tensor precision against the pinned implementation;
a vocabulary size is not a context limit, and stored precision can differ from
resident precision. Keep discovery claims separate from the qualified manifest.

Research within the requested date window. Use relevant community reports and
leaderboards to discover candidates, then verify consequential claims against
upstream recipes, code, issues, model cards, and images. For DGX Spark selection,
include Spark Arena, LocalLLaMA, and NVIDIA developer forums. Record evidence
dates and distinguish published claims from local measurements. A dated working
recipe is a baseline, not a permanent recommendation.

Choose a bounded protocol before trials: workload-relevant cases, matched
sampling/thinking and output budgets, repeated runs, and explicit selection
criteria. Keep the baseline alongside serious candidates. Reuse existing results
only where their configurations and conditions match. Label exploratory,
interrupted, and superseded runs rather than mixing their best numbers.

## Qualify the candidates

- Read [performance](references/benchmarks.md) for latency, prefill/decode,
  depth, concurrency, prefix reuse, and traffic isolation. Use upstream
  llama-benchy for compatible endpoints instead of building a parallel harness.
- Read [quality and clients](references/quality.md) for tool use, coding,
  long-context correctness, and actual agent checks. Use established evaluators
  with their grading contract intact; a small core suite does not prove parity.
- Read [completion and publication](references/completion.md) when resuming a
  multi-stage run or turning results into a durable recommendation.
- Read [temporary trials](references/operations.md) before staging or changing
  an engine. Follow the environment's own install, telemetry, and rollback
  procedures; this generic skill does not grant host-operation authority.

Honor existing grants for temporary trials and any confirmation reserved for
permanent deployment. Complete authorized measurements and restoration before
handing back a recommendation for approval. Evaluation alone does not authorize
interrupting callers, paid API use, public benchmark uploads, or a permanent
default change. Native inference follows its operational contract; CI resource
profiles apply only when actually dispatching through that CI system.

## Reach a decision

Compare completed evidence in one table: exact model/precision/topology,
quality scores and denominators, per-request and aggregate speed, complete
response latency, tested concurrency/context combinations, and material failures.
Report actual token counts, sampling/speculation settings, and repeated-run
spread. Engine response time does not measure whole-agent task completion.

Memory is a fit and stability constraint; spare memory alone does not rank
model usefulness. Sequence slots do not prove that many full-context streams
fit. Quantization and speculative decoding require quality as well as speed
measurements.

Inspect consequential raw failures, including the baseline's. Preserve upstream
scores separately from adjudication or disputed grader cases. One small
stochastic sample does not establish population-level parity or regression.
If uncertainty can change the decision, run a targeted follow-up within scope
rather than substituting a report of missing work for the requested evaluation.

Recommend a configuration for the actual workload with measured tradeoffs and
remaining uncertainty. Keeping the original is valid when the completed
comparison supports it. If required evidence is externally blocked, name the
exact blocker and remaining work without calling qualification complete. Link
raw artifacts, pins, commands, and restoration evidence. Save the final report
and bounded reproducibility data with the environment’s owning registry when
requested; keep large raw/private artifacts in their protected evidence store.
Record selection, temporary serving, persistent deployment, and client
verification separately.
