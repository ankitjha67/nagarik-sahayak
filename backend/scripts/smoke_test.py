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
  8. The combined gate the API actually returns
  9. Central/State catalog coverage and domicile gating
 10. Demo applicants in four States, end to end
 11. KYC: offline Aadhaar, tolerant matching, and what it decides
 12. Language coverage across the Eighth Schedule
 13. DPDP: notice scope and the processing register
 14. The wiring between all of the above, as the API traverses it
 15. Form geometry: the ruled grid, and values staying inside it

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


def stage_catalog_coverage() -> None:
    banner("STAGE 9  Catalog — Central and State coverage")

    from data.gov_forms import catalog_states, get_catalog

    catalog = get_catalog()
    central = [e for e in catalog if e["level"] == "Central"]
    state = [e for e in catalog if e["level"] == "State"]
    check("Catalog spans both levels", bool(central) and bool(state),
          f"{len(central)} Central, {len(state)} State, {len(catalog)} total")
    check("Coverage reaches most of the country", len(catalog_states()) >= 25,
          f"{len(catalog_states())} States and UTs")

    # Every State scheme must be gated on residence, or it is offered to people
    # who will be turned away at the counter.
    ungated = [
        e["schemeName"] for e in state
        if not [r for r in e["eligibilityCriteria"]["rules"]
                if r["field"] == "state" and r["value"] == e["state"]]
    ]
    check("Every State scheme is gated on residence", not ungated,
          ", ".join(ungated) or "all 23+ gated")

    # And the opposite error: a State view that hides Central schemes.
    bihar = get_catalog(state="Bihar")
    bihar_central = [e for e in bihar if e["level"] == "Central"]
    check("A State view still shows every Central scheme",
          len(bihar_central) == len(central),
          f"Bihar resident sees {len(bihar)} schemes "
          f"({len(bihar_central)} Central + {len(bihar) - len(bihar_central)} State)")

    foreign = [e["schemeName"] for e in bihar
               if e["level"] == "State" and e["state"] != "Bihar"]
    check("A State view hides other States' schemes", not foreign,
          ", ".join(foreign[:3]) or "no cross-State leakage")


