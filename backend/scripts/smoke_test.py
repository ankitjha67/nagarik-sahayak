#!/usr/bin/env python3
"""End-to-end smoke test of the whole engine against a LIVE government form.

Run from the backend/ directory:

    python scripts/smoke_test.py                 # full run
    python scripts/smoke_test.py --offline       # skip the network stage

Stages
  1. Fetch a real, currently-published government form over the network
  2. Extract its fields (OCR if the form is a scan)
  3. Validate a citizen's answers
  4. Decide eligibility against the scheme's stated rules
  5. Screen for fraud and abuse
  6. Generate the filled PDF
  7. Re-run stages 3-5 against adversarial inputs and confirm each is caught

Needs no database and no LLM key. Exit code is non-zero if any stage fails, so
it doubles as a CI check.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# A real, verified-live government form (Haryana sports scholarship).
LIVE_FORM_URL = (
    "https://cdnbbsr.s3waas.gov.in/s3e069ea4c9c233d36ff9c7f329bc08ff1"
    "/uploads/2024/06/202406272030716079.pdf"
)
# A scanned form, to exercise the OCR path specifically.
SCANNED_FORM_URL = "https://pmkisan.gov.in/Documents/Kcc.pdf"

PASS, FAIL = "PASS", "FAIL"
_results: list[tuple[str, str, str]] = []


def check(stage: str, ok: bool, detail: str = "") -> bool:
    _results.append((PASS if ok else FAIL, stage, detail))
    print(f"  [{PASS if ok else FAIL}] {stage}" + (f" — {detail}" if detail else ""))
    return ok


def banner(title: str) -> None:
    print(f"\n{'─' * 74}\n{title}\n{'─' * 74}")


def make_valid_aadhaar(prefix11: str) -> str:
    """Build a synthetic Aadhaar with a correct checksum.

    Real Aadhaar numbers must never appear in a test fixture, so we generate
    numbers that are structurally valid but belong to nobody.
    """
    from validation import verhoeff_check_digit
    return prefix11 + verhoeff_check_digit(prefix11)


async def stage_fetch_and_extract(offline: bool) -> dict | None:
    banner("STAGE 1-2  Fetch a live government form and extract its fields")
    if offline:
        print("  (skipped: --offline)")
        return None

    from form_extractor import extract_form_fields

    import time
    t0 = time.time()
    result = await extract_form_fields(pdf_url=LIVE_FORM_URL)
    elapsed = time.time() - t0

    if result.get("error"):
        check("Live form extraction", False, result["error"][:70])
        return None

    fields = result.get("extractedFields", [])
    check("Downloaded live government PDF", True, LIVE_FORM_URL.split("/")[-1])
    check("Extracted form fields", len(fields) > 0,
          f"{len(fields)} fields in {elapsed:.1f}s via {result.get('_extraction_method')}")
    check("Fields are typed", any(f.get("type") != "text" for f in fields),
          ", ".join(sorted({f["type"] for f in fields})))
    check("Fields carry canonical profile keys",
          any(f.get("profileKey") == "name" for f in fields),
          f"e.g. {', '.join(f['profileKey'] for f in fields[:4])}")

    print(f"\n  Detected form: {result.get('schemeName', '?')[:66]}")
    print(f"  Category     : {result.get('category')}")
    for f in fields[:8]:
        print(f"    · {f['profileKey']:26s} {f['type']:9s} {f['labelEnglish'][:34]}")
    if len(fields) > 8:
        print(f"    … and {len(fields) - 8} more")
    return result


async def stage_ocr(offline: bool) -> None:
    banner("STAGE 2b  OCR path — a scanned form with no extractable text")
    if offline:
        print("  (skipped: --offline)")
        return

    from form_extractor import extract_form_fields, _HAS_TESSERACT

    if not _HAS_TESSERACT:
        check("OCR available", False,
              "tesseract not installed — scanned forms will yield no fields")
        return

    import time
    t0 = time.time()
    r = await extract_form_fields(pdf_url=SCANNED_FORM_URL)
    elapsed = time.time() - t0
    if r.get("error"):
        check("Scanned form extraction", False, r["error"][:70])
        return
    check("Scanned form read via OCR", r.get("_extraction_method") == "ocr",
          f"{r.get('totalFields')} fields in {elapsed:.1f}s")


def stage_legitimate_applicant() -> dict:
    banner("STAGE 3-5  A legitimate applicant")

    from eligibility_engine import evaluate_scheme
    from fraud_detection import ApplicantHistory, assess
    from data.gov_forms import get_by_name
    from validation import validate_profile

    scheme = get_by_name("Indira Gandhi National Old Age Pension")
    profile = {
        "name": "Kamla Devi",
        "father_husband_name": "Ram Prasad",
        "aadhaar_number": make_valid_aadhaar("48291736450"),
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
        "ration_card_number": "UP2619876543",
        "annual_income": 42000,
        "bank_account_number": "50100234567890",
        "ifsc_code": "SBIN0001234",
        "bank_name": "State Bank of India",
    }

    v = validate_profile(profile, scheme["extractedFields"])
    check("Validation passes", not v.is_blocking,
          f"{len(v.errors)} errors, {len(v.warnings)} warnings")

    e = evaluate_scheme(profile, scheme)
    check("Eligibility granted", e.is_eligible, e.summary_en[:60])

    risk = assess(profile, scheme, ApplicantHistory())
    check("No fraud signals raised", risk.decision.value == "allow",
          f"risk score {risk.score}")
    return profile


async def stage_generate_pdf(profile: dict) -> None:
    banner("STAGE 6  Generate the filled application PDF")

    from data.gov_forms import get_by_name
    from pdf_generator import generate_real_filled_form_pdf

    scheme = get_by_name("Indira Gandhi National Old Age Pension")
    out = Path("/tmp/smoke_filled_form.pdf")
    try:
        generate_real_filled_form_pdf(
            filled_fields=profile,
            scheme_name=scheme["schemeName"],
            scheme_name_hindi=scheme["schemeNameHindi"],
            sections=scheme["sections"],
            form_fields=scheme["extractedFields"],
            output_path=str(out),
            is_draft=True,
        )
    except Exception as e:
        check("PDF generated", False, f"{type(e).__name__}: {e}")
        return

    ok = out.exists() and out.stat().st_size > 1000
    check("PDF generated", ok,
          f"{out} ({out.stat().st_size:,} bytes)" if ok else "not written")
    if ok:
        check("Output is a valid PDF", out.read_bytes()[:4] == b"%PDF")


def stage_adversarial() -> None:
    banner("STAGE 7  Adversarial cases — each must be caught")

    from eligibility_engine import evaluate_scheme
    from fraud_detection import ApplicantHistory, assess
    from data.gov_forms import get_by_name
    from validation import validate_aadhaar, validate_ifsc, validate_profile

    pension = get_by_name("Indira Gandhi National Old Age Pension")
    widow = get_by_name("Widow and Destitute Women Pension (Haryana)")
    sukanya = get_by_name("Sukanya Samriddhi Yojana")
    base_aadhaar = make_valid_aadhaar("48291736450")

    # T1 — fabricated identity
    check("T1 Invented Aadhaar rejected",
          validate_aadhaar("123456789012").is_blocking, "starts with 1")
    good = make_valid_aadhaar("23456789012")
    tampered = good[:5] + str((int(good[5]) + 1) % 10) + good[6:]
    check("T1 Digit-tampered Aadhaar rejected",
          validate_aadhaar(tampered).is_blocking, "checksum failure")
    check("T1 Repeated-digit Aadhaar rejected",
          validate_aadhaar("999999999999").is_blocking, "placeholder pattern")
    check("T1 Malformed IFSC rejected",
          validate_ifsc("SB1N123").is_blocking, "wrong format")

    # T3 — age gaming for an old-age pension
    too_young = {"name": "Suresh", "age": 34, "is_bpl": "Yes",
                 "aadhaar_number": base_aadhaar}
    e = evaluate_scheme(too_young, pension)
    check("T3 Under-age old-age pension refused", not e.is_eligible,
          e.failed[0].message_en[:52] if e.failed else "")

    # T3 — age inflated to clear the threshold, contradicted by date of birth
    lying = {"name": "Suresh", "age": 62, "date_of_birth": "1992-06-01",
             "is_bpl": "Yes", "aadhaar_number": base_aadhaar}
    r = assess(lying, pension, ApplicantHistory())
    check("T3 Age contradicting date of birth flagged",
          any(s.code == "age_dob_mismatch" for s in r.signals),
          f"risk {r.score}")

    # T3 — a man applying for a women-only pension
    male = {"name": "Mohan", "gender": "Male", "age": 45,
            "marital_status": "Married", "aadhaar_number": base_aadhaar}
    r = assess(male, widow, ApplicantHistory())
    check("T3 Gender mismatch on women-only scheme flagged",
          any(s.code == "gender_scheme_mismatch" for s in r.signals),
          f"risk {r.score}")
    e = evaluate_scheme(male, widow)
    check("T3 Gender rule also fails eligibility", not e.is_eligible)

    # T3 — over-age child for Sukanya Samriddhi
    old_child = {"girl_child_name": "Anu", "girl_child_age": 14}
    r = assess(old_child, sukanya, ApplicantHistory())
    check("T3 Over-age child for Sukanya flagged",
          any(s.code == "child_age_ineligible" for s in r.signals))
    check("T3 Over-age child also fails eligibility",
          not evaluate_scheme(old_child, sukanya).is_eligible)

    # T2 — means-test gaming
    rich_farmer = {"name": "Vikram", "annual_income": 0,
                   "land_holding_acres": 25, "aadhaar_number": base_aadhaar}
    r = assess(rich_farmer, None, ApplicantHistory())
    check("T2 Zero income with 25 acres flagged",
          any(s.code == "zero_income_with_land" for s in r.signals),
          f"risk {r.score}")

    taxpayer = {"name": "Anil", "is_income_tax_payer": "Yes",
                "annual_income": 90000}
    check("T2 Taxpayer declaring poverty income flagged",
          any(s.code == "taxpayer_low_income"
              for s in assess(taxpayer, None, ApplicantHistory()).signals))

    bpl_rich = {"name": "Rekha", "is_bpl": "Yes", "annual_income": 1200000}
    check("T2 BPL claim with high income flagged",
          any(s.code == "bpl_high_income"
              for s in assess(bpl_rich, None, ApplicantHistory()).signals))

    # T5 — benefit diversion: many genuine applicants, one collecting account
    clean = {"name": "Sita", "age": 70, "is_bpl": "Yes",
             "aadhaar_number": base_aadhaar}
    r = assess(clean, pension,
               ApplicantHistory(users_sharing_bank_account=12))
    check("T5 Shared collection account escalated",
          r.decision.value == "escalate",
          f"risk {r.score}, 12 applicants on one account")

    # T1 — one Aadhaar across several accounts
    r = assess(clean, pension, ApplicantHistory(users_sharing_aadhaar=4))
    check("T1 Aadhaar reused across accounts flagged",
          any(s.code == "aadhaar_shared_across_users" for s in r.signals),
          f"risk {r.score}")

    # T4 — duplicate and household claims
    r = assess(clean, pension,
               ApplicantHistory(prior_applications_same_scheme=3))
    check("T4 Repeat application flagged",
          any(s.code == "duplicate_scheme_application" for s in r.signals))
    r = assess(clean, pension, ApplicantHistory(household_claims_same_scheme=4))
    check("T4 Household double-dipping flagged",
          any(s.code == "household_duplicate_claim" for s in r.signals))

    # T6 — bulk filing
    r = assess(clean, pension, ApplicantHistory(applications_last_24h=45))
    check("T6 Bulk filing flagged",
          any(s.code.startswith("velocity") for s in r.signals),
          f"risk {r.score}")

    # Missing mandatory data must be caught before a form is issued
    v = validate_profile({"name": "Ramesh"}, pension["extractedFields"])
    check("Missing required fields caught", v.is_blocking,
          f"{len(v.errors)} required fields absent")

    # ── False-positive guards: legitimate people must NOT be penalised ──
    shared_phone = assess(clean, pension, ApplicantHistory(users_sharing_mobile=6))
    check("FP guard: family sharing one phone is not flagged",
          shared_phone.decision.value == "allow",
          f"risk {shared_phone.score}")

    destitute = {"name": "Phoolwati", "age": 72, "annual_income": 0,
                 "is_bpl": "Yes", "aadhaar_number": base_aadhaar}
    v = validate_profile(destitute, None)
    check("FP guard: genuine zero income warns but never blocks",
          not v.is_blocking and len(v.warnings) > 0,
          "income certificate requested, application proceeds")

    e = evaluate_scheme({"name": "Partial"}, pension)
    check("FP guard: incomplete form is not treated as ineligible",
          e.verdict.value == "incomplete",
          "asks for missing fields instead of refusing")


async def stage_gate_integration() -> None:
    banner("STAGE 8  Combined gate — the decision the API actually returns")

    from data.gov_forms import get_by_name
    from fraud_detection import ApplicantHistory
    from services import application_guard

    pension = get_by_name("Indira Gandhi National Old Age Pension")
    aadhaar = make_valid_aadhaar("48291736450")
    common = {
        "name": "Kamla Devi", "father_husband_name": "Ram Prasad",
        "aadhaar_number": aadhaar, "date_of_birth": "1958-04-12", "age": 68,
        "gender": "Female", "category": "OBC", "mobile_number": "9876543210",
        "address_line": "House 42", "district": "Sitapur",
        "state": "Uttar Pradesh", "pincode": "261001", "is_bpl": "Yes",
        "annual_income": 42000, "bank_account_number": "50100234567890",
        "ifsc_code": "SBIN0001234", "bank_name": "State Bank of India",
    }

    cases = [
        ("Legitimate applicant", common, ApplicantHistory(), "approved", True),
        ("Invalid Aadhaar", {**common, "aadhaar_number": "111111111111"},
         ApplicantHistory(), "blocked_invalid_data", False),
        ("Too young for the scheme", {**common, "age": 30, "date_of_birth": "1996-04-12"},
         ApplicantHistory(), "blocked_not_eligible", False),
        ("Payments funnelled to one account", common,
         ApplicantHistory(users_sharing_bank_account=12),
         "approved_with_review", True),
    ]

    for label, profile, history, expected, should_issue in cases:
        g = await application_guard.evaluate_application(
            profile=profile, scheme=pension, history=history, check_fraud=True,
        )
        ok = g.outcome.value == expected and g.may_issue_form == should_issue
        reason = (g.reasons_en[0][:44] if g.reasons_en else "")
        check(f"Gate: {label}", ok, f"{g.outcome.value} — {reason}")

    # An audit record must exist for every decision, for appeal purposes.
    g = await application_guard.evaluate_application(
        profile={**common, "age": 30, "date_of_birth": "1996-04-12"},
        scheme=pension, history=ApplicantHistory(), check_fraud=True,
    )
    rec = application_guard.audit_record("user123", g)
    check("Refusals produce an audit record",
          rec["outcome"] == "blocked_not_eligible" and bool(rec["decided_at"]),
          f"fields: {', '.join(rec['failed_rule_fields'])}")


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true",
                    help="Skip stages that need network access")
    args = ap.parse_args()

    print("=" * 74)
    print("NAGARIK SAHAYAK — FULL ENGINE SMOKE TEST")
    print("=" * 74)

    await stage_fetch_and_extract(args.offline)
    await stage_ocr(args.offline)
    profile = stage_legitimate_applicant()
    await stage_generate_pdf(profile)
    stage_adversarial()
    await stage_gate_integration()

    passed = sum(1 for s, _, _ in _results if s == PASS)
    failed = sum(1 for s, _, _ in _results if s == FAIL)
    banner("SUMMARY")
    print(f"  {passed} passed, {failed} failed, {len(_results)} checks total")
    if failed:
        print("\n  Failed checks:")
        for status, stage, detail in _results:
            if status == FAIL:
                print(f"    · {stage} — {detail}")
    print()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
