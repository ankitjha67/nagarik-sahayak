#!/usr/bin/env python3
"""Fill one real government form, end to end, and show every step.

    python scripts/demo_fill.py                       # default scheme
    python scripts/demo_fill.py --scheme "PM-KISAN Samman Nidhi"
    python scripts/demo_fill.py --out /tmp/demo --png  # also render page images

Unlike the smoke test, which asserts, this narrates: it prints what was
downloaded, what was read out of it, what the citizen supplied, which values
went into which fields, what the gate decided, and where the file landed. It is
what you run when someone asks "show me it actually working".

The applicant is synthetic. The Aadhaar carries a correct Verhoeff checksum so
the validator exercises its real path, but the number belongs to nobody.
"""
import argparse
import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_SCHEME = "Sports Achievement Scholarship (Haryana)"


def rule(title=""):
    print(f"\n{'─' * 78}")
    if title:
        print(title)
        print("─" * 78)


def kv(label, value, indent=2):
    print(f"{' ' * indent}{label:<26} {value}")


def demo_applicant():
    """A synthetic applicant for the Haryana sports scholarship."""
    from validation import verhoeff_check_digit

    return {
        "name": "Priya Sharma",
        "father_husband_name": "Rajesh Sharma",
        "mother_name": "Kamla Sharma",
        "aadhaar_number": "73629184057" + verhoeff_check_digit("73629184057"),
        "date_of_birth": "2005-08-14",
        "age": 20,
        "gender": "Female",
        "category": "OBC",
        "mobile_number": "9812345678",
        "email": "priya.sharma@example.com",
        "address_line": "House No. 214, Sector 7, Model Town",
        "village": "Bahadurgarh",
        "district": "Jhajjar",
        "state": "Haryana",
        "pincode": "124507",
        "domicile_certificate_number": "HR/JHJ/2019/004821",
        "institution_name": "Government College for Women, Bahadurgarh",
        "sport_name": "Kabaddi",
        "event_name": "Haryana State Senior Kabaddi Championship 2025",
        "event_date": "2025-11-18",
        "achievement_position": "First",
        "bank_account_number": "39281746503921",
        "ifsc_code": "PUNB0123456",
        "bank_name": "Punjab National Bank",
        "branch_name": "Bahadurgarh Main",
    }


