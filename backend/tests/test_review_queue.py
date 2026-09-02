"""Tests for the reviewer queue.

The queue is the half of fraud detection that makes it legitimate: the screen
never refuses anyone on suspicion, it defers to a person. These tests cover the
rules that keep that deferral honest — decisions are attributable, refusals
carry a reason, closed cases are not silently overwritten, and no case can be
starved out of the queue.
"""
import pytest

from services.review_queue import (
    CaseStatus, TransitionError, prioritise, priority_of, summarise,
    validate_transition,
)


def case(risk=0, status="pending", created="2026-01-01T00:00:00", signals=None,
         scheme="Scheme"):
    return {
        "riskScore": risk, "status": status, "createdAt": created,
        "signals": signals or [], "schemeName": scheme,
    }


class TestTransitions:
    def test_pending_can_be_decided(self):
        validate_transition("pending", "approved")
        validate_transition("pending", "rejected")

    @pytest.mark.parametrize("closed", ["approved", "rejected"])
    def test_closed_case_cannot_be_redecided(self, closed):
        """Re-deciding would overwrite who decided and why."""
        with pytest.raises(TransitionError) as e:
            validate_transition(closed, "approved")
        assert "already" in str(e.value).lower()

    def test_unknown_status_rejected(self):
        with pytest.raises(TransitionError):
            validate_transition("pending", "maybe")
        with pytest.raises(TransitionError):
            validate_transition("banana", "approved")

    def test_cannot_transition_to_pending(self):
        """Reopening is a separate, explicitly recorded act."""
        with pytest.raises(TransitionError):
            validate_transition("pending", "pending")


class TestPrioritisation:
    def test_highest_risk_first(self):
        ordered = prioritise([case(risk=10), case(risk=90), case(risk=50)])
        assert [c["riskScore"] for c in ordered] == [90, 50, 10]

    def test_equal_risk_oldest_first(self):
        """A case must not be starved by newer arrivals at the same risk."""
        ordered = prioritise([
            case(risk=50, created="2026-03-01T00:00:00"),
            case(risk=50, created="2026-01-01T00:00:00"),
            case(risk=50, created="2026-02-01T00:00:00"),
        ])
        assert [c["createdAt"][:7] for c in ordered] == \
            ["2026-01", "2026-02", "2026-03"]

    def test_high_risk_beats_old_low_risk(self):
        ordered = prioritise([
            case(risk=5, created="2020-01-01T00:00:00"),
            case(risk=80, created="2026-06-01T00:00:00"),
        ])
        assert ordered[0]["riskScore"] == 80

    def test_missing_fields_do_not_crash(self):
        assert len(prioritise([{}, {"riskScore": 5}])) == 2
        assert priority_of({}) == (0, "")

    def test_empty_queue(self):
        assert prioritise([]) == []


class TestSummary:
    def test_counts_by_status(self):
        s = summarise([
            case(status="pending"), case(status="pending"),
            case(status="approved"), case(status="rejected"),
        ])
        assert s["pending"] == 2 and s["approved"] == 1 and s["rejected"] == 1
        assert s["total"] == 4

    def test_high_risk_counts_only_pending(self):
        """A resolved high-risk case is not outstanding work."""
        s = summarise([
            case(risk=80, status="pending"),
            case(risk=90, status="approved"),
            case(risk=20, status="pending"),
        ])
        assert s["high_risk_pending"] == 1

    def test_top_signals_from_pending_only(self):
        s = summarise([
            case(status="pending", signals=[{"code": "bank_account_collection_point"}]),
            case(status="pending", signals=[{"code": "bank_account_collection_point"},
                                            {"code": "velocity_high"}]),
            case(status="approved", signals=[{"code": "should_not_count"}]),
        ])
        assert s["top_signals"]["bank_account_collection_point"] == 2
        assert "should_not_count" not in s["top_signals"]

    def test_handles_malformed_signals(self):
        s = summarise([case(status="pending", signals=["plain_string", {}, None])])
        assert isinstance(s["top_signals"], dict)

    def test_empty(self):
        s = summarise([])
        assert s["pending"] == 0 and s["total"] == 0 and s["top_signals"] == {}


class TestQueueContract:
    """Properties the queue must hold for the deferral promise to be real."""

    def test_status_values_are_stable(self):
        # These strings are persisted and appear in API responses; changing one
        # silently orphans existing rows.
        assert {s.value for s in CaseStatus} == {"pending", "approved", "rejected"}

    def test_only_flagged_applications_are_enqueued(self):
        """A clean application must never create reviewer workload."""
        import asyncio
        from types import SimpleNamespace

        clean = SimpleNamespace(
            risk={"requires_human_review": False, "risk_score": 0, "signals": []},
            scheme="Any", outcome=SimpleNamespace(value="approved"),
        )
        # Returns before touching the database, so this runs without one.
        from services.review_queue import enqueue
        assert asyncio.run(enqueue("user-1", clean)) is None
