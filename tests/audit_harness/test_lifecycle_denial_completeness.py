"""Task 38.6 Phase A integrity correction, item 1: lifecycle denial
completeness.

Regression coverage for a real bug found and fixed in this pass: the
static walker's "don't re-explore a nested provider closure the outer
registrar already excluded" optimization (added to stop a different,
earlier double-processing bug) accidentally meant a provider that is
*registered but never resolved* by any of the 24 ``SAFE_SERVICE_KEYS``
roots (every framework's ``Engine``, registered alongside its
``Manager`` but never itself a required dependency) was never explored
at all -- silently dropping 19 ``Engine`` nodes and 19 lifecycle
methods from the audit (14 patched instead of the real 33). Fixed by
also reading every *registered* provider directly from one
representative container's registry (Requirement 1's "no container
reused across roots" invariant is unaffected -- this is one extra,
separate, throwaway container built solely to enumerate registrations,
never resolved from).

The two tests below assert against a fixed, hand-curated baseline
recorded at the time the fix landed -- not against a value the
production code under test derives for itself. Deriving "expected"
from ``discover_lifecycle_targets()`` or from ``run_trace()``'s own
``.engine.`` node set made the earlier version of this test circular:
if a future edit to discovery/tracing silently dropped a node, the
"expected" side would drop with it and the test would keep passing.
A baseline mismatch here means either a real regression, or a
deliberate, reviewed change that must update ``EXPECTED_*`` alongside
the production code.
"""

from __future__ import annotations

from audit_harness.run_audit import _load_classes
from audit_harness.runtime_denial import run_paper_only_denial_check
from audit_harness.trace import run_trace

#: Recorded at the time the lifecycle-completeness fix landed (14 -> 33
#: patched targets). Not a production allowlist -- a regression
#: baseline. A future *intentional* lifecycle change (new engine, new
#: lifecycle method name, framework removed) must update this set
#: deliberately, in the same change, with review.
EXPECTED_LIFECYCLE_TARGETS: frozenset[str] = frozenset(
    {
        "agents.engine.DefaultDecisionEngine.start",
        "backtesting.engine.DefaultBacktestEngine.start",
        "dashboard.composer.DefaultComposer.compose",
        "dashboard.engine.DefaultDashboardEngine.start",
        "execution.engine.DefaultExecutionEngine.start",
        "learning.engine.DefaultLearningEngine.start",
        "market_data.service.MarketDataPipelineService.start",
        "memory.engine.DefaultMemoryEngine.start",
        "model_gateway.engine.DefaultModelGatewayEngine.invoke",
        "model_gateway.engine.DefaultModelGatewayEngine.start",
        "model_gateway.manager.DefaultModelGatewayManager.invoke",
        "monitoring.engine.DefaultMonitoringEngine.start",
        "notification.engine.DefaultNotificationEngine.start",
        "optimization.engine.DefaultOptimizationEngine.start",
        "order_management.engine.DefaultOrderEngine.start",
        "paper_trading.engine.DefaultPaperTradingEngine.start",
        "performance.engine.DefaultPerformanceEngine.start",
        "portfolio.engine.DefaultPortfolioEngine.start",
        "positions.engine.DefaultPositionEngine.start",
        "reporting.engine.DefaultReportingEngine.start",
        "risk.engine.RiskEvaluationEngine.start",
        "scheduler.engine.DefaultSchedulerEngine.schedule",
        "scheduler.engine.DefaultSchedulerEngine.start",
        "scheduler.manager.DefaultSchedulerManager.schedule",
        "storage.engine.DefaultStorageEngine.start",
        "strategies.manager.StrategyExecutionManager.start",
        "trades.engine.DefaultTradeEngine.start",
        "workers.engine.DefaultWorkerEngine.enqueue",
        "workers.engine.DefaultWorkerEngine.start",
        "workers.manager.DefaultWorkerManager.enqueue",
        "workflows.engine.DefaultWorkflowEngine.compose",
        "workflows.engine.DefaultWorkflowEngine.start",
        "workflows.manager.DefaultWorkflowManager.compose",
    }
)

#: The 22 frameworks that register a `*.engine.*` class (the other two
#: wired frameworks, market_data and strategies, use a differently
#: named Service/Manager pattern, not "Engine", and are intentionally
#: absent from this list). Same non-circularity rationale as above.
EXPECTED_ENGINE_NODES: frozenset[str] = frozenset(
    {
        "agents.engine.DefaultDecisionEngine",
        "backtesting.engine.DefaultBacktestEngine",
        "dashboard.engine.DefaultDashboardEngine",
        "execution.engine.DefaultExecutionEngine",
        "learning.engine.DefaultLearningEngine",
        "memory.engine.DefaultMemoryEngine",
        "model_gateway.engine.DefaultModelGatewayEngine",
        "monitoring.engine.DefaultMonitoringEngine",
        "notification.engine.DefaultNotificationEngine",
        "optimization.engine.DefaultOptimizationEngine",
        "order_management.engine.DefaultOrderEngine",
        "paper_trading.engine.DefaultPaperTradingEngine",
        "performance.engine.DefaultPerformanceEngine",
        "portfolio.engine.DefaultPortfolioEngine",
        "positions.engine.DefaultPositionEngine",
        "reporting.engine.DefaultReportingEngine",
        "risk.engine.RiskEvaluationEngine",
        "scheduler.engine.DefaultSchedulerEngine",
        "storage.engine.DefaultStorageEngine",
        "trades.engine.DefaultTradeEngine",
        "workers.engine.DefaultWorkerEngine",
        "workflows.engine.DefaultWorkflowEngine",
    }
)


def test_patched_lifecycle_set_equals_independently_derived_set() -> None:
    trace = run_trace()
    classes, _unimportable = _load_classes([n.qualname for n in trace.nodes])

    result = run_paper_only_denial_check(classes)

    patched_qualnames = frozenset(result.lifecycle_methods_patched)
    assert patched_qualnames == EXPECTED_LIFECYCLE_TARGETS, (
        f"missing={sorted(EXPECTED_LIFECYCLE_TARGETS - patched_qualnames)} "
        f"extra={sorted(patched_qualnames - EXPECTED_LIFECYCLE_TARGETS)}"
    )


def test_every_wired_engine_class_is_present_in_the_node_collection() -> None:
    """Regression guard for the specific root cause: every one of the 22
    frameworks that register a `*.engine.*` class must appear in the
    traced node collection, not just the ones some sibling framework
    happens to also resolve."""
    trace = run_trace()
    engine_qualnames = frozenset(
        n.qualname for n in trace.nodes if ".engine." in n.qualname
    )
    assert engine_qualnames == EXPECTED_ENGINE_NODES, (
        f"missing={sorted(EXPECTED_ENGINE_NODES - engine_qualnames)} "
        f"extra={sorted(engine_qualnames - EXPECTED_ENGINE_NODES)}"
    )