def stage_state_applicants() -> None:
    banner("STAGE 10  Demo applicants across four States")

    from eligibility_engine import Verdict, evaluate_scheme
    from data.gov_forms import get_by_name, get_catalog
    from validation import validate_profile

    # Four demo citizens, each resident in a different State. Names and numbers
    # are synthetic; the Aadhaar values carry correct checksums but belong to
    # nobody.
    demos = [
        {
            "label": "Sunita Devi, 34, Madhya Pradesh",
            "scheme": "Mukhyamantri Ladli Behna Yojana (Madhya Pradesh)",
            "profile": {
                "name": "Sunita Devi", "father_husband_name": "Mahesh Kumar",
                "aadhaar_number": make_valid_aadhaar("39182746501"),
                "date_of_birth": "1992-03-15", "age": 34, "gender": "Female",
                "category": "OBC", "mobile_number": "9812345670",
                "marital_status": "Married", "state_family_id": "MP1234567890",
                "address_line": "12 Nehru Ward", "district": "Rewa",
                "state": "Madhya Pradesh", "pincode": "486001",
                "annual_income": 120000, "is_income_tax_payer": "No",
                "is_govt_employee": "No", "land_holding_acres": 1.5,
                "ration_card_type": "Priority Household (PHH)",
                "bank_account_number": "20100234567891", "ifsc_code": "SBIN0004321",
                "bank_name": "State Bank of India",
            },
        },
        {
            "label": "Meena Murugan, 41, Tamil Nadu",
            "scheme": "Kalaignar Magalir Urimai Thogai (Tamil Nadu)",
            "profile": {
                "name": "Meena Murugan", "father_husband_name": "Murugan S",
                "aadhaar_number": make_valid_aadhaar("51726394820"),
                "date_of_birth": "1985-07-22", "age": 41, "gender": "Female",
                "category": "General", "mobile_number": "9445566778",
                "marital_status": "Widowed",
                "address_line": "3/45 Anna Nagar", "district": "Madurai",
                "state": "Tamil Nadu", "pincode": "625020",
                "annual_income": 96000, "is_income_tax_payer": "No",
                "is_govt_employee": "No",
                "ration_card_type": "Priority Household (PHH)",
                "bank_account_number": "30987654321012", "ifsc_code": "IOBA0001234",
                "bank_name": "Indian Overseas Bank",
            },
        },
        {
            "label": "Anjali Basumatary, 52, Assam",
            "scheme": "Orunodoi (Assam)",
            "profile": {
                "name": "Anjali Basumatary", "father_husband_name": "Bipul Basumatary",
                "aadhaar_number": make_valid_aadhaar("62817394056"),
                "date_of_birth": "1974-11-02", "age": 52, "gender": "Female",
                "category": "ST", "mobile_number": "9678123456",
                "marital_status": "Married",
                "address_line": "Village Bhairabkunda", "district": "Udalguri",
                "state": "Assam", "pincode": "784509",
                "family_members": 5, "annual_income": 84000,
                "is_govt_employee": "No", "is_income_tax_payer": "No",
                "disability_type": "None",
                "ration_card_type": "Priority Household (PHH)",
                "bank_account_number": "40192837465012", "ifsc_code": "UCBA0002468",
                "bank_name": "UCO Bank",
            },
        },
        {
            "label": "Tenzing Bhutia, 29, Sikkim",
            "scheme": "Aama Yojana (Sikkim)",
            "profile": {
                "name": "Pema Bhutia", "father_husband_name": "Tenzing Bhutia",
                "aadhaar_number": make_valid_aadhaar("70918263540"),
                "date_of_birth": "1997-01-19", "age": 29, "gender": "Female",
                "category": "ST", "mobile_number": "9832145670",
                "marital_status": "Married", "number_of_daughters": 2,
                "address_line": "Upper Tadong", "district": "Gangtok",
                "state": "Sikkim", "pincode": "737102",
                "is_govt_employee": "No", "annual_income": 60000,
                "bank_account_number": "50223344556677", "ifsc_code": "SBIN0009876",
                "bank_name": "State Bank of India",
            },
        },
    ]

    for demo in demos:
        scheme = get_by_name(demo["scheme"])
        profile = demo["profile"]
        v = validate_profile(profile, scheme["extractedFields"])
        e = evaluate_scheme(profile, scheme)
        check(f"{demo['label']} — {scheme['schemeName'][:38]}",
              not v.is_blocking and e.verdict is Verdict.ELIGIBLE,
              f"{len(v.errors)} errors, verdict {e.verdict.value}")

    # The same citizen against the whole catalog: what a State resident is
    # actually shown, Central and State together.
    sunita = demos[0]["profile"]
    eligible = []
    for entry in get_catalog(state="Madhya Pradesh"):
        if evaluate_scheme(sunita, entry).is_eligible:
            eligible.append(entry)
    central_hits = sum(1 for e in eligible if e["level"] == "Central")
    check("A State resident is matched against Central schemes too",
          central_hits > 0,
          f"{len(eligible)} eligible: {central_hits} Central, "
          f"{len(eligible) - central_hits} State")
    for entry in eligible[:6]:
        print(f"        · [{entry['level']:7}] {entry['schemeName']}")

    # Cross-State refusal, in the engine the API actually calls.
    mp_scheme = get_by_name("Mukhyamantri Ladli Behna Yojana (Madhya Pradesh)")
    outsider = dict(sunita, state="Bihar")
    r = evaluate_scheme(outsider, mp_scheme)
    check("Same applicant, wrong State, is refused",
          not r.is_eligible and "state" in {x.field for x in r.failed},
          "domicile rule caught it before she travelled to an office")


