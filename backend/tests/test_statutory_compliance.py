"""Tests for Aadhaar policy, incident handling, grievance SLAs and the register.

The Aadhaar tests carry the most weight here. Section 29(4) and the
Authentication Regulations carry criminal liability rather than a penalty, so
"we mask it in most places" is not a defence — the tests assert that the unmasked
path does not exist at all, not merely that it is not currently called.
"""
from datetime import datetime, timedelta, timezone

import pytest

from dpdp import aadhaar_policy, grievance, incident, statutes
from dpdp.aadhaar_policy import AadhaarStorageViolation
from dpdp.statutes import Exposure, Status
from validation import verhoeff_check_digit


AADHAAR = "23456789012" + verhoeff_check_digit("23456789012")


class TestAadhaarMasking:
    def test_masks_to_last_four(self):
        """UIDAI permits only the last four digits to be shown."""
        assert aadhaar_policy.mask(AADHAAR) == f"XXXX XXXX {AADHAAR[-4:]}"

    def test_masked_output_hides_the_first_eight(self):
        masked = aadhaar_policy.mask(AADHAAR)
        assert AADHAAR[:8] not in masked

    def test_handles_spaced_input(self):
        spaced = f"{AADHAAR[:4]} {AADHAAR[4:8]} {AADHAAR[8:]}"
        assert aadhaar_policy.mask(spaced) == aadhaar_policy.mask(AADHAAR)

    def test_malformed_value_is_fully_masked_not_echoed(self):
        """A malformed value may still be someone's identifier."""
        assert aadhaar_policy.mask("12345") == "XXXXX"

    def test_empty_stays_empty(self):
        assert aadhaar_policy.mask("") == ""
        assert aadhaar_policy.mask(None) == ""

    def test_pdf_generator_cannot_emit_an_unmasked_number(self):
        """The criminal exposure must not be one keyword argument away."""
        from pdf_generator import _mask_aadhaar
        for kwargs in ({}, {"full": True}, {"full": False}):
            out = _mask_aadhaar(AADHAAR, **kwargs)
            assert AADHAAR[:8] not in out, f"unmasked with {kwargs}"
            assert out.startswith("XXXX XXXX")


class TestAadhaarNonStorage:
    def test_strips_aadhaar_from_storable_profile(self):
        storable, withheld = aadhaar_policy.strip_for_storage(
            {"name": "Kamla", "aadhaar_number": AADHAAR})
        assert "aadhaar_number" not in storable
        assert withheld["aadhaar_number"] == AADHAAR
        assert storable["name"] == "Kamla"

    def test_keeps_last_four_for_recognition(self):
        storable, _ = aadhaar_policy.strip_for_storage({"aadhaar_number": AADHAAR})
        assert storable["aadhaar_number_last4"] == AADHAAR[-4:]

    def test_full_number_absent_from_storable(self):
        storable, _ = aadhaar_policy.strip_for_storage({"aadhaar_number": AADHAAR})
        assert AADHAAR not in str(storable)

    def test_handles_guardian_aadhaar_too(self):
        storable, withheld = aadhaar_policy.strip_for_storage(
            {"guardian_aadhaar": AADHAAR})
        assert "guardian_aadhaar" not in storable
        assert withheld["guardian_aadhaar"] == AADHAAR

    def test_malformed_value_is_discarded_entirely(self):
        """Storing a partial identifier is neither useful nor safe."""
        storable, _ = aadhaar_policy.strip_for_storage({"aadhaar_number": "12345"})
        assert "aadhaar_number" not in storable
        assert "aadhaar_number_last4" not in storable

    def test_profile_without_aadhaar_is_untouched(self):
        original = {"name": "Kamla", "district": "Sitapur"}
        storable, withheld = aadhaar_policy.strip_for_storage(original)
        assert storable == original and withheld == {}

    def test_detects_a_full_aadhaar(self):
        assert aadhaar_policy.contains_full_aadhaar({"aadhaar_number": AADHAAR})
        assert not aadhaar_policy.contains_full_aadhaar({"aadhaar_number": "123"})

    def test_assertion_blocks_a_storage_violation(self):
        with pytest.raises(AadhaarStorageViolation) as exc:
            aadhaar_policy.assert_no_stored_aadhaar({"aadhaar_number": AADHAAR})
        # The message must explain the obligation, not just fail.
        assert "Requesting Entity" in str(exc.value)

    def test_assertion_passes_on_a_stripped_profile(self):
        storable, _ = aadhaar_policy.strip_for_storage({"aadhaar_number": AADHAAR})
        aadhaar_policy.assert_no_stored_aadhaar(storable)   # must not raise

    def test_redact_for_display_masks(self):
        out = aadhaar_policy.redact_for_display({"aadhaar_number": AADHAAR})
        assert out["aadhaar_number"].startswith("XXXX XXXX")


