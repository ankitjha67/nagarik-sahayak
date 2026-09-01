"""Tests for validation, eligibility and fraud safeguards.

Two things are being protected here, and the second matters as much as the first:

  * fraud is caught, and
  * legitimate poor applicants are NOT caught.

A welfare system that blocks a destitute widow because her declared income is
zero has failed more seriously than one that lets a questionable file reach a
human reviewer. The false-positive tests below encode that.

No real Aadhaar number appears in this file — valid ones are generated from the
checksum function itself.
"""
import pytest

from eligibility_engine import RuleOutcome, Verdict, evaluate_rule, evaluate_scheme
from fraud_detection import (
    ApplicantHistory, Decision, assess,
    check_internal_consistency, check_scheme_specific,
)
from data.gov_forms import get_by_name
from validation import (
    Severity, compute_age, parse_date, validate_aadhaar, validate_bank_account,
    validate_date_of_birth, validate_ifsc, validate_income, validate_mobile,
    validate_name, validate_pan, validate_pincode, validate_profile,
    verhoeff_check_digit, verhoeff_is_valid,
)


def valid_aadhaar(prefix11="23456789012"):
    """A structurally valid but entirely synthetic Aadhaar number."""
    return prefix11 + verhoeff_check_digit(prefix11)


def complete_pension_profile(**overrides):
    """A fully answered application for the old-age pension.

    The guard reports a half-filled form as INCOMPLETE rather than refusing it,
    so tests that exercise approval or refusal must supply every required field;
    otherwise they only ever exercise the incomplete path.
    """
    profile = {
        "name": "Kamla Devi",
        "father_husband_name": "Ram Prasad",
        "aadhaar_number": valid_aadhaar(),
        "date_of_birth": "1958-04-12",
        "age": 68,
        "gender": "Female",
        "category": "OBC",
        "mobile_number": "9876543210",
        "address_line": "House 42, Ward 3, Rampur",
        "district": "Sitapur",
        "state": "Uttar Pradesh",
        "pincode": "261001",
        "is_bpl": "Yes",
        "annual_income": 42000,
        "bank_account_number": "50100234567890",
        "ifsc_code": "SBIN0001234",
        "bank_name": "State Bank of India",
    }
    profile.update(overrides)
    return profile


class TestVerhoeff:
    def test_known_vectors(self):
        # 2363 is the canonical worked example for the Verhoeff algorithm.
        assert verhoeff_is_valid("2363")
        assert verhoeff_check_digit("12345") == "1"

    def test_generated_numbers_validate(self):
        for payload in ["12345678901", "98765432109", "23456789012", "55555555555"]:
            assert verhoeff_is_valid(payload + verhoeff_check_digit(payload))

    def test_detects_single_digit_error(self):
        num = valid_aadhaar()
        for i in range(len(num)):
            corrupted = num[:i] + str((int(num[i]) + 1) % 10) + num[i + 1:]
            assert not verhoeff_is_valid(corrupted), f"missed corruption at {i}"

    def test_detects_adjacent_transposition(self):
        """Transposing neighbouring digits is the most common typo."""
        num = valid_aadhaar()
        caught = 0
        for i in range(len(num) - 1):
            if num[i] == num[i + 1]:
                continue
            swapped = num[:i] + num[i + 1] + num[i] + num[i + 2:]
            if not verhoeff_is_valid(swapped):
                caught += 1
        assert caught > 0

    def test_rejects_non_digits(self):
        assert not verhoeff_is_valid("abcd")
        assert not verhoeff_is_valid("")


class TestAadhaarValidation:
    def test_accepts_valid(self):
        assert not validate_aadhaar(valid_aadhaar()).is_blocking

    def test_accepts_spaced_format(self):
        a = valid_aadhaar()
        spaced = f"{a[:4]} {a[4:8]} {a[8:]}"
        assert not validate_aadhaar(spaced).is_blocking

    @pytest.mark.parametrize("bad,code", [
        ("", "aadhaar_missing"),
        ("12345", "aadhaar_length"),
        ("012345678901", "aadhaar_prefix"),
        ("123456789012", "aadhaar_prefix"),
        ("999999999999", "aadhaar_placeholder"),
    ])
    def test_rejects_invalid(self, bad, code):
        r = validate_aadhaar(bad)
        assert r.is_blocking
        assert r.errors[0].code == code

    def test_rejects_bad_checksum(self):
        a = valid_aadhaar()
        bad = a[:11] + str((int(a[11]) + 1) % 10)
        r = validate_aadhaar(bad)
        assert r.is_blocking and r.errors[0].code == "aadhaar_checksum"

    def test_findings_are_bilingual(self):
        for f in validate_aadhaar("12345").findings:
            assert f.message_en and f.message_hi


