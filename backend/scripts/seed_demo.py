#!/usr/bin/env python3
"""Seed a roster of demo citizens so every use case can be walked end to end.

Each demo citizen has a complete, realistic profile and a known phone number.
In a DEMO_MODE build you sign in as any of them with that number and OTP 123456
and land straight in the app with data for the whole flow - the eligible
schemes, the intake answers already filled, the document checklist, KYC, the
filled PDF and the DPDP screens. Together they cover the main outcomes: women's
schemes, old-age and widow pensions, scholarships, farmer support, a girl-child
savings scheme, disability, and an ineligible/flagged applicant so the refusal
and review paths can be seen too.

    cd backend
    python scripts/seed_demo.py           # create/refresh every demo citizen
    python scripts/seed_demo.py --list    # print the roster (no database needed)
    python scripts/seed_demo.py --only 3  # just citizen #3
    python scripts/seed_demo.py --remove  # delete all demo citizens

Profiles are stored through the same path the app uses, so the full Aadhaar is
never persisted - only its last four and a keyed fingerprint - and the blob is
encrypted at rest. Every Aadhaar here is synthetic with a valid checksum and
belongs to nobody. Needs the server's environment (MONGO_URL,
DATA_ENCRYPTION_KEY, IDENTITY_HASH_SALT); the server itself need not be running.
"""
import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _aadhaar(prefix11: str) -> str:
    from validation import verhoeff_check_digit
    return prefix11 + verhoeff_check_digit(prefix11)


def _base(**over) -> dict:
    """Common fields; each profile overrides what matters for its use case."""
    p = {
        "email": "", "category": "General", "is_income_tax_payer": "No",
        "is_govt_employee": "No", "disability_type": "None",
    }
    p.update(over)
    return p


