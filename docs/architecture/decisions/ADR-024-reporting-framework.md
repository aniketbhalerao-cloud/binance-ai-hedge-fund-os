# ADR-024: Reporting Framework

**Status:** Accepted

## Context
A dedicated reporting layer is required to transform standardized outputs into immutable reporting domain objects without persistence or external delivery.

## Decision
Implement a standalone `reporting/` package using the pipeline:

`Context → Collector → Builder → Exporter → Metrics → Result`

The framework publishes reporting events, maintains immutable registry-owned state, and never performs file generation, network communication, or external delivery.

## Consequences
### Positive
- Consistent framework architecture
- Deterministic and testable
- Easily extensible through dependency injection

### Negative
- External persistence/export remains outside this framework.
