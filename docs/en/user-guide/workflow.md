# Complete Workflow

Algocode is not a single input-to-output process. It advances through phases with gates and evidence checks at each critical point. When something fails, the task can pause, switch candidates, or replan from history.

## 1. Initialization: `algocode init`

`init` prepares a project for Algocode. It does not optimize source code directly.

It:

1. Detects or initializes a Git repository.
2. Detects the primary language: `auto`, `cpp`, or `python`.
3. Generates `.algocode/config.yaml`.
4. Discovers the Project Contract and generates a Contract Test.
5. Creates the initial Task.
6. Captures the Baseline.
7. Attempts the initial Correctness and baseline Benchmark runs.

If the entry point reads from stdin, Contract Discovery can also produce a family of increasing-size inputs. After validation, the runtime writes them to `.algocode/benchmarks/benchmark.yaml` under `inputs`.

When the Contract contains a `benchmarkHarness`, Algocode writes `.algocode/benchmarks/harness.py` for Python and writes and compiles `.algocode/benchmarks/harness.cpp` for single-file C++ projects. It then calibrates a fixed repeat count near a target duration. Fixed is intentional: an adaptive count would make each sample perform different work and add variance.

Generated outputs include:

```text
.algocode/config.yaml
.algocode/contract.json
.algocode/oracle/
.algocode/benchmarks/benchmark.yaml
.algocode/current-task.json
```

Re-running `algocode init` after a successful initialization rechecks the project without changing the optimization flow.

## 2. Analyze: Read-Only Reconnaissance

During Analyze, the Agent only reads the project. It must identify public APIs, entry points, state changes, errors, boundary conditions, observable output, determinism requirements, hotspots, complexity sources, performance goals, and candidate optimization directions.

It also produces structured problem analysis (`problemStructure`) and a complexity baseline (`complexityBaseline`), including input model, data distribution, query/update ratio, monotonicity, constraints, algebraic properties, current complexity, known-best complexity, and the gap.

At least three algorithm or data-structure candidates (`algorithmCandidates`) must be supplied with applicability and expected gain. Missing fields make the report invalid.

## 3. Baseline: Establish the Comparison Point

Every later piece of evidence is compared with the Baseline. It records the baseline Git revision, source snapshot hash, environment hash, and build outputs. Plan and Generate Candidate require a Baseline.

## 4. Plan: Produce an Optimization Plan

The Agent performs read-only reconnaissance against the real source, then submits an `OptimizationPlan` containing strategy, target files, risks, constraints, verification methods, and expected gain. The plan must be grounded in `problemStructure` and `complexityBaseline`, including `algorithm`, `complexityBefore`, `complexityAfter`, `whyFaster`, and `structureRef`.

`algocode retry` injects historical optimization records here to avoid repeating failed directions.

## 5. Generate Candidate: Create an Isolated Candidate

The CLI creates an independent Git worktree from the Baseline. The Agent never edits the user workspace directly. The VS Code extension uses a temporary shadow workspace instead. Both entry points still operate on an isolated copy.

## 6. Implement: Make the Change

The Agent edits only the candidate workspace. Allowed tools include `apply_patch`, `write_file`, `edit_file`, `run_candidate_check`, and `get_candidate_diff`. Each phase exposes only its tool allowlist and injects remaining turns, remaining tool calls, and candidate self-check requirements.

The Agent may fail and repair the candidate repeatedly until it is ready for Verify.

## 7. Verify: Correctness and Contract

Verify is the gate before Benchmark. The candidate must pass Build, Correctness, and Contract. If any item fails, the candidate cannot enter Benchmark.

Correctness normally has two kinds of cases: the fixed contract baseline output (`primary-output`) and reference cross-checks (`oracle-*`) that rerun the protected reference copy under `.algocode/oracle/reference/`. The reference cross-check forces a new algorithm to behave byte-for-byte like the original on supported test inputs. The reference is protected from candidate edits.

## 8. Benchmark: Measure Performance

Benchmark runs only after Correctness and Contract pass. It interleaves Baseline and Candidate runs, records warmup and repeated samples, uses environment and comparison hashes to prevent invalid comparisons, and applies paired permutation tests, bootstrap confidence intervals, and MAD-based robust variation.

If `benchmark.yaml` declares `size` for inputs, each input is summarized separately. The overall improvement is the median of per-input improvements, and variation uses the worst per-input value.

## 9. Compare: Evaluate the Evidence

Compare summarizes baseline and candidate medians and produces a Comparison Result. Improvement is represented as the median paired relative improvement. Significance uses a paired permutation test; the confidence interval uses paired bootstrap.

When at least three inputs declare `size`, Algocode fits `log(time)` against `log(size)` and records `growthBaseline`, `growthCandidate`, `growthDelta`, and `growthPoints`. A meaningful drop in growth exponent is algorithmic evidence even if the candidate is slower on the smallest input.

## 10. Decide: Apply the Acceptance Policy

Typical acceptance conditions include `requireCorrectness`, `minMedianImprovementPercent`, growth exponent reduction requirements, peak-memory regression limits, compile-time regression limits, variation limits, and a paired confidence interval that does not cross zero.

If the outcome is not `accepted`, Algocode evaluates whether the direction is worth continuing. Significant improvement or a fitted growth drop can trigger refinement of the same candidate. Regression or noise triggers a new candidate and a different search direction.

## 11. Review, Accept, and Apply

```bash
algocode review
algocode diff
algocode accept <task-id> <candidate-id>
algocode apply
```

`accept` records the decision only. `apply` writes the candidate patch to the user workspace after checking the decision, frozen state, stale state, and rollback manifest.

## 12. Rollback

If a problem is found after Apply:

```bash
algocode rollback
```

The CLI uses the manifest saved during Apply. The VS Code extension restores file backups.

## 13. Report

```bash
algocode report <task-id>
```

It generates internal JSON and Markdown artifacts plus a root-level `report.md` for archival or review.

## Phase Gates

| Phase | Prerequisite |
| --- | --- |
| Plan / Generate Candidate | Baseline must exist. |
| Implement / Verify / Benchmark / Compare / Decide | Candidate must exist. |
| Benchmark / Compare / Decide | Candidate Correctness must pass. |
| Compare / Decide | Candidate benchmark comparison must exist. |

A failed gate leaves the task in `waiting_user`; the recommended command is usually `algocode optimize` or `algocode status`.

## Failure and Retry Paths

### Gate Failed

Run `algocode status`, supply the missing prerequisite evidence, then run `algocode optimize` again.

### Verify Failed

The candidate is marked `rejected`; the next run can create a new candidate and implement again.

### Benchmark Invalid

Inspect the run and experiment, then confirm that baseline and candidate comparison keys match.

### Insufficient Gain or Wrong Direction

Replan from history:

```bash
algocode retry
```

### Apply Failed

Common causes are an unaccepted candidate, a stale workspace, or inconsistent patch state. Inspect `algocode status` and `algocode review` before touching rollback data manually.
