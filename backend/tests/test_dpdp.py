"""Tests for the DPDP Act 2023 compliance engine.

The properties under test are the ones a regulator or a citizen would actually
rely on:

  * personal data is detected accurately — and *not* over-detected, because a
    scanner that cries wolf gets switched off and then protects nobody;
  * every field the application stores is declared with a purpose and a
    retention period;
  * obligations are checked per row, and the finding names the section;
  * redaction genuinely removes the value before it leaves the process.

No real Aadhaar appears here; valid ones are generated from the checksum.
"""
import re
from datetime import datetime, timedelta, timezone

import pytest

from dpdp import registry, retention
from dpdp.classifier import (
    PIICategory, Sensitivity, detect_in_object, detect_in_text,
    highest_sensitivity, redact_object, redact_text,
)
from dpdp.engine import Severity, check_row, merge, scan_payload, scan_source
from dpdp.registry import LawfulBasis, Purpose
from validation import verhoeff_check_digit


def synthetic_aadhaar(prefix11="23456789012"):
    return prefix11 + verhoeff_check_digit(prefix11)


AADHAAR = synthetic_aadhaar()


class TestPIIDetection:
    def test_detects_valid_aadhaar(self):
        found = detect_in_text(f"applicant aadhaar is {AADHAAR}")
        assert any(d.category == PIICategory.AADHAAR for d in found)

    def test_ignores_twelve_digits_that_fail_the_checksum(self):
        """Precision guard: bank refs and timestamps are also 12 digits."""
        bad = AADHAAR[:11] + str((int(AADHAAR[11]) + 1) % 10)
        found = detect_in_text(f"reference number {bad}")
        assert not any(d.category == PIICategory.AADHAAR for d in found)

    def test_detects_spaced_aadhaar(self):
        spaced = f"{AADHAAR[:4]} {AADHAAR[4:8]} {AADHAAR[8:]}"
        assert any(d.category == PIICategory.AADHAAR
                   for d in detect_in_text(f"UID {spaced}"))

    @pytest.mark.parametrize("text,category", [
        ("PAN ABCDE1234F on file", PIICategory.PAN),
        ("branch code SBIN0001234", PIICategory.IFSC),
        ("call me on 9876543210", PIICategory.MOBILE),
        ("write to kamla@example.com", PIICategory.EMAIL),
    ])
    def test_detects_other_identifiers(self, text, category):
        assert any(d.category == category for d in detect_in_text(text))

    def test_bank_account_needs_a_cue_word(self):
        """Without a cue, any long number would match — too noisy to be useful."""
        assert not any(d.category == PIICategory.BANK_ACCOUNT
                       for d in detect_in_text("order 50100234567890 shipped"))
        assert any(d.category == PIICategory.BANK_ACCOUNT
                   for d in detect_in_text("account no 50100234567890"))

    def test_clean_text_produces_nothing(self):
        assert detect_in_text("The scheme provides housing assistance.") == []
        assert detect_in_text("") == []

    def test_preview_never_contains_the_value(self):
        for d in detect_in_text(f"aadhaar {AADHAAR}"):
            assert AADHAAR not in d.value_preview

    def test_detects_by_field_name_in_objects(self):
        found = detect_in_object({"annual_income": 42000, "district": "Sitapur"})
        cats = {d.category for d in found}
        assert PIICategory.FINANCIAL in cats and PIICategory.ADDRESS in cats

    def test_walks_nested_structures(self):
        found = detect_in_object({"applications": [{"profile": {"aadhaar_number": AADHAAR}}]})
        assert any(d.category == PIICategory.AADHAAR for d in found)

    def test_highest_sensitivity(self):
        found = detect_in_object({"district": "Sitapur", "aadhaar_number": AADHAAR})
        assert highest_sensitivity(found) == Sensitivity.CRITICAL
        assert highest_sensitivity([]) is None


class TestRedaction:
    def test_removes_identifiers_from_text(self):
        out = redact_text(f"aadhaar {AADHAAR} phone 9876543210 pan ABCDE1234F")
        assert AADHAAR not in out and "9876543210" not in out and "ABCDE1234F" not in out
        assert "[AADHAAR_REDACTED]" in out

    def test_preserves_non_personal_text(self):
        assert redact_text("Eligible for housing assistance.") == \
            "Eligible for housing assistance."

    def test_redacts_objects_by_field(self):
        out = redact_object({"name": "Kamla", "aadhaar_number": AADHAAR,
                             "scheme": "PM-KISAN"})
        assert AADHAAR not in str(out)
        assert out["scheme"] == "PM-KISAN"       # non-personal survives

    def test_redacts_nested_and_lists(self):
        out = redact_object({"users": [{"aadhaar_number": AADHAAR}]})
        assert AADHAAR not in str(out)

    def test_survives_deep_nesting(self):
        deep = current = {}
        for _ in range(30):
            current["next"] = {}
            current = current["next"]
        current["aadhaar_number"] = AADHAAR
        assert "TRUNCATED" in str(redact_object(deep))

    def test_handles_non_string_values(self):
        out = redact_object({"count": 5, "flag": True, "nothing": None})
        assert out == {"count": 5, "flag": True, "nothing": None}


