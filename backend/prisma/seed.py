"""Seed the Scheme table with 3 government schemes."""
import asyncio
from prisma import Prisma


SCHEMES = [
    {
        "name": "Pradhan Mantri Awas Yojana",
        "eligibilityCriteriaText": (
            "Family income < \u20b93 lakh per annum, no pucca house owned, "
            "rural or urban BPL category."
        ),
        "pdfUrl": "https://pmaymis.gov.in/pdf/pmay_guidelines.pdf",
    },
    {
        "name": "Vidyasiri Scholarship",
        "eligibilityCriteriaText": (
            "Karnataka resident, passed 10th or equivalent, "
            "family income < \u20b91.5 lakh, studying in Karnataka."
        ),
        "pdfUrl": "https://karnataka.gov.in/scholarship/vidyasiri.pdf",
    },
    {
        "name": "Vidya Lakshmi Education Loan",
        "eligibilityCriteriaText": (
            "Indian citizen, 12th pass, pursuing higher education "
            "in approved institution."
        ),
        "pdfUrl": "https://www.vidyalakshmi.co.in/files/guidelines.pdf",
    },
]


async def main():
    db = Prisma()
    await db.connect()

    # Upsert schemes (idempotent)
    for s in SCHEMES:
        existing = await db.scheme.find_first(where={"name": s["name"]})
        if existing:
            await db.scheme.update(where={"id": existing.id}, data=s)
            print(f"  Updated: {s['name']}")
        else:
            await db.scheme.create(data=s)
            print(f"  Created: {s['name']}")

    count = await db.scheme.count()
    print(f"\nScheme table: {count} records")

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
