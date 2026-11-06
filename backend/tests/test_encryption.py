"""Tests for encryption at rest and the central profile accessor.

The properties that matter:

  * ciphertext does not contain the plaintext, and is authenticated so tampering
    is detected rather than silently yielding altered data;
  * a nonce is never reused, since AES-GCM fails catastrophically if one is;
  * plaintext and ciphertext both read, so a backfill can run incrementally on a
    live system;
  * the Aadhaar non-storage rule holds on every write path, including erasure.
"""
import base64
import os

import pytest

from dpdp import crypto, profile_store
from dpdp.aadhaar_policy import AadhaarStorageViolation
from validation import verhoeff_check_digit

AADHAAR = "23456789012" + verhoeff_check_digit("23456789012")


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


class Row:
    """Stand-in for a Prisma user row."""
    def __init__(self, full=None, basic=None, uid="u1", phone="9876543210"):
        self.id, self.phone = uid, phone
        self.fullProfile, self.profile = full, basic
        self.createdAt = None


class TestKeyHandling:
    def test_generated_key_is_32_bytes(self):
        assert len(base64.urlsafe_b64decode(crypto.generate_key())) == 32

    def test_enabled_only_with_a_key(self, key):
        assert crypto.is_enabled() is True

    def test_disabled_without_a_key(self, no_key):
        assert crypto.is_enabled() is False

    def test_malformed_key_is_ignored(self, monkeypatch):
        monkeypatch.setenv("DATA_ENCRYPTION_KEY", "not-base64!!")
        assert crypto.is_enabled() is False

    def test_wrong_length_key_is_ignored(self, monkeypatch):
        monkeypatch.setenv("DATA_ENCRYPTION_KEY",
                           base64.urlsafe_b64encode(os.urandom(16)).decode())
        assert crypto.is_enabled() is False


class TestEncryption:
    def test_roundtrip(self, key):
        assert crypto.decrypt(crypto.encrypt("Kamla Devi")) == "Kamla Devi"

    def test_ciphertext_hides_the_plaintext(self, key):
        ct = crypto.encrypt(f"aadhaar {AADHAAR}")
        assert AADHAAR not in ct and "aadhaar" not in ct

    def test_ciphertext_is_marked(self, key):
        assert crypto.is_encrypted(crypto.encrypt("x"))
        assert not crypto.is_encrypted("plain text")

    def test_nonce_is_never_reused(self, key):
        """AES-GCM leaks catastrophically if a (key, nonce) pair repeats."""
        outputs = {crypto.encrypt("same input") for _ in range(50)}
        assert len(outputs) == 50

    def test_tampering_is_detected(self, key):
        """GCM is authenticated: altered ciphertext must fail, not decrypt."""
        ct = crypto.encrypt("annual_income: 42000")
        body = ct.rsplit(":", 1)[1]
        flipped = ("A" if body[0] != "A" else "B") + body[1:]
        tampered = ct.rsplit(":", 1)[0] + ":" + flipped
        with pytest.raises(crypto.DecryptionError):
            crypto.decrypt(tampered)

    def test_wrong_key_cannot_decrypt(self, key, monkeypatch):
        ct = crypto.encrypt("secret")
        monkeypatch.setenv("DATA_ENCRYPTION_KEY", crypto.generate_key())
        with pytest.raises(crypto.DecryptionError):
            crypto.decrypt(ct)

    def test_old_key_still_reads_during_rotation(self, key, monkeypatch):
        """Rotation must not require a flag-day migration."""
        original = os.environ["DATA_ENCRYPTION_KEY"]
        ct = crypto.encrypt("written with the old key")
        monkeypatch.setenv("DATA_ENCRYPTION_KEY", crypto.generate_key())
        monkeypatch.setenv("DATA_ENCRYPTION_KEY_OLD", original)
        assert crypto.decrypt(ct) == "written with the old key"

    def test_never_double_encrypts(self, key):
        once = crypto.encrypt("x")
        assert crypto.encrypt(once) == once

    def test_plaintext_passes_through_on_decrypt(self, key):
        """Lets a backfill convert rows gradually on a live system."""
        assert crypto.decrypt("legacy plaintext") == "legacy plaintext"

    def test_passthrough_without_a_key(self, no_key):
        assert crypto.encrypt("visible") == "visible"

    def test_empty_values(self, key):
        assert crypto.encrypt("") == ""
        assert crypto.decrypt("") == ""

    def test_json_roundtrip(self, key):
        data = {"name": "कमला देवी", "income": 42000, "nested": {"a": [1, 2]}}
        assert crypto.decrypt_json(crypto.encrypt_json(data)) == data

    def test_json_handles_unicode(self, key):
        """Hindi must survive the round trip intact."""
        assert crypto.decrypt_json(crypto.encrypt_json({"n": "कमला"}))["n"] == "कमला"

    def test_decrypt_json_accepts_a_dict(self, key):
        assert crypto.decrypt_json({"already": "parsed"}) == {"already": "parsed"}

    def test_malformed_envelope_raises(self, key):
        with pytest.raises(crypto.DecryptionError):
            crypto.decrypt(crypto.ENVELOPE_PREFIX + "garbage")

    def test_status_reports_the_gap(self, no_key):
        st = crypto.status()
        assert st["enabled"] is False and "DATA_ENCRYPTION_KEY" in st["warning"]

    def test_status_warns_about_key_loss(self, key):
        assert "no recovery" in crypto.status()["key_loss_warning"].lower()