def stage_kyc() -> None:
    banner("STAGE 11  KYC — offline Aadhaar, matching, and what it decides")

    from kyc import aadhaar_offline as ao
    from kyc import matching, service
    from kyc.methods import Assurance, METHODS, available_methods

    usable = available_methods()
    licensed = [m for m in METHODS if m.availability.value == "needs_licence"]
    check("Every KYC method is catalogued", len(METHODS) >= 14,
          f"{len(METHODS)} methods, {len(usable)} usable here, "
          f"{len(licensed)} need a UIDAI licence")
    check("A route exists that needs no smartphone",
          any(m.channel.value in ("self_offline", "assisted", "in_person")
              for m in usable))
    check("A licensed method is never reported as usable",
          all(not m.effective_availability.is_usable for m in licensed),
          ", ".join(m.key for m in licensed))

    # A synthetic UIDAI Secure QR. Reference ID starts with the last four
    # Aadhaar digits, which is the only part of the number UIDAI puts in it.
    qr = ao.build_test_qr({
        "email_mobile_present": "3", "reference_id": "0124202601011200000",
        "name": "Kamla Devi", "dob": "12-04-1958", "gender": "F",
        "careof": "W/O Ram Prasad", "district": "Sitapur",
        "landmark": "Near Temple", "house": "42", "location": "Kachhwa",
        "pincode": "261001", "postoffice": "Kachhwa", "state": "Uttar Pradesh",
        "street": "Main Road", "subdistrict": "Misrikh", "vtc": "Kachhwa",
    }, photo=b"\x00" * 40, signature=b"S" * 256)

    record = ao.parse_secure_qr(qr)
    check("Secure QR parsed", record.demographics.get("name") == "Kamla Devi",
          f"last4 {record.aadhaar_last4}, "
          f"{len(record.demographics)} fields recovered")

    from dpdp.aadhaar_policy import contains_full_aadhaar
    check("No full Aadhaar anywhere in the parsed record",
          not contains_full_aadhaar(record.as_dict()),
          "s29(4): publishing an Aadhaar number is a criminal offence")

    check("Unverified signature is NOT reported as verified",
          record.assurance is Assurance.DOCUMENTED,
          f"{record.assurance.label_en} — no UIDAI certificate configured")

    # A citizen whose typed name differs from the document by transliteration.
    claimed = {"name": "Kamala Devi", "date_of_birth": "1958-04-12",
               "gender": "Female", "pincode": "261001"}
    outcome = service.verify_secure_qr(claimed, qr)
    check("Transliteration difference does not block", outcome.succeeded,
          f"score {outcome.score:.2f}, review={outcome.needs_review}")

    # A date of birth twenty years out cannot be a transcription slip.
    lying = dict(claimed, date_of_birth="1978-04-12")
    bad = service.verify_secure_qr(lying, qr)
    check("Contradicted date of birth is escalated, not refused",
          bad.contradicted and bad.fraud_signal > 0 and bad.succeeded,
          f"signal +{bad.fraud_signal}, message says: "
          f"{'not been refused' in bad.message_en}")

    # The exclusion cases: each must survive.
    survivors = [
        ("Married woman, maiden name on her bank account",
         matching.compare_names("Sunita Sharma", "Sunita Verma")),
        ("UIDAI holds only a year of birth",
         matching.compare_dates_of_birth("1958-04-12", "1958")),
        ("Transgender applicant, document not yet corrected",
         matching.compare_genders("Transgender", "M")),
        ("Migrant worker living in another PIN code",
         matching.compare_pincodes("261001", "110001")),
    ]
    for label, result in survivors:
        check(f"Not refused: {label}", not result.decisive,
              f"score {result.score:.2f} — routed to a reviewer")

    # Verification must buy an honest applicant something, or nobody bothers.
    # Measured on a profile that actually carries risk: a citizen reapplying to
    # the same scheme after two rejected attempts looks suspicious on volume
    # alone, and a UIDAI-signed document is better evidence than that inference.
    import fraud_detection as fd
    repeat = fd.ApplicantHistory(prior_applications_same_scheme=3)
    base = fd.assess(claimed, history=repeat)
    with_kyc = fd.assess(claimed, history=repeat, kyc_outcomes=[outcome])
    # The credit is graduated: this document's UIDAI signature could not be
    # checked, so it earns less than a fully verified one would. That is the
    # design working, not a weak result.
    check("Verifying lowers the risk score for an honest applicant",
          with_kyc.score < base.score,
          f"risk {base.score} ({base.decision.value}) -> "
          f"{with_kyc.score} ({with_kyc.decision.value}); "
          f"credit {outcome.fraud_signal} at {outcome.assurance.label_en}")

    full = service.VerificationOutcome(
        method="aadhaar_offline_xml", succeeded=True,
        assurance=Assurance.VERIFIED, fraud_signal=-15)
    verified = fd.assess(claimed, history=repeat, kyc_outcomes=[full])
    check("A checked signature earns more credit than an unchecked one",
          verified.score < with_kyc.score,
          f"{with_kyc.score} ({with_kyc.decision.value}) vs "
          f"{verified.score} ({verified.decision.value}) with UIDAI's "
          "signature actually verified")

    hard = fd.assess({}, history=fd.ApplicantHistory(users_sharing_bank_account=12),
                     kyc_outcomes=[outcome])
    check("Verification cannot clear a genuinely bad case",
          hard.decision.value != "allow",
          f"still {hard.decision.value} at risk {hard.score}")

    summary = service.assurance_summary([outcome])
    check("Status message never says refused",
          "refus" not in summary["nextStep"].lower(),
          summary["nextStep"][:58])


