"""Learning journal.

:class:`DefaultJournal` appends learned outcomes to an append-only
:class:`~learning.models.LearningHistory`. It is stateless — it returns a new
history and never mutates existing records, so the outcome timeline is immutable
and can never be rewritten.
"""

from __future__ import annotations

from learning.models import JournalEntry, LearningHistory, LearningOutcome

__all__ = ["DefaultJournal"]


class DefaultJournal:
    """Stateless, append-only outcome-recording service."""

    def record(
        self, history: LearningHistory, outcome: LearningOutcome
    ) -> LearningHistory:
        """Return a new history with ``outcome`` recorded as the next entry."""
        entry = JournalEntry(index=len(history.entries), outcome=outcome)
        return history.append(entry)
