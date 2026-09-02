"""Tests for alternative identity documents — Aadhaar Act s7 proviso.

The property under test is exclusion, not validation. The people least likely to
hold a working Aadhaar are the elderly, the homeless, migrant workers and people
whose fingerprints no longer read — precisely the population an old-age pension
or a BPL housing scheme exists to serve. A form that will not proceed without
Aadhaar excludes the intended beneficiary.

So the central assertions are that a citizen holding *only* a voter ID, or only
a ration card, can complete every scheme in the catalog.
"""
import pytest

from dpdp import identity_documents as ids
from data.gov_forms import get_catalog
from validation import validate_profile, verhoeff_check_digit


AADHAAR = "23456789012" + verhoeff_check_digit("23456789012")


def base_profile(**overrides):
    """Everything the old-age pension needs except an identity document."""
    profile = {
        "name": "Kamla Devi", "father_husband_name": "Ram Prasad",
        "date_of_birth": "1958-04-12", "age": 68, "gender": "Female",
        "category": "OBC", "mobile_number": "9876543210",
        "address_line": "House 42", "district": "Sitapur",
        "state": "Uttar Pradesh", "pincode": "261001", "is_bpl": "Yes",
        "annual_income": 42000, "bank_account_number": "50100234567890",
        "ifsc_code": "SBIN0001234", "bank_name": "State Bank of India",
    }
    profile.update(overrides)
    return profile


class TestAcceptedDocuments:
    def test_aadhaar_is_one_option_among_several(self):
        keys = ids.DOCUMENT_KEYS
        assert "aadhaar_number" in keys
        assert len(keys) >= 5, "a single alternative is not a real choice"

    def test_covers_documents_the_poorest_actually_hold(self):
        """Ration and job cards reach people who have no Aadhaar or PAN."""
        keys = set(ids.DOCUMENT_KEYS)
        assert {"ration_card_number", "job_card_number", "voter_id_number"} <= keys

    def test_every_document_is_bilingual(self):
        for d in ids.ACCEPTED_DOCUMENTS:
            assert d.name_en and d.name_hi
            assert d.hint_en and d.hint_hi
            assert d.issuer

    def test_options_are_serialisable(self):
        opts = ids.options()
        assert len(opts) == len(ids.ACCEPTED_DOCUMENTS)
        assert all("name_hi" in o and "issuer" in o for o in opts)


class TestDocumentValidation:
    def test_valid_aadhaar_accepted(self):
        ok, _, _ = ids.validate(AADHAAR, "aadhaar_number")
        assert ok

    def test_aadhaar_still_checksum_verified(self):
        """The alternative route must not weaken Aadhaar's own check."""
        bad = AADHAAR[:11] + str((int(AADHAAR[11]) + 1) % 10)
        ok, en, _ = ids.validate(bad, "aadhaar_number")
        assert not ok and "checksum" in en.lower()

    @pytest.mark.parametrize("value,key", [
        ("ABC1234567", "voter_id_number"),
        ("ABCDE1234F", "pan_number"),
        ("A1234567", "passport_number"),
    ])
    def test_formatted_documents_accepted(self, value, key):
        assert ids.validate(value, key)[0]

    @pytest.mark.parametrize("value,key", [
        ("AB1234567", "voter_id_number"),
        ("ABCD1234F", "pan_number"),
    ])
    def test_malformed_documents_rejected(self, value, key):
        ok, en, hi = ids.validate(value, key)
        assert not ok and en and hi

    @pytest.mark.parametrize("value", [
        "UP2619876543", "RJ/2019/00123", "1234-5678-90",
    ])
    def test_state_documents_accepted_on_presence(self, value):
        """Ration card formats vary by state; rejecting a genuine one would
        recreate the exclusion this module exists to prevent."""
        assert ids.validate(value, "ration_card_number")[0]

    def test_empty_value_rejected(self):
        assert not ids.validate("", "voter_id_number")[0]

    def test_unknown_document_type_rejected(self):
        assert not ids.validate("X", "library_card")[0]

    def test_normalises_separators(self):
        assert ids.normalise("ABC 1234-567", "voter_id_number") == "ABC1234567"
        assert ids.normalise("2345 6789 0124", "aadhaar_number") == "234567890124"