class TestRegistry:
    def test_every_catalog_field_is_declared(self):
        """A collected field with no registry entry has no declared purpose."""
        from data.gov_forms import all_profile_keys
        undeclared = sorted(set(all_profile_keys()) - set(registry.BY_FIELD))
        assert not undeclared, f"undeclared personal data fields: {undeclared}"

    @pytest.mark.parametrize("record", registry.REGISTRY, ids=lambda r: r.field)
    def test_record_is_complete(self, record):
        assert record.purposes, f"{record.field} serves no declared purpose"
        assert record.retention_days > 0
        assert isinstance(record.basis, LawfulBasis)

    def test_sensitive_identifiers_are_critical(self):
        for field in ("aadhaar_number", "bank_account_number"):
            assert registry.BY_FIELD[field].sensitivity == Sensitivity.CRITICAL

    def test_child_fields_are_marked(self):
        for field in ("girl_child_name", "girl_child_dob", "girl_child_age"):
            assert registry.BY_FIELD[field].child_data, f"{field} must be s9 data"

    def test_means_test_fields_are_decisional(self):
        """s8(3) accuracy duty attaches to anything deciding an entitlement."""
        for field in ("annual_income", "age", "is_bpl", "category"):
            assert registry.BY_FIELD[field].decisional

    def test_undeclared_fields_detected(self):
        assert registry.undeclared_fields({"name": "K", "mystery": "x"}) == ["mystery"]

    def test_internal_keys_are_not_flagged(self):
        assert registry.undeclared_fields({"_complete": True, "notifications": {}}) == []

    def test_unknown_identifier_suffix_is_protected(self):
        """Better to over-protect an unenumerated *_aadhaar than to leak it."""
        assert registry.category_for_field("spouse_aadhaar") == PIICategory.AADHAAR

    def test_notice_covers_every_purpose_with_fields(self):
        summary = registry.notice_summary()
        covered = {s["purpose"] for s in summary}
        for purpose in Purpose:
            if registry.fields_for_purpose(purpose):
                assert purpose.value in covered


class TestRowCompliance:
    def test_clean_row_with_consent_passes(self):
        report = check_row(
            {"name": "Kamla", "district": "Sitapur"},
            created_at=datetime.now(timezone.utc),
            consented_purposes={p.value for p in Purpose},
        )
        assert report.compliant

    def test_missing_consent_record_is_high(self):
        report = check_row({"name": "Kamla"}, consented_purposes=None)
        codes = {f.code for f in report.findings}
        assert "no_consent_record" in codes
        assert any(f.section == "s6(1)" for f in report.findings)

    def test_purpose_without_consent(self):
        report = check_row({"annual_income": 42000},
                           consented_purposes={Purpose.FORM_COMPLETION.value})
        assert "purpose_without_consent" in {f.code for f in report.findings}

    def test_child_data_without_parental_consent(self):
        report = check_row(
            {"girl_child_name": "Anu"},
            consented_purposes={p.value for p in Purpose},
            has_parental_consent=False,
        )
        finding = next(f for f in report.findings
                       if f.code == "child_data_without_parental_consent")
        assert finding.section == "s9(1)" and finding.severity == Severity.HIGH

    def test_child_data_with_parental_consent_passes(self):
        report = check_row(
            {"girl_child_name": "Anu"},
            consented_purposes={p.value for p in Purpose},
            has_parental_consent=True,
        )
        assert "child_data_without_parental_consent" not in {f.code for f in report.findings}

    def test_placeholder_in_decisional_field(self):
        """s8(3): a decision must not rest on 'N/A'."""
        report = check_row({"annual_income": "N/A"},
                           consented_purposes={p.value for p in Purpose})
        assert "decisional_field_placeholder" in {f.code for f in report.findings}

    def test_retention_exceeded(self):
        report = check_row(
            {"aadhaar_number": AADHAAR},
            created_at=datetime.now(timezone.utc) - timedelta(days=800),
            consented_purposes={p.value for p in Purpose},
        )
        finding = next(f for f in report.findings if f.code == "retention_exceeded")
        assert finding.section == "s8(6)"

    def test_within_retention_passes(self):
        report = check_row(
            {"aadhaar_number": AADHAAR},
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
            consented_purposes={p.value for p in Purpose},
        )
        assert "retention_exceeded" not in {f.code for f in report.findings}

    def test_undeclared_field_flagged(self):
        report = check_row({"mystery_field": "x"},
                           consented_purposes={p.value for p in Purpose})
        assert "undeclared_field" in {f.code for f in report.findings}

    def test_every_finding_cites_a_section(self):
        report = check_row({"girl_child_name": "Anu", "mystery": "x"},
                           consented_purposes=None)
        assert report.findings
        for f in report.findings:
            assert re.match(r"^s\d+", f.section), f"{f.code} has no section"
            assert f.remediation, f"{f.code} gives no remediation"

    def test_empty_profile_is_compliant(self):
        assert check_row({}, consented_purposes=set()).compliant


