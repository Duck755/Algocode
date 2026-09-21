# Troubleshooting

## `optimize` Does Not Reach `completed`

The workflow can be blocked by model output, failed validation, a step budget, or a phase gate. Check these locations first:

- `.algocode/cache/model-logs/`: model requests and errors.
- `.algocode/cache/optimization-records/`: records for each optimization attempt.
- `.algocode/current-task.json`: current task state.

Use `algocode status` to see the recommended next command, or retry from history when appropriate.

## `init` Fails

Common causes include:

- The project is not a Git repository and automatic initialization failed.
- The code cannot compile or run.
- No supported Python or C++ entry point was found.
- The provider is not configured or cannot be reached.

## `apply` Fails

Common causes include:

- The candidate has not been accepted.
- The user workspace changed during optimization.
- The current workspace state no longer matches the candidate baseline snapshot.

## Evidence Locations

- Correctness: `.algocode/cache/artifacts/`.
- Benchmark: `.algocode/cache/artifacts/`.
- Contract: `.algocode/contract.json`.