def download(url: str, dest: Path) -> Path | None:
    import requests

    try:
        r = requests.get(url, timeout=45, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as exc:
        print(f"  Could not download: {type(exc).__name__}: {exc}")
        return None
    if not r.content.startswith(b"%PDF"):
        print("  Downloaded, but it is not a PDF.")
        return None
    dest.write_bytes(r.content)
    return dest


def render_pages(pdf: Path, out_dir: Path, prefix: str, limit: int = 4) -> list[Path]:
    """Rasterise the first few pages so the result can actually be looked at."""
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf
        except ImportError:
            return []
    images = []
    doc = pymupdf.open(pdf)
    for i, page in enumerate(doc):
        if i >= limit:
            break
        pix = page.get_pixmap(dpi=110)
        path = out_dir / f"{prefix}_page{i + 1}.png"
        pix.save(str(path))
        images.append(path)
    doc.close()
    return images


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scheme", default=DEFAULT_SCHEME)
    ap.add_argument("--out", default="/tmp/demo_fill")
    ap.add_argument("--png", action="store_true", help="Render pages to PNG")
    args = ap.parse_args()

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    from data.gov_forms import get_by_name

    scheme = get_by_name(args.scheme)
    if not scheme:
        print(f"'{args.scheme}' is not in the catalog.")
        return 1

    print("=" * 78)
    print("NAGARIK SAHAYAK — FILLING ONE REAL GOVERNMENT FORM")
    print("=" * 78)
    kv("Scheme", scheme["schemeName"], indent=0)
    kv("Hindi", scheme["schemeNameHindi"], indent=0)
    kv("Level", f"{scheme['level']}" + (f" · {scheme['state']}" if scheme["state"] else ""), indent=0)
    kv("Department portal", scheme["officialWebsite"], indent=0)

    # ── 1. The source document ───────────────────────────────────────────
    rule("1  THE SOURCE DOCUMENT")
    source_url = scheme.get("official_pdf_url", "")
    source_pdf = None
    if source_url:
        kv("Published at", source_url)
        source_pdf = download(source_url, out / "original.pdf")
        if source_pdf:
            size = source_pdf.stat().st_size
            kv("Downloaded", f"{source_pdf} ({size:,} bytes)")
            try:
                import pymupdf
            except ImportError:
                import fitz as pymupdf
            doc = pymupdf.open(source_pdf)
            text_chars = sum(len(p.get_text().strip()) for p in doc)
            widgets = sum(1 for p in doc for _ in p.widgets())
            kv("Pages", len(doc))
            kv("Extractable text", f"{text_chars:,} characters"
               + ("" if text_chars > 200 else "  ← image-only, needs OCR"))
            kv("Interactive fields", widgets if widgets else "0  ← not a fillable AcroForm")
            doc.close()
    else:
        kv("Published form", "none — this scheme is portal-only")

    # ── 2. What the app knows about the form ─────────────────────────────
    rule("2  WHAT THE APP KNOWS ABOUT THIS FORM")
    fields = scheme["extractedFields"]
    kv("Fields defined", len(fields))
    kv("Sections", ", ".join(s["name"] for s in scheme["sections"]))
    print()
    print(f"  {'FIELD ON THE FORM':<38} {'TYPE':<9} {'REQ':<4} PROFILE KEY")
    print(f"  {'-' * 38} {'-' * 9} {'-' * 4} {'-' * 24}")
    for f in fields:
        print(f"  {f['labelEnglish'][:37]:<38} {f['type']:<9} "
              f"{'yes' if f.get('required') else 'no':<4} {f['profileKey']}")

    # ── 3. The applicant ─────────────────────────────────────────────────
    rule("3  THE APPLICANT (synthetic)")
    profile = demo_applicant()
    from dpdp.aadhaar_policy import mask
    for key, value in profile.items():
        shown = mask(value) if key == "aadhaar_number" else value
        kv(key, shown)

    # ── 4. Field-by-field mapping ────────────────────────────────────────
    rule("4  HOW EACH FORM FIELD GETS ITS VALUE")
    from pdf_filler import _format_value_for_fill

    filled = missing = 0
    print(f"  {'FORM FIELD':<34} {'← PROFILE KEY':<26} VALUE WRITTEN")
    print(f"  {'-' * 34} {'-' * 26} {'-' * 22}")
    for f in fields:
        key = f["profileKey"]
        raw = profile.get(key)
        if raw in (None, ""):
            missing += 1
            note = "— blank" + (" (REQUIRED)" if f.get("required") else " (optional)")
            print(f"  {f['labelEnglish'][:33]:<34} {key:<26} {note}")
            continue
        filled += 1
        written = _format_value_for_fill(raw, f["type"])
        if key == "aadhaar_number":
            written = mask(written)
        print(f"  {f['labelEnglish'][:33]:<34} {key:<26} {str(written)[:22]}")
    print()
    kv("Filled", f"{filled} of {len(fields)}")
    kv("Left blank", missing)

    # ── 5. The gate ──────────────────────────────────────────────────────
    rule("5  THE GATE — may this form be issued?")
    from services import application_guard

    result = await application_guard.evaluate_application(
        profile=profile, scheme=scheme, check_fraud=True,
        history=__import__("fraud_detection").ApplicantHistory(),
    )
    kv("Outcome", result.outcome.value)
    kv("May issue the form", result.may_issue_form)
    kv("Validation errors", len(result.validation.get("findings", [])))
    kv("Risk score", result.risk.get("risk_score", 0))
    kv("Identity assurance", result.identity["label"])
    for r in result.reasons_en:
        kv("Reason", r)
    if not result.may_issue_form:
        print("\n  The gate refused, so no form is produced. That is the point of it.")
        return 1

    # ── 6. Writing onto the real government PDF ──────────────────────────
    rule("6  WRITING ONTO THE REAL GOVERNMENT PDF")
    overlay_out = out / "filled_official.pdf"
    if source_pdf:
        from pdf_filler import fill_pdf_form

        report = fill_pdf_form(
            source_pdf_path=str(source_pdf), output_path=str(overlay_out),
            field_values=profile, form_fields=fields,
        )
        kv("Strategy used", report.get("method", "none"))
        kv("Succeeded", report.get("success"))
        if report.get("success"):
            kv("Values written", f"{report.get('filled_count', 0)} of {len(fields)}")
            kv("Output", f"{overlay_out} ({overlay_out.stat().st_size:,} bytes)")
            unplaced = report.get("unplaced") or []
            if unplaced:
                print()
                print("  The printed form has no labelled space for these, so the")
                print("  citizen is told to write them by hand before they travel:")
                for u in unplaced:
                    flag = "must" if u["required"] else "optional"
                    print(f"      · {u['label'][:44]:<46} ({flag})")
        else:
            kv("Why not", report.get("error", "")[:66])
            print("      The published PDF is a flat scan with no interactive fields,")
            print("      so there is nowhere to put a value that would land in the")
            print("      right box. The app produces its own filled form instead —")
            print("      which is what a citizen carries to the office anyway.")
    else:
        kv("Skipped", "no published PDF for this scheme")

    # ── 7. The form the citizen actually gets ────────────────────────────
    rule("7  THE FORM THE CITIZEN ACTUALLY GETS")
    from pdf_generator import generate_real_filled_form_pdf

    for is_draft, name in ((True, "draft"), (False, "final")):
        path = out / f"application_{name}.pdf"
        generate_real_filled_form_pdf(
            filled_fields=profile,
            scheme_name=scheme["schemeName"],
            scheme_name_hindi=scheme["schemeNameHindi"],
            sections=scheme["sections"],
            form_fields=fields,
            output_path=str(path),
            is_draft=is_draft,
        )
        try:
            import pymupdf
        except ImportError:
            import fitz as pymupdf
        doc = pymupdf.open(path)
        text = "\n".join(p.get_text() for p in doc)
        pages = len(doc)
        doc.close()
        kv(f"{name.title()} PDF", f"{path} ({path.stat().st_size:,} bytes, {pages} pages)")
        kv("  Aadhaar rendered as",
           next((w for w in text.split() if "X" in w and w.count("X") >= 6),
                "not present"))
        kv("  Devanagari present", "yes" if any("ऀ" <= c <= "ॿ" for c in text) else "no")

    # ── 8. What is provably not in the file ──────────────────────────────
    rule("8  WHAT IS PROVABLY NOT IN THE FILE")
    from dpdp.aadhaar_policy import contains_full_aadhaar

    for name in ("application_draft", "application_final"):
        path = out / f"{name}.pdf"
        try:
            import pymupdf
        except ImportError:
            import fitz as pymupdf
        doc = pymupdf.open(path)
        text = "\n".join(p.get_text() for p in doc)
        doc.close()
        leaked = contains_full_aadhaar({"pdf_text": text})
        kv(f"{name}.pdf", "no full Aadhaar" if not leaked else f"LEAK: {leaked}")
    print("\n  Aadhaar Act s29(4) makes publishing an Aadhaar number an offence,")
    print("  so the generated form carries the last four digits only. The number")
    print("  the citizen writes on the counter copy is theirs to write.")

    # ── 9. Rendered pages ────────────────────────────────────────────────
    if args.png:
        rule("9  RENDERED PAGES")
        for pdf_name, prefix in (("original.pdf", "original"),
                                 ("filled_official.pdf", "filled_official"),
                                 ("application_final.pdf", "application")):
            path = out / pdf_name
            if not path.exists():
                continue
            for img in render_pages(path, out, prefix):
                kv(img.name, f"{img.stat().st_size:,} bytes")

    rule("EVERYTHING WRITTEN TO")
    for p in sorted(out.iterdir()):
        print(f"  {p}  ({p.stat().st_size:,} bytes)")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
