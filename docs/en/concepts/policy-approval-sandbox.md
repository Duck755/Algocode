# Policy, Approval, and Sandbox

## Policy

The Policy Engine decides whether a tool call is `allow`, `ask`, or `deny`. Rules are evaluated across Hard, Managed, User, Project, and Default layers.

## Approval

When the policy result is `ask`, an Approval Provider must return an approval decision. In non-interactive mode, calls that require approval fail closed.

## Sandbox

The sandbox runs builds, tests, and Benchmarks. It supports Native, Docker, and WSL2 backends and limits environment variables, timeout, memory, output size, and network access.

## Protected Files

Protected files cannot be modified by the Agent. Examples include test directories, Oracle files, Benchmark configuration, and contract files.