class TestAadhaarFormFill:
    def test_uses_the_number_supplied_with_the_request(self):
        merged = aadhaar_policy.merge_for_form_fill(
            {"name": "Kamla", "aadhaar_number_last4": AADHAAR[-4:]},
            {"aadhaar_number": AADHAAR})
        assert merged["aadhaar_number"] == AADHAAR

    def test_falls_back_to_masked_when_not_supplied(self):
        """The cost of non-storage: the citizen writes it in by hand."""
        merged = aadhaar_policy.merge_for_form_fill(
            {"aadhaar_number_last4": AADHAAR[-4:]}, None)
        assert merged["aadhaar_number"] == f"XXXX XXXX {AADHAAR[-4:]}"

    def test_absent_entirely_when_nothing_is_known(self):
        merged = aadhaar_policy.merge_for_form_fill({"name": "Kamla"}, None)
        assert "aadhaar_number" not in merged


class TestGrievanceSLA:
    def test_deadlines_match_the_rule(self):
        """IT Rules 2021 rule 3(2): 24 hours to acknowledge, 15 days to resolve."""
        created = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        dl = grievance.deadlines_for(created)
        assert dl["acknowledge_by"] == created + timedelta(hours=24)
        assert dl["resolve_by"] == created + timedelta(days=15)

    def test_naive_datetime_is_treated_as_utc(self):
        dl = grievance.deadlines_for(datetime(2026, 1, 1, 10, 0))
        assert dl["acknowledge_by"].tzinfo is not None

    def test_officer_reports_when_unconfigured(self, monkeypatch):
        """A fake officer is worse than a visibly missing one."""
        monkeypatch.delenv("GRIEVANCE_OFFICER_NAME", raising=False)
        monkeypatch.delenv("GRIEVANCE_OFFICER_EMAIL", raising=False)
        info = grievance.officer()
        assert info["configured"] is False
        assert info["name"] is None
        assert "rule 3(2)" in info["warning"].lower()

    def test_officer_reports_when_configured(self, monkeypatch):
        monkeypatch.setenv("GRIEVANCE_OFFICER_NAME", "Officer Sharma")
        monkeypatch.setenv("GRIEVANCE_OFFICER_EMAIL", "grievance@example.gov.in")
        info = grievance.officer()
        assert info["configured"] is True and info["warning"] is None

    def test_officer_states_both_statutory_bases(self):
        bases = " ".join(grievance.officer()["statutory_basis"])
        assert "rule 3(2)" in bases and "DPDP" in bases


class TestIncidentPolicy:
    def test_cert_in_deadline_is_six_hours(self):
        assert incident.CERT_IN_DEADLINE_HOURS == 6

    def test_log_retention_is_180_days_in_india(self):
        policy = incident.log_policy()
        assert policy["retention_days"] == 180
        assert policy["residency_required"] == "India"

    def test_log_policy_is_honest_about_enforcement(self):
        """The app cannot guarantee where logs are shipped; it must not claim to."""
        assert "deployment" in incident.log_policy()["enforced_by"]

    def test_time_sync_names_the_indian_servers(self):
        sync = incident.log_policy()["time_sync_required"]
        assert "nic.in" in sync or "nplindia" in sync


class TestStatutoryRegister:
    def test_covers_the_major_instruments(self):
        names = " ".join(o.statute for o in statutes.OBLIGATIONS)
        for expected in ("Aadhaar Act 2016", "DPDP Act 2023", "CERT-In",
                         "RPwD Act 2016", "GIGW", "IT Act 2000"):
            assert expected in names, f"{expected} not in the register"

    @pytest.mark.parametrize("ob", statutes.OBLIGATIONS,
                             ids=lambda o: f"{o.statute}:{o.provision}")
    def test_entry_is_complete(self, ob):
        assert ob.requirement and ob.evidence
        # Anything not fully satisfied must say what would satisfy it.
        if ob.status in (Status.PARTIAL, Status.NON_COMPLIANT,
                         Status.NEEDS_LEGAL_INPUT):
            assert ob.remediation, f"{ob.provision} has no remediation"

    def test_no_unresolved_criminal_exposure(self):
        """The Aadhaar obligations are the reason this test exists."""
        unresolved = [o for o in statutes.OBLIGATIONS
                      if o.exposure == Exposure.CRIMINAL
                      and o.status not in (Status.COMPLIANT, Status.NOT_APPLICABLE)]
        assert not unresolved, [o.provision for o in unresolved]

    def test_outstanding_is_ordered_by_exposure(self):
        order = {Exposure.CRIMINAL: 0, Exposure.PENALTY: 1,
                 Exposure.DIRECTION: 2, Exposure.GUIDELINE: 3}
        seq = [order[o.exposure] for o in statutes.outstanding()]
        assert seq == sorted(seq)

    def test_summary_reports_counts(self):
        s = statutes.summary()
        assert s["total_obligations"] == len(statutes.OBLIGATIONS)
        assert sum(s["counts"].values()) == len(statutes.OBLIGATIONS)
        assert s["criminal_exposure_unresolved"] == []

    def test_register_is_honest_about_gaps(self):
        """A register grading everything COMPLIANT would be worthless."""
        assert statutes.outstanding(), "register claims no gaps at all"
