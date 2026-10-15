---
name: write-benchmark
description: Use when creating or modifying a benchmark, performance experiment, load test, or evaluation runner. Requires live JSON progress and partial results, crash-safe checkpoints and resume, reproducible measurements, and safe testing-environment reset between independent measurements and after interruption.
---

# Write Benchmark

Write a benchmark that stays observable while running, resumes without losing committed work, and measures the intended workload in a controlled environment. Prefer the project's existing benchmark tools and the standard library; do not build a generic benchmark framework.

## 1. Define the experiment

Inspect the existing runner, fixtures, reporting, and commands before editing. Reuse their conventions. Establish the following from the request and repository; ask only when a missing decision changes the experiment:

- **Question and metrics:** what is being compared, the workload, units, and what counts as a valid result. Validate correctness as well as speed; a wrong answer is not a faster result.
- **Work plan:** variants, cases, repetitions, random seeds, order, and a unique stable ID for each checkpoint unit. Choose a unit small enough that replaying one interrupted unit is acceptable; persist the plan before execution.
- **Measurement protocol:** setup, reset, warmup, measured work, validation, and teardown. State whether the workload represents a cold or warm environment. Use a monotonic clock for durations and synchronize asynchronous work before stopping the timer when applicable.
- **Environment contract:** owned resources, reset scope and frequency, baseline state, relevant hardware/runtime/dependency versions, and any shared or external dependencies. Keep input data and comparison conditions equivalent across variants; record or control order effects.
- **Recovery contract:** output location, checkpoint unit, maximum lost work, compatibility identity, failure behavior, and exact commands for a fresh run, resume, and viewing partial results.

Use sensible defaults where the repository permits them. Do not add automatic retries, distributed orchestration, a dashboard, or new dependencies without a demonstrated need. Do not impose latency percentiles or timing-specific warmup on benchmarks where they do not apply.

## 2. Reset the testing environment safely

A reset is part of the experiment, not an unconditional cleanup command.

- Use benchmark-owned temporary directories, database schemas, containers, or equivalent isolated resources. Preserve immutable fixtures and keep checkpoints/results outside the reset scope. Never reset production, shared resources, unrelated files, host-wide caches, or global settings without explicit authorization and a restoration plan.
- Define reset frequency at the run, case, or sample level to match independence requirements. Restore mutable data, application caches, random generators, transactions, background jobs, and external test state only where relevant. Verify the intended baseline before measuring; fail visibly if setup or reset fails.
- Make reset safe to repeat after partial setup or a crash. Validate ownership and resolved paths before deleting resources; do not follow links out of the owned scope. Prevent overlapping runners from resetting or writing the same resources, using the existing isolation or locking mechanism.
- On resume, reconstruct the required environment before replaying unfinished work. A checkpoint proves committed results, not that a process, connection, cache, or database is still usable. If external side effects cannot be reset or replayed safely, stop with an actionable error rather than claiming recovery or exactly-once execution.
- For a **warm** measurement: reset, prepare, warm up, then measure without erasing the warmed state. For a **cold** measurement: establish the declared cold state before each independent sample. For intentionally stateful workloads: reset between independent sequences, not inside the sequence. Exclude reset/setup/teardown from measured time unless they are the stated subject of the benchmark; document unavoidable cache or background-I/O effects.

Attempt teardown on success, failure, timeout, and cancellation without hiding the original error. Teardown must preserve reports and checkpoints. Abrupt termination may bypass teardown, so the next run must handle stale benchmark-owned resources safely.

## 3. Persist live progress and partial results

### Minimum progress contract

Create `progress.json` before expensive setup or measured work. It must remain valid JSON for concurrent readers and contain enough information to understand and resume the run:

| Information | Required content |
| --- | --- |
| Identity | Schema version, run ID, compatibility fingerprint and its manifest, persisted work plan |
| Lifecycle | Run status (`running`, `completed`, `failed`, or `cancelled`), phase, start time, last update time |
| Progress | Total, completed, failed, and pending unit counts; active unit IDs; consistent accounting for active work |
| Work state | Stable unit IDs, per-unit status and attempt information, committed raw results or durable result references |
| Diagnostics | Unit/phase errors, relevant environment metadata, heartbeat/report cadence |

Field spelling may follow project conventions. Use wall-clock timestamps for human observation, not elapsed-time measurement. A fresh process starting the run must not silently overwrite existing output.

For small runs, one atomic JSON snapshot can hold both progress and results. For larger runs, use the existing durable result store or per-unit result files plus references. Use JSONL only if needed and define how to handle a truncated last record and duplicate attempts. Do not rewrite an unbounded result history on every heartbeat.

### Commit and update rules

