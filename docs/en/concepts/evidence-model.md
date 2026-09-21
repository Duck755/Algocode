# Evidence Model

Algocode does not rely on self-evaluation from the model. It turns optimization results into three durable forms of evidence.

## Correctness

Correctness verifies that a candidate reproduces baseline behavior. It supports `cases`, `oracle`, `stress`, and `hybrid` modes.

It answers:

- Are outputs identical?
- Are exit codes identical?
- Are boundary behavior, errors, and state transitions preserved?

## Contract

Contract protects behavior outside the algorithm itself, including public APIs, configuration semantics, return ordering, exceptions, and structural invariants.

It answers:

- Did optimization change the user-observable contract?
- Were necessary checks removed?
- Did ordering, state, or error behavior change?

## Benchmark

Benchmark measures performance in a controlled environment and records warmup, repeated samples, medians, MAD-based robust variation, confidence intervals, and environment hashes.

It answers:

- Is the candidate actually faster?
- Is the improvement stable?
- Is the measurement trustworthy?

Baseline and candidate samples are paired by input and repeat. Paired permutation tests, bootstrap confidence intervals, and robust variation prevent one scheduling spike from invalidating an otherwise strong result.

When at least three inputs declare `size`, Algocode also estimates `growthBaseline`, `growthCandidate`, and `growthDelta`. A clear reduction in growth exponent can serve as algorithmic evidence.

## Evidence Order

Correctness must pass, Contract must pass, and only then can Benchmark qualify for the decision phase.