class TestProfileStore:
    def test_reads_plaintext_json(self, no_key):
        assert profile_store.load(Row(full='{"name": "Kamla"}'))["name"] == "Kamla"

    def test_reads_a_dict(self, no_key):
        assert profile_store.load(Row(full={"name": "Kamla"}))["name"] == "Kamla"

    def test_reads_ciphertext(self, key):
        row = Row(full=crypto.encrypt_json({"name": "Kamla"}))
        assert profile_store.load(row)["name"] == "Kamla"

    def test_full_profile_wins_over_basic(self, no_key):
        row = Row(full={"name": "From Full"},
                  basic='{"name": "From Basic", "district": "Sitapur"}')
        merged = profile_store.load(row)
        assert merged["name"] == "From Full"
        assert merged["district"] == "Sitapur"

    def test_empty_row(self, no_key):
        assert profile_store.load(Row()) == {}

    def test_malformed_blob_does_not_crash(self, no_key):
        assert profile_store.load(Row(full="{not json")) == {}

    def test_undecryptable_row_raises_rather_than_looking_empty(self, key, monkeypatch):
        """An empty profile could trigger a wrongful refusal, so this must raise."""
        row = Row(full=crypto.encrypt_json({"name": "Kamla"}))
        monkeypatch.setenv("DATA_ENCRYPTION_KEY", crypto.generate_key())
        monkeypatch.delenv("DATA_ENCRYPTION_KEY_OLD", raising=False)
        with pytest.raises(crypto.DecryptionError):
            profile_store.load(row)

    def test_prepare_encrypts_when_configured(self, key):
        stored, plain = profile_store.prepare_full_profile({"name": "Kamla"})
        assert crypto.is_encrypted(stored)
        assert plain == {"name": "Kamla"}

    def test_prepare_passes_through_without_a_key(self, no_key):
        stored, _ = profile_store.prepare_full_profile({"name": "Kamla"})
        assert stored == {"name": "Kamla"}

    def test_aadhaar_is_stripped_before_storage(self, key):
        stored, plain = profile_store.prepare_full_profile(
            {"name": "Kamla", "aadhaar_number": AADHAAR})
        assert "aadhaar_number" not in plain
        assert plain["aadhaar_number_last4"] == AADHAAR[-4:]
        assert AADHAAR not in str(stored)

    def test_aadhaar_stripped_even_without_encryption(self, no_key):
        """Non-storage is a separate obligation and must not depend on a key."""
        _, plain = profile_store.prepare_full_profile({"aadhaar_number": AADHAAR})
        assert "aadhaar_number" not in plain

    def test_basic_profile_is_a_string_column(self, key):
        stored, _ = profile_store.prepare_basic_profile({"name": "Kamla"})
        assert isinstance(stored, str)

    def test_encrypted_row_survives_a_full_roundtrip(self, key):
        """The end-to-end guarantee: write, store, read back unchanged."""
        original = {"name": "कमला देवी", "annual_income": 42000,
                    "aadhaar_number": AADHAAR, "district": "Sitapur"}
        stored, _ = profile_store.prepare_full_profile(original)
        recovered = profile_store.load(Row(full=stored))
        assert recovered["name"] == "कमला देवी"
        assert recovered["annual_income"] == 42000
        assert recovered["district"] == "Sitapur"
        # The Aadhaar is gone; its last four remain.
        assert "aadhaar_number" not in recovered
        assert recovered["aadhaar_number_last4"] == AADHAAR[-4:]

    def test_status_reports_both_controls(self, key):
        st = profile_store.status()
        assert st["encryption"]["enabled"] is True
        assert "Requesting Entity" in st["aadhaar_storage"]["basis"]