def stage_languages() -> None:
    banner("STAGE 12  Languages — coverage, honesty, and right-to-left")

    from i18n import languages, resolve
    from i18n.catalog import KEYS, Quality, coverage, quality_of

    s = resolve.summary()
    check("Every Eighth Schedule language has text",
          s["withTranslations"] == 22 and not s["missing"],
          f"22 of 22 scheduled languages, {s['interfaceKeys']} keys each")
    check("None claims a review that did not happen",
          s["nativelyReviewed"] == 0,
          f"{len(s['lowConfidence'])} marked low-confidence: "
          f"{', '.join(s['lowConfidence'])}")

    for code in ("hi", "ta", "ur", "sat", "mni"):
        lang = languages.get(code)
        b = resolve.bundle(code)
        grade = coverage(code)["quality"]
        warn = " ⚠ warns the reader" if b["lowConfidence"] else ""
        print(f"        · {lang.name_en:<10} {lang.endonym:<12} "
              f"{lang.script:<16} {b['language']['direction']}  "
              f"{grade}{warn}")
        print(f"          {KEYS[2]} = {b['strings'][KEYS[2]]}")

    check("Right-to-left languages are marked",
          languages.rtl_codes() == {"ur", "ks", "sd"},
          "Urdu, Kashmiri, Sindhi")

    low = resolve.bundle("sat")
    check("An unchecked translation ships with a standing warning",
          low["lowConfidence"] and bool(low["qualityWarning"]),
          low["qualityWarning"][:56])
    solid = resolve.bundle("bn")
    check("A solid draft does not cry wolf",
          not solid["lowConfidence"], "no banner on Bengali")

    check("No Indian language falls back to another",
          all(not [c for c in languages.fallback_chain(l.code)
                   if c not in (l.code, languages.DEFAULT)]
              for l in languages.LANGUAGES),
          "sharing a script is not sharing a language")

    tn = resolve.suggest(state="Tamil Nadu", accept_language="hi-IN")
    check("A State's own language outranks the browser",
          tn["recommended"] == "ta", "Tamil Nadu resident is offered Tamil")

    mz = resolve.suggest(state="Mizoram")
    check("A gap in the Schedule itself is reported, not hidden",
          mz["recommended"] == "en" and mz["unscheduledLocalLanguages"],
          f"Mizoram: {', '.join(mz['unscheduledLocalLanguages'])} "
          "are not in the Eighth Schedule")

    # The two strings that protect a citizen from being defrauded must exist in
    # every language, not only the ones an English speaker can check.
    from i18n.catalog import MESSAGES
    untranslated_safety = [
        c for c in MESSAGES if c != "en"
        and MESSAGES[c]["msg.no_fee"] == MESSAGES["en"]["msg.no_fee"]
    ]
    check("The anti-fraud warnings are translated everywhere",
          not untranslated_safety,
          "\"never pay anyone\" reaches every language")


