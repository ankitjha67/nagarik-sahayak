"""Tests for the reviewer-facing applicant context.

Two guarantees are under test:

  * A reviewer can see enough to adjudicate a flag.
  * They cannot see more than that. Full identifiers never leave the backend,
    and fields outside the disclosable set are withheld — the review console is
    for deciding one flagged application, not a general window into a citizen's
    file.
"""
import pytest
from types import SimpleNamespace

from services.review_context import (
    DISCLOSABLE_FIELDS, SIGNAL_GUIDANCE, build_applicant_context,
    explain_signal, mask_identifier, _load_profile,
)


FULL_PROFILE = {
    "name": "Kamla Devi",
    "father_husband_name": "Ram Prasad",
    "aadhaar_number": "234567890124",
    "bank_account_number": "50100234567890",
    "mobile_number": "9876543210",
    "ration_card_number": "UP2619876543",
    "age": 68,
    "gender": "Female",
    "district": "Sitapur",
    "annual_income": 42000,
    # Not in DISCLOSABLE_FIELDS — must not be surfaced.
    "ifsc_code": "SBIN0001234",
    "address_line": "House 42, Ward 3, Rampur",
    "email": "kamla@example.com",
}


_UNSET = object()


def fake_user(profile=_UNSET, uid="user-1", phone="9876543210"):
    # A sentinel, not `or`: an explicitly empty profile is a real case to test
    # and must not silently fall through to the populated default.
    return SimpleNamespace(
        id=uid, phone=phone,
        fullProfile=FULL_PROFILE if profile is _UNSET else profile,
        profile=None, createdAt=None,
    )


class TestMasking:
    def test_aadhaar_shows_only_last_four(self):
        masked = mask_identifier("234567890124", "aadhaar")
        assert masked == "XXXX XXXX 0124"
        assert "23456789" not in masked

    def test_phone_shows_only_last_four(self):
        masked = mask_identifier("9876543210", "phone")
        assert masked.endswith("3210")
        assert "987654" not in masked

    def test_account_number_mostly_hidden(self):
        masked = mask_identifier("50100234567890")
        assert masked.endswith("7890")
        assert "5010023456" not in masked

    def test_short_values_fully_hidden(self):
        """Too short to mask meaningfully, so reveal nothing."""
        assert mask_identifier("123") == "XXX"

    def test_empty_returns_empty(self):
        """Distinguishes 'not supplied' from 'supplied but hidden'."""
        assert mask_identifier("") == ""
        assert mask_identifier(None) == ""

    def test_strips_separators_before_masking(self):
        assert mask_identifier("2345 6789 0124", "aadhaar") == "XXXX XXXX 0124"


class TestApplicantContext:
    def test_discloses_adjudication_fields(self):
        ctx = build_applicant_context(fake_user())
        assert ctx["fields"]["name"] == "Kamla Devi"
        assert ctx["fields"]["age"] == 68
        assert ctx["fields"]["annual_income"] == 42000

    def test_withholds_fields_outside_the_disclosable_set(self):
        ctx = build_applicant_context(fake_user())
        for withheld in ("ifsc_code", "address_line", "email"):
            assert withheld not in ctx["fields"], f"{withheld} should be withheld"

    def test_never_exposes_a_full_identifier(self):
        """The single most important property of this module."""
        ctx = build_applicant_context(fake_user())
        blob = str(ctx)
        for secret in ("234567890124", "50100234567890", "9876543210",
                       "UP2619876543"):
            assert secret not in blob, f"{secret} leaked into reviewer context"

    def test_identifiers_present_but_masked(self):
        ctx = build_applicant_context(fake_user())
        masked = ctx["identifiers_masked"]
        # A reviewer must still be able to tell *which* number was used.
        assert masked["aadhaar_number"].endswith("0124")
        assert masked["bank_account_number"].endswith("7890")

    def test_absent_identifiers_are_omitted(self):
        ctx = build_applicant_context(fake_user({"name": "Solo"}))
        assert "aadhaar_number" not in ctx["identifiers_masked"]

    def test_counts_supplied_fields(self):
        ctx = build_applicant_context(fake_user())
        assert ctx["fields_supplied"] == len(FULL_PROFILE)

    def test_handles_empty_profile(self):
        ctx = build_applicant_context(fake_user({}))
        assert ctx["fields"] == {} and ctx["identifiers_masked"] == {}

    def test_merges_full_and_basic_profiles(self):
        user = SimpleNamespace(
            id="u", phone="", createdAt=None,
            fullProfile={"name": "From Full"},
            profile={"name": "From Basic", "district": "Sitapur"},
        )
        merged = _load_profile(user)
        # fullProfile wins where both define a key.
        assert merged["name"] == "From Full"
        assert merged["district"] == "Sitapur"

    def test_tolerates_json_strings(self):
        import json
        user = SimpleNamespace(id="u", phone="", createdAt=None,
                               fullProfile=json.dumps({"name": "Encoded"}),
                               profile=None)
        assert _load_profile(user)["name"] == "Encoded"

    def test_tolerates_malformed_profile(self):
        user = SimpleNamespace(id="u", phone="", createdAt=None,
                               fullProfile="{not json", profile=None)
        assert _load_profile(user) == {}


