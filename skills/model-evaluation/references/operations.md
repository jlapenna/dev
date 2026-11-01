# Temporary trials and turn-up

Read the environment's owning runbook and recipe before host operations. This
skill describes measurement boundaries; the environment owns installation,
identities, service management, gateway policy, monitoring, and deployment.
A documentation change grants no restart or model-switch permission. If no
runbook exists, establish service ownership and startup/restoration commands
from the live configuration before authorized changes. Read-only API evals
do not require host changes or an invented deployment process.

## Stage and recover a coherent configuration

Use reproducible third-party image digests, model/tokenizer revisions, engine
versions, and patch identities. Follow each source owner's update policy.
Verify hardware/driver support in the actual image and complete checkpoints,
shard indexes, and any copied weights on all participating devices before
changing the working service.

Budget weights, embeddings/offload, KV and recurrent caches, draft models,
graphs/compiler temporaries, and host workloads without double-counting
already-quantized tensors. Inspect context/output budgets, prefill chunk,
cache precision, speculative depth, graph sizes, request limits, and memory
fraction together. Use a supported recipe, not a universal batch-size or
eager-mode rule. Independent replicas each need a full model unless their
recipe explicitly says otherwise. An estimator can omit real allocations;
diagnose an OOM rather than blindly retrying or relaxing the contract.

Record storage placement and warm-up. Direct storage, a loop filesystem, and
warm page cache can produce materially different loading/prefill behavior.
Keep conditions comparable or label differences.

Capture working pins, flags, units, routes, defaults, and recovery procedure.
Identify task-owned containers, downloads, metrics bridges, listeners, timers,
and mounts. Preserve process/session handles and loading/compilation progress.
An observer timeout is not proof the process stopped; avoid duplicate loaders
or launch scripts competing with an existing service manager.
For multi-stage work, keep one authoritative run record with phase, candidate,
launch owner, live units/handles, expected outputs and next transition. Before
a restart or continuation, inspect those units and completed artifacts. A
watcher notification grants no new authority and must not duplicate a parent’s
queued launches. Preserve the original exit status and repair the component
that failed; do not rerun completed quality because an observer or grader failed.

## Observe real service and cleanup

Before timing, verify native engine activity and the environment's monitoring
consumer. A loopback-only candidate still needs an explicit metrics path if
that consumer is part of the service contract. Missing telemetry is not idle.
Do not claim service-manager loading state for an unmanaged candidate.

Watch actual loading, transport, memory pressure, swap-out, allocator/kernel
errors, and restarts on participating hosts. Unified host/GPU memory requires
host-level observations as well as container statistics. Startup duration and
transient swap alone do not prove failure. Diagnose stalled progress with
sustained pressure or allocation errors; stop only affected task-owned work.

Use the environment's supported install/restart path for persistent changes
and preserve caller routes, limits, capabilities, credentials, and fallback
policy. For an outage, restore service before extended comparisons. Test real
clients according to [quality and client qualification](quality.md).

After temporary trials, restore the recorded original unless a persistent
choice is authorized. Close task-owned pauses and silences, restore timers,
and remove temporary listeners, helpers and mounts. Verify pins, units,
monitoring, and a successful final request through the actual client route.
Compare exact restored source hashes, image/model revisions and material flags
with the pre-trial snapshot. Match observer preconditions to live service activity:
production requests resuming after restoration are not a failed idle engine.
After removing helpers, verify one fresh authenticated ordinary request without
benchmark headers or response-cache reuse, plus the normal monitoring path.
Clean the task worktree through its repository workflow; preserve needed source
and recovery evidence outside it first. Retained offline weights are distinct
from an installed candidate service.
Retain restoration and failure evidence. Short qualification does not prove
indefinite reliability or the cause of a historical failure.