class TestOtherFieldValidation:
    @pytest.mark.parametrize("value", ["9876543210", "+91 9876543210", "919876543210"])
    def test_mobile_accepts_valid(self, value):
        assert not validate_mobile(value).is_blocking

    @pytest.mark.parametrize("value", ["1234567890", "5876543210", "98765", ""])
    def test_mobile_rejects_invalid(self, value):
        assert validate_mobile(value).is_blocking

    @pytest.mark.parametrize("value", ["SBIN0001234", "hdfc0000123"])
    def test_ifsc_accepts_valid(self, value):
        assert not validate_ifsc(value).is_blocking

    @pytest.mark.parametrize("value", ["SBIN1001234", "SBI0001234", "SBIN000123", ""])
    def test_ifsc_rejects_invalid(self, value):
        assert validate_ifsc(value).is_blocking

    def test_bank_account_bounds(self):
        assert not validate_bank_account("50100234567890").is_blocking
        assert validate_bank_account("123").is_blocking
        assert validate_bank_account("1" * 25).is_blocking

    def test_pincode(self):
        assert not validate_pincode("261001").is_blocking
        assert validate_pincode("061001").is_blocking
        assert not validate_pincode("").is_blocking  # optional

    def test_pan(self):
        assert not validate_pan("ABCDE1234F").is_blocking
        assert validate_pan("ABCD1234F").is_blocking

    def test_dob_rejects_future_and_impossible(self):
        assert validate_date_of_birth("2099-01-01").is_blocking
        assert validate_date_of_birth("1800-01-01").is_blocking
        assert validate_date_of_birth("not-a-date").is_blocking
        assert not validate_date_of_birth("1958-04-12").is_blocking

    @pytest.mark.parametrize("text", ["1958-04-12", "12/04/1958", "12-04-1958", "12.04.1958"])
    def test_parses_indian_date_formats(self, text):
        d = parse_date(text)
        assert d is not None and d.year == 1958

    def test_name_validation(self):
        assert not validate_name("Kamla Devi").is_blocking
        assert not validate_name("कमला देवी").is_blocking
        assert validate_name("").is_blocking
        assert validate_name("123").is_blocking

    def test_income_negative_blocks_but_zero_does_not(self):
        assert validate_income(-500).is_blocking
        zero = validate_income(0)
        assert not zero.is_blocking and len(zero.warnings) == 1


class TestProfileValidation:
    def test_missing_required_field_blocks(self):
        fields = [{"profileKey": "name", "labelEnglish": "Name",
                   "labelHindi": "नाम", "required": True, "type": "text"}]
        r = validate_profile({}, fields)
        assert r.is_blocking
        assert r.errors[0].code == "required_missing"

    def test_optional_field_absent_is_fine(self):
        fields = [{"profileKey": "email", "labelEnglish": "Email",
                   "required": False, "type": "email"}]
        assert not validate_profile({}, fields).is_blocking

    def test_validates_sensitive_keys_not_declared_by_form(self):
        """A bad Aadhaar is invalid whether or not this form asked for it."""
        r = validate_profile({"aadhaar_number": "111111111111"}, [])
        assert r.is_blocking


class TestEligibilityEngine:
    def test_numeric_rules(self):
        rule = {"field": "age", "op": ">=", "value": 60}
        assert evaluate_rule({"age": 65}, rule).outcome == RuleOutcome.PASS
        assert evaluate_rule({"age": 45}, rule).outcome == RuleOutcome.FAIL
        assert evaluate_rule({}, rule).outcome == RuleOutcome.UNKNOWN

    def test_age_is_derived_from_dob(self):
        """An applicant who gave a birth date has supplied their age."""
        r = evaluate_rule({"date_of_birth": "1958-04-12"},
                          {"field": "age", "op": ">=", "value": 60})
        assert r.outcome == RuleOutcome.PASS

    def test_equality_is_case_insensitive(self):
        rule = {"field": "is_bpl", "op": "==", "value": "Yes"}
        assert evaluate_rule({"is_bpl": "yes"}, rule).outcome == RuleOutcome.PASS
        assert evaluate_rule({"is_bpl": "No"}, rule).outcome == RuleOutcome.FAIL

    def test_parses_values_with_units_and_symbols(self):
        r = evaluate_rule({"annual_income": "₹1,20,000"},
                          {"field": "annual_income", "op": "<=", "value": 250000})
        assert r.outcome == RuleOutcome.PASS

    def test_eligible_applicant(self):
        scheme = get_by_name("Indira Gandhi National Old Age Pension")
        res = evaluate_scheme({"age": 70, "is_bpl": "Yes"}, scheme)
        assert res.verdict == Verdict.ELIGIBLE and res.is_eligible

    def test_ineligible_applicant_gets_reason(self):
        scheme = get_by_name("Indira Gandhi National Old Age Pension")
        res = evaluate_scheme({"age": 30, "is_bpl": "Yes"}, scheme)
        assert res.verdict == Verdict.NOT_ELIGIBLE
        assert res.failed[0].field == "age"
        assert "60" in res.failed[0].message_en
        assert res.failed[0].message_hi     # refusals must be translated

    def test_incomplete_is_distinct_from_ineligible(self):
        """Not having answered yet must never read as 'you do not qualify'."""
        scheme = get_by_name("Indira Gandhi National Old Age Pension")
        res = evaluate_scheme({}, scheme)
        assert res.verdict == Verdict.INCOMPLETE
        assert not res.is_eligible and not res.failed

    def test_scheme_without_rules_is_eligible(self):
        assert evaluate_scheme({}, {"schemeName": "X",
                                    "eligibilityCriteria": {"rules": []}}).is_eligible