def roster() -> list[dict]:
    return [
        {
            "n": 1, "phone": "9000000001", "use_case": "Women's scheme + girl child + farmer household",
            "schemes": "Ladli Behna, Sukanya Samriddhi, PM-KISAN, scholarships",
            "profile": _base(
                name="Sunita Devi", father_husband_name="Mahesh Kumar",
                aadhaar_number=_aadhaar("48291736450"), date_of_birth="1992-03-15", age=33,
                gender="Female", category="OBC", marital_status="Married", mobile_number="9000000001",
                address_line="12 Nehru Ward, Rewa", district="Rewa", tehsil="Huzur",
                state="Madhya Pradesh", pincode="486001", state_family_id="MP1234567890",
                annual_income=96000, is_bpl="Yes", ration_card_type="Priority Household (PHH)",
                ration_card_number="MP486001234567", occupation="Homemaker",
                land_holding_acres=1.2, land_ownership_type="Owned", farmer_category="Small",
                girl_child_name="Anjali", girl_child_dob="2019-06-10", girl_child_age=6,
                number_of_daughters=1, family_members=4,
                bank_account_number="20100234567891", ifsc_code="SBIN0004321",
                bank_name="State Bank of India", branch_name="Rewa Main"),
        },
        {
            "n": 2, "phone": "9000000002", "use_case": "Old-age pension (senior, widow, BPL)",
            "schemes": "Indira Gandhi National Old Age Pension, widow pension",
            "profile": _base(
                name="Kamla Devi", father_husband_name="Ram Prasad (late)",
                aadhaar_number=_aadhaar("50182736491"), date_of_birth="1956-07-02", age=69,
                gender="Female", category="OBC", marital_status="Widowed", mobile_number="9000000002",
                address_line="House 42, Ward 3, Sitapur", district="Sitapur",
                state="Uttar Pradesh", pincode="261001", annual_income=24000, is_bpl="Yes",
                ration_card_type="Antyodaya (AAY)", occupation="None", family_members=2,
                bank_account_number="50100234567810", ifsc_code="SBIN0001234",
                bank_name="State Bank of India", branch_name="Sitapur"),
        },
        {
            "n": 3, "phone": "9000000003", "use_case": "Scholarship (student, sports achievement)",
            "schemes": "Sports Achievement Scholarship (Haryana), education scholarships",
            "profile": _base(
                name="Priya Sharma", father_husband_name="Rajesh Sharma", mother_name="Kamla Sharma",
                aadhaar_number=_aadhaar("73629184057"), date_of_birth="2005-08-14", age=20,
                gender="Female", category="OBC", marital_status="Unmarried", mobile_number="9000000003",
                email="priya@example.com", address_line="House 214, Sector 7", district="Jhajjar",
                state="Haryana", pincode="124507", annual_income=180000,
                institution_name="Government College for Women", course_name="B.A. II",
                roll_number="HR-BA-2024-0214", last_exam_percentage=78, academic_session="2025-26",
                sport_name="Kabaddi", event_name="Haryana State Senior Kabaddi Championship 2025",
                achievement_position="First", domicile_certificate_number="HR/JHJ/2019/004821",
                bank_account_number="39281746503921", ifsc_code="PUNB0123456",
                bank_name="Punjab National Bank", branch_name="Bahadurgarh Main"),
        },
        {
            "n": 4, "phone": "9000000004", "use_case": "Farmer support (land-owning cultivator)",
            "schemes": "PM-KISAN Samman Nidhi, Kisan Credit Card",
            "profile": _base(
                name="Ramesh Kumar", father_husband_name="Balwant Singh",
                aadhaar_number=_aadhaar("61928374052"), date_of_birth="1980-01-20", age=45,
                gender="Male", category="General", marital_status="Married", mobile_number="9000000004",
                address_line="Village Rampura, Ludhiana", district="Ludhiana",
                state="Punjab", pincode="141001", annual_income=240000, is_bpl="No",
                occupation="Farmer", land_holding_acres=3.0, land_ownership_type="Owned",
                farmer_category="Small", survey_khasra_number="KH-114/2", family_members=5,
                bank_account_number="30987654321012", ifsc_code="PUNB0141001",
                bank_name="Punjab National Bank", branch_name="Ludhiana City"),
        },
        {
            "n": 5, "phone": "9000000005", "use_case": "State women's entitlement (widow, Tamil Nadu)",
            "schemes": "Kalaignar Magalir Urimai Thogai (Tamil Nadu)",
            "profile": _base(
                name="Meena Murugan", father_husband_name="Murugan S (late)",
                aadhaar_number=_aadhaar("51726394820"), date_of_birth="1984-07-22", age=41,
                gender="Female", category="General", marital_status="Widowed", mobile_number="9000000005",
                address_line="3/45 Anna Nagar", district="Madurai", state="Tamil Nadu",
                pincode="625020", annual_income=96000, is_bpl="No",
                ration_card_type="Priority Household (PHH)", occupation="Daily wage",
                family_members=3, bank_account_number="30987654321099", ifsc_code="IOBA0001234",
                bank_name="Indian Overseas Bank", branch_name="Madurai Anna Nagar"),
        },
        {
            "n": 6, "phone": "9000000006", "use_case": "North-East welfare (ST household, Assam)",
            "schemes": "Orunodoi (Assam)",
            "profile": _base(
                name="Anjali Basumatary", father_husband_name="Bipul Basumatary",
                aadhaar_number=_aadhaar("62817394056"), date_of_birth="1973-11-02", age=52,
                gender="Female", category="ST", marital_status="Married", mobile_number="9000000006",
                address_line="Village Bhairabkunda", district="Udalguri", state="Assam",
                pincode="784509", annual_income=84000, is_bpl="Yes",
                ration_card_type="Priority Household (PHH)", family_members=5,
                bank_account_number="40192837465012", ifsc_code="UCBA0002468",
                bank_name="UCO Bank", branch_name="Udalguri"),
        },
        {
            "n": 7, "phone": "9000000007", "use_case": "Disability (benchmark disability, Delhi)",
            "schemes": "Disability pension and assistance",
            "profile": _base(
                name="Deepak Verma", father_husband_name="Suresh Verma",
                aadhaar_number=_aadhaar("70918263541"), date_of_birth="1995-04-18", age=30,
                gender="Male", category="General", marital_status="Unmarried", mobile_number="9000000007",
                address_line="B-14, Rohini Sector 9", district="North West Delhi", state="Delhi",
                pincode="110085", annual_income=60000, is_bpl="Yes",
                disability_type="Locomotor", disability_percentage=60,
                disability_certificate_number="DL/UDID/2021/0099213", occupation="Self-employed",
                family_members=3, bank_account_number="50223344556611", ifsc_code="SBIN0009876",
                bank_name="State Bank of India", branch_name="Rohini"),
        },
        {
            "n": 8, "phone": "9000000008", "use_case": "INELIGIBLE / flagged - tests the refusal and review path",
            "schemes": "BPL claim contradicted by income + income-tax status",
            "profile": _base(
                name="Rekha Agarwal", father_husband_name="Vinod Agarwal",
                aadhaar_number=_aadhaar("82910374651"), date_of_birth="1986-09-09", age=39,
                gender="Female", category="General", marital_status="Married", mobile_number="9000000008",
                address_line="21 Civil Lines", district="Kanpur Nagar", state="Uttar Pradesh",
                pincode="208001", annual_income=1800000, is_bpl="Yes",        # contradiction on purpose
                is_income_tax_payer="Yes", is_govt_employee="No", occupation="Business owner",
                land_holding_acres=12.0, family_members=4,
                bank_account_number="50100999888777", ifsc_code="HDFC0000123",
                bank_name="HDFC Bank", branch_name="Kanpur Civil Lines"),
        },
    ]


