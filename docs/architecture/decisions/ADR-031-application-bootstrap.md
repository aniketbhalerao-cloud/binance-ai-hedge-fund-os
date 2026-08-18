# ADR-031: Application Bootstrap & Dry-Run Runtime Composition

**Status:** Accepted

## Context
By Sprint 18, 24 independent frameworks each exposed a `register_<framework>` function but none of them was permitted to import another — that isolation is what makes each framework independently testable. Nothing in the codebase, however, proved that all 24 could actually be wired together into one dependency-injection container: an unregistered dependency, a circular reference, or a typo in a service key would only surface the first time someone tried to run the whole system for real, at the worst possible moment. A composition root was needed — but building and retaining the real, long-lived runtime container was explicitly out of scope for this task; a live container would need to make real network/database/Redis connections and start real framework engines, which contradicts "prove the graph would wire" being a *safe*, repeatable, CI-friendly check.

## Decision
Implement a standalone `app/` package as the one sanctioned cross-framework import site, confined to 8 files (not the 14-module domain-framework blueprint, since there is exactly one implementation of a composition root):

`BootstrapContext → planner.plan → preflight.validate_service_keys → container_factory() → wiring.COMPONENT_REGISTRARS[id](container) → preflight.run → RuntimeSnapshot / LifecyclePlan`

Every bootstrap run obtains a **disposable** candidate container by calling `container_factory` — never by accepting one as a parameter — registers all 24 known components into it in deterministic topological order, and runs a real resolution pass against every declared service key before discarding the container; nothing is retained, cached, or returned live. A preflight report with any failed check is itself a failed bootstrap (`FAILED` status, zero artifacts), so a successful run is proof the *entire* declared graph resolves — not a partial credit. Because `strategies`, `backtesting`, `paper_trading`, and `market_data` itself all need a `MarketDataProvider` to resolve their managers, `market_data`'s registrar is bound via `functools.partial` to a `_DryRunMarketDataProvider` — a construction-only, `__slots__ = ()` stand-in that accepts and discards `on_data()`'s callback and fails closed on `connect`/`disconnect` — so the default dry run reaches `24/24` without ever touching a real exchange.

## Alternatives Considered
- **Build and retain the real, long-lived container in this task.** Rejected: that requires real network/database/Redis connections and starting real framework engines, which is unsafe to run in CI or as a routine preflight check. Deferred to a future live-runtime task; Task 38 only proves the graph *would* wire.
- **Skip `market_data`-dependent components in the default manifest, or leave their preflight checks failing.** Rejected in a later patch round: a `20/24` "mostly passing" default run is a weaker, less trustworthy signal than a real `24/24` pass, and silently tolerates a wiring gap instead of proving it closed. A deterministic, I/O-free dry-run provider closes the gap honestly instead.
- **Let `preflight.run` accept the full `Container` (registration capability included) instead of a narrow resolver.** Rejected: the public API of this task accepts no container instance anywhere; `preflight.run` was changed to take a restricted `Callable[[type], object]` so it structurally cannot register, reset, or otherwise mutate anything — only resolve.
- **Echo the offending id/key into `PlanningError`/`PreflightError` messages for easier debugging.** Rejected: a `ComponentManifest` is caller-supplied input and is not trusted to be safe to surface verbatim; every error is a fixed, generic string instead, verified with dedicated secret-marker tests.
- **Give `_DryRunMarketDataProvider` an `__init__` that stores the registered callback for later inspection.** Rejected: that is exactly the kind of shared mutable state a stateless dry-run stand-in must not have. `__slots__ = ()` makes retaining anything structurally impossible, not just a coding convention.

## Consequences
### Positive
- The full 24-framework object graph is proven to wire on every run, in CI, with zero real I/O and zero risk
- A caller-supplied, noncompliant `container_factory` cannot leak a live container back out through this task's own code — proven structurally, not just by convention
- Failures are safe by construction: no raw exception, credential, internal connection detail, stack trace, or caller-supplied manifest value ever reaches `BootstrapResult.errors`
- The one shared `_DryRunMarketDataProvider` instance is genuinely stateless and safe under concurrent/repeated use

### Negative
- `market_data`-dependent managers are only proven to *construct*, not to actually stream data — a live-runtime task must still supply and validate a real provider
- The dry-run provider is dead weight once a live-runtime task exists; it should be revisited then, not extended with more fake behavior in the meantime

## Safety Boundaries
The framework never: retains, returns, or leaks the disposable candidate container; mutates a container it did not create for that run; calls `.start()` on any Engine or `.compose()`/`.invoke()`/`.schedule()`/`.enqueue()` on any manager; triggers an Agent, executes a trade, or performs inference; resolves a constructor capable of I/O (only the explicit, proven-I/O-free `SAFE_SERVICE_KEYS` allowlist is ever resolved); makes a real network, database, or Redis connection; writes a file; spawns a thread or process; or sleeps. `config.settings.get_settings()` is the only external read anywhere in the pipeline — verified under `socket.socket`/`threading.Thread.start`/`multiprocessing.Process.start` monkeypatches configured to raise, with a full default dry run still completing successfully. Cross-framework imports are confined to `app/wiring.py` alone, verified by an AST-based boundary check across every other `app/` module.

## Related
- Task: Task 38 — Application Bootstrap & Dry-Run Runtime Composition (`docs/prompts/task-38.md`, `docs/reviews/task-38-review.md`)
- Commit: `397a706` — "Implement Task 38 Application Bootstrap and Dry-Run Composition"
- Tag: `v4.12-application-bootstrap`

## Note
`docs/architecture/roadmap-v2.md` still describes Task 38 under its earlier working title, "Feedback & Trade Journal Framework" (a `feedback/` package producing `JournalEntry`/`FeedbackRequest` objects) — that section was superseded by the Application Bootstrap & Dry-Run Runtime Composition concept actually implemented and is not updated by this ADR.