def stage_dpdp_and_notice() -> None:
    banner("STAGE 13  DPDP — the notice is narrower than the interface")

    from routes import dpdp as dpdp_routes
    from i18n import resolve

    notice = dpdp_routes.NOTICE_LANGUAGES
    interface = resolve.summary()["withTranslations"]
    check("Consent notice is served only where it can be relied on",
          notice == {"en", "hi"},
          f"notice: {len(notice)} languages, interface: {interface}")
    check("The two numbers are reported separately",
          interface > len(notice),
          "a mistranslated consent notice is a defective consent")

    from dpdp import registry
    from data.gov_forms import all_profile_keys
    undeclared = sorted(set(all_profile_keys()) - set(registry.BY_FIELD))
    check("Every field the catalog collects is in the processing register",
          not undeclared, ", ".join(undeclared) or
          f"{len(all_profile_keys())} fields declared")

    health = [f for f in registry.REGISTRY if f.category.value == "health"]
    check("Disability and maternity data classified as health, not financial",
          len(health) >= 5,
          ", ".join(sorted(f.field for f in health)[:4]) + " …")


async def stage_end_to_end_integration() -> None:
    """The path the API actually takes, with every layer connected.

    Every other stage exercises a layer. This one checks the wiring between
    them, which is where both of the bugs it now guards were found: KYC
    evidence that never reached the decision, and a missing document that was
    reported as invalid data rather than an unfinished form.
    """
    banner("STAGE 14  End to end — the wiring between the layers")

    import fraud_detection as fd
    from data.gov_forms import get_by_name, get_catalog
    from kyc.methods import Assurance
    from kyc.service import VerificationOutcome
    from services import application_guard
    from services.application_guard import GateOutcome

    pension = get_by_name("Indira Gandhi National Old Age Pension")
    aadhaar = make_valid_aadhaar("48291736450")
    full = {
        "name": "Kamla Devi", "father_husband_name": "Ram Prasad",
        "aadhaar_number": aadhaar, "date_of_birth": "1958-04-12", "age": 68,
        "gender": "Female", "category": "OBC", "mobile_number": "9876543210",
        "address_line": "House 42", "district": "Sitapur",
        "state": "Uttar Pradesh", "pincode": "261001", "is_bpl": "Yes",
        "annual_income": 42000, "bank_account_number": "50100234567890",
        "ifsc_code": "SBIN0001234", "bank_name": "State Bank of India",
    }

    async def run(profile, **kw):
        return await application_guard.evaluate_application(
            profile=profile, scheme=pension, **kw)

    # An unfinished form asks for more. It does not refuse.
    partial = await run({"name": "Sunita Devi", "age": 34, "gender": "Female"})
    check("Unfinished form is INCOMPLETE, not a refusal",
          partial.outcome is GateOutcome.INCOMPLETE,
          f"{partial.outcome.value} — "
          f"{partial.reasons_en[0][:44] if partial.reasons_en else ''}")

    # An identity document that is absent is an absence, not bad data.
    from validation import ABSENCE_CODES
    check("A missing identity document is an absence, not invalid data",
          "identity_document_missing" in ABSENCE_CODES,
          "the difference between 'please add this' and 'you are rejected'")

    # But something objectively wrong still blocks.
    bad = await run(dict(full, aadhaar_number="111111111111"))
    check("An impossible value still blocks",
          bad.outcome is GateOutcome.BLOCKED_INVALID_DATA,
          bad.reasons_en[0][:52] if bad.reasons_en else "")

    # KYC evidence must reach the decision, not just the unit that computes it.
    repeat = fd.ApplicantHistory(prior_applications_same_scheme=3)
    verified = VerificationOutcome(
        method="aadhaar_offline_xml", succeeded=True,
        assurance=Assurance.VERIFIED, fraud_signal=-15)

    without = await run(full, history=repeat)
    with_kyc = await run(full, history=repeat, kyc_outcomes=[verified])
    check("Verification changes the gate's outcome",
          without.outcome is GateOutcome.APPROVED_WITH_REVIEW
          and with_kyc.outcome is GateOutcome.APPROVED,
          f"{without.outcome.value} (risk {without.risk['risk_score']}) -> "
          f"{with_kyc.outcome.value} (risk {with_kyc.risk['risk_score']})")

    # And it must survive the JSON round trip a browser puts it through.
    as_json = await run(full, history=repeat, kyc_outcomes=[verified.as_dict()])
    check("Outcomes survive the wire as plain JSON",
          as_json.outcome is with_kyc.outcome
          and as_json.risk["risk_score"] == with_kyc.risk["risk_score"],
          "dict and object produce the same decision")

    # Malformed client input must not lose somebody's application.
    junk = await run(full, kyc_outcomes=[{"assurance": "high"}, None, "nonsense"])
    check("Malformed client input degrades instead of raising",
          junk.outcome is GateOutcome.APPROVED,
          "a bad client must not cost the citizen their application")

    # Never a refusal on identity grounds, whatever the evidence.
    for label, outcomes in [("no checks", []),
                            ("verified", [verified])]:
        result = await run(full, kyc_outcomes=outcomes)
        text = (result.identity["label"] + result.identity["reviewer_note"]
                if "reviewer_note" in result.identity
                else result.identity["label"]).lower()
        check(f"Identity state reads neutrally: {label}",
              "refus" not in text and "reject" not in text
              and result.identity["verificationIsOptional"] is True,
              result.identity["label"])

    # The reviewer sees the identity evidence, or cannot weigh the case.
    from services import review_context
    panel = review_context.build_identity_context(
        {"kycOutcomes": [verified.as_dict()]})
    check("Reviewer console shows what identity evidence exists",
          panel["assurance"] == int(Assurance.VERIFIED)
          and "UIDAI" in panel["reviewer_note"],
          panel["label"])

    empty_panel = review_context.build_identity_context({})
    check("An unverified applicant is shown neutrally to the reviewer",
          "normal" in empty_panel["reviewer_note"].lower(),
          "self-declared is a lawful state, not a strike")

    # Screening narrows to the citizen's State without hiding Central schemes.
    home = get_catalog(state="Uttar Pradesh")
    central_total = sum(1 for e in get_catalog() if e["level"] == "Central")
    home_central = sum(1 for e in home if e["level"] == "Central")
    check("Screening narrows by State but keeps every Central scheme",
          home_central == central_total and len(home) < len(get_catalog()),
          f"UP resident screened against {len(home)} of {len(get_catalog())} "
          f"({central_total} Central + {len(home) - central_total} State)")