1. Publish lifecycle/phase changes, each finished unit, and terminal status. During long setup or work, publish a bounded-cadence heartbeat even when no unit finishes; use the project's cadence, otherwise default to five seconds. Include the active phase/unit so stale progress is distinguishable from slow work. Do not depend on the measured operation returning to publish a heartbeat.
2. Write each snapshot to a temporary file in the same directory, flush it, and atomically replace `progress.json`. State the durability guarantee: process-crash recovery is required; use file/directory sync or the store's transaction guarantees if recovery from host/power failure is claimed. Temporary-file debris is not a committed checkpoint.
3. Commit results before marking their unit completed, or commit both in the same atomic snapshot/transaction. A completed unit must never reference missing or incomplete results. If a crash leaves an unreferenced result, define reconciliation or safe replacement on replay; never count it twice.
4. Give parallel workers a single coordinated writer, or use the existing transactional store. Heartbeats and result commits must not overwrite each other with stale snapshots. Keep reporting, serialization, and checkpoint writes outside timed regions; account for background interference rather than claiming zero measurement overhead.
5. Publish human-readable partial results during execution, not just a percentage or a final report. Use the same committed results for machine-readable progress, live summaries, and the final report. Flush buffered output. Label incomplete reports, show sample/failure counts and units, and distinguish measured metrics from progress estimates. Report distributions or uncertainty when appropriate, retaining raw samples rather than only averages.

Do not turn failed samples into zero-valued measurements, mix warmup samples into measured results, or silently remove failed cases from the denominator. Declare whether failures stop the run or allow other independent work to continue. An exhausted work queue with failed units is not a successful `completed` run.

If progress or result persistence fails, stop scheduling work, report the error, and exit non-success while preserving the last committed checkpoint. Do not let a failed reporting thread silently turn a run into an unobservable success.

## 4. Resume from the progress file

Expose and document an explicit resume command that accepts the progress file. Recovery must work when the saved status is `failed`, `cancelled`, or still `running` after abrupt termination.

1. Load and validate the checkpoint and its referenced results before mutating the environment or output. Reject malformed JSON, unknown schema versions, broken result references, and incompatible experiments with an actionable error; preserve the existing evidence. If the run is still owned by a live process, reject concurrent resume.
2. Compare a persisted compatibility manifest/fingerprint covering benchmark implementation (including relevant uncommitted changes), inputs, variants, parameters, seeds, work plan, dependencies, measurement/reset protocol, and environment attributes that affect comparability. Do not use volatile values such as PID or timestamps as compatibility inputs. On mismatch, require a separate fresh run rather than silently combining results or bypassing the check.
3. Keep the original run ID, plan, ordering, and committed results. Skip completed units; restore pending units and explicitly reattempt unfinished/failed units under the declared policy. Track attempts separately from unique completed work and preserve error history. A completed compatible run is a no-work resume, not an excuse to reset its environment or rerun it.
4. Reestablish the environment contract, including reset and warmup where appropriate, before new measurements. Replay interrupted units from their checkpoint boundary; do not append a second successful result for the same unit. Restore planned seeds/state so resuming does not silently change the experiment.
5. Publish resumed progress and partial results immediately, then follow the same commit protocol as a fresh run. Handle cancellation and declared timeouts with best-effort checkpointing and a non-success exit; recovery must still work if no signal handler ran. Record downtime separately if reporting cumulative active elapsed time.

The guarantee is **no loss or duplication of committed results**, not exactly-once execution of interrupted work. State the replay boundary and any unavoidable limitations involving external systems.

## 5. Prove the generated benchmark works

Run the actual generated command with a tiny, deterministic workload before presenting it as complete. Use isolated resources and bounded execution. Test behavior through commands, progress files, results, and observable environment state, not source-text assertions.

1. **Live visibility:** read and parse `progress.json` while the process is still running. Observe a partial measured result and flushed human-readable output before completion. Make one unit longer than the heartbeat interval; observe advancing timestamps with the same active unit. Check that readers never observe partial JSON.
2. **Abrupt recovery:** after at least one committed unit and while another is active, forcefully terminate the runner without its cleanup handlers. Resume from the saved `running` progress file. Verify committed units were not rerun, interrupted work was replayed, unique result IDs and counts match the plan, and dirty environment state was reset. Compare deterministic outputs and accounting with an uninterrupted run, not wall-clock timings.
3. **Commit boundaries:** exercise interruption between result persistence and completion publication if these are separate operations. Verify no missing references, double counting, or corruption. If both are one atomic snapshot/transaction, exercise interruption around that commit instead.
4. **Failure and safety:** exercise a failed unit and resume, rejected incompatible/corrupt checkpoints, and a failed reset. Verify failures stay visible, invalid state is rejected before destructive work, no invalid measurement is accepted, and an out-of-scope sentinel resource survives reset and teardown.
5. **Completion and isolation:** verify cancellation preserves committed work, a completed resume performs no measured work or reset, teardown preserves evidence, and overlapping runs cannot corrupt the same output/environment. Exercise the benchmark's correctness checks and run applicable existing project checks.

Prefer a small permanent regression test for uncertain recovery/reset boundaries, following repository conventions; otherwise use a throwaway smoke script. Do not keep source-text tests, framework scaffolding, failure-injection switches, or temporary artifacts solely to demonstrate this skill. Never report an unexercised scenario as verified.

## Delivery

Update the project's benchmark documentation or changelog. Provide the exact fresh-run, resume, and live-report commands; output paths; metric/reset/recovery semantics; and the smoke scenarios actually exercised. State blockers or unverified external-environment behavior explicitly. Deliver working benchmark code for the requested workload, not a placeholder runner or a framework skeleton.
