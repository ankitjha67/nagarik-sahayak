"""Malformed input must get a 4xx, never a 500 — and never leak an Aadhaar.

Found by an adversarial probe of the live API. Every case here once answered
500 (a Prisma validation error on a user id that was not an ObjectId, a string
iterated as a list, a dict.update() on a string) or 200 where a refusal was
due. Runs against a live server, like the other integration tests.
"""
import json
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
SCHEME = "Saraswati Vidya Yojana Scholarship"

pytestmark = pytest.mark.skipif(not BASE_URL, reason="needs a live server")


@pytest.fixture(scope="module")
def user_id():
    phone = f"9602{int(time.time()) % 1000000:06d}"
    requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
    return requests.post(f"{BASE_URL}/api/auth/verify-otp",
                         json={"phone": phone, "otp": "123456"}).json()["user_id"]


MALFORMED_IDS = ["not-an-objectid", "'; drop", "x" * 24, 12345, ["x"], "000000000000000000000000"]


@pytest.mark.parametrize("bad", MALFORMED_IDS)
@pytest.mark.parametrize("path,extra", [
    ("/api/v2/smart-profiler", {}),
    ("/api/v2/answer-field", {"profileKey": "name", "value": "A"}),
    ("/api/v2/generate-filled-forms", {}),
])
def test_v2_endpoints_reject_malformed_user_id_cleanly(path, extra, bad, user_id):
    """A malformed or foreign id is refused with a 4xx, never a 500.

    Anonymous: 401 (the request names a user and carries no identity).
    Signed in as someone else: 403 (not yours), or 400/422 for an id that
    is not even a string."""
    body = {"user_id": bad, "scheme_names": [SCHEME], **extra}
    r = requests.post(f"{BASE_URL}{path}", json=body)
    assert r.status_code in (400, 401, 422), f"anonymous {path} {bad!r} -> {r.status_code}"
    r = requests.post(f"{BASE_URL}{path}", json=body, headers={"X-User-Id": user_id})
    # 403 for a string that is not this caller; 400/422 for an id that is not
    # a string at all; 404 when a non-string slips past binding to the lookup.
    assert r.status_code in (400, 403, 404, 422), f"signed-in {path} {bad!r} -> {r.status_code}"


@pytest.mark.parametrize("bad", ["not-an-objectid", "'; drop", "000000000000000000000000"])
def test_profile_routes_reject_malformed_user_id_cleanly(bad, user_id):
    # Anonymous callers are refused before the id is even looked at.
    assert requests.get(f"{BASE_URL}/api/profile/{bad}").status_code == 401
    assert requests.get(f"{BASE_URL}/api/v2/user-profile/{bad}").status_code == 401
    # A signed-in citizen asking about any id but their own is refused too:
    # the malformed id is never a path to a 500 or to another person's data.
    h = {"X-User-Id": user_id}
    assert requests.get(f"{BASE_URL}/api/profile/{bad}", headers=h).status_code == 403
    assert requests.get(f"{BASE_URL}/api/v2/user-profile/{bad}", headers=h).status_code == 403
    assert requests.post(f"{BASE_URL}/api/v2/user-profile/{bad}",
                         json={"fields": {"name": "A"}}, headers=h).status_code == 403


def test_chat_with_malformed_user_id_does_not_crash():
    # Chat tolerates unknown ids (demo mode sends placeholders), but a
    # malformed one must not take the request down.
    r = requests.post(f"{BASE_URL}/api/chat",
                      json={"user_id": "not-an-objectid", "content": "namaste", "language": "hi"})
    assert r.status_code < 500


def test_chat_requires_a_user_id():
    r = requests.post(f"{BASE_URL}/api/chat",
                      json={"user_id": "", "content": "namaste", "language": "hi"})
    assert r.status_code == 400


@pytest.mark.parametrize("names", [SCHEME, [], [None, 5], [""], "   "])
def test_scheme_names_must_be_a_list_of_names(user_id, names):
    for path in ("/api/v2/smart-profiler", "/api/v2/generate-filled-forms"):
        r = requests.post(f"{BASE_URL}{path}", json={"user_id": user_id, "scheme_names": names})
        assert r.status_code == 400, f"{path} {names!r} -> {r.status_code}"


def test_profile_fields_must_be_an_object(user_id):
    r = requests.post(f"{BASE_URL}/api/v2/user-profile/{user_id}", json={"fields": "name=x"})
    assert r.status_code == 400


def test_answer_field_rejects_a_key_the_form_does_not_have(user_id):
    for key in ("ssn", "__proto__", "constructor"):
        r = requests.post(f"{BASE_URL}/api/v2/answer-field",
                          json={"user_id": user_id, "scheme_names": [SCHEME],
                                "profileKey": key, "value": "x"})
        assert r.status_code == 400


def test_answer_field_tolerates_any_value_type(user_id):
    for value in (["a", "b"], {"a": 1}, 12, None, "x" * 100_000):
        r = requests.post(f"{BASE_URL}/api/v2/answer-field",
                          json={"user_id": user_id, "scheme_names": [SCHEME],
                                "profileKey": "address_line", "value": value})
        assert r.status_code == 200
        assert "accepted" in r.json()


def test_full_aadhaar_is_never_echoed_or_stored(user_id):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from validation import verhoeff_check_digit
    aadhaar = "48291736450" + verhoeff_check_digit("48291736450")

    r = requests.post(f"{BASE_URL}/api/v2/answer-field",
                      json={"user_id": user_id, "scheme_names": [SCHEME],
                            "profileKey": "aadhaar_number", "value": aadhaar})
    assert r.status_code == 200 and r.json()["accepted"]
    assert aadhaar not in r.text
    assert r.json()["storedValue"].endswith(aadhaar[-4:])     # masked, last four visible

    stored = requests.get(f"{BASE_URL}/api/v2/user-profile/{user_id}").text
    assert aadhaar not in stored
    assert "aadhaar_number_last4" in json.loads(stored)["fullProfile"]


def test_ssrf_targets_are_refused_for_live_extraction(user_id):
    # Live extraction downloads on the server's behalf, so it needs a signed-in
    # caller first; then every internal or non-http target is refused.
    assert requests.post(f"{BASE_URL}/api/forms/extract-live",
                         json={"pdf_url": "http://127.0.0.1:8006/api/schemes"}).status_code == 401
    for url in ("http://127.0.0.1:8006/api/schemes", "http://169.254.169.254/latest/meta-data/",
                "file:///etc/passwd", "javascript:alert(1)"):
        r = requests.post(f"{BASE_URL}/api/forms/extract-live", json={"pdf_url": url},
                          headers={"X-User-Id": user_id})
        assert r.status_code in (400, 422), f"{url} -> {r.status_code}"
