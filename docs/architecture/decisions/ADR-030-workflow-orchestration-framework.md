# ADR-030: Workflow Orchestration Framework

**Status:** Accepted

## Context
The system needed a way to declare multi-step workflows — each with its own internal dependency graph — and deterministically resolve both which workflow runs first and, within each workflow, which step runs first, without the orchestration layer itself ever executing a step, triggering an Agent, or calling into Scheduler, Workers, or the Model Provider Gateway. A single, unqualified "priority" concept was not enough: a workflow-level priority (which whole workflow goes first) and a step-level priority (which step inside one workflow goes first) are conceptually different values that must never be allowed to influence each other, or workflow ordering and step ordering would become inseparable and unpredictable once more than one workflow was in flight.

## Decision
Implement a standalone `workflows/` package following the established framework pipeline:

`Context → Collector → Planner → Dispatcher → Metrics → Result`

Ordering is resolved at two strictly independent levels. **Workflow level**: across the `WorkflowDefinition` objects in one `WorkflowBatch`, ordered by workflow priority (higher first), then stable workflow identifier (lexical ascending). **Step level**: within one `WorkflowDefinition`, independently of every other, using a genuine Kahn's-algorithm topological sort with a deterministic ready-heap — never `sorted(steps)` — keyed by step priority (higher first), then stable step identifier (lexical ascending). Each `WorkflowDefinition` owns an independent dependency graph; a dependency may reference a step only within the same definition, and a cross-workflow dependency reference is rejected the same way as a missing one. `WorkflowPlan`/`WorkflowRequest` are immutable, declarative domain objects — the framework only validates, orders, and plans; it never executes anything.

## Alternatives Considered
- **A single unified `priority` field used at both workflow and step level.** Rejected: the spec requires workflow priority to never be used to order steps inside a definition, and vice versa; collapsing them into one field would make that separation impossible to enforce or verify.
- **`sorted(steps)` by priority alone, ignoring the dependency graph.** Rejected: this is not a topological sort — it would happily place a dependent step before the step it depends on whenever priority disagreed with the graph. A real Kahn's-algorithm sort with a priority-ordered ready-queue was required so dependency correctness and deterministic tie-breaking hold simultaneously.
- **Allow a dependency to reference a step in another `WorkflowDefinition` within the same batch.** Rejected: this would join two definitions' graphs together, making each workflow's validation and ordering depend on every other workflow in the batch — directly against the requirement that a validation failure in one definition must never affect another.
- **Let the Planner call the four handoff-target frameworks (`agents`, `model_gateway`, `scheduler`, `workers`) directly to validate a step's target is reachable.** Rejected: validation is limited to checking the handoff-target string against the four supported domain values; no framework's manager or engine method is ever called from within `workflows/`.

## Consequences
### Positive
- Consistent framework architecture, matching every sibling framework's pipeline
- Workflow ordering and step ordering are each independently deterministic and testable, including under multiple simultaneous workflows
- Immutable plan/request domain, safe to log, cache, or diff
- Cross-workflow dependency joins are structurally impossible, not just discouraged

### Negative
- Actually running a workflow — executing a step, triggering an Agent, or handing off to Scheduler/Workers/Model Provider Gateway — remains outside this framework; a future execution layer is required to act on a `WorkflowRequest`.
- Every `WorkflowDefinition`'s graph must be revalidated on every composition; there is no cross-run graph cache (a deliberate consequence of never retaining execution state here).

## Safety Boundaries
The framework never: executes a workflow step, triggers an Agent, calls `ModelGatewayManager.invoke()`, `SchedulerManager.schedule()`, or `WorkerManager.enqueue()`, executes a trade, performs inference, trains a model, makes a network request, spawns a thread or process, sleeps, writes a file or database, or mutates any other framework's state — including agent, learning, optimization, strategy, or portfolio state directly. An AST-based boundary check (real `Import`/`Name`/`Attribute` nodes, not source substrings) confirms the collector, planner, dispatcher, manager, and engine never import or reference `scheduler`, `workers`, `agents`, or `model_gateway` as executable code, even though their docstrings mention those frameworks' method names in prose.

## Related
- Task: Task 37 — Workflow Orchestration Framework (`docs/prompts/task-37.md`, `docs/reviews/task-37-review.md`)
- Commit: `f162c26` — "Implement Task 37 Workflow Orchestration Framework"
- Tag: `v4.11-workflow-orchestration`
