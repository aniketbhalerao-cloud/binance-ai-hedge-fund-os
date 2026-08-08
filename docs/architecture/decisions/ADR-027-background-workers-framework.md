# ADR-027: Background Workers Framework

**Status:** Accepted

## Context
A dedicated background-work planning layer is required to transform standardized outputs (storage requests, report objects, notification requests, monitoring reports, and schedule requests) into immutable worker-request domain objects without executing, running, or triggering anything.

## Decision
Implement a standalone `workers/` package mirroring the Scheduler Framework's pipeline:

`Context → Collector → Planner → Dispatcher → Metrics → Result`

The framework publishes worker events, maintains immutable registry-owned state, and never executes a job, starts a timer, creates a cron job, spawns a thread, opens a socket, or performs a network call.

## Consequences
### Positive
- Consistent framework architecture
- Deterministic and testable
- Easily extensible through dependency injection

### Negative
- Actual job execution/triggering remains outside this framework.