class TestPayloadScanning:
    def test_detects_leaked_identifier(self):
        report = scan_payload({"user": {"aadhaar_number": AADHAAR}})
        assert not report.compliant
        assert report.of(Severity.CRITICAL)

    def test_allow_list_permits_intended_disclosure(self):
        """A citizen reading their own record must still receive it."""
        report = scan_payload({"aadhaar_number": AADHAAR},
                              allow=frozenset({PIICategory.AADHAAR}))
        assert report.compliant

    def test_clean_payload_passes(self):
        assert scan_payload({"schemes": ["PM-KISAN"], "count": 1}).compliant


class TestSourceScanning:
    def test_flags_pii_sent_to_third_party(self, tmp_path):
        (tmp_path / "bad.py").write_text(
            "import agnost\nagnost.track(user_id='u', input=str(profile))\n")
        report = scan_source(tmp_path)
        assert "pii_to_third_party" in {f.code for f in report.findings}

    def test_flags_pii_interpolated_into_logs(self, tmp_path):
        (tmp_path / "bad.py").write_text('logger.info(f"saving {profile}")\n')
        assert "pii_in_logs" in {f.code for f in scan_source(tmp_path).findings}

    def test_message_text_alone_is_not_a_leak(self, tmp_path):
        """The false positive that would have made this scanner unusable."""
        (tmp_path / "ok.py").write_text(
            'logger.error(f"Profile reset failed: {e}")\n')
        assert scan_source(tmp_path).compliant

    def test_live_codebase_has_no_outstanding_leaks(self):
        """Regression guard: the leaks found in the audit stay fixed."""
        from pathlib import Path
        report = scan_source(Path(__file__).resolve().parent.parent)
        assert report.compliant, [f.as_dict() for f in report.findings]


class TestRetention:
    def test_expired_fields_identified(self):
        expired = retention.expired_fields(
            {"aadhaar_number": AADHAAR, "mobile_number": "9876543210"},
            datetime.now(timezone.utc) - timedelta(days=500))
        fields = {f for f, _ in expired}
        # Aadhaar expires at 365 days; the mobile number supports alerts for
        # three years and must survive.
        assert "aadhaar_number" in fields and "mobile_number" not in fields

    def test_nothing_expired_when_recent(self):
        assert retention.expired_fields(
            {"aadhaar_number": AADHAAR}, datetime.now(timezone.utc)) == []

    def test_legal_hold_field_never_expires(self):
        expired = retention.expired_fields(
            {"phone": "9876543210"},
            datetime.now(timezone.utc) - timedelta(days=5000))
        assert not expired

    def test_fields_for_withdrawn_purposes(self):
        withdrawn = retention.fields_for_withdrawn_purposes(
            {"annual_income": 42000, "name": "Kamla"}, consented=set())
        assert "annual_income" in withdrawn

    def test_field_survives_while_any_purpose_retains_consent(self):
        withdrawn = retention.fields_for_withdrawn_purposes(
            {"mobile_number": "9876543210"},
            consented={Purpose.SERVICE_COMMUNICATION.value})
        assert "mobile_number" not in withdrawn

    def test_legitimate_use_does_not_depend_on_consent(self):
        """s7 legitimate uses survive consent withdrawal by design."""
        withdrawn = retention.fields_for_withdrawn_purposes(
            {"aadhaar_number": AADHAAR}, consented=set())
        assert "aadhaar_number" not in withdrawn


class TestReportMerging:
    def test_worst_findings_come_first(self):
        a = check_row({"mystery": "x"}, consented_purposes={p.value for p in Purpose})
        b = check_row({"girl_child_name": "Anu"},
                      consented_purposes={p.value for p in Purpose})
        combined = merge(a, b)
        severities = [f.severity for f in combined.findings]
        assert severities == sorted(
            severities,
            key=lambda s: {Severity.CRITICAL: 0, Severity.HIGH: 1,
                           Severity.WARNING: 2, Severity.INFO: 3}[s])
