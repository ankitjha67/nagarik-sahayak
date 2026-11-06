"""Tests for the hashed, indexed identity fingerprints.

Three properties matter:

  * Two applicants using the same identifier produce the same digest, however
    they typed it — otherwise a fraudster evades detection with a space.
  * The stored digest does not reveal the identifier, and is not enumerable
    without the secret salt.
  * Looking up shared identifiers is a counted query, not a scan of every user.
"""
import os
import pytest
from types import SimpleNamespace

import identity_index
from identity_index import (
    INDEXED_IDENTIFIERS, _canonical, count_sharing, fingerprint,
    fingerprints_for, merge_into_update,
)


@pytest.fixture(autouse=True)
def fixed_salt(monkeypatch):
    """Pin the salt so digests are reproducible within a test run."""
    monkeypatch.setenv("IDENTITY_HASH_SALT", "test-salt-abc123")
    yield


class TestCanonicalisation:
    @pytest.mark.parametrize("written", [
        "234567890124", "2345 6789 0124", "2345-6789-0124", " 234567890124 ",
    ])
    def test_aadhaar_formats_converge(self, written):
        """A space must not defeat shared-identifier detection."""
        assert _canonical(written, "aadhaar_number") == "234567890124"

    def test_mobile_tolerates_country_code(self):
        assert (_canonical("+91 98765 43210", "mobile_number")
                == _canonical("9876543210", "mobile_number"))

    def test_ration_card_is_alphanumeric_case_insensitive(self):
        assert (_canonical("UP-26/1987 6543", "ration_card_number")
                == _canonical("up2619876543", "ration_card_number"))

    def test_empty_stays_empty(self):
        assert _canonical("", "aadhaar_number") == ""
        assert _canonical(None, "aadhaar_number") == ""


class TestFingerprint:
    def test_same_identifier_same_digest(self):
        assert (fingerprint("2345 6789 0124", "aadhaar_number")
                == fingerprint("234567890124", "aadhaar_number"))

    def test_different_identifiers_differ(self):
        assert (fingerprint("234567890124", "aadhaar_number")
                != fingerprint("234567890125", "aadhaar_number"))

    def test_same_digits_in_different_fields_do_not_collide(self):
        """A number reused across two fields must not look like a match."""
        assert (fingerprint("9876543210", "mobile_number")
                != fingerprint("9876543210", "bank_account_number"))

    def test_digest_does_not_contain_the_identifier(self):
        digest = fingerprint("234567890124", "aadhaar_number")
        assert "234567890124" not in digest
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)

    def test_salt_changes_every_digest(self, monkeypatch):
        """Rotating the salt invalidates stored digests — hence the backfill."""
        before = fingerprint("234567890124", "aadhaar_number")
        monkeypatch.setenv("IDENTITY_HASH_SALT", "a-completely-different-salt")
        assert fingerprint("234567890124", "aadhaar_number") != before

    def test_not_enumerable_without_the_salt(self, monkeypatch):
        """A bare SHA-256 of a 12-digit number is brute-forceable; this is not."""
        import hashlib
        digest = fingerprint("234567890124", "aadhaar_number")
        naive = hashlib.sha256(b"234567890124").hexdigest()
        assert digest != naive

    def test_missing_identifier_yields_empty(self):
        assert fingerprint("", "aadhaar_number") == ""
        assert fingerprint(None, "aadhaar_number") == ""


class TestFingerprintsForProfile:
    def test_maps_every_indexed_field(self):
        fps = fingerprints_for({
            "aadhaar_number": "234567890124",
            "bank_account_number": "50100234567890",
            "mobile_number": "9876543210",
            "ration_card_number": "UP2619876543",
        })
        assert set(fps) == set(INDEXED_IDENTIFIERS.values())
        assert all(v for v in fps.values())

    def test_absent_fields_produce_empty_digests(self):
        """A cleared field must clear its digest, not leave a stale match."""
        fps = fingerprints_for({"name": "Kamla"})
        assert all(v == "" for v in fps.values())

    def test_handles_empty_and_none(self):
        assert all(v == "" for v in fingerprints_for({}).values())
        assert all(v == "" for v in fingerprints_for(None).values())

    def test_merge_preserves_original_payload(self):
        data = merge_into_update(
            {"fullProfile": {"x": 1}, "profileLastUpdated": "now"},
            {"aadhaar_number": "234567890124"},
        )
        assert data["fullProfile"] == {"x": 1}
        assert data["profileLastUpdated"] == "now"
        assert data["aadhaarFp"]

    def test_no_raw_identifier_reaches_the_update_payload(self):
        data = merge_into_update({}, {
            "aadhaar_number": "234567890124",
            "bank_account_number": "50100234567890",
        })
        blob = str(data)
        assert "234567890124" not in blob and "50100234567890" not in blob


