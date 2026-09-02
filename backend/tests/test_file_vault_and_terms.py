"""Tests for document encryption at rest and the published terms.

The document tests mirror the profile ones: a filled application form carries
the same personal data as the database row it came from, so encrypting one and
not the other protects the harder target and ignores the easier one.

The terms tests check substance rather than presence. Four disclosures exist to
stop a citizen believing they have applied when they have not, or paying a
middleman — so the tests assert those are actually said, in both languages.
"""
import pytest

from dpdp import crypto, file_vault, terms


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", crypto.generate_key())
    monkeypatch.delenv("DATA_ENCRYPTION_KEY_OLD", raising=False)
    yield


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.delenv("DATA_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("DATA_ENCRYPTION_KEY_OLD", raising=False)
    yield


# A stand-in for a filled form: a real PDF header plus recognisable personal data.
DOCUMENT = b"%PDF-1.4\nKamla Devi\n50100234567890\nAnnual income 42000\n%%EOF"


class TestDocumentEncryption:
    def test_roundtrip(self, key):
        assert file_vault.decrypt_bytes(file_vault.encrypt_bytes(DOCUMENT)) == DOCUMENT

    def test_ciphertext_hides_personal_data(self, key):
        ct = file_vault.encrypt_bytes(DOCUMENT)
        for secret in (b"Kamla Devi", b"50100234567890", b"42000"):
            assert secret not in ct

    def test_ciphertext_is_not_a_pdf(self, key):
        """Anyone reading the directory should not see a openable document."""
        ct = file_vault.encrypt_bytes(DOCUMENT)
        assert not ct.startswith(b"%PDF")
        assert ct.startswith(file_vault.MAGIC)

    def test_nonce_is_never_reused(self, key):
        assert len({file_vault.encrypt_bytes(DOCUMENT) for _ in range(30)}) == 30

    def test_tampering_is_detected(self, key):
        ct = bytearray(file_vault.encrypt_bytes(DOCUMENT))
        ct[-1] ^= 0x01
        with pytest.raises(crypto.DecryptionError):
            file_vault.decrypt_bytes(bytes(ct))

    def test_wrong_key_cannot_decrypt(self, key, monkeypatch):
        ct = file_vault.encrypt_bytes(DOCUMENT)
        monkeypatch.setenv("DATA_ENCRYPTION_KEY", crypto.generate_key())
        with pytest.raises(crypto.DecryptionError):
            file_vault.decrypt_bytes(ct)

    def test_old_key_reads_during_rotation(self, key, monkeypatch):
        import os
        original = os.environ["DATA_ENCRYPTION_KEY"]
        ct = file_vault.encrypt_bytes(DOCUMENT)
        monkeypatch.setenv("DATA_ENCRYPTION_KEY", crypto.generate_key())
        monkeypatch.setenv("DATA_ENCRYPTION_KEY_OLD", original)
        assert file_vault.decrypt_bytes(ct) == DOCUMENT

    def test_never_double_encrypts(self, key):
        once = file_vault.encrypt_bytes(DOCUMENT)
        assert file_vault.encrypt_bytes(once) == once

    def test_plaintext_passes_through_on_read(self, key):
        """Legacy documents must keep serving before the migration runs."""
        assert file_vault.decrypt_bytes(DOCUMENT) == DOCUMENT

    def test_passthrough_without_a_key(self, no_key):
        assert file_vault.encrypt_bytes(DOCUMENT) == DOCUMENT

    def test_empty_input(self, key):
        assert file_vault.encrypt_bytes(b"") == b""
        assert file_vault.decrypt_bytes(b"") == b""


class TestFileOperations:
    def test_write_then_read(self, key, tmp_path):
        p = tmp_path / "form.pdf"
        file_vault.write(p, DOCUMENT)
        assert p.read_bytes() != DOCUMENT        # ciphertext on disk
        assert file_vault.read(p) == DOCUMENT    # plaintext to the caller

    def test_is_encrypted_detects_both_forms(self, key, tmp_path):
        enc, plain = tmp_path / "a.pdf", tmp_path / "b.pdf"
        file_vault.write(enc, DOCUMENT)
        plain.write_bytes(DOCUMENT)
        assert file_vault.is_encrypted(enc)
        assert not file_vault.is_encrypted(plain)

    def test_encrypt_in_place(self, key, tmp_path):
        p = tmp_path / "legacy.pdf"
        p.write_bytes(DOCUMENT)
        assert file_vault.encrypt_in_place(p) is True
        assert file_vault.is_encrypted(p)
        assert file_vault.read(p) == DOCUMENT

    def test_encrypt_in_place_is_idempotent(self, key, tmp_path):
        p = tmp_path / "f.pdf"
        file_vault.write(p, DOCUMENT)
        assert file_vault.encrypt_in_place(p) is False   # already done
        assert file_vault.read(p) == DOCUMENT

    def test_no_temp_file_left_behind(self, key, tmp_path):
        p = tmp_path / "f.pdf"
        p.write_bytes(DOCUMENT)
        file_vault.encrypt_in_place(p)
        assert not list(tmp_path.glob("*.enc-tmp"))

    def test_missing_file_is_not_an_error(self, key, tmp_path):
        assert file_vault.encrypt_in_place(tmp_path / "absent.pdf") is False

    def test_status_counts_both_forms(self, key, tmp_path):
        file_vault.write(tmp_path / "enc.pdf", DOCUMENT)
        (tmp_path / "plain.pdf").write_bytes(DOCUMENT)
        st = file_vault.status([tmp_path])
        assert st["files_encrypted"] == 1 and st["files_plaintext"] == 1
        assert st["fully_encrypted"] is False
        assert "predate encryption" in st["warning"]

    def test_status_clean_when_all_encrypted(self, key, tmp_path):
        file_vault.write(tmp_path / "a.pdf", DOCUMENT)
        st = file_vault.status([tmp_path])
        assert st["fully_encrypted"] is True and st["warning"] is None

    def test_status_warns_when_disabled(self, no_key, tmp_path):
        (tmp_path / "a.pdf").write_bytes(DOCUMENT)
        assert "DATA_ENCRYPTION_KEY" in file_vault.status([tmp_path])["warning"]


class TestTermsOfService:
    def test_has_a_version_and_date(self):
        t = terms.terms()
        assert t["version"] and t["effective_date"]

    def test_states_it_is_not_the_government(self):
        """The disclosure that most protects the citizen."""
        d = next(x for x in terms.CRITICAL_DISCLOSURES if x["id"] == "not_government")
        assert "not a government" in d["en"].lower()
        assert "सरकारी वेबसाइट नहीं" in d["hi"]

    def test_states_no_guarantee_of_benefit(self):
        d = next(x for x in terms.CRITICAL_DISCLOSURES if x["id"] == "no_guarantee")
        assert "guarantee" in d["en"].lower() and d["hi"]

    def test_states_the_service_is_free(self):
        """Demands for money in this app's name are the obvious scam vector."""
        d = next(x for x in terms.CRITICAL_DISCLOSURES if x["id"] == "never_pay")
        assert "free" in d["en"].lower() and "fraud" in d["en"].lower()
        assert "निःशुल्क" in d["hi"] and "धोखाधड़ी" in d["hi"]

    def test_states_the_citizen_must_submit(self):
        d = next(x for x in terms.CRITICAL_DISCLOSURES
                 if x["id"] == "you_must_submit")
        assert "not an application" in d["en"].lower()

    def test_every_disclosure_is_bilingual(self):
        """Terms a person cannot read are not terms they have agreed to."""
        for section in (terms.CRITICAL_DISCLOSURES, terms.USER_OBLIGATIONS,
                        terms.PROHIBITED_USES, terms.OUR_COMMITMENTS,
                        terms.LIMITATIONS):
            for item in section:
                assert item.get("en"), item
                assert item.get("hi"), item

    def test_user_obligations_cite_the_statute(self):
        """These are the citizen's s15 duties, not house rules."""
        cited = [o for o in terms.USER_OBLIGATIONS if o.get("basis")]
        assert any("s15" in o["basis"] for o in cited)
        assert any("s9" in o["basis"] for o in cited)

    def test_warns_against_sharing_the_otp(self):
        o = next(x for x in terms.USER_OBLIGATIONS
                 if x["id"] == "keep_credentials_safe")
        assert "ask you for it" in o["en"].lower()

    def test_prohibits_charging_for_the_service(self):
        assert any("fee" in p["en"].lower() for p in terms.PROHIBITED_USES)

    def test_limitations_are_stated_honestly(self):
        ids = {x["id"] for x in terms.LIMITATIONS}
        assert {"scheme_information_accuracy", "form_accuracy",
                "eligibility_is_indicative"} <= ids

    def test_eligibility_is_described_as_a_guide_not_a_decision(self):
        lim = next(x for x in terms.LIMITATIONS
                   if x["id"] == "eligibility_is_indicative")
        assert "not a decision" in lim["en"].lower()

    def test_includes_grievance_contact(self):
        assert "service_levels" in terms.terms()["grievance"]

    def test_links_the_privacy_notice(self):
        assert terms.terms()["related"]["privacy_notice"] == "/api/dpdp/notice"