class TestFraudInternalConsistency:
    def test_age_contradicting_dob(self):
        s = check_internal_consistency({"age": 62, "date_of_birth": "1992-06-01"})
        assert any(x.code == "age_dob_mismatch" for x in s)

    def test_small_age_gap_tolerated(self):
        """Age is often recorded a year out; that is not fraud."""
        from datetime import date
        born = date(date.today().year - 60, 1, 1).isoformat()
        s = check_internal_consistency({"age": 61, "date_of_birth": born})
        assert not any(x.code == "age_dob_mismatch" for x in s)

    def test_zero_income_with_land(self):
        s = check_internal_consistency({"annual_income": 0, "land_holding_acres": 25})
        assert any(x.code == "zero_income_with_land" for x in s)

    def test_landless_zero_income_not_flagged(self):
        s = check_internal_consistency({"annual_income": 0, "land_holding_acres": 0})
        assert not any(x.code == "zero_income_with_land" for x in s)

    def test_taxpayer_claiming_poverty(self):
        s = check_internal_consistency({"is_income_tax_payer": "Yes",
                                        "annual_income": 90000})
        assert any(x.code == "taxpayer_low_income" for x in s)

    def test_bpl_with_high_income(self):
        s = check_internal_consistency({"is_bpl": "Yes", "annual_income": 1200000})
        assert any(x.code == "bpl_high_income" for x in s)


class TestFraudSchemeSpecific:
    def test_male_applying_for_widow_pension(self):
        scheme = get_by_name("Widow and Destitute Women Pension (Haryana)")
        s = check_scheme_specific({"gender": "Male"}, scheme)
        assert any(x.code == "gender_scheme_mismatch" for x in s)

    def test_female_applicant_not_flagged(self):
        scheme = get_by_name("Widow and Destitute Women Pension (Haryana)")
        s = check_scheme_specific({"gender": "Female", "marital_status": "Widowed"},
                                  scheme)
        assert not s

    def test_overage_child_for_sukanya(self):
        scheme = get_by_name("Sukanya Samriddhi Yojana")
        s = check_scheme_specific({"girl_child_age": 14}, scheme)
        assert any(x.code == "child_age_ineligible" for x in s)

    def test_no_scheme_context_yields_nothing(self):
        assert check_scheme_specific({"gender": "Male"}, None) == []


class TestFraudCrossApplicant:
    def test_shared_aadhaar(self):
        r = assess({}, None, ApplicantHistory(users_sharing_aadhaar=4))
        assert any(s.code == "aadhaar_shared_across_users" for s in r.signals)

    def test_collection_account_escalates_alone(self):
        """Benefit diversion must escalate without needing a second signal."""
        r = assess({}, None, ApplicantHistory(users_sharing_bank_account=12))
        assert r.decision == Decision.ESCALATE

    def test_two_sharing_an_account_is_not_flagged(self):
        """Spouses sharing an account is normal and must not be penalised."""
        r = assess({}, None, ApplicantHistory(users_sharing_bank_account=2))
        assert r.decision == Decision.ALLOW

    def test_duplicate_and_household_claims(self):
        assert any(s.code == "duplicate_scheme_application" for s in
                   assess({}, None, ApplicantHistory(prior_applications_same_scheme=2)).signals)
        assert any(s.code == "household_duplicate_claim" for s in
                   assess({}, None, ApplicantHistory(household_claims_same_scheme=3)).signals)

    def test_bulk_filing(self):
        r = assess({}, None, ApplicantHistory(applications_last_24h=45))
        assert any(s.code.startswith("velocity") for s in r.signals)

    def test_no_history_means_no_cross_signals(self):
        assert assess({"name": "A"}, None, None).decision == Decision.ALLOW


