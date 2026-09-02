"""KYC — identity verification that admits automatically and never refuses.

The tests are organised around the two ways an identity system in a welfare
context goes wrong:

**It lies about what it checked.** An unverified signature reported as verified
poisons every downstream decision, because everyone then trusts a document
nobody validated. TestHonesty pins the assurance level to what actually
happened.

**It excludes the people it exists to serve.** Every automated check here has a
predictable false-negative population — the widow with a maiden name on her
bank account, the labourer whose UIDAI record holds only a year of birth, the
transgender applicant whose documents disagree with each other. TestNoOneIsShutOut
asserts none of them is refused.
"""
import base64
import gzip
import io
import zipfile

import pytest

from kyc import aadhaar_offline as ao
from kyc import matching, service
from kyc.methods import Assurance, Availability, Channel, METHODS, options


# ── Fixtures ─────────────────────────────────────────────────────────────

VALID_XML = """<?xml version="1.0" encoding="UTF-8"?>
<OfflinePaperlessKyc referenceId="0124202401011200000">
  <UidData>
    <Poi dob="12-04-1958" gender="F" name="Kamla Devi"/>
    <Poa careof="W/O: Ram Prasad" country="India" dist="Sitapur" house="42"
         landmark="Near Temple" loc="Kachhwa" pc="261001" po="Kachhwa"
         state="Uttar Pradesh" street="Main Road" subdist="Misrikh" vtc="Kachhwa"/>
    <Pht>Zm9vYmFy</Pht>
  </UidData>
  <Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
    <SignatureValue>abc</SignatureValue>
  </Signature>
</OfflinePaperlessKyc>
"""

UNSIGNED_XML = VALID_XML.replace(
    """  <Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
    <SignatureValue>abc</SignatureValue>
  </Signature>
""", "")


