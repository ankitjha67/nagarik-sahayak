#!/usr/bin/env python3
"""Seed a demo citizen so the app can be walked end to end.

Creates (or refreshes) one user with a complete, realistic profile, keyed to a
known phone number. In a DEMO_MODE build you sign in as them with that number
and OTP 123456 — and because the profile is already complete, you land straight
in the app with data for every feature: eligibility across many schemes, the
form-intake questions already answered, the document checklist, KYC, the filled
PDF, and the DPDP screens.

    cd backend
    python scripts/seed_demo.py            # create/refresh the demo citizen
    python scripts/seed_demo.py --remove   # delete only the demo citizen

The profile is stored through the same path the app uses, so the full Aadhaar
is never persisted — only its last four and a keyed fingerprint — and the blob
is encrypted at rest. The Aadhaar here is synthetic with a valid checksum and
belongs to nobody.

Needs the same environment as the server (MONGO_URL, DATA_ENCRYPTION_KEY,
IDENTITY_HASH_SALT). It talks to the database directly; the server need not be
running.
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEMO_PHONE = "9000000001"


def _demo_profile() -> dict:
    """A broad, internally consistent citizen: a married woman in Madhya
    Pradesh with a girl child and a farmer household, so she matches several
    Central and State schemes, with every field a common form asks for."""
    from validation import verhoeff_check_digit

    aadhaar = "48291736450" + verhoeff_check_digit("48291736450")
    return {
        # identity
        "name": "Sunita Devi",
        "father_husband_name": "Mahesh Kumar",
        "aadhaar_number": aadhaar,          # stored as last-4 + fingerprint only
        "date_of_birth": "1992-03-15",
        "age": 33,
        "gender": "Female",
        "category": "OBC",
        "marital_status": "Married",
        "mobile_number": DEMO_PHONE,
        "email": "sunita.devi@example.com",
        # address
        "address_line": "12 Nehru Ward, Rewa",
        "district": "Rewa",
        "tehsil": "Huzur",
        "state": "Madhya Pradesh",
        "pincode": "486001",
        "state_family_id": "MP1234567890",
        # economic / eligibility signals
        "annual_income": 96000,
        "is_bpl": "Yes",
        "ration_card_type": "Priority Household (PHH)",
        "ration_card_number": "MP486001234567",
        "is_income_tax_payer": "No",
        "is_govt_employee": "No",
        "occupation": "Homemaker",
        "land_holding_acres": 1.2,
        "land_ownership_type": "Owned",
        "farmer_category": "Small",
        # household / scheme-specific
        "girl_child_name": "Anjali",
        "girl_child_dob": "2019-06-10",
        "girl_child_age": 6,
        "number_of_daughters": 1,
        "family_members": 4,
        "disability_type": "None",
        # education (for scholarship forms)
        "institution_name": "Government Girls College, Rewa",
        "course_name": "B.A. Second Year",
        "roll_number": "MP-BA-2024-0481",
        "last_exam_percentage": 72,
        "academic_session": "2025-26",
        # banking (for DBT / filled forms)
        "bank_account_number": "20100234567891",
        "ifsc_code": "SBIN0004321",
        "bank_name": "State Bank of India",
        "branch_name": "Rewa Main",
    }


async def seed(remove: bool) -> int:
    from prisma import Json

    import identity_index
    from database import prisma
    from dpdp import profile_store
    from dpdp.terms import TERMS_VERSION

    await prisma.connect()
    try:
        existing = await prisma.user.find_unique(where={"phone": DEMO_PHONE})

        if remove:
            if existing:
                await prisma.chatlog.delete_many(where={"userId": existing.id})
                await prisma.application.delete_many(where={"userId": existing.id})
                await prisma.user.delete(where={"id": existing.id})
                print(f"Removed demo citizen ({DEMO_PHONE}).")
            else:
                print("No demo citizen to remove.")
            return 0

        profile = _demo_profile()
        full_stored, full_plain = profile_store.prepare_full_profile(profile)
        basic_stored, _ = profile_store.prepare_basic_profile({
            "name": profile["name"], "age": profile["age"],
            "income": profile["annual_income"], "state": profile["state"],
            "_complete": True,
        })

        data = identity_index.merge_into_update({
            "fullProfile": Json(full_stored),
            "profile": Json(basic_stored),
            "language": "hi",
            "profileLastUpdated": datetime.now(timezone.utc),
            "termsVersion": TERMS_VERSION,
            "termsAcceptedAt": datetime.now(timezone.utc),
        }, profile)

        if existing:
            user = await prisma.user.update(where={"id": existing.id}, data=data)
            action = "Refreshed"
        else:
            user = await prisma.user.create(data={"phone": DEMO_PHONE, **data})
            action = "Created"

        stored = profile_store.load(user)
        print(f"{action} demo citizen: {profile['name']}  (id {user.id})")
        print(f"  phone     : {DEMO_PHONE}   (OTP 123456 in a DEMO_MODE build)")
        print(f"  profile   : {len(stored)} fields stored; "
              f"aadhaar kept as {stored.get('aadhaar_number_last4', '—')} (last 4 only)")
        print(f"  state     : {profile['state']}, {profile['district']}")
        print()
        print("Walk the app end to end:")
        print("  1. Log in with the phone above and OTP 123456.")
        print("  2. Discover: the profile is complete, so eligible Central + State")
        print("     schemes show at once (Ladli Behna, Sukanya, PM-KISAN, scholarships…).")
        print("  3. Pick a scheme → the intake questions are already answered →")
        print("     generate the filled government PDF → download it.")
        print("  4. Documents: open 'what to carry' for any scheme.")
        print("  5. Voice: tap the mic (DEMO_MODE returns a mock transcript, or")
        print("     configure a speech engine — see backend/.env.example).")
        print("  6. KYC / DPDP: try identity verification, the privacy notice,")
        print("     consent, and 'my data' — the demo citizen has data to show.")
        print("  7. Language: switch among the 22 languages.")
        return 0
    finally:
        await prisma.disconnect()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--remove", action="store_true", help="Delete the demo citizen and exit")
    args = ap.parse_args()
    return asyncio.run(seed(args.remove))


if __name__ == "__main__":
    sys.exit(main())