async def stage_form_geometry(offline: bool) -> None:
    """Reading the ruled grid off a scan, and staying inside it."""
    banner("STAGE 15  Form geometry — placing values without spilling over")

    import form_geometry
    from form_geometry import Cell
    from pdf_filler import _collides, _looks_like_a_label, _token_ratio

    # Pure-geometry checks first, so this stage still says something offline.
    cells = [Cell(20, 100, 400, 120)]

    class _R:
        x0, y0, x1, y1 = 30, 104, 90, 116

    gaps = form_geometry.writable_gaps(cells, _R(), [], page_width=600)
    check("A value is bounded by its printed cell", gaps and gaps[0][1] <= 400,
          f"cell ends at 400, gap ends at {gaps[0][1]:.0f}" if gaps else "")

    words = [(200, 104, 250, 116, "Email", 0, 0, 0),
             (252, 104, 280, 116, "ID:", 0, 0, 1)]
    gaps = form_geometry.writable_gaps(cells, _R(), words, page_width=600)
    check("A value stops at the next field's label",
          gaps and gaps[0][1] <= 200,
          "'8. Mobile No: | Email ID:' is two fields on one row")

    hint = [(100, 104, 180, 116, "(Enclose", 0, 0, 0)]
    gaps = form_geometry.writable_gaps(cells, _R(), hint, page_width=600)
    widest = max(gaps, key=lambda g: g[1] - g[0]) if gaps else (0, 0)
    check("A long value may use the space past a printed hint",
          widest[0] >= 180,
          "'Date of birth:(Enclose Certificate)' leaves room after the hint")

    check("Adjacent table rows are not a collision",
          not _collides({"x": 100, "y": 181.5, "width": 67, "font_size": 9.7},
                        {"x": 100, "y": 168.5, "width": 64, "font_size": 9.7}),
          "rows sit 13pt apart with 9.7pt text")
    check("Two values on one line are a collision",
          _collides({"x": 100, "y": 200, "width": 60, "font_size": 10},
                    {"x": 130, "y": 200, "width": 60, "font_size": 10}))

    check("Father and mother can never trade places",
          _token_ratio("fathersname", "mothersname") < 0.86,
          "they differ by two characters in eleven")
    check("A stray OCR letter does not make a label into prose",
          _looks_like_a_label("I Mother's Occupation: "))

    if offline:
        return

    # And against the real scanned form.
    from pathlib import Path

    from data.gov_forms import get_by_name
    from pdf_filler import audit_form, fill_pdf_form

    scheme = get_by_name("Sports Achievement Scholarship (Haryana)")
    source = Path("/tmp/smoke_source_form.pdf")
    try:
        import requests

        response = requests.get(LIVE_FORM_URL, timeout=45,
                                headers={"User-Agent": "Mozilla/5.0"})
        source.write_bytes(response.content)
    except Exception as exc:  # noqa: BLE001
        check("Fetched the source form for geometry checks", False,
              f"{type(exc).__name__}")
        return

    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf

    page = pymupdf.open(source)[0]
    check("A scanned form has no vector lines at all", not page.get_drawings(),
          "borders are pixels — page.get_drawings() returns nothing")

    grid = form_geometry.describe(page)
    check("The grid is recovered from the image", grid["gridDetected"],
          f"{grid['cells']} cells from {grid['horizontalRules']} horizontal "
          f"and {grid['verticalRules']} vertical rules")

    profile = {
        "name": "Priya Sharma", "father_husband_name": "Rajesh Sharma",
        "mother_name": "Kamla Sharma", "father_occupation": "Farmer",
        "mother_occupation": "Homemaker", "state_family_id": "HR-1234567890",
        "current_class": "B.A. II", "academic_session": "2025-26",
        "event_name": "Haryana State Senior Kabaddi Championship 2025",
        "event_date": "2025-11-18", "achievement_position": "First",
        "domicile_certificate_number": "HR/JHJ/2019/004821",
        "aadhaar_number": make_valid_aadhaar("73629184057"),
        "date_of_birth": "2005-08-14", "gender": "Female", "category": "OBC",
        "mobile_number": "9812345678", "email": "priya@example.com",
        "address_line": "House No. 214, Sector 7", "district": "Jhajjar",
        "state": "Haryana", "pincode": "124507",
        "institution_name": "Government College for Women",
        "sport_name": "Kabaddi", "bank_account_number": "39281746503921",
        "ifsc_code": "PUNB0123456", "bank_name": "Punjab National Bank",
        # This form prints no "Branch Name" anywhere, so the value has nowhere
        # to go. Supplied on purpose: it is what makes the report below prove
        # something rather than pass by having nothing left over.
        "branch_name": "Bahadurgarh Main",
    }

    audit = audit_form(str(source), scheme["extractedFields"], profile)
    check("The form is audited before anything is written",
          audit["available"] and audit["addressableOnForm"],
          f"{len(audit['addressableOnForm'])} of {audit['totalFields']} fields "
          f"have a labelled slot on this form")
    check("Fields the form cannot take are named, not silently dropped",
          bool(audit["notAddressableOnForm"]),
          ", ".join(audit["notAddressableOnForm"][:4]))

    out = Path("/tmp/smoke_filled_official.pdf")
    report = fill_pdf_form(str(source), str(out), profile,
                           scheme["extractedFields"])
    check("Values written onto the published PDF", report.get("success"),
          f"{report.get('filled_count', 0)} of {len(scheme['extractedFields'])}")

    check("Mother's name is found despite the OCR middle dot",
          any(w["profileKey"] == "mother_name" for w in report.get("written", [])),
          "the page text reads \"Mother's·Name:\"")
    check("Father's and Mother's occupation are filled",
          {"father_occupation", "mother_occupation"} <=
          {w["profileKey"] for w in report.get("written", [])},
          "fields the catalog did not model until the audit found them")

    verification = report.get("verification") or {}
    check("The written file is re-opened and checked",
          verification.get("verified"), f"{verification.get('checked', 0)} values")
    check("Nothing overlaps and nothing crosses a cell border",
          verification.get("clean"),
          "; ".join(f"{p['kind']}:{p['profileKey']}"
                    for p in verification.get("problems", [])) or "clean")
    written_keys = {w["profileKey"] for w in report.get("written", [])}
    mandatory = {f["profileKey"] for f in scheme["extractedFields"]
                 if f.get("required") and profile.get(f["profileKey"])}
    satisfied = {k for w in report.get("written", [])
                 for k in w.get("satisfies", [w["profileKey"]])}

    # The property, not a quota. An earlier version required the report to be
    # non-empty, which made every improvement to the filler look like a
    # failure. What matters is that nothing falls between the two lists: a
    # value the citizen gave is either on the page or named as theirs to write.
    reported = {u["profileKey"] for u in report.get("unplaced", [])}
    accounted = satisfied | written_keys | reported
    supplied = {f["profileKey"] for f in scheme["extractedFields"]
                if profile.get(f["profileKey"])}
    check("Every value the citizen gave is either on the page or reported",
          supplied <= accounted,
          ", ".join(sorted(supplied - accounted)) or
          f"{len(reported)} to be written by hand")
    check("Every mandatory field the citizen answered is on the form",
          mandatory <= satisfied,
          f"{len(mandatory & satisfied)} of {len(mandatory)}; missing: "
          f"{sorted(mandatory - satisfied) or 'none'}")

    check("A column heading writes into the box beneath it",
          "institution_name" in written_keys,
          "the College/School row has nothing beside its heading")
    check("A composite box absorbs the parts that belong in it",
          {"state", "pincode"} <= satisfied,
          "state and PIN code go into the address block")
    check("A value recorded by column is placed under the right one",
          "achievement_position" in written_keys,
          "\"First\" written under the Gold column, not a tick")


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
    stage_catalog_coverage()
    stage_state_applicants()
    stage_kyc()
    stage_languages()
    stage_dpdp_and_notice()
    await stage_end_to_end_integration()
    await stage_form_geometry(args.offline)

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
