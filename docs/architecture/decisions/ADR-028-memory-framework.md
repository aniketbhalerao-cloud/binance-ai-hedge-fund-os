# ADR-028: Memory Framework

**Status:** Accepted

## Context
A dedicated memory layer is required to transform standardized outputs from agents, learning, reporting, and storage into immutable memory-request domain objects supporting Working, Episodic, and Semantic scopes without directly invoking AI providers, embeddings, vector databases, external networks, databases, or files.

## Decision
Implement a standalone `memory/` package following the established framework pipeline:

`Context → Collector → Planner → Dispatcher → Metrics → Result`

The framework publishes memory events, maintains immutable registry-owned state, and never invokes external AI, embedding, vector database, network, database, or file infrastructure.

## Consequences
### Positive
- Consistent framework architecture
- Deterministic and testable
- Immutable memory domain
- Easily extensible through dependency injection

### Negative
- Actual persistence, embedding, retrieval infrastructure, and AI integration remain outside this framework.
