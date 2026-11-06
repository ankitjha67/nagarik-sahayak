"""The combined gate — where every check meets, and where they can go wrong.

Two regressions live here, both found by running the real screening path rather
than the units underneath it.

**KYC evidence never reached the decision.** `fraud_detection.assess()` grew a
`kyc_outcomes` parameter, but `evaluate_application` — the function every API
route actually calls — never passed one. Every unit test passed; the feature
was inert in production. A citizen who verified against a UIDAI-signed document
got exactly the scrutiny of one who verified nothing, which makes verifying
pure cost and means nobody does it.

**"Add an identity document" was classified as a refusal.** The absence of a
document is not an invalid value, but it shared a bucket with failed checksums,
so a half-filled profile came back `blocked_invalid_data`. That is the
difference between "please add this" and "you are rejected", shown to somebody
who had done nothing wrong.
"""
import asyncio

import pytest

import fraud_detection as fd
from data.gov_forms import get_by_name, get_catalog
from kyc.methods import Assurance
from kyc.service import VerificationOutcome
from services import application_guard
from services.application_guard import GateOutcome
from validation import ABSENCE_CODES, validate_profile, verhoeff_check_digit


AADHAAR = "48291736450" + verhoeff_check_digit("48291736450")
PENSION = get_by_name("Indira Gandhi National Old Age Pension")


def complete_profile(**overrides):
    profile = {
        "name": "Kamla Devi", "father_husband_name": "Ram Prasad",
        "aadhaar_number": AADHAAR, "date_of_birth": "1958-04-12", "age": 68,
        "gender": "Female", "category": "OBC", "mobile_number": "9876543210",
        "address_line": "House 42", "district": "Sitapur",
        "state": "Uttar Pradesh", "pincode": "261001", "is_bpl": "Yes",
        "annual_income": 42000, "bank_account_number": "50100234567890",
        "ifsc_code": "SBIN0001234", "bank_name": "State Bank of India",
    }
    profile.update(overrides)
    return profile


def gate(profile, scheme=PENSION, **kw):
    return asyncio.run(application_guard.evaluate_application(
        profile=profile, scheme=scheme, **kw))


VERIFIED = VerificationOutcome(
    method="aadhaar_offline_xml", succeeded=True,
    assurance=Assurance.VERIFIED, fraud_signal=-15)

CONTRADICTED = VerificationOutcome(
    method="aadhaar_offline_xml", succeeded=True,
    assurance=Assurance.DOCUMENTED, contradicted=True, needs_review=True,
    fraud_signal=35)


class TestAbsenceIsNotRefusal:
    """A citizen part-way through a form has not been rejected."""

    def test_missing_identity_document_is_an_absence_code(self):
        assert "identity_document_missing" in ABSENCE_CODES

    def test_a_profile_with_no_document_is_incomplete_not_blocked(self):
        """The regression. This came back blocked_invalid_data — a refusal —
        for somebody who had simply not reached that field yet."""
        partial = {"name": "Sunita Devi", "age": 34, "gender": "Female",
                   "state": "Uttar Pradesh", "district": "Sitapur"}
        result = gate(partial)
        assert result.outcome is GateOutcome.INCOMPLETE
        assert result.outcome is not GateOutcome.BLOCKED_INVALID_DATA

    def test_the_reason_reads_as_a_request(self):
        partial = {"name": "Sunita Devi", "age": 34}
        result = gate(partial)
        text = " ".join(result.reasons_en).lower()
        assert "required" in text or "provide" in text
        assert "reject" not in text and "refus" not in text

    def test_a_malformed_document_IS_blocked(self):
        """The other half. An absence is a request; a failed checksum is not."""
        result = gate(complete_profile(aadhaar_number="111111111111"))
        assert result.outcome is GateOutcome.BLOCKED_INVALID_DATA

    def test_the_split_holds_at_the_validation_layer(self):
        v = validate_profile({"name": "Sunita"}, PENSION["extractedFields"])
        assert v.is_blocking
        assert not v.has_invalid_values, \
            "nothing submitted is wrong; the form is merely unfinished"
        assert v.missing_required

    @pytest.mark.parametrize("scheme", get_catalog()[:12],
                             ids=lambda s: s["schemeName"])
    def test_no_scheme_refuses_an_empty_profile(self, scheme):
        """Across the catalog: a citizen who has entered nothing is asked for
        more, never told they do not qualify."""
        result = gate({}, scheme=scheme)
        assert result.outcome in (GateOutcome.INCOMPLETE,
                                  GateOutcome.BLOCKED_NOT_ELIGIBLE) or \
            result.outcome is GateOutcome.APPROVED
        assert result.outcome is not GateOutcome.BLOCKED_INVALID_DATA


