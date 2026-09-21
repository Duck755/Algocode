# Storage and Artifacts

Algocode uses SQLite for events and projections, and a file artifact store for large content.

## Event Store

- All critical state is written through events.
- Each aggregate has a monotonic `seq`.
- Writes use expected sequence numbers for concurrency control.
- Projections update in the same transaction.

## Artifact Store

Artifacts store:

- Correctness specifications and results.
- Benchmark specifications, samples, and comparisons.
- Context snapshots.
- Model logs.
- Optimization records.
- Candidate patches.

Artifacts are content-addressed. Writes record a digest and metadata. SQLite stores only `ArtifactRef` references; actual bytes live in the filesystem.

## Project Directory

Project state lives primarily under `.algocode/`. The `cache/` directory should not be edited by hand.

See [Project Layout](../reference/project-layout.md) for the complete layout.

## State Derivation

`algocode status` reads the Task projection and Event Store. Current phase, turn, tool count, active tool, last tool, and phase duration are derived from the event sequence instead of maintained as separate volatile state.