class FakePrisma:
    """Records how the user table was queried."""
    def __init__(self, count_result=0, fail=False):
        self.count_result, self.fail = count_result, fail
        self.count_calls, self.find_many_calls = [], 0
        outer = self

        class UserTable:
            async def count(self, where=None):
                if outer.fail:
                    raise RuntimeError("database unavailable")
                outer.count_calls.append(where)
                return outer.count_result

            async def find_many(self, where=None):
                outer.find_many_calls += 1
                return []

        self.user = UserTable()


class TestCountSharing:
    @pytest.mark.asyncio
    async def test_counts_other_users(self):
        db = FakePrisma(count_result=3)
        n = await count_sharing(db, "aadhaarFp", "deadbeef", exclude_user_id="u1")
        assert n == 3
        assert db.count_calls[0] == {"aadhaarFp": "deadbeef", "id": {"not": "u1"}}

    @pytest.mark.asyncio
    async def test_empty_digest_counts_zero_without_querying(self):
        """'Nobody supplied this' must never read as 'everybody shares it'."""
        db = FakePrisma(count_result=99)
        assert await count_sharing(db, "aadhaarFp", "") == 0
        assert db.count_calls == []

    @pytest.mark.asyncio
    async def test_database_failure_degrades_to_zero(self):
        """Losing a fraud signal beats blocking a citizen on an outage."""
        db = FakePrisma(fail=True)
        assert await count_sharing(db, "aadhaarFp", "deadbeef") == 0

    @pytest.mark.asyncio
    async def test_uses_a_counted_query_not_a_scan(self):
        """The bug this replaced loaded every user on every application."""
        db = FakePrisma(count_result=1)
        await count_sharing(db, "aadhaarFp", "deadbeef", "u1")
        assert db.find_many_calls == 0, "must not enumerate users"


class TestBuildHistoryUsesTheIndex:
    @pytest.mark.asyncio
    async def test_no_user_table_scan(self, monkeypatch):
        """Guards the regression directly: build_history must not list users."""
        import sys, types
        import fraud_detection

        db = FakePrisma(count_result=2)

        class AppTable:
            async def find_many(self, where=None):
                return []

        db.application = AppTable()
        db.scheme = types.SimpleNamespace(
            find_first=lambda where=None: _async_none())

        fake_db_module = types.ModuleType("database")
        fake_db_module.prisma = db
        monkeypatch.setitem(sys.modules, "database", fake_db_module)

        history = await fraud_detection.build_history(
            "u1", {"aadhaar_number": "234567890124",
                   "bank_account_number": "50100234567890"}, "Some Scheme")

        assert db.find_many_calls == 0, "build_history still scans the user table"
        # Counts include the applicant themselves for the shared-identifier
        # signals, which compare "how many people use this number".
        assert history.users_sharing_aadhaar == 3
        assert history.users_sharing_bank_account == 3

    @pytest.mark.asyncio
    async def test_survives_database_outage(self, monkeypatch):
        import sys, types
        import fraud_detection

        fake_db_module = types.ModuleType("database")
        fake_db_module.prisma = FakePrisma(fail=True)
        monkeypatch.setitem(sys.modules, "database", fake_db_module)

        history = await fraud_detection.build_history("u1", {"aadhaar_number": "234567890124"}, "S")
        # Falls back to an all-clear history rather than raising.
        assert history.users_sharing_aadhaar >= 1


async def _async_none():
    return None
