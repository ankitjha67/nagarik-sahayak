"""Tests for form intake — collecting every detail a form needs, then filling.

The intake brain is pure: it takes a form's fields and whatever is stored about
a citizen and works out what to ask next, validates each answer, and decides
when the form can be filled. These run with no server, database or network.

Two behaviours matter most and are easy to regress:

* The Aadhaar number is *transient* — asked for at fill time, used once, never
  stored. A naive loop would ask for it forever, because the store strips it.
* Absence is not invalidity — an unfinished form is not a rejected one, so a
  blank optional answer is a valid "skip" and only a malformed value is refused.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.gov_forms import get_by_name  # noqa: E402
from services import form_intake as fi  # noqa: E402


SCHEME = "Saraswati Vidya Yojana Scholarship"


def _fields():
    return get_by_name(SCHEME)["extractedFields"]


def _field(key):
    return next(f for f in _fields() if fi.field_key(f) == key)


# ── Discovery ────────────────────────────────────────────────────────────

def test_collect_fields_dedupes_across_schemes():
    a = {"extractedFields": [{"profileKey": "name"}, {"profileKey": "mobile_number"}]}
    b = {"extractedFields": [{"profileKey": "mobile_number"}, {"profileKey": "pincode"}]}
    keys = [fi.field_key(f) for f in fi.collect_fields([a, b])]
    assert keys == ["name", "mobile_number", "pincode"]


def test_aadhaar_is_transient_not_a_missing_field():
    state = fi.intake_state({}, _fields())
    transient_keys = {fi.field_key(f) for f in state["transient"]}
    assert "aadhaar_number" in transient_keys
    # It must never appear as something still to be collected into the profile.
    missing = {fi.field_key(f) for f in state["missingRequired"] + state["missingOptional"]}
    assert "aadhaar_number" not in missing


def test_a_known_field_is_not_asked_again():
    profile = {"name": "Nisha Patel", "mobile_number": "9825011223"}
    state = fi.intake_state(profile, _fields())
    known = {k["profileKey"] for k in state["known"]}
    assert {"name", "mobile_number"} <= known
    assert state["nextQuestion"]["profileKey"] not in known


def test_required_asked_before_optional():
    # With every required field answered, the next question must be an optional
    # one — required are never skipped ahead of.
    required = {fi.field_key(f) for f in _fields() if f.get("required")}
    profile = {k: _plausible(k) for k in required}
    state = fi.intake_state(profile, _fields())
    assert state["requiredComplete"] is True
    assert state["allComplete"] is False
    nxt = state["nextQuestion"]["profileKey"]
    assert nxt not in required  # it is one of the optional fields


def test_all_complete_when_everything_answered():
    storable = {fi.field_key(f) for f in _fields()
                if fi.field_key(f) not in fi.TRANSIENT_KEYS}
    profile = {k: _plausible(k) for k in storable}
    state = fi.intake_state(profile, _fields())
    assert state["requiredComplete"] and state["allComplete"]
    assert state["nextQuestion"] is None
    assert state["progress"] == 100.0


# ── Questions ────────────────────────────────────────────────────────────

def test_question_carries_label_type_and_options():
    q = fi.question_for(_field("gender"))
    assert q["type"] == "select"
    assert q["options"] == ["Male", "Female", "Transgender"]
    assert q["labelHindi"] and q["labelEnglish"]


def test_transient_question_is_flagged_and_noted():
    q = fi.question_for(_field("aadhaar_number"))
    assert q["transient"] is True
    # The citizen is reassured it is not kept.
    assert "not stored" in q["note_en"].lower()


# ── Answer validation ──────────────────────────────────────────────────────

def test_date_answer_is_normalised_to_iso():
    value, en, hi = fi.validate_answer(_field("date_of_birth"), "14-08-2005")
    assert value == "2005-08-14" and not en


def test_bad_mobile_is_rejected_in_both_languages():
    value, en, hi = fi.validate_answer(_field("mobile_number"), "98-345")
    assert value is None and en and hi


def test_pincode_must_be_six_digits():
    assert fi.validate_answer(_field("pincode"), "3962")[0] is None
    assert fi.validate_answer(_field("pincode"), "396230")[0] == "396230"


def test_ifsc_is_upper_cased():
    assert fi.validate_answer(_field("ifsc_code"), "sbin0011785")[0] == "SBIN0011785"


def test_select_matches_case_insensitively_and_stores_canonical():
    assert fi.validate_answer(_field("gender"), "female")[0] == "Female"
    assert fi.validate_answer(_field("gender"), "nonsense")[0] is None


def test_required_blank_is_an_error_optional_blank_is_a_skip():
    req_value, req_err, _ = fi.validate_answer(_field("name"), "")
    assert req_value is None and req_err
    opt_value, opt_err, _ = fi.validate_answer(_field("branch_name"), "")
    assert opt_value == "" and not opt_err


def test_transient_aadhaar_still_validates():
    # It is not stored, but a typo must still be caught before it is written.
    from validation import verhoeff_check_digit
    valid = "48291736450" + verhoeff_check_digit("48291736450")
    assert fi.validate_answer(_field("aadhaar_number"), valid)[0] == valid
    assert fi.validate_answer(_field("aadhaar_number"), "123456789012")[0] is None


# ── helpers ────────────────────────────────────────────────────────────────

def _plausible(key):
    """A valid value for each field key, so completeness can be simulated."""
    from validation import verhoeff_check_digit
    return {
        "name": "Nisha Patel",
        "father_husband_name": "Dinesh Patel",
        "aadhaar_number": "48291736450" + verhoeff_check_digit("48291736450"),
        "date_of_birth": "2004-09-12",
        "gender": "Female",
        "email": "n@example.com",
        "marital_status": "Single",
        "mobile_number": "9825011223",
        "address_line": "House 58, Silvassa",
        "district": "Dadra and Nagar Haveli",
        "state": "Dadra and Nagar Haveli and Daman and Diu",
        "pincode": "396230",
        "tehsil": "Silvassa",
        "institution_name": "Government College",
        "course_name": "B.Com",
        "roll_number": "DNH-2024-0137",
        "last_exam_percentage": 78,
        "bank_account_number": "31920847561023",
        "ifsc_code": "SBIN0011785",
        "bank_name": "State Bank of India",
        "branch_name": "Silvassa Main",
    }.get(key, "x")