def make_zip(xml: str = VALID_XML, password: bytes | None = b"AB12") -> bytes:
    """A ZipCrypto-protected archive, as UIDAI produces."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("offlineaadhaar.xml", xml)
    data = buf.getvalue()
    if password is None:
        return data
    # Python's zipfile can read but not write encrypted archives, so encrypt
    # with the same legacy scheme the reader expects.
    return _zipcrypt(data, password)


def _zipcrypt(zip_bytes: bytes, password: bytes) -> bytes:
    """Re-encode an archive with legacy ZipCrypto so zipfile can decrypt it.

    Small and self-contained rather than a dependency, so the test proves the
    real read path rather than a mock of it.
    """
    src = zipfile.ZipFile(io.BytesIO(zip_bytes))
    info = src.infolist()[0]
    raw = src.read(info.filename)
    import binascii
    import struct

    # CRC-32 table, built from the polynomial rather than derived from
    # binascii.crc32 — the library function applies an initial and final xor
    # that a table lookup must not.
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ (0xEDB88320 if c & 1 else 0)
        table.append(c)

    class _Keys:
        def __init__(self, pw):
            self.k = [305419896, 591751049, 878082192]
            for c in pw:
                self.update(c)

        def crc32(self, ch, crc):
            return ((crc >> 8) ^ table[(crc ^ ch) & 0xFF]) & 0xFFFFFFFF

        def update(self, c):
            self.k[0] = self.crc32(c, self.k[0])
            self.k[1] = (self.k[1] + (self.k[0] & 0xFF)) & 0xFFFFFFFF
            self.k[1] = (self.k[1] * 134775813 + 1) & 0xFFFFFFFF
            self.k[2] = self.crc32((self.k[1] >> 24) & 0xFF, self.k[2])

        def byte(self):
            t = (self.k[2] | 2) & 0xFFFF
            return ((t * (t ^ 1)) >> 8) & 0xFF

        def encrypt(self, data):
            out = bytearray()
            for ch in data:
                k = self.byte()
                out.append(ch ^ k)
                self.update(ch)
            return bytes(out)

    import zlib
    compressed = zlib.compress(raw, 9)[2:-4]
    crc = binascii.crc32(raw) & 0xFFFFFFFF
    header = bytes(11) + bytes([(crc >> 24) & 0xFF])
    body = _Keys(password).encrypt(header + compressed)

    name = info.filename.encode()
    flags = 0x01
    local = (struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, flags, 8, 0, 0,
                         crc, len(body), len(raw), len(name), 0) + name + body)
    central = (struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, flags, 8, 0, 0,
                           crc, len(body), len(raw), len(name), 0, 0, 0, 0, 0, 0)
               + name)
    end = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 1, 1,
                      len(central), len(local), 0)
    return local + central + end


QR_VALUES = {
    "email_mobile_present": "3",
    "reference_id": "0124202401011200000",
    "name": "Kamla Devi", "dob": "12-04-1958", "gender": "F",
    "careof": "W/O Ram Prasad", "district": "Sitapur", "landmark": "Near Temple",
    "house": "42", "location": "Kachhwa", "pincode": "261001",
    "postoffice": "Kachhwa", "state": "Uttar Pradesh", "street": "Main Road",
    "subdistrict": "Misrikh", "vtc": "Kachhwa",
}


@pytest.fixture
def qr():
    return ao.build_test_qr(QR_VALUES, photo=b"\x00" * 40, signature=b"S" * 256)


CLAIMED = {"name": "Kamla Devi", "date_of_birth": "1958-04-12",
           "gender": "Female", "pincode": "261001"}


# ── Method catalogue ─────────────────────────────────────────────────────

class TestMethodCatalogue:
    def test_every_method_is_bilingual_and_explained(self):
        for m in METHODS:
            assert m.name_en and m.name_hi
            assert m.what_it_proves_en and m.what_it_proves_hi
            assert m.requirements_en and m.requirements_hi
            assert m.legal_basis

    def test_every_method_states_who_it_excludes(self):
        """A method with no exclusion note has not been thought about."""
        for m in METHODS:
            assert m.excludes_en and m.excludes_hi, f"{m.key} names nobody it fails"

    def test_licensed_methods_are_not_claimed_as_available(self):
        """The failure this prevents: telling a citizen they are 'verified' when
        the check needs a UIDAI appointment nobody has obtained."""
        for m in METHODS:
            if m.availability is Availability.NEEDS_LICENCE:
                assert not m.effective_availability.is_usable

    def test_credentialled_methods_go_inert_without_configuration(self, monkeypatch):
        digilocker = next(m for m in METHODS if m.key == "digilocker")
        for key in digilocker.config_keys:
            monkeypatch.delenv(key, raising=False)
        assert digilocker.effective_availability is Availability.NEEDS_CREDENTIALS

    def test_configuring_credentials_enables_a_method(self, monkeypatch):
        digilocker = next(m for m in METHODS if m.key == "digilocker")
        for key in digilocker.config_keys:
            monkeypatch.setenv(key, "x")
        assert digilocker.effective_availability is Availability.IMPLEMENTED

    def test_options_are_serialisable_and_ranked(self):
        opts = options()
        assert len(opts) == len(METHODS)
        usable = [o["usable"] for o in opts]
        # Usable methods first — an unusable one must never head the list.
        assert usable == sorted(usable, reverse=True)
        assert all("missingConfig" in o for o in opts)

    def test_unavailable_methods_are_shown_not_hidden(self):
        keys = {o["key"] for o in options()}
        assert "aadhaar_otp_ekyc" in keys, \
            "a method that needs a licence must still be listed, and labelled"


class TestNoOneIsShutOut:
    def test_an_offline_route_always_exists(self):
        """Someone with no smartphone and no data connection must still be able
        to establish an identity."""
        from kyc.methods import available_methods
        offline = [m for m in available_methods()
                   if m.channel in (Channel.SELF_OFFLINE, Channel.ASSISTED,
                                    Channel.IN_PERSON)]
        assert offline

    def test_a_human_route_always_exists(self):
        """When every digital method has failed, someone must still be able to
        stand in front of an official — the Aadhaar s7 proviso route."""
        from kyc.methods import available_methods, Assurance as A
        human = [m for m in available_methods()
                 if m.channel in (Channel.ASSISTED, Channel.IN_PERSON)
                 and m.assurance >= A.SUBSTANTIAL]
        assert human, "no human fallback reaches a usable assurance"

    def test_biometrics_are_not_the_only_high_assurance_route(self):
        """Fingerprints fail routinely for labourers and the elderly. UIDAI's own
        circulars require an alternative."""
        from kyc.methods import available_methods, Assurance as A
        high = [m for m in available_methods() if m.assurance >= A.VERIFIED]
        assert any(m.key != "aadhaar_biometric" for m in high)

    def test_self_declaration_never_stops_being_available(self):
        """It proves nothing, and that is the point: it is what lets someone
        with none of the prerequisites start an application at all."""
        from kyc.methods import available_methods
        assert any(m.key == "self_declaration" for m in available_methods())


# ── Aadhaar offline XML ──────────────────────────────────────────────────

class TestOfflineXml:
    def test_parses_demographics_into_profile_keys(self):
        record = ao.parse_offline_xml_bytes(VALID_XML.encode())
        d = record.demographics
        assert d["name"] == "Kamla Devi"
        assert d["date_of_birth"] == "12-04-1958"
        assert d["gender"] == "Female"
        assert d["district"] == "Sitapur"
        assert d["state"] == "Uttar Pradesh"
        assert d["pincode"] == "261001"
        assert "42" in d["address_line"]

    def test_extracts_only_the_last_four_aadhaar_digits(self):
        record = ao.parse_offline_xml_bytes(VALID_XML.encode())
        assert record.aadhaar_last4 == "0124"
        assert record.demographics["aadhaar_number_last4"] == "0124"

    def test_never_yields_a_storable_full_aadhaar(self):
        """s29(4) makes publishing an Aadhaar number criminal. UIDAI omits it
        from these files; this asserts nothing reassembles one."""
        from dpdp.aadhaar_policy import contains_full_aadhaar
        record = ao.parse_offline_xml_bytes(VALID_XML.encode())
        assert not contains_full_aadhaar(ao.to_profile(record))

    def test_opens_a_share_code_protected_archive(self):
        record = ao.parse_offline_xml(make_zip(), "AB12")
        assert record.demographics["name"] == "Kamla Devi"

    def test_wrong_share_code_gives_a_fixable_message(self):
        with pytest.raises(ao.OfflineKycError) as exc:
            ao.parse_offline_xml(make_zip(), "ZZZZ")
        assert exc.value.code == "bad_share_code"
        assert exc.value.message_hi, "a citizen who cannot read English is stuck"
        assert "share code" in exc.value.message_en.lower()

    def test_missing_share_code_is_named_as_the_problem(self):
        with pytest.raises(ao.OfflineKycError) as exc:
            ao.parse_offline_xml(make_zip(), "")
        assert exc.value.code == "share_code_required"

    def test_a_non_zip_upload_is_explained(self):
        with pytest.raises(ao.OfflineKycError) as exc:
            ao.parse_offline_xml(b"this is not a zip", "AB12")
        assert exc.value.code == "not_a_zip"

    def test_oversized_upload_is_refused_before_parsing(self):
        with pytest.raises(ao.OfflineKycError) as exc:
            ao.parse_offline_xml(b"x" * (ao.MAX_ZIP_BYTES + 1), "AB12")
        assert exc.value.code == "too_large"

    def test_wrong_xml_document_is_identified(self):
        with pytest.raises(ao.OfflineKycError) as exc:
            ao.parse_offline_xml_bytes(b"<SomethingElse/>")
        assert exc.value.code == "wrong_document"

    def test_year_only_date_of_birth_is_flagged_not_rejected(self):
        """UIDAI holds a bare year for many elderly holders. Rejecting that
        would exclude exactly the old-age pension population."""
        xml = VALID_XML.replace('dob="12-04-1958"', 'dob="1958"')
        record = ao.parse_offline_xml_bytes(xml.encode())
        assert record.demographics["date_of_birth"] == "1958"
        assert any("year of birth" in w for w in record.warnings)


class TestHonesty:
    """An unverified signature must never be reported as verified."""

    def test_unchecked_signature_yields_documented_not_verified(self, monkeypatch):
        monkeypatch.delenv(ao.UIDAI_CERT_ENV, raising=False)
        record = ao.parse_offline_xml_bytes(VALID_XML.encode())
        assert record.signature_verified is False
        assert record.assurance is Assurance.DOCUMENTED
        assert record.assurance < Assurance.VERIFIED

    def test_the_reason_is_stated_in_both_languages(self, monkeypatch):
        monkeypatch.delenv(ao.UIDAI_CERT_ENV, raising=False)
        record = ao.parse_offline_xml_bytes(VALID_XML.encode())
        assert "certificate is configured" in record.signature_note_en
        assert record.signature_note_hi

    def test_an_unsigned_document_says_so(self):
        record = ao.parse_offline_xml_bytes(UNSIGNED_XML.encode())
        assert record.signature_verified is False
        assert "no UIDAI signature" in record.signature_note_en

    def test_missing_certificate_file_does_not_crash_the_upload(self, monkeypatch):
        monkeypatch.setenv(ao.UIDAI_CERT_ENV, "/nonexistent/uidai.pem")
        record = ao.parse_offline_xml_bytes(VALID_XML.encode())
        assert record.signature_verified is False
        assert record.assurance is Assurance.DOCUMENTED

    def test_outcome_carries_the_unverified_note_forward(self, monkeypatch):
        monkeypatch.delenv(ao.UIDAI_CERT_ENV, raising=False)
        outcome = service.verify_offline_xml(CLAIMED, make_zip(), "AB12")
        assert outcome.assurance is Assurance.DOCUMENTED
        assert outcome.warnings, "the reason for the downgrade was dropped"
        assert outcome.needs_review, \
            "an unverified document must reach a human, not be waved through"


# ── Secure QR ────────────────────────────────────────────────────────────

class TestSecureQr:
    def test_round_trips_the_documented_field_order(self, qr):
        record = ao.parse_secure_qr(qr)
        assert record.demographics["name"] == "Kamla Devi"
        assert record.demographics["state"] == "Uttar Pradesh"
        assert record.aadhaar_last4 == "0124"

    def test_detects_the_photo_and_signature_block(self, qr):
        record = ao.parse_secure_qr(qr)
        assert record.has_photo
        assert "not checked" in record.signature_note_en

    def test_qr_signature_is_never_claimed_as_verified(self, qr):
        record = ao.parse_secure_qr(qr)
        assert record.signature_verified is False
        assert record.assurance is Assurance.DOCUMENTED

    def test_whitespace_from_a_scanner_is_tolerated(self, qr):
        spaced = " ".join(qr[i:i + 12] for i in range(0, len(qr), 12))
        assert ao.parse_secure_qr(spaced).demographics["name"] == "Kamla Devi"

    def test_a_non_numeric_scan_is_explained(self):
        with pytest.raises(ao.OfflineKycError) as exc:
            ao.parse_secure_qr("http://example.com")
        assert exc.value.code == "not_secure_qr"
        assert exc.value.message_hi

    def test_a_legacy_unsigned_qr_points_at_an_alternative(self):
        """Old Aadhaar letters carry an unsigned QR. The citizen must be sent to
        another route, not simply refused."""
        with pytest.raises(ao.OfflineKycError) as exc:
            ao.parse_secure_qr("12345678901234567890")
        assert exc.value.code == "legacy_qr"
        assert "offline e-KYC" in exc.value.message_en

    def test_empty_input_is_named(self):
        with pytest.raises(ao.OfflineKycError) as exc:
            ao.parse_secure_qr("")
        assert exc.value.code == "empty"

    def test_truncated_payload_is_reported_not_half_parsed(self):
        truncated = ao.build_test_qr({"name": "Kamla"})
        with pytest.raises(ao.OfflineKycError):
            # A payload with too few delimiters must fail loudly rather than
            # silently establishing a partial identity.
            record = ao.parse_secure_qr(truncated[: len(truncated) // 2])
            assert record


# ── Matching ─────────────────────────────────────────────────────────────

class TestNameMatching:
    @pytest.mark.parametrize("a,b", [
        ("Kamla Devi", "Kamala Devi"),
        ("Mohd. Rafiq", "Mohammad Rafique"),
        ("Md Salim", "Mohammed Saleem"),
        ("Lakshmi Bai", "Laxmi Bai"),
        ("Ram Prasad Yadav", "R P Yadav"),
        ("Smt. Sunita Sharma", "Sunita Sharma"),
        ("Sunita Kumari Singh", "Sunita Singh"),
        ("Krishan Chander", "Krishna Chandra"),
    ])
    def test_transliteration_and_abbreviation_still_match(self, a, b):
        """Each of these is one person. Scoring them as mismatches would send a
        large and specific share of applicants to manual review for nothing."""
        assert matching.compare_names(a, b).is_match, \
            f"{a!r} vs {b!r} scored {matching.compare_names(a, b).score:.2f}"

    def test_genuinely_different_names_score_low(self):
        assert matching.compare_names("Kamla Devi", "Rajesh Kumar").score < 0.45

    def test_a_name_mismatch_is_never_decisive(self):
        """The maiden-name case. A woman's bank account may legitimately carry a
        different surname from her ration card, so this can only ever be a
        review flag."""
        result = matching.compare_names("Sunita Sharma", "Sunita Verma")
        assert not result.decisive
        assert result.needs_review

    def test_missing_name_does_not_assert_a_mismatch(self):
        assert matching.compare_names("", "Kamla Devi").score == 0.0
        assert not matching.compare_names("", "Kamla Devi").decisive


class TestDateMatching:
    @pytest.mark.parametrize("value,expected", [
        ("1958-04-12", (1958, 4, 12)),
        ("12-04-1958", (1958, 4, 12)),
        ("12/04/1958", (1958, 4, 12)),
        ("12.04.1958", (1958, 4, 12)),
        ("12 Apr 1958", (1958, 4, 12)),
    ])
    def test_parses_the_formats_records_actually_use(self, value, expected):
        d = matching.parse_date(value)
        assert (d.year, d.month, d.day) == expected

    def test_a_bare_year_parses_to_mid_year(self):
        """UIDAI stores a year alone for holders who never knew their birthday."""
        assert matching.parse_date("1958").year == 1958

    def test_same_year_different_day_is_not_a_mismatch(self):
        result = matching.compare_dates_of_birth("1958-04-12", "1958-01-01")
        assert result.is_match
        assert not result.decisive

    def test_a_twenty_year_gap_is_decisive(self):
        result = matching.compare_dates_of_birth("1958-04-12", "1978-04-12")
        assert result.decisive
        assert result.score == 0.0

    def test_an_unparseable_date_is_not_treated_as_a_contradiction(self):
        assert not matching.compare_dates_of_birth("not a date", "1958").decisive


class TestGenderMatching:
    def test_matching_genders_pass(self):
        assert matching.compare_genders("Female", "F").is_match

    def test_a_gender_difference_is_never_decisive(self):
        """The Transgender Persons Act 2019 gives the right to a self-perceived
        identity; documents may lag behind it. Refusing on that would be both
        unlawful and cruel."""
        result = matching.compare_genders("Transgender", "M")
        assert not result.decisive
        assert "reviewer" in result.reason_en


class TestPincodeMatching:
    def test_same_pincode_matches(self):
        assert matching.compare_pincodes("261001", "261001").is_match

    def test_a_local_move_is_not_a_contradiction(self):
        result = matching.compare_pincodes("261001", "261125")
        assert not result.decisive
        assert result.needs_review

    def test_a_distant_move_still_only_flags(self):
        """People migrate. A Bihar-born worker living in Delhi is the norm, not
        a fraud signal."""
        assert not matching.compare_pincodes("261001", "110001").decisive


# ── Orchestration ────────────────────────────────────────────────────────

class TestService:
    def test_a_clean_match_lowers_the_fraud_score(self, monkeypatch, qr):
        """Verification must buy the honest applicant something, or nobody
        bothers to verify."""
        outcome = service.verify_secure_qr(CLAIMED, qr)
        assert outcome.succeeded
        assert outcome.fraud_signal < 0

    def test_a_decisive_contradiction_raises_suspicion_without_refusing(self, qr):
        claimed = dict(CLAIMED, date_of_birth="1978-04-12")
        outcome = service.verify_secure_qr(claimed, qr)
        assert outcome.contradicted
        assert outcome.fraud_signal > 0
        assert outcome.succeeded, "the check ran; it is the reviewer who decides"
        assert "not been refused" in outcome.message_en

    def test_a_soft_mismatch_says_the_application_continues(self, qr):
        claimed = dict(CLAIMED, name="Sunita Verma")
        outcome = service.verify_secure_qr(claimed, qr)
        assert outcome.needs_review
        assert "continues" in outcome.message_en

    def test_an_empty_profile_is_populated_rather_than_compared(self, qr):
        outcome = service.verify_secure_qr({}, qr)
        assert outcome.established["name"] == "Kamla Devi"
        assert not outcome.matches
        assert outcome.succeeded

    def test_a_licensed_method_refuses_to_pretend(self):
        with pytest.raises(RuntimeError) as exc:
            service.record_attestation({}, method="aadhaar_otp_ekyc",
                                       attestor_name="X", attestor_role="Y")
        assert "not enabled" in str(exc.value)

    def test_attestation_requires_a_named_attestor(self):
        outcome = service.record_attestation({"name": "Kamla Devi"},
                                             method="csc_assisted",
                                             attestor_name="", attestor_role="VLE")
        assert not outcome.succeeded

    def test_attestation_without_an_id_warns_about_traceability(self):
        outcome = service.record_attestation(
            {"name": "Kamla Devi", "district": "Sitapur"},
            method="csc_assisted", attestor_name="R. Kumar", attestor_role="VLE")
        assert outcome.succeeded
        assert outcome.needs_review, "a human vouching is evidence, not proof"
        assert any("cannot be linked" in w for w in outcome.warnings)

    def test_self_declaration_is_recorded_as_unverified(self):
        outcome = service.record_self_declaration({"voter_id_number": "ABC1234567"})
        assert outcome.succeeded
        assert outcome.assurance is Assurance.ASSERTED
        assert "not been checked" in outcome.message_en

    def test_self_declaration_without_any_document_fails_helpfully(self):
        outcome = service.record_self_declaration({"name": "Kamla"})
        assert not outcome.succeeded
        assert "Voter ID" in outcome.message_en, \
            "the message must name alternatives, not demand Aadhaar"


class TestAggregation:
    def _outcome(self, level, **kw):
        return service.VerificationOutcome(
            method=kw.pop("method", "m"), succeeded=kw.pop("succeeded", True),
            assurance=level, **kw)

    def test_the_best_check_wins_not_the_latest(self):
        """Supplying more evidence must never demote someone."""
        outcomes = [self._outcome(Assurance.VERIFIED),
                    self._outcome(Assurance.DOCUMENTED)]
        assert service.profile_assurance(outcomes) is Assurance.VERIFIED

    def test_a_failed_check_does_not_count(self):
        outcomes = [self._outcome(Assurance.VERIFIED, succeeded=False)]
        assert service.profile_assurance(outcomes) is Assurance.NONE

    def test_no_summary_ever_says_refused(self):
        for level in Assurance:
            for contradicted in (True, False):
                summary = service.assurance_summary(
                    [self._outcome(level, contradicted=contradicted)])
                text = (summary["nextStep"] + summary["nextStepHindi"]).lower()
                assert "refus" not in text and "reject" not in text
                assert summary["nextStepHindi"]

    def test_the_unverified_citizen_is_told_aadhaar_is_optional(self):
        summary = service.assurance_summary([])
        assert "one option among several" in summary["nextStep"]

    def test_scheme_gap_never_blocks_an_application(self):
        from data.gov_forms import get_catalog
        for scheme in get_catalog():
            gap = service.gap_for_scheme([], scheme)
            assert gap["canStillApply"] is True

    def test_scheme_gap_suggests_something_reachable(self):
        from data.gov_forms import get_by_name
        gap = service.gap_for_scheme([], get_by_name("Ayushman Bharat PM-JAY"))
        assert gap["suggestedMethods"], "told to verify, with no way to do it"
        from kyc.methods import BY_KEY
        assert all(BY_KEY[k].effective_availability.is_usable
                   for k in gap["suggestedMethods"])


class TestFraudIntegration:
    def test_verification_reduces_the_score_of_an_honest_application(self):
        import fraud_detection as fd
        profile = {"name": "Kamla Devi", "date_of_birth": "1958-04-12",
                   "annual_income": 42000, "state": "Uttar Pradesh"}
        base = fd.assess(profile)
        verified = fd.assess(profile, kyc_outcomes=[
            service.VerificationOutcome(method="aadhaar_offline_xml", succeeded=True,
                                        assurance=Assurance.VERIFIED,
                                        fraud_signal=-15)])
        assert verified.score <= base.score

    def test_the_score_never_goes_negative(self):
        """Otherwise an applicant could bank credit by verifying and spend it on
        genuinely suspicious behaviour."""
        import fraud_detection as fd
        result = fd.assess({}, kyc_outcomes=[
            service.VerificationOutcome(method="a", succeeded=True,
                                        assurance=Assurance.VERIFIED,
                                        fraud_signal=-100)])
        assert result.score >= 0
        assert result.decision is fd.Decision.ALLOW

    def test_a_contradiction_reaches_the_fraud_engine(self):
        import fraud_detection as fd
        result = fd.assess({}, kyc_outcomes=[
            service.VerificationOutcome(method="aadhaar_offline_xml", succeeded=True,
                                        assurance=Assurance.DOCUMENTED,
                                        contradicted=True, fraud_signal=35)])
        assert result.decision is not fd.Decision.ALLOW
        assert any(s.code == "identity_document_contradicted" for s in result.signals)

    def test_verification_alone_cannot_clear_a_genuinely_bad_case(self):
        """Someone who verifies their own identity and then claims for eight
        household members is still escalated."""
        import fraud_detection as fd
        history = fd.ApplicantHistory(users_sharing_bank_account=12,
                                      applications_last_24h=30)
        result = fd.assess({}, history=history, kyc_outcomes=[
            service.VerificationOutcome(method="aadhaar_offline_xml", succeeded=True,
                                        assurance=Assurance.VERIFIED,
                                        fraud_signal=-15)])
        assert result.decision is not fd.Decision.ALLOW


class TestNoAadhaarLeaks:
    """Aadhaar Act s29(4) makes publishing an Aadhaar number a criminal offence."""

    def test_no_serialised_outcome_carries_twelve_digits(self, qr):
        from dpdp.aadhaar_policy import contains_full_aadhaar
        outcome = service.verify_secure_qr(CLAIMED, qr)
        assert not contains_full_aadhaar(outcome.as_dict())

    def test_offline_record_serialisation_is_clean(self):
        from dpdp.aadhaar_policy import contains_full_aadhaar
        record = ao.parse_offline_xml_bytes(VALID_XML.encode())
        assert not contains_full_aadhaar(record.as_dict())

    def test_the_reference_id_is_not_an_aadhaar_number(self):
        record = ao.parse_offline_xml_bytes(VALID_XML.encode())
        assert len(record.reference_id) != 12