class TestNoFalsePositivesOnLegitimateApplicants:
    """The poorest, most eligible citizens must sail through untouched."""

    def test_destitute_widow_is_clean(self):
        scheme = get_by_name("Widow and Destitute Women Pension (Haryana)")
        profile = {
            "name": "Phoolwati", "gender": "Female", "marital_status": "Widowed",
            "age": 54, "date_of_birth": "1972-03-15", "annual_income": 0,
            "aadhaar_number": valid_aadhaar(), "mobile_number": "9876543210",
        }
        assert assess(profile, scheme, ApplicantHistory()).decision == Decision.ALLOW
        assert not validate_profile(profile, None).is_blocking

    def test_landless_labourer_is_clean(self):
        profile = {"name": "Ramu", "annual_income": 18000,
                   "land_holding_acres": 0, "is_bpl": "Yes",
                   "aadhaar_number": valid_aadhaar("34567890123")}
        assert assess(profile, None, ApplicantHistory()).decision == Decision.ALLOW

    def test_family_sharing_one_phone_is_clean(self):
        """One handset per household is the norm in rural India."""
        r = assess({"name": "Sita"}, None, ApplicantHistory(users_sharing_mobile=6))
        assert r.decision == Decision.ALLOW

    def test_csc_operator_volume_does_not_escalate_alone(self):
        """Common Service Centre staff legitimately file for many citizens."""
        r = assess({"name": "Sita"}, None,
                   ApplicantHistory(users_sharing_mobile=12, applications_last_24h=9))
        assert r.decision != Decision.ESCALATE

    def test_smallholder_with_modest_income_is_clean(self):
        profile = {"name": "Gopal", "annual_income": 60000,
                   "land_holding_acres": 1.5}
        assert assess(profile, None, ApplicantHistory()).decision == Decision.ALLOW


class TestApplicationGuard:
    @pytest.mark.asyncio
    async def test_legitimate_application_approved(self):
        from services.application_guard import GateOutcome, evaluate_application
        scheme = get_by_name("Indira Gandhi National Old Age Pension")
        g = await evaluate_application(
            profile=complete_pension_profile(),
            scheme=scheme, history=ApplicantHistory(),
        )
        assert g.outcome == GateOutcome.APPROVED and g.may_issue_form

    @pytest.mark.asyncio
    async def test_invalid_data_blocks_form_issue(self):
        from services.application_guard import GateOutcome, evaluate_application
        scheme = get_by_name("Indira Gandhi National Old Age Pension")
        g = await evaluate_application(
            profile=complete_pension_profile(aadhaar_number="111111111111"),
            scheme=scheme, history=ApplicantHistory(),
        )
        assert g.outcome == GateOutcome.BLOCKED_INVALID_DATA
        assert not g.may_issue_form and g.reasons_en

    @pytest.mark.asyncio
    async def test_ineligible_blocks_with_translated_reason(self):
        from services.application_guard import GateOutcome, evaluate_application
        scheme = get_by_name("Indira Gandhi National Old Age Pension")
        g = await evaluate_application(
            profile=complete_pension_profile(age=25, date_of_birth="2001-04-12"),
            scheme=scheme, history=ApplicantHistory(),
        )
        assert g.outcome == GateOutcome.BLOCKED_NOT_ELIGIBLE
        assert g.reasons_en and g.reasons_hi

    @pytest.mark.asyncio
    async def test_fraud_signal_issues_form_but_flags_it(self):
        """Suspicion must not deny the form — only route it for checking."""
        from services.application_guard import GateOutcome, evaluate_application
        scheme = get_by_name("Indira Gandhi National Old Age Pension")
        g = await evaluate_application(
            profile=complete_pension_profile(),
            scheme=scheme,
            history=ApplicantHistory(users_sharing_bank_account=12),
        )
        assert g.outcome == GateOutcome.APPROVED_WITH_REVIEW
        assert g.may_issue_form and g.risk["requires_human_review"]

    @pytest.mark.asyncio
    async def test_audit_record_captures_decision(self):
        from services.application_guard import audit_record, evaluate_application
        scheme = get_by_name("Indira Gandhi National Old Age Pension")
        g = await evaluate_application(
            profile=complete_pension_profile(age=25, date_of_birth="2001-04-12"),
            scheme=scheme, history=ApplicantHistory(),
        )
        rec = audit_record("user-1", g)
        assert rec["outcome"] == "blocked_not_eligible"
        assert "age" in rec["failed_rule_fields"]
        assert rec["decided_at"]

    @pytest.mark.asyncio
    async def test_audit_record_excludes_identifiers(self):
        """The decision log must not become a second copy of personal data."""
        from services.application_guard import audit_record, evaluate_application
        scheme = get_by_name("Indira Gandhi National Old Age Pension")
        profile = complete_pension_profile()
        aadhaar = profile["aadhaar_number"]
        g = await evaluate_application(
            profile=profile, scheme=scheme, history=ApplicantHistory(),
        )
        blob = str(audit_record("user-1", g))
        assert aadhaar not in blob and "9876543210" not in blob
