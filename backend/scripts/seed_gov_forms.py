#!/usr/bin/env python3
"""CLI for managing the real government form catalog.

Usage (run from the backend/ directory):

    python scripts/seed_gov_forms.py seed              # seed DB from catalog
    python scripts/seed_gov_forms.py seed --overwrite  # force-refresh templates
    python scripts/seed_gov_forms.py verify            # check catalog PDF links
    python scripts/seed_gov_forms.py extract <URL>     # extract a live PDF
    python scripts/seed_gov_forms.py refresh [scheme]  # re-extract from live PDF

`verify` and `extract` need no database, so they are usable as a quick
connectivity/extraction smoke test in CI or on a fresh machine.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

# Allow running as `python scripts/seed_gov_forms.py` from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def cmd_seed(args) -> int:
    from database import prisma
    from services.form_seeder import seed_from_catalog

    await prisma.connect()
    try:
        report = await seed_from_catalog(overwrite=args.overwrite)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1 if report["errors"] else 0
    finally:
        await prisma.disconnect()


async def cmd_verify(args) -> int:
    from services.form_seeder import verify_catalog_urls

    report = await verify_catalog_urls()
    for r in report["results"]:
        if r.get("status") == "no_url":
            # Curated-only scheme: intentional, not a broken link.
            icon, detail = "CURATED", "no published PDF — using curated fields"
        elif r["ok"]:
            icon = "OK"
            detail = f"HTTP {r['http_status']}, valid PDF"
        else:
            icon = "BROKEN"
            detail = (f"HTTP {r['http_status']}, pdf={r.get('is_pdf')}"
                      if r.get("http_status") else r.get("status", "unreachable"))
        print(f"[{icon:7s}] {r['scheme'][:42]:42s} {detail}")

    broken = report["with_url"] - report["healthy"]
    print(
        f"\n{report['healthy']}/{report['with_url']} live PDF links healthy, "
        f"{report['total'] - report['with_url']} curated-only "
        f"({report['total']} catalog entries)"
    )
    # Only genuinely broken links are a failure; curated-only entries are fine.
    return 1 if broken else 0


async def cmd_extract(args) -> int:
    from form_extractor import extract_form_fields

    result = await extract_form_fields(pdf_url=args.url, scheme_hint=args.hint or "")
    if result.get("error"):
        print(f"ERROR: {result['error']}", file=sys.stderr)
        return 1

    print(f"Scheme:  {result.get('schemeName', '?')}")
    print(f"Category:{result.get('category', '?')}")
    print(f"Engine:  {result.get('_extraction_engine')} "
          f"(text via {result.get('_extraction_method')})")
    print(f"Fields:  {result.get('totalFields', 0)}\n")
    for f in result.get("extractedFields", []):
        req = "*" if f.get("required") else " "
        print(f"  {req} {f.get('profileKey', ''):28s} {f.get('type', ''):9s} "
              f"{f.get('labelEnglish', '')[:44]}")
    return 0


async def cmd_refresh(args) -> int:
    from database import prisma
    from data.gov_forms import get_catalog
    from services.form_seeder import refresh_from_live_pdf

    names = [args.scheme] if args.scheme else [
        e["schemeName"] for e in get_catalog() if e.get("official_pdf_url")
    ]

    await prisma.connect()
    try:
        failures = 0
        for name in names:
            result = await refresh_from_live_pdf(name)
            status = "ok" if result.get("success") else "FAILED"
            note = result.get("reason") or result.get("error") or result.get("action", "")
            if not result.get("success"):
                failures += 1
            print(f"[{status:6s}] {name[:40]:40s} {note}")
        return 1 if failures else 0
    finally:
        await prisma.disconnect()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed", help="Seed DB from the curated catalog")
    p_seed.add_argument("--overwrite", action="store_true",
                        help="Replace existing templates (discards live/uploaded edits)")
    p_seed.set_defaults(func=cmd_seed)

    p_verify = sub.add_parser("verify", help="Check catalog PDF links are live")
    p_verify.set_defaults(func=cmd_verify)

    p_extract = sub.add_parser("extract", help="Extract fields from a live PDF URL")
    p_extract.add_argument("url")
    p_extract.add_argument("--hint", help="Scheme name hint")
    p_extract.set_defaults(func=cmd_extract)

    p_refresh = sub.add_parser("refresh", help="Re-extract catalog forms from live PDFs")
    p_refresh.add_argument("scheme", nargs="?", help="Scheme name (default: all)")
    p_refresh.set_defaults(func=cmd_refresh)

    args = parser.parse_args()
    return asyncio.run(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
