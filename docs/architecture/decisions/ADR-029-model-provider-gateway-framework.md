# ADR-029: Model Provider Gateway Framework

**Status:** Accepted

## Context
The system needed a standardized way to turn the running system's already-produced outputs (agent decisions, memory records, learning records, optimization plans) into model invocation *requests*, and to choose which declared provider/model candidate each request should target — without the framework core ever calling an AI provider, importing a provider SDK, performing inference, computing an embedding, or accessing a vector database. Provider/model selection also needed to be fully reproducible under test, since a non-deterministic dispatcher would make every downstream framework that consumes its output (Agents, Learning, Optimization) unreproducible in turn.

## Decision
Implement a standalone `model_gateway/` package following the established framework pipeline:

`Context → Collector → Planner → Dispatcher → Metrics → Result`

The Dispatcher resolves provider/model candidates using a fixed, ordered precedence evaluated entirely from immutable domain input: explicit provider/model identity (still subject to mandatory requirements), capability requirements, context requirements, routing-policy priority, provider/model priority, cost/routing policy (`Decimal`), availability metadata (declared input, never live/external state), then stable lexical tie-breaking on provider identifier and model identifier. `ModelProviderProfile` is treated as an immutable routing candidate; `ModelInvocationRequest` is an immutable domain object describing intent only. The framework publishes model-gateway events, maintains immutable registry-owned state, and never invokes external AI, embedding, vector-database, or network infrastructure.

## Alternatives Considered
- **Let each consuming framework (Agents, Learning, Optimization) pick its own provider/model directly.** Rejected: routing logic would be duplicated and drift across frameworks, and none of them would gain a single deterministic, testable seam for cost/availability policy changes.
- **Route by first-match / insertion order over the candidate collection.** Rejected: the spec explicitly forbids selecting a candidate solely because it appears first in a collection; all routing collections are normalized into a stable ordering before selection so the outcome never depends on how a caller happened to list its candidates.
- **Perform a live provider health check as part of routing.** Rejected: routing must be reproducible under test and must never depend on network state or external service response; availability is supplied as declared domain input instead.
- **Let the gateway actually call the chosen provider once routed.** Rejected out of scope for this framework — an invocation *request* is the framework's entire output; a future adapter layer is responsible for turning a request into a real provider call.

## Consequences
### Positive
- Consistent framework architecture, matching every sibling framework's pipeline
- Provider/model routing is deterministic and testable — identical input always produces an identical routing decision
- Immutable model-invocation domain, safe to log, cache, or diff
- New routing policies (cost, priority, capability) plug in without changing the framework (Open/Closed)

### Negative
- Actual provider invocation, inference, embedding computation, and vector-database access remain outside this framework — a future adapter is required to act on a `ModelInvocationRequest`.
- Availability metadata must be kept fresh by an external process; the gateway itself never re-checks it.

## Safety Boundaries
The framework never: calls an AI provider, imports a provider SDK, performs model inference, computes an embedding, accesses a vector database, makes a network or API call, performs provider discovery or a live health check, handles or stores an API key, writes to a database or file, spawns a thread or process, sleeps, or directly mutates agent, learning, optimization, strategy, or portfolio state. No secret value may appear in a model, context, event, log, metric, registry entry, or request object — provider profiles are metadata only, and any future secret-management integration must occur through an external adapter without altering this deterministic core.

## Related
- Task: Task 36 — Model Provider Gateway Framework (`docs/prompts/task-36.md`, `docs/reviews/task-36-review.md`)
- Commit: `f2001ca` — "Implement Task 36 Model Provider Gateway Framework"
- Tag: `v4.10-model-provider-gateway`
