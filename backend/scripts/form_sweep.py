#!/usr/bin/env python3
"""Fill every form in the catalog and report what went wrong.

One form tells you the filler works on one form. The Haryana sports form was
developed against, so of course it fills; the question that matters is what
happens on the next form, drawn by a different department in a different state
with different conventions. This runs the whole catalog and prints a diagnosis
per form, so a regression anywhere is visible in one place.

The synthetic applicant is built per scheme from the field catalog, the same
way scripts/demo_fill.py builds one, so a form asking about land holdings gets
a farmer and a form asking about a course gets a student.

What it checks, per form:

  * the PDF downloads and opens at all
  * the grid is recovered (or honestly reported as absent)
  * the pre-flight audit agrees with what the fill actually managed
  * every mandatory field the applicant answered is on the page
  * the post-fill verification is clean
  * nothing the applicant supplied vanished — it is placed or reported
  * values are not silently mangled: truncated, de-spaced, or ellipsised

Usage:
    python scripts/form_sweep.py                # every form with a PDF
    python scripts/form_sweep.py haryana daman  # only matching schemes
    python scripts/form_sweep.py --json out.json
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pdf_filler  # noqa: E402
from pdf_filler import audit_form, fill_pdf_form  # noqa: E402
from data.gov_forms import GOV_FORM_CATALOG  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo_fill import demo_applicant  # noqa: E402

CACHE = Path(os.environ.get("FORM_SWEEP_CACHE", "/tmp/form_sweep_pdfs"))
OUT = Path(os.environ.get("FORM_SWEEP_OUT", "/tmp/form_sweep_filled"))


def source_url(scheme: dict) -> str:
    """The PDF to fill. Only an official form counts.

    A reference PDF is a booklet or an eligibility leaflet — PM-KISAN's scheme
    booklet, the SARAL information sheet — and filling one is not a thing that
    can succeed. Judging those as failures buried the forms that genuinely
    were failing, so they are listed separately and not scored.
    """
    return scheme.get("official_pdf_url") or ""


def fetch(scheme: dict) -> Path | None:
    """The scheme's PDF on disk, downloaded once and kept."""
    url = source_url(scheme)
    if not url:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() else "_" for c in scheme["schemeName"])[:60]
    path = CACHE / f"{slug}.pdf"
    if path.exists() and path.stat().st_size > 1000:
        return path
    try:
        urllib.request.urlretrieve(url, path)
    except Exception as exc:  # noqa: BLE001 — an unreachable form is a finding
        print(f"    download failed: {type(exc).__name__}: {exc}")
        return None
    return path if path.exists() else None


# Words that mark a document as something other than an application form.
# Each was found on a PDF the catalog was offering as a form to fill.
_NOT_A_FORM = {
    "post applied for": "a recruitment form, not an application for the scheme",
    "teaching experience": "a recruitment form, not an application for the scheme",
    "rts time limit": "a service-charter leaflet, not a form",
    "fees for the service": "a service-charter leaflet, not a form",
}


def looks_like_the_wrong_document(path, scheme: dict) -> list[str]:
    """Whether this PDF is plausibly the form this scheme says it is.

    Three of the six PDFs in the catalog turned out to be something else: a
    scheme booklet, an eligibility leaflet, and a teacher-recruitment form
    offered as a school admission form. Each was caught only by reading the
    PDF, and each would have sent a citizen to a counter with the wrong paper.
    So the check runs every sweep.

    Two signals, both weak on their own and reported rather than enforced:
    the document announces itself as something else, or it carries none of the
    words in the scheme's own name.
    """
    import pymupdf

    try:
        doc = pymupdf.open(str(path))
        text = " ".join((doc[i].get_text() or "") for i in range(min(4, doc.page_count)))
        doc.close()
    except Exception:  # noqa: BLE001
        return []

    flat = " ".join(text.lower().split())
    if len(flat) < 40:
        return []          # a scan; OCR judges it elsewhere, not here

    out = []
    for marker, why in _NOT_A_FORM.items():
        if marker in flat:
            out.append(f"looks like {why} (found {marker!r})")

    stop = {"scheme", "yojana", "the", "and", "of", "for", "a", "pension",
            "scholarship", "card", "national", "central", "state"}
    keywords = [w.strip("()-,").lower() for w in scheme["schemeName"].split()]
    keywords = [w for w in keywords if len(w) > 3 and w not in stop]
    if keywords and not any(k in flat for k in keywords):
        out.append(f"none of the scheme's own words appear in it: {keywords}")
    return out


def mangled(written: dict, profile: dict, fields: list) -> list[str]:
    """Values that reached the page in a form the citizen did not give.

    A value that arrives truncated, ellipsised, or with its spaces removed is
    worse than one left blank: the citizen signs a form that misstates their
    own name, and neither they nor the clerk has any way to tell it was the
    software that did it.
    """
    types = {f.get("profileKey"): f.get("type", "text") for f in fields}
    out = []
    for item in written.values():
        key = item.get("profileKey")
        given = profile.get(key)
        if given in (None, ""):
            continue
        got = str(item.get("text", ""))
        # Numbers are deliberately stripped of the separators a citizen types,
        # and an Aadhaar is deliberately masked. Both are correct, not mangled.
        if types.get(key) in ("aadhaar", "phone", "number"):
            continue
        if item.get("truncated"):
            out.append(f"{key}: truncated to {got!r}")
        elif "…" in got or got.endswith("..."):
            out.append(f"{key}: ellipsised to {got!r}")
        elif " " in str(given).strip() and " " not in got and len(got) > 3:
            out.append(f"{key}: spaces lost, {str(given)!r} -> {got!r}")
    return out