class TestSignalGuidance:
    def test_every_guided_signal_is_complete(self):
        """Half-written guidance is worse than none — it misleads a reviewer."""
        for code, g in SIGNAL_GUIDANCE.items():
            assert g.get("means"), f"{code} missing 'means'"
            assert g.get("innocent"), f"{code} missing 'innocent'"
            assert g.get("check"), f"{code} missing 'check'"

    def test_guidance_covers_every_emitted_signal(self):
        """A reviewer must never meet a flag the console cannot explain."""
        import inspect
        import fraud_detection

        source = inspect.getsource(fraud_detection)
        emitted = set(__import__("re").findall(r'Signal\(\s*"([a-z0-9_]+)"', source))
        missing = emitted - set(SIGNAL_GUIDANCE)
        assert not missing, f"signals without reviewer guidance: {sorted(missing)}"

    def test_explain_attaches_guidance(self):
        out = explain_signal({"code": "bank_account_collection_point", "weight": 60})
        assert out["what_it_means"]
        assert out["innocent_explanation"]
        assert out["suggested_check"]
        assert out["weight"] == 60      # original fields preserved

    def test_unknown_signal_degrades_gracefully(self):
        out = explain_signal({"code": "brand_new_signal", "weight": 10})
        assert out["what_it_means"] == ""
        assert out["code"] == "brand_new_signal"

    def test_weak_signals_are_marked_as_weak(self):
        """Shared phones and assisted filing must not read as accusations."""
        for code in ("mobile_shared_widely", "velocity_high",
                     "threshold_age_unverified"):
            text = (SIGNAL_GUIDANCE[code]["innocent"] + " " +
                    SIGNAL_GUIDANCE[code]["check"]).lower()
            assert any(w in text for w in
                       ("legitimate", "common", "benign", "weak", "do not")), \
                f"{code} guidance does not convey that it is weak evidence"


class TestIdentityPanel:
    """What a reviewer learns about the applicant's identity evidence.

    The panel exists because a flagged case with a UIDAI-signed document behind
    it and a flagged case with nothing behind it look identical in a queue, and
    they warrant very different amounts of a reviewer's time.
    """

    def test_no_verification_is_a_neutral_state(self):
        """"Self-declared" is the lawful, ordinary condition of an applicant
        under the Aadhaar Act s7 proviso. A panel that reads it as a strike
        would train reviewers to treat the unverified poor as suspects."""
        from services.review_context import build_identity_context

        panel = build_identity_context({})
        assert panel["assurance"] == 0
        assert panel["verificationIsOptional"] is True
        note = panel["reviewer_note"].lower()
        assert "normal" in note and "lawful" in note
        assert "suspic" not in note and "fail" not in note

    def test_a_verified_applicant_is_distinguishable(self):
        from services.review_context import build_identity_context

        panel = build_identity_context({"kycOutcomes": [
            {"method": "aadhaar_offline_xml", "succeeded": True, "assurance": 3},
        ]})
        assert panel["assurance"] == 3
        assert "aadhaar_offline_xml" in panel["methodsUsed"]
        assert "UIDAI" in panel["reviewer_note"]

    def test_citizen_facing_text_is_not_mistaken_for_reviewer_advice(self):
        """assurance_summary() addresses the applicant directly ("Your identity
        is verified"). In a reviewer panel that reads as an instruction unless
        it is clearly labelled as what the applicant was told."""
        from services.review_context import build_identity_context

        panel = build_identity_context({"kycOutcomes": [
            {"method": "aadhaar_offline_xml", "succeeded": True, "assurance": 3},
        ]})
        assert "nextStep" not in panel
        assert panel["citizen_is_told"]["en"].startswith("Your")
        assert not panel["reviewer_note"].startswith("Your")

    def test_a_contradiction_is_surfaced(self):
        from services.review_context import build_identity_context

        panel = build_identity_context({"kycOutcomes": [
            {"method": "aadhaar_offline_xml", "succeeded": True,
             "assurance": 2, "contradicted": True, "needsReview": True},
        ]})
        assert panel["contradiction"] is True

    def test_malformed_stored_outcomes_do_not_break_the_panel(self):
        """A reviewer must not lose the whole case screen because one stored
        field is the wrong shape."""
        from services.review_context import build_identity_context

        for junk in (None, [], ["nonsense"], [{"assurance": "high"}], [{}]):
            panel = build_identity_context({"kycOutcomes": junk})
            assert "label" in panel and panel["verificationIsOptional"] is True


class TestIdentitySignalGuidance:
    def test_both_identity_signals_carry_guidance(self):
        from services.review_context import SIGNAL_GUIDANCE

        for code in ("identity_verified", "identity_document_contradicted"):
            g = SIGNAL_GUIDANCE[code]
            assert g["means"] and g["innocent"] and g["check"]

    def test_the_contradiction_guidance_rules_out_the_common_innocent_cases(self):
        """Name and gender mismatches never reach this signal. The guidance has
        to say so, or a reviewer will read a date-of-birth flag as covering
        them and refuse someone on a maiden name."""
        from services.review_context import SIGNAL_GUIDANCE

        text = SIGNAL_GUIDANCE["identity_document_contradicted"]["innocent"]
        assert "NEVER" in text
        assert "name" in text.lower() and "gender" in text.lower()

    def test_the_positive_signal_is_not_presented_as_suspicion(self):
        from services.review_context import SIGNAL_GUIDANCE

        text = SIGNAL_GUIDANCE["identity_verified"]["innocent"]
        assert "lowers the risk" in text

    def test_no_guidance_tells_a_reviewer_to_refuse_on_identity_alone(self):
        from services.review_context import SIGNAL_GUIDANCE

        check = SIGNAL_GUIDANCE["identity_document_contradicted"]["check"]
        assert "do not refuse on this alone" in check.lower()