class TestProfileIdentity:
    def test_detects_which_documents_are_present(self):
        found = ids.which_provided({"voter_id_number": "ABC1234567",
                                    "ration_card_number": "UP123"})
        assert set(found) == {"voter_id_number", "ration_card_number"}

    def test_recognises_a_stored_aadhaar_remnant(self):
        """Aadhaar itself is never persisted; the last four are.

        A returning citizen must not be told they supplied no identity document
        simply because the number was correctly not stored.
        """
        assert ids.has_any({"aadhaar_number_last4": "0124"})
        assert "aadhaar_number" in ids.which_provided({"aadhaar_number_last4": "0124"})

    def test_no_document_is_reported(self):
        ok, en, hi = ids.validate_profile_identity({"name": "Kamla"})
        assert not ok
        # The message must name the alternatives, not demand Aadhaar.
        assert "Voter ID" in en and "Ration Card" in en
        assert hi

    def test_one_valid_document_is_enough(self):
        assert ids.validate_profile_identity({"voter_id_number": "ABC1234567"})[0]

    def test_a_good_document_survives_a_mistyped_one(self):
        """A citizen who mistyped their PAN but gave a good voter ID must not
        be blocked."""
        ok, _, _ = ids.validate_profile_identity({
            "voter_id_number": "ABC1234567", "pan_number": "WRONG",
        })
        assert ok

    def test_all_documents_malformed_is_rejected(self):
        ok, en, _ = ids.validate_profile_identity({"pan_number": "WRONG"})
        assert not ok and en


class TestNoSchemeRequiresAadhaarSpecifically:
    """The point of the whole module, asserted against the real catalog."""

    @pytest.mark.parametrize("scheme", get_catalog(), ids=lambda s: s["schemeName"])
    def test_voter_id_alone_is_accepted(self, scheme):
        profile = base_profile(voter_id_number="ABC1234567")
        result = validate_profile(profile, scheme["extractedFields"])
        blocking = [e.code for e in result.errors
                    if e.code in ("identity_document_missing", "aadhaar_missing")]
        assert not blocking, f"{scheme['schemeName']} still demands Aadhaar"

    @pytest.mark.parametrize("scheme", get_catalog(), ids=lambda s: s["schemeName"])
    def test_ration_card_alone_is_accepted(self, scheme):
        profile = base_profile(ration_card_number="UP2619876543")
        result = validate_profile(profile, scheme["extractedFields"])
        blocking = [e.code for e in result.errors
                    if e.code in ("identity_document_missing", "aadhaar_missing")]
        assert not blocking, f"{scheme['schemeName']} still demands Aadhaar"

    def test_aadhaar_still_works(self):
        from data.gov_forms import get_by_name
        scheme = get_by_name("Indira Gandhi National Old Age Pension")
        result = validate_profile(base_profile(aadhaar_number=AADHAAR),
                                  scheme["extractedFields"])
        assert not result.is_blocking

    def test_no_document_at_all_is_still_refused(self):
        """The proviso offers alternatives, not an exemption from identifying."""
        from data.gov_forms import get_by_name
        scheme = get_by_name("Indira Gandhi National Old Age Pension")
        result = validate_profile(base_profile(), scheme["extractedFields"])
        assert result.is_blocking
        assert "identity_document_missing" in {e.code for e in result.errors}

    def test_alternatives_are_declared_in_the_processing_register(self):
        from dpdp import registry
        for key in ("voter_id_number", "passport_number", "driving_licence_number"):
            assert registry.record_for(key), f"{key} is not declared"