def run_one(scheme: dict) -> dict:
    name = scheme["schemeName"]
    where = scheme.get("state") or scheme.get("level")
    print(f"\n{'=' * 74}\n{name}  [{where}]\n{'=' * 74}")

    fields = scheme["extractedFields"]
    result = {"scheme": name, "where": where, "totalFields": len(fields)}

    path = fetch(scheme)
    if path is None:
        print("    no downloadable PDF — nothing to fill")
        result["status"] = "no-pdf"
        return result

    profile = demo_applicant(scheme)
    supplied = {f["profileKey"] for f in fields if profile.get(f["profileKey"])}
    mandatory = {f["profileKey"] for f in fields
                 if f.get("required") and profile.get(f["profileKey"])}

    t0 = time.time()
    audit = audit_form(str(path), fields, profile)
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / f"{path.stem}_filled.pdf"
    report = fill_pdf_form(str(path), str(out_path), profile, fields)
    elapsed = time.time() - t0

    written = {w["fieldName"]: w for w in report.get("written", [])}
    satisfied = {k for w in report.get("written", [])
                 for k in w.get("satisfies", [w["profileKey"]])}
    reported = {u["profileKey"] for u in report.get("unplaced", [])}
    verification = report.get("verification") or {}
    problems = verification.get("problems", [])

    print(f"    pages {audit.get('pages', '?')}   "
          f"grid {'yes' if audit.get('gridDetected') else 'no'}   "
          f"{elapsed:.0f}s")
    print(f"    audit says addressable   {len(audit.get('addressableOnForm', []))}"
          f" of {len(fields)}")
    print(f"    actually written         {len(written)}")
    print(f"    mandatory answered       "
          f"{len(mandatory & satisfied)} of {len(mandatory)}")

    issues = list(looks_like_the_wrong_document(path, scheme))
    missing_mandatory = sorted(mandatory - satisfied)
    if missing_mandatory:
        issues.append("mandatory not on the form: " + ", ".join(missing_mandatory))
    lost = sorted(supplied - satisfied - reported - set(written))
    if lost:
        issues.append("supplied but neither placed nor reported: " + ", ".join(lost))
    for p in problems:
        issues.append(f"{p['kind']}: {p.get('profileKey')} — {p.get('detail', '')}")
    issues.extend(mangled(written, profile, fields))
    if not report.get("success"):
        issues.append(f"fill failed: {report.get('error')}")

    if issues:
        print("    ISSUES")
        for i in issues:
            print(f"      · {i}")
    else:
        print("    clean")

    result.update({
        "status": "ok" if not issues else "issues",
        "seconds": round(elapsed, 1),
        "pages": audit.get("pages"),
        "gridDetected": audit.get("gridDetected"),
        "addressable": len(audit.get("addressableOnForm", [])),
        "written": len(written),
        "mandatory": [len(mandatory & satisfied), len(mandatory)],
        "issues": issues,
        "placements": [
            {"field": w["fieldName"], "page": w["page"],
             "x": round(w["x"], 1), "y": round(w["y"], 1), "text": w["text"]}
            for w in sorted(report.get("written", []),
                            key=lambda w: (w["page"], w["y"]))
        ],
        "output": str(out_path),
    })
    return result


def main() -> int:
    argv = sys.argv[1:]
    json_out = None
    if "--json" in argv:
        i = argv.index("--json")
        json_out = argv[i + 1] if i + 1 < len(argv) else "/tmp/form_sweep.json"
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]

    reference_only = [s for s in GOV_FORM_CATALOG
                      if not source_url(s) and s.get("reference_pdf_url")]
    online_only = [s for s in GOV_FORM_CATALOG
                   if not source_url(s) and not s.get("reference_pdf_url")]
    schemes = [s for s in GOV_FORM_CATALOG if source_url(s)]
    if args:
        wanted = [a.lower() for a in args]
        schemes = [s for s in schemes
                   if any(w in s["schemeName"].lower()
                          or w in str(s.get("state", "")).lower()
                          for w in wanted)]

    results = [run_one(s) for s in schemes]

    print(f"\n{'=' * 74}\nSUMMARY\n{'=' * 74}")
    for r in results:
        flag = {"ok": "clean", "no-pdf": "no pdf"}.get(r["status"], "ISSUES")
        counts = (f"{r.get('written', 0):2d}/{r['totalFields']:2d} written, "
                  f"{r.get('mandatory', [0, 0])[0]}/{r.get('mandatory', [0, 0])[1]} mandatory"
                  if r["status"] != "no-pdf" else "")
        print(f"  {flag:7s} {r['scheme'][:44]:46s} {counts}")
        for i in r.get("issues", []):
            print(f"            · {i[:100]}")

    if not args:
        for s in reference_only:
            print(f"  ref     {s['schemeName'][:44]:46s} "
                  f"reference document, no form to fill")
        for s in online_only:
            print(f"  online  {s['schemeName'][:44]:46s} "
                  f"applied for online, no published form")

    total_issues = sum(len(r.get("issues", [])) for r in results)
    print(f"\n  {len(results)} fillable forms, {total_issues} issues; "
          f"{len(reference_only)} reference-only, {len(online_only)} online-only")

    if json_out:
        Path(json_out).write_text(json.dumps(results, indent=2, default=str))
        print(f"  written to {json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
