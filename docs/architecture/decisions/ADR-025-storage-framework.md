# ADR-025: Storage Framework

**Status:** Accepted

## Context
A dedicated storage layer is required to transform standardized outputs into immutable storage-request domain objects without persistence or external I/O.

## Decision
Implement a standalone `storage/` package using the pipeline:

`Context → Collector → Serializer → Persistence Planner → Metrics → Result`

The framework publishes storage events, maintains immutable registry-owned state, and never connects to databases, executes SQL, writes files, uploads objects, or accesses cloud storage.

## Consequences
### Positive
- Consistent framework architecture
- Deterministic and testable
- Easily extensible through dependency injection

### Negative
- External persistence/storage remains outside this framework.