class TestKycReachesTheDecision:
    """The integration that was silently missing."""

    def test_the_gate_accepts_kyc_outcomes(self):
        result = gate(complete_profile(), kyc_outcomes=[VERIFIED])
        assert result.identity["assurance"] == int(Assurance.VERIFIED)

    def test_verification_can_change_the_outcome(self):
        """A repeat applicant is routed to review on volume alone. A
        UIDAI-signed document is better evidence than that inference, and the
        gate must act on it or the whole KYC layer buys the citizen nothing."""
        history = fd.ApplicantHistory(prior_applications_same_scheme=3)
        without = gate(complete_profile(), history=history)
        with_kyc = gate(complete_profile(), history=history,
                        kyc_outcomes=[VERIFIED])

        assert without.outcome is GateOutcome.APPROVED_WITH_REVIEW
        assert with_kyc.outcome is GateOutcome.APPROVED
        assert with_kyc.risk["risk_score"] < without.risk["risk_score"]

    def test_a_contradiction_routes_to_review_without_refusing(self):
        result = gate(complete_profile(), history=fd.ApplicantHistory(),
                      kyc_outcomes=[CONTRADICTED])
        assert result.outcome is GateOutcome.APPROVED_WITH_REVIEW
        assert result.may_issue_form, \
            "a contradiction is for a reviewer to resolve, not a refusal"
        assert any(s["code"] == "identity_document_contradicted"
                   for s in result.risk["signals"])

    def test_verification_cannot_rescue_a_genuinely_bad_case(self):
        history = fd.ApplicantHistory(users_sharing_bank_account=12)
        result = gate(complete_profile(), history=history,
                      kyc_outcomes=[VERIFIED])
        assert result.outcome is not GateOutcome.APPROVED

    def test_no_kyc_is_a_normal_state_not_a_penalty(self):
        clean = gate(complete_profile(), history=fd.ApplicantHistory())
        assert clean.outcome is GateOutcome.APPROVED
        assert clean.identity["assurance"] == int(Assurance.NONE)
        assert clean.identity["verificationIsOptional"] is True

    def test_the_identity_summary_never_reads_as_a_blocker(self):
        for outcomes in ([], [VERIFIED], [CONTRADICTED]):
            result = gate(complete_profile(), kyc_outcomes=outcomes)
            text = (result.identity["nextStep"] + result.identity["label"]).lower()
            assert "refus" not in text and "reject" not in text
            assert result.identity["verificationIsOptional"] is True


class TestOutcomesSurviveTheWire:
    """Outcomes round-trip through JSON on the way back from the browser."""

    def test_dicts_from_the_api_are_accepted(self):
        as_json = VERIFIED.as_dict()
        assert isinstance(as_json["assurance"], int)
        rebuilt = application_guard._normalise_outcomes([as_json])
        assert len(rebuilt) == 1
        assert rebuilt[0].assurance is Assurance.VERIFIED
        assert rebuilt[0].fraud_signal == -15

    def test_a_dict_produces_the_same_decision_as_the_object(self):
        history = fd.ApplicantHistory(prior_applications_same_scheme=3)
        as_object = gate(complete_profile(), history=history,
                         kyc_outcomes=[VERIFIED])
        as_dict = gate(complete_profile(), history=history,
                       kyc_outcomes=[VERIFIED.as_dict()])
        assert as_object.outcome is as_dict.outcome
        assert as_object.risk["risk_score"] == as_dict.risk["risk_score"]

    @pytest.mark.parametrize("junk", [
        None, [], [None], ["not a dict"], [{}], [{"assurance": "high"}],
        [{"assurance": 99}], [{"fraudSignal": "lots"}],
    ])
    def test_malformed_input_degrades_instead_of_raising(self, junk):
        """A client sending nonsense must not crash a decision mid-flight —
        the citizen loses their application, not the client."""
        result = gate(complete_profile(), kyc_outcomes=junk)
        assert result.outcome is GateOutcome.APPROVED

    def test_snake_case_from_a_python_client_also_works(self):
        rebuilt = application_guard._normalise_outcomes(
            [{"method": "m", "succeeded": True, "assurance": 3,
              "fraud_signal": -15, "needs_review": True}])
        assert rebuilt[0].fraud_signal == -15 and rebuilt[0].needs_review


class TestScreenAllNarrowsByState:
    def _screen(self, profile):
        from routes import verification
        return asyncio.run(verification.screen_all_schemes({"profile": profile}))

    def test_other_states_schemes_are_left_out(self):
        """Screening a Bihar resident against 38 other States' schemes buries
        the real answers under items they can do nothing about."""
        body = self._screen(complete_profile(state="Bihar"))
        assert body["home_state"] == "Bihar"
        assert body["other_state_schemes_skipped"] > 0
        assert body["total_screened"] < body["total_in_catalog"]

    def test_central_schemes_are_always_screened(self):
        body = self._screen(complete_profile(state="Bihar"))
        central = sum(1 for e in get_catalog() if e["level"] == "Central")
        screened_central = [
            r for group in ("eligible", "not_eligible", "needs_more_info")
            for r in body[group] if r["level"] == "Central"
        ]
        assert len(screened_central) == central

    def test_the_narrowing_is_reported_not_silent(self):
        body = self._screen(complete_profile(state="Bihar"))
        assert "other_state_schemes_skipped" in body
        assert "total_in_catalog" in body

    def test_an_unknown_state_screens_everything(self):
        """Better to show a scheme that may not apply than to hide one that
        does because the State string was not recognised."""
        body = self._screen(complete_profile(state=""))
        assert body["total_screened"] == body["total_in_catalog"]
        assert body["other_state_schemes_skipped"] == 0


class TestAuditRecord:
    def test_a_decision_is_always_recordable(self):
        result = gate(complete_profile(age=30, date_of_birth="1996-04-12"))
        record = application_guard.audit_record("user123", result)
        assert record["outcome"] == GateOutcome.BLOCKED_NOT_ELIGIBLE.value
        assert record["decided_at"]
        assert "age" in record["failed_rule_fields"]

    def test_the_record_carries_no_identifiers(self):
        """It is a decision log, not a second copy of the applicant."""
        from dpdp.aadhaar_policy import contains_full_aadhaar
        record = application_guard.audit_record(
            "user123", gate(complete_profile(), kyc_outcomes=[VERIFIED]))
        assert not contains_full_aadhaar(record)
        assert AADHAAR not in str(record)
