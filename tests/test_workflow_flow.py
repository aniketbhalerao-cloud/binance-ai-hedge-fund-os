"""Integration tests for the Workflow Orchestration Framework via the DI container.

Wires the workflow engine into a container and runs the compose-loop input
by input over declarative workflow definitions. The Registry owns the
running record across calls. No network, no sleeps, no randomness, no model
training, and no direct calls into Scheduler, Workers, Agents, or Model
Provider Gateway anywhere.
"""

from __future__ import annotations

import ast
import inspect
import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.workflow_fakes import (
    make_context,
    make_definition,
    make_dependency,
    make_step,
)
from workflows import (
    DefaultWorkflowEngine,
    WorkflowCompleted,
    WorkflowRegistry,
    WorkflowResultStatus,
    register_workflows,
)

#: The four handoff-target frameworks' package names — an executable
#: ``import`` of any of these (as opposed to a docstring *mention*) would be
#: a boundary violation.
_FORBIDDEN_MODULES = {"scheduler", "workers", "agents", "model_gateway"}

#: Manager/engine class names the framework may only ever mention in prose
#: (docstrings), never reference as executable code.
_FORBIDDEN_IDENTIFIERS = {
    "SchedulerManager", "SchedulerEngine",
    "WorkerManager", "WorkerEngine",
    "AgentManager", "AgentEngine",
    "ModelGatewayManager", "ModelGatewayEngine",
}


def _collect_identifiers(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Return ``(imported_top_level_modules, referenced_names)`` from ``tree``.

    Only *executable* references count: comments are stripped by the
    tokenizer before parsing, and a docstring is a string ``Constant``
    node — never a ``Name`` or ``Attribute`` node — so both are naturally
    excluded without any special-casing.
    """
    modules: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return modules, names


class WorkflowIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        c = ServiceContainer()
        c.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_workflows(c)
        return c

    async def test_compose_loop_produces_requests(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultWorkflowEngine)
        registry = c.resolve(WorkflowRegistry)
        bus = c.resolve(EventBus)
        done = FakeSubscriber()
        bus.subscribe(WorkflowCompleted, done.handle)

        result = await engine.compose(make_context(workflow_id="wf1"))

        self.assertEqual(result.status, WorkflowResultStatus.SUCCESS)
        assert result.metrics is not None
        self.assertTrue(result.requests)
        self.assertEqual(registry.get("wf1").step_count, 2)
        self.assertEqual(len(done.received), 1)

    async def test_record_accumulates_across_inputs(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultWorkflowEngine)
        registry = c.resolve(WorkflowRegistry)
        await engine.compose(make_context(workflow_id="wf1"))
        await engine.compose(
            make_context(
                workflow_id="wf1",
                definitions=(make_definition("w2", steps=(make_step("solo"),)),),
            )
        )
        self.assertEqual(registry.get("wf1").step_count, 3)

    async def test_sessions_isolated(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultWorkflowEngine)
        registry = c.resolve(WorkflowRegistry)
        await engine.compose(make_context(workflow_id="a"))
        await engine.compose(make_context(workflow_id="b"))
        self.assertEqual(len(registry.list()), 2)

    async def test_end_to_end_multi_workflow_ordering_through_full_pipeline(
        self,
    ) -> None:
        c = self._container()
        engine = c.resolve(DefaultWorkflowEngine)

        w1 = make_definition(
            "w1",
            workflow_priority="1",
            steps=(
                make_step("fetch", "5", handoff_target="scheduler"),
                make_step("train", "1", handoff_target="workers"),
            ),
            dependencies=(make_dependency("train", "fetch"),),
        )
        w2 = make_definition(
            "w2",
            workflow_priority="9",
            steps=(make_step("decide", "0", handoff_target="agents"),),
        )
        result = await engine.compose(
            make_context(workflow_id="g1", definitions=(w1, w2))
        )

        self.assertEqual(result.status, WorkflowResultStatus.SUCCESS)
        self.assertEqual(len(result.requests), 3)
        # w2 (priority 9) resolves entirely before w1 (priority 1); within
        # w1, "fetch" resolves before its dependent "train".
        self.assertEqual(
            [r.subject for r in result.requests], ["decide", "fetch", "train"]
        )
        self.assertEqual(
            [r.handoff_target for r in result.requests],
            ["agents", "scheduler", "workers"],
        )

    async def test_no_direct_calls_into_other_framework_managers(self) -> None:
        """AST-based boundary check: no executable import of, or executable
        ``Name``/``Attribute`` reference to, another framework's module or
        manager/engine class. ``workflows.dispatcher``'s own docstring
        *mentions* ``SchedulerManager.schedule()`` etc. in prose — proving
        this check tolerates that mention (a string ``Constant``, not a
        ``Name``/``Attribute`` node) rather than false-positiving on it."""
        import workflows.dispatcher
        import workflows.manager
        import workflows.planner

        for module in (workflows.dispatcher, workflows.planner, workflows.manager):
            tree = ast.parse(inspect.getsource(module))
            modules, names = _collect_identifiers(tree)
            self.assertTrue(_FORBIDDEN_MODULES.isdisjoint(modules))
            self.assertTrue(_FORBIDDEN_IDENTIFIERS.isdisjoint(names))

    async def test_ast_boundary_check_ignores_docstring_mentions(self) -> None:
        """The helper itself must not false-positive on a forbidden name or
        module that appears only inside a docstring, not as executable code."""
        source = (
            '"""Mentions SchedulerManager.schedule(), WorkerManager.enqueue(), '
            'and model_gateway only in prose, never as real code."""\n'
            "from __future__ import annotations\n"
            "x = 1\n"
        )
        modules, names = _collect_identifiers(ast.parse(source))
        self.assertTrue(_FORBIDDEN_MODULES.isdisjoint(modules))
        self.assertTrue(_FORBIDDEN_IDENTIFIERS.isdisjoint(names))


if __name__ == "__main__":
    unittest.main()
