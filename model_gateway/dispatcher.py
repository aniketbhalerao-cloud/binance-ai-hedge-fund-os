"""Model Gateway dispatcher — deterministic provider routing.

:class:`DefaultDispatcher` turns the dispatch-eligible entries in a planned
batch into deterministic :class:`~model_gateway.models.ModelInvocationRequest`
domain objects by selecting one :class:`~model_gateway.models.ModelProviderProfile`
candidate per entry from ``context.parameters.provider_profiles``. It is
stateless and fully deterministic: it never calls an AI provider, performs
model inference, imports a provider SDK, or accesses a vector database — it
only *selects* a declared, credential-free routing candidate and constructs
an immutable request describing the desired inference.

Routing precedence — the **exact** ordered dimensions required by
``docs/prompts/task-36.md`` ("Deterministic Provider Routing"):

1. Explicit provider/model identity, when specified by the invocation
   request — a matching candidate is preferred, but only if it is still
   eligible under dimensions 2-3 ("must never override mandatory
   capability or context requirements").
2. Capability requirements — a candidate that fails a required capability
   is **suppressed** (removed from consideration entirely), per
   ``docs/prompts/task-36.md`` "Provider Routing Rules".
3. Context requirements — likewise suppressed on failure.
4. Routing policy priority (``ModelProviderProfile.routing_policy_priority``,
   higher preferred) — kept distinct from dimension 5 per spec.
5. Provider/model priority (``ModelProviderProfile.priority``, higher
   preferred).
6. Cost/routing policy (``ModelProviderProfile.cost``, lower preferred,
   compared as ``Decimal``).
7. Availability metadata (``ModelProviderProfile.available``, declared
   domain input — available candidates are preferred over unavailable
   ones). This is a *ranking* dimension, not an elimination filter: unlike
   capability/context (2-3), the spec never states an unavailable candidate
   is "suppressed" — only that availability is precedence dimension 7, so
   it is applied strictly after priority (5) and cost (6) have already
   decided, exactly as ordered. The framework never queries live
   availability; it only reads the declared value.
8. Stable provider identifier — lexical comparison.
9. Stable model identifier — lexical comparison.

Final tie-break ("Routing Tie-Breaking"): if two or more candidates are
still tied after dimension 9, the stable immutable ``routing_id`` decides.
If neither tied candidate has one, "the candidate is invalid and must not
be selected" — the entry is suppressed (no request produced) rather than
resolved arbitrarily.

No dimension here depends on the current time, randomness, dict/hash
iteration order, or any live provider/network/process state — every
comparison is over immutable domain values supplied on the context.
"""

from __future__ import annotations

from model_gateway.context import ModelGatewayContext
from model_gateway.exceptions import DispatchError
from model_gateway.models import (
    ModelInvocationBatch,
    ModelInvocationEntry,
    ModelInvocationRequest,
    ModelProviderProfile,
)

__all__ = ["DefaultDispatcher"]

#: Sorts a missing ``routing_id`` last among otherwise-tied candidates; see
#: ``_select`` for how a genuinely unresolvable tie (both top candidates
#: lacking one) is then rejected outright rather than picked arbitrarily.
_NO_ROUTING_ID = "￿"

# Index into the sort-key tuple up to and including dimension 9
# (provider_id, model_id) — used to detect a tie *before* the final
# routing_id dimension.
_THROUGH_DIMENSION_9 = 7


class DefaultDispatcher:
    """Stateless, deterministic provider routing and request generation."""

    def dispatch(
        self, batch: ModelInvocationBatch, context: ModelGatewayContext
    ) -> tuple[ModelInvocationRequest, ...]:
        """Return one model invocation request per routable, dispatch-eligible entry.

        An entry that is dispatch-eligible but has no eligible or
        resolvable provider candidate produces no request (suppressed).

        Raises:
            DispatchError: If an unexpected failure occurs.
        """
        try:
            profiles = context.parameters.provider_profiles
            requests = []
            for entry in batch.entries:
                if not entry.dispatch:
                    continue
                candidate = _select(entry, profiles)
                if candidate is None:
                    continue
                requests.append(
                    ModelInvocationRequest(
                        subject=entry.source.name,
                        source=entry.source.source,
                        provider_id=candidate.provider_id,
                        model_id=candidate.model_id,
                        capabilities=entry.source.required_capabilities,
                        context_requirements=entry.source.required_context,
                        routing_policy_priority=candidate.routing_policy_priority,
                        priority=candidate.priority,
                        cost=candidate.cost,
                        available=candidate.available,
                        detail=entry.detail,
                    )
                )
            return tuple(requests)
        except DispatchError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise DispatchError(str(exc)) from exc


def _eligible(
    entry: ModelInvocationEntry, profiles: tuple[ModelProviderProfile, ...]
) -> list[ModelProviderProfile]:
    """Precedence dimensions 2-3: capability/context suppression only.

    Availability is intentionally *not* filtered here — per the spec it is
    precedence dimension 7, applied during ranking in ``_sort_key``, not an
    elimination filter like capability/context are.
    """
    required_capabilities = set(entry.source.required_capabilities)
    required_context = set(entry.source.required_context)
    return [
        p
        for p in profiles
        if required_capabilities <= set(p.capabilities)
        and required_context <= set(p.context_support)
    ]


def _sort_key(
    candidate: ModelProviderProfile, entry: ModelInvocationEntry
) -> tuple[int, object, object, object, int, str, str, str]:
    """The exact 9-dimension precedence (1, 4-9; 2-3 are pre-filtered) plus
    the final ``routing_id`` tie-break, as one ascending-preferred tuple."""
    source = entry.source
    explicit_match = bool(source.preferred_provider_id) and (
        candidate.provider_id == source.preferred_provider_id
        and (
            not source.preferred_model_id
            or candidate.model_id == source.preferred_model_id
        )
    )
    return (
        0 if explicit_match else 1,  # 1. explicit provider/model identity
        -candidate.routing_policy_priority,  # 4. routing policy priority
        -candidate.priority,  # 5. provider/model priority
        candidate.cost,  # 6. cost/routing policy
        0 if candidate.available else 1,  # 7. availability metadata
        candidate.provider_id,  # 8. stable provider identifier
        candidate.model_id,  # 9. stable model identifier
        candidate.routing_id or _NO_ROUTING_ID,  # final tie-break
    )


def _select(
    entry: ModelInvocationEntry, profiles: tuple[ModelProviderProfile, ...]
) -> ModelProviderProfile | None:
    eligible = _eligible(entry, profiles)
    if not eligible:
        return None

    eligible.sort(key=lambda p: _sort_key(p, entry))
    best = eligible[0]
    if len(eligible) > 1:
        second = eligible[1]
        # Tied through dimension 9 (provider_id, model_id), and neither has
        # a stable routing_id to decide by: unresolvable, per "Routing
        # Tie-Breaking" — the candidate must not be selected.
        if (
            _sort_key(best, entry)[:_THROUGH_DIMENSION_9]
            == _sort_key(second, entry)[:_THROUGH_DIMENSION_9]
            and not best.routing_id
            and not second.routing_id
        ):
            return None
    return best