DEMO_PHONES = [c["phone"] for c in roster()]


async def _upsert(prisma, Json, identity_index, profile_store, TERMS_VERSION, citizen) -> str:
    profile = citizen["profile"]
    full_stored, _ = profile_store.prepare_full_profile(profile)
    basic_stored, _ = profile_store.prepare_basic_profile({
        "name": profile["name"], "age": profile.get("age"),
        "income": profile.get("annual_income"), "state": profile.get("state"),
        "_complete": True,
    })
    data = identity_index.merge_into_update({
        "fullProfile": Json(full_stored), "profile": Json(basic_stored), "language": "hi",
        "profileLastUpdated": datetime.now(timezone.utc),
        "termsVersion": TERMS_VERSION, "termsAcceptedAt": datetime.now(timezone.utc),
    }, profile)
    existing = await prisma.user.find_unique(where={"phone": citizen["phone"]})
    if existing:
        await prisma.user.update(where={"id": existing.id}, data=data)
        return "refreshed"
    await prisma.user.create(data={"phone": citizen["phone"], **data})
    return "created"


async def run(only: int | None, remove: bool) -> int:
    from prisma import Json

    import identity_index
    from database import prisma
    from dpdp import profile_store
    from dpdp.terms import TERMS_VERSION

    await prisma.connect()
    try:
        citizens = roster()
        if only:
            citizens = [c for c in citizens if c["n"] == only]
            if not citizens:
                print(f"No demo citizen #{only}."); return 1

        if remove:
            n = 0
            for c in roster():
                u = await prisma.user.find_unique(where={"phone": c["phone"]})
                if u:
                    await prisma.chatlog.delete_many(where={"userId": u.id})
                    await prisma.application.delete_many(where={"userId": u.id})
                    await prisma.user.delete(where={"id": u.id})
                    n += 1
            print(f"Removed {n} demo citizen(s)."); return 0

        print("Seeding demo citizens (sign in with the phone + OTP 123456 in a DEMO_MODE build):\n")
        for c in citizens:
            action = await _upsert(prisma, Json, identity_index, profile_store, TERMS_VERSION, c)
            print(f"  [{action:9}] #{c['n']}  {c['phone']}  {c['profile']['name']:16} - {c['use_case']}")
        print(f"\n{len(citizens)} demo citizen(s) ready. Pick any phone above, OTP 123456, "
              f"and the app opens with a complete profile for that use case.")
        return 0
    finally:
        await prisma.disconnect()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="Print the roster and exit (no database)")
    ap.add_argument("--only", type=int, metavar="N", help="Seed only demo citizen N")
    ap.add_argument("--remove", action="store_true", help="Delete all demo citizens and exit")
    args = ap.parse_args()

    if args.list:
        print("Demo roster (phone - name - use case); OTP 123456 in a DEMO_MODE build:\n")
        for c in roster():
            print(f"  #{c['n']}  {c['phone']}  {c['profile']['name']:16} - {c['use_case']}")
            print(f"        schemes: {c['schemes']}")
        return 0
    return asyncio.run(run(args.only, args.remove))


if __name__ == "__main__":
    sys.exit(main())
