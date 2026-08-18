# Sprint 17 – Task 37 Review

## Task
Workflow Orchestration Framework

## Objective
Implement a standalone Workflow Orchestration Framework that consumes declarative `WorkflowDefinition` objects, validates each definition's *independent* dependency graph, deterministically orders workflows and their steps into an immutable `WorkflowPlan`, and produces deterministic `WorkflowRequest` handoff-intent objects only — never executing a step, triggering an Agent, or calling into Scheduler, Workers, or the Model Provider Gateway.

## Deliverables
- `workflows/` package (14 modules: `__init__.py`, `state.py`, `models.py`, `context.py`, `interfaces.py`, `exceptions.py`, `events.py`, `collector.py`, `planner.py`, `dispatcher.py`, `metrics.py`, `registry.py`, `manager.py`, `engine.py`)
- Dependency injection via `register_workflows`
- Thread-safe registry and manager
- Event-driven architecture
- Deterministic two-level ordering (workflow level, then step level) via a genuine Kahn's-algorithm topological sort
- Unit tests: `tests/test_workflows.py`
- Integration tests: `tests/test_workflow_flow.py`
- Fixtures: `tests/workflow_fakes.py`

## Verification
- Workflow tests (unit + integration): 50/50 passed
- Full suite: 741/741 passed
- Targeted Ruff (`workflows/`): clean
- Targeted mypy (`workflows/`): 14 DI typing errors matching the existing baseline

## Acceptance Criteria
- Deterministic workflow request generation
- Independent workflow dependency graphs — no cross-workflow dependency references
- Deterministic multi-workflow ordering (workflow priority, then lexical workflow id)
- Deterministic topological step ordering within each workflow (step priority, then lexical step id)
- Workflow priority never influences step ordering, and vice versa
- Duplicate step id / missing dependency / self-dependency / cyclic dependency / cross-workflow dependency rejection
- Invalid handoff-target rejection (only `agents`, `model_gateway`, `scheduler`, `workers` are valid)
- Immutable `WorkflowPlan` / `WorkflowRequest`
- Registry-owned state, dependency injection, event-driven architecture
- No step execution, no Agent triggering, no calls into `SchedulerManager`, `WorkerManager`, or `ModelGatewayManager`
- No network calls, no database/file writes
- No modification of any previous framework

## Architecture Summary

The Workflow Orchestration Framework mirrors the established Storage/Scheduler/Workers/Memory/Model-Gateway pipeline, adapted for two independent levels of deterministic ordering.

Pipeline:

```
WorkflowContext
        │
        ▼
Collector
        │
        ▼
Planner  (workflow-level ordering, then per-workflow step-level ordering)
        │
        ▼
Dispatcher  (produces WorkflowRequest handoff-intent objects)
        │
        ▼
Metrics
        │
        ▼
WorkflowResult
```

`WorkflowPlan` is declarative only: it describes a resolved order and intended handoff targets (`agents`, `model_gateway`, `scheduler`, `workers`) and is never itself executed by anything in this framework.

The framework remains:

- deterministic
- immutable
- event-driven
- exchange-independent
- dependency-injected
- registry-owned

## Determinism and Safety Boundaries

Ordering is resolved at two strictly independent levels, verified directly in `workflows/planner.py`:

- **Workflow level** — across the `WorkflowDefinition` objects in one `WorkflowBatch`: ordered by workflow priority (higher first), then stable workflow identifier (lexical ascending). `_plan()` computes this ordering key from `workflow_priority`/`workflow_id` only.
- **Step level** — within one `WorkflowDefinition`, independently of every other: a genuine Kahn's-algorithm topological sort (`_topological_order()`) with a deterministic ready-heap keyed `(-step.priority, step_id)` — never `sorted(steps)`. Among simultaneously-ready steps: step priority (higher first), then stable step identifier (lexical ascending).

Workflow priority is read only inside `_plan()`'s workflow-level sort key (`workflows/planner.py:89`, `key=lambda d: (-d.workflow_priority, d.workflow_id)`); it is never passed into, or read by, `_topological_order()`. Step priority is read only inside `_topological_order()`'s heap key (`workflows/planner.py:152`, `(-steps_by_id[step_id].priority, step_id)`); it never influences workflow-level ordering. `_topological_order()` receives a single `WorkflowDefinition` and has no parameter through which a workflow priority could reach it — the two priority values are structurally incapable of crossing levels.

Every `WorkflowDefinition`'s dependency graph is validated and resolved independently: duplicate step ids, missing dependencies, cross-workflow dependency references, self-dependencies, and cycles are each rejected with `PlanningError` before any partial `WorkflowPlan` is produced, and a failure in one definition never affects another definition in the same batch. `WorkflowPlanEntry.dependencies` is canonicalized to lexical-ascending order, so equivalent graphs with differently-ordered dependency declarations produce identical plan entries.

The framework never: executes a workflow step, triggers an Agent, calls `ModelGatewayManager.invoke()`, `SchedulerManager.schedule()`, or `WorkerManager.enqueue()`, executes a trade, performs inference, makes a network request, spawns a thread or process, sleeps, or writes a file or database. `tests/test_workflow_flow.py` enforces this with an AST-based boundary check (`ast.Import`/`Name`/`Attribute` nodes only — a docstring mention of `SchedulerManager.schedule()` is not a false positive) confirming `workflows/collector.py`, `planner.py`, `dispatcher.py`, `manager.py`, and `engine.py` never import or reference `scheduler`, `workers`, `agents`, or `model_gateway` as executable code.

## Verification Results

Workflows package import:

PASS

Workflow tests (`tests/test_workflows.py` + `tests/test_workflow_flow.py`):

50 / 50 Passed

Entire repository:

741 / 741 Passed

Targeted Ruff (`workflows/`):

All checks passed — the framework's one `(str, Enum)` class (`WorkflowResultStatus`) already carries the same `# noqa: UP042` the sibling frameworks use.

Targeted mypy (`workflows/`):

14 errors — all `Container` DI-typing (`attr-defined` / `type-abstract`) findings, identical in shape and count to the documented baseline shared by every sibling framework's `__init__.py`.

Full-repo baseline (pre-existing, unrelated to Task 37):

- `ruff check .`: 75 pre-existing `UP042` findings across other frameworks.
- `mypy .`: 1 pre-existing `adapters/binance/adapter.py` duplicate-module-path error that halts whole-repo mypy before it reaches package-scoped checks.

## Audit Conclusion

The Task 37 implementation was audited against `docs/prompts/task-37.md` and the established Storage/Scheduler/Workers/Memory/Model-Gateway architecture. Workflow-level and step-level ordering are confirmed structurally independent — workflow priority is never read by the step-level Kahn's-algorithm sort, and step priority is never read by the workflow-level sort — so the critical audit condition ("workflow priority never affects step ordering") holds by construction, not merely by test coincidence. Each `WorkflowDefinition`'s dependency graph is validated as a genuinely independent, real topological sort (never `sorted(steps)`), matching the spec's explicit prohibition on cross-workflow dependency joins.

## Commit and Release Tag

- Commit: `f162c26` — "Implement Task 37 Workflow Orchestration Framework"
- Tag: `v4.11-workflow-orchestration`

## Conclusion

Task 37 completed successfully with no regressions and follows the architectural pattern established by Tasks 27–36.
