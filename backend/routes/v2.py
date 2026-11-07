"""V2.0 API routes - real form templates, smart profiler, filled PDF generation."""
import json
import logging
import time as _time
from datetime import datetime, timezone
from fastapi import HTTPException
from database import prisma, find_user
from config import PDF_DIR, AGNOST_WRITE_KEY
from routes import api_router

logger = logging.getLogger(__name__)


def _fields_from_template(ft) -> list:
    """The extractedFields of a form template, tolerating list or JSON-string."""
    f = ft.extractedFields
    if isinstance(f, list):
        return f
    if isinstance(f, str) and f:
        try:
            return json.loads(f)
        except json.JSONDecodeError:
            return []
    return []


def _require_scheme_names(req: dict) -> list[str]:
    """The scheme names a request selects, or a 400.

    A string where a list was meant iterates as its characters and resolved
    to whichever schemes those letters happened to prefix; a None or a number
    inside the list raised. Both answered 200 or 500 where 400 was due.
    """
    names = req.get("scheme_names")
    if (not isinstance(names, list) or not names
            or not all(isinstance(n, str) and n.strip() for n in names)):
        raise HTTPException(
            status_code=400,
            detail="scheme_names must be a non-empty list of scheme names")
    return [n.strip() for n in names]


async def _fields_for_scheme(scheme_name: str) -> list:
    """Every field a scheme's form asks for.

    Prefers the curated catalog, which carries canonical profile keys, select
    options and bilingual labels and is always present. Falls back to a
    database-seeded template for a scheme uploaded or live-refreshed but not in
    the bundled catalog.
    """
    from data.gov_forms import get_by_name

    entry = get_by_name(scheme_name)
    if entry and entry.get("extractedFields"):
        return entry["extractedFields"]
    ft = await prisma.formtemplate.find_first(where={"schemeName": scheme_name})
    return _fields_from_template(ft) if ft else []


def _ensure_local_source(official_pdf_url: str) -> str:
    """A local path to the blank official form, fetched once and reused.

    The real fill engine overlays answers onto the published government PDF, so
    it needs that PDF on disk. A `/api/pdf/<id>` URL already names a local file;
    an http(s) URL is downloaded once into a cache under PDF_DIR and reused on
    later fills. The blank form is a public document carrying no citizen data,
    so it is cached in the clear. Any failure returns "" and the caller falls
    back to a generated form rather than denying the citizen a document.
    """
    if not official_pdf_url:
        return ""
    if official_pdf_url.startswith("/api/pdf/"):
        local_id = official_pdf_url.replace("/api/pdf/", "").strip("/")
        candidate = PDF_DIR / f"{local_id}.pdf"
        return str(candidate) if candidate.exists() else ""
    if not official_pdf_url.lower().startswith(("http://", "https://")):
        return ""

    import hashlib

    cache_dir = PDF_DIR / "_form_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / (hashlib.sha256(official_pdf_url.encode()).hexdigest()[:20] + ".pdf")
    if cached.exists() and cached.stat().st_size > 1000:
        return str(cached)
    try:
        import requests

        resp = requests.get(official_pdf_url, timeout=45,
                            headers={"User-Agent": "Mozilla/5.0 (NagarikSahayak)"})
        resp.raise_for_status()
        if resp.content[:4] != b"%PDF":
            logger.warning(f"Official form URL did not return a PDF: {official_pdf_url}")
            return ""
        cached.write_bytes(resp.content)
        return str(cached)
    except Exception as e:  # noqa: BLE001 - never let a dead link deny a form
        logger.warning(f"Could not fetch official form {official_pdf_url}: {e}")
        return ""


async def _store_full_profile(user, fields: dict) -> dict:
    """Merge validated fields into the citizen's encrypted full profile.

    One write path, shared by the bulk profile update and the single-answer
    intake step, so the Aadhaar-stripping, fingerprinting and Json() wrapping
    are defined once. The Aadhaar is NOT dropped here: profile_store strips the
    full number on the way to disk but keeps the last-four marker and keyed
    fingerprint, and that marker is what tells the eligibility gate an identity
    document was supplied. Stripping the whole field before storage (an earlier
    mistake) erased the marker, so a citizen who had given their Aadhaar was
    then refused for "no identity document".
    """
    from datetime import datetime, timezone

    from prisma import Json
    import identity_index
    from dpdp import profile_store

    existing = profile_store.load_full(user)
    existing.update(fields)

    fingerprint_source = dict(existing)
    stored_value, storable = profile_store.prepare_full_profile(existing)
    await prisma.user.update(
        where={"id": user.id},
        data=identity_index.merge_into_update({
            "fullProfile": Json(stored_value),
            "profileLastUpdated": datetime.now(timezone.utc),
        }, fingerprint_source),
    )
    return storable


@api_router.get("/v2/schemes")
async def get_all_schemes_v2():
    """Return all 4 real schemes with metadata."""
    schemes = await prisma.scheme.find_many()
    result = []
    for s in schemes:
        result.append({
            "id": s.id, "name": s.name, "nameHindi": s.nameHindi,
            "category": s.category, "description": s.description,
            "descriptionHindi": s.descriptionHindi,
            "officialWebsite": s.officialWebsite,
            "eligibilityCriteriaText": s.eligibilityCriteriaText,
        })
    return {"schemes": result, "count": len(result)}


@api_router.get("/v2/form-template/{scheme_name}")
async def get_form_template(scheme_name: str):
    """Return the full form template with all extracted fields for a scheme."""
    ft = await prisma.formtemplate.find_first(where={"schemeName": scheme_name})
    if not ft:
        raise HTTPException(status_code=404, detail=f"Form template not found for: {scheme_name}")
    fields = ft.extractedFields if isinstance(ft.extractedFields, list) else json.loads(ft.extractedFields) if isinstance(ft.extractedFields, str) else []
    sections = ft.sections if isinstance(ft.sections, list) else json.loads(ft.sections) if isinstance(ft.sections, str) else []
    eligibility = ft.eligibilityCriteria if isinstance(ft.eligibilityCriteria, dict) else json.loads(ft.eligibilityCriteria) if isinstance(ft.eligibilityCriteria, str) else {}
    return {
        "id": ft.id, "schemeName": ft.schemeName, "schemeNameHindi": ft.schemeNameHindi,
        "officialPdfUrl": ft.officialPdfUrl, "officialWebsite": ft.officialWebsite,
        "description": ft.description, "descriptionHindi": ft.descriptionHindi,
        "category": ft.category, "totalFields": ft.totalFields,
        "sections": sections, "eligibilityCriteria": eligibility,
        "extractedFields": fields,
    }


@api_router.get("/v2/form-templates")
async def get_all_form_templates():
    """Return summary of all form templates."""
    templates = await prisma.formtemplate.find_many()
    result = []
    for ft in templates:
        result.append({
            "id": ft.id, "schemeName": ft.schemeName,
            "schemeNameHindi": ft.schemeNameHindi, "category": ft.category,
            "totalFields": ft.totalFields, "description": ft.description,
            "descriptionHindi": ft.descriptionHindi,
        })
    return {"templates": result, "count": len(result)}


@api_router.get("/v2/user-profile/{user_id}")
async def get_user_full_profile(user_id: str):
    """Return persistent full profile for a user."""
    try:
        user = await find_user(user_id)
    except Exception:
        raise HTTPException(status_code=404, detail="User not found")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    from dpdp import profile_store
    full_profile = profile_store.load_full(user)
    return {
        "user_id": user.id, "phone": user.phone, "fullProfile": full_profile,
        "profileLastUpdated": user.profileLastUpdated.isoformat() if user.profileLastUpdated else None,
        "schemeHistory": user.schemeHistory if isinstance(user.schemeHistory, list) else json.loads(user.schemeHistory) if isinstance(user.schemeHistory, str) and user.schemeHistory else [],
    }


@api_router.post("/v2/user-profile/{user_id}")
async def update_user_full_profile(user_id: str, req: dict = {}):
    """Update persistent full profile with new field values. Merges, never overwrites."""
    fields = req.get("fields", {})
    if not isinstance(fields, dict) or not fields:
        # A string or list here used to reach dict.update() and raise a 500.
        raise HTTPException(status_code=400, detail="No fields provided")
    try:
        user = await find_user(user_id)
    except Exception:
        raise HTTPException(status_code=404, detail="User not found")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # One shared write path handles Aadhaar-stripping, fingerprinting and the
    # Json() wrapping fullProfile's column requires (passing the raw `enc:v1:...`
    # ciphertext unwrapped makes Prisma try to parse it as JSON and 500 every
    # save while encryption is on).
    storable = await _store_full_profile(user, fields)
    return {"success": True, "fullProfile": storable, "fieldsUpdated": list(fields.keys())}


@api_router.post("/v2/smart-profiler")
async def smart_profiler(req: dict = {}):
    """Given the forms a citizen has chosen, say what still has to be collected.

    Returns every field the forms ask for, split into what is already known,
    what is still needed (required *and* optional - the aim is to store all of a
    form's details, not only the mandatory ones), and the next question to ask,
    localised and with its type and options. Transient fields such as the
    Aadhaar number are reported separately and never counted as "missing": they
    are collected at the moment the form is filled and are not stored, so
    treating them as profile gaps would ask for them on every turn forever.
    """
    user_id = req.get("user_id", "")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id and scheme_names required")
    scheme_names = _require_scheme_names(req)

    user = await find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    from dpdp import profile_store
    from services import form_intake

    full_profile = profile_store.load(user)

    schemes = [{"extractedFields": await _fields_for_scheme(s)} for s in scheme_names]
    all_fields = form_intake.collect_fields(schemes)
    state = form_intake.intake_state(full_profile, all_fields)

    # `missing` (required only) and the flat counts are kept for existing
    # callers; the richer split (optional, transient, requiredComplete) is added
    # alongside so the interface can keep asking past the mandatory minimum.
    return {
        "totalFields": state["storableTotal"],
        "filledCount": state["knownCount"],
        "missingCount": state["missingRequiredCount"],
        "progress": state["progress"],
        "filled": state["known"],
        "missing": state["missingRequired"],
        "missingOptional": state["missingOptional"],
        "transient": [form_intake.question_for(f) for f in state["transient"]],
        "nextQuestion": state["nextQuestion"],
        "requiredComplete": state["requiredComplete"],
        "allComplete": state["allComplete"],
    }


@api_router.post("/v2/answer-field")
async def answer_field(req: dict = {}):
    """Record one answer the citizen has given, then hand back the next question.

    This is the interactive loop: the form asks for a detail, the citizen types
    it, this validates it, stores it against their profile (so the next form
    that needs it will not ask again), and returns the next thing to collect.

    Body: {user_id, profileKey, value, scheme_names: [...]}

    A malformed answer is rejected with a message in both languages and nothing
    is stored - the same question comes back so the citizen can correct it. An
    absent answer to an optional field is accepted as "skip". Transient fields
    (the Aadhaar number) are validated and echoed back for immediate use but are
    deliberately not persisted.
    """
    user_id = req.get("user_id", "")
    profile_key = str(req.get("profileKey") or req.get("field") or "").strip()
    if not user_id or not profile_key:
        raise HTTPException(
            status_code=400,
            detail="user_id, profileKey and scheme_names are required")
    scheme_names = _require_scheme_names(req)

    user = await find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from dpdp import profile_store
    from services import form_intake

    schemes = [{"extractedFields": await _fields_for_scheme(s)} for s in scheme_names]
    all_fields = form_intake.collect_fields(schemes)
    field = next((f for f in all_fields
                  if form_intake.field_key(f) == profile_key), None)
    if not field:
        raise HTTPException(
            status_code=400,
            detail=f"'{profile_key}' is not a field of the selected form(s)")

    value, error_en, error_hi = form_intake.validate_answer(field, req.get("value"))
    if error_en:
        # Rejected: say why, and ask the same question again. Nothing stored.
        return {
            "accepted": False,
            "profileKey": profile_key,
            "errorEnglish": error_en,
            "errorHindi": error_hi,
            "question": form_intake.question_for(field),
        }

    transient = profile_key in form_intake.TRANSIENT_KEYS
    stored = False
    if value != "":
        # Blank optional answers are a valid "skip" and need no write. A
        # transient field (the Aadhaar) is still written: profile_store keeps
        # only its last-four marker, never the full number, and that marker is
        # what spares the citizen from being asked for it again and lets the
        # eligibility gate see that an identity document was supplied.
        await _store_full_profile(user, {profile_key: value})
        stored = True

    user = await find_user(user_id)
    full_profile = profile_store.load(user)
    state = form_intake.intake_state(full_profile, all_fields)

    # Never echo a full Aadhaar back, even to its owner (Aadhaar Act s29(4));
    # the client only needs to see that it was accepted.
    echoed = value
    if transient and value:
        from dpdp.aadhaar_policy import mask
        echoed = mask(str(value))

    return {
        "accepted": True,
        "profileKey": profile_key,
        "storedValue": echoed,
        "stored": stored,
        "transient": transient,
        "progress": state["progress"],
        "requiredComplete": state["requiredComplete"],
        "allComplete": state["allComplete"],
        "nextQuestion": state["nextQuestion"],
        "readyToFill": state["requiredComplete"],
    }


@api_router.post("/v2/generate-filled-forms")
async def generate_real_filled_forms(req: dict = {}):
    """Generate pre-filled PDFs for selected schemes."""
    import uuid
    from pdf_generator import generate_real_filled_form_pdf
    from pdf_filler import fill_pdf_form
    from prisma import Json

    user_id = req.get("user_id", "")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id and scheme_names required")
    scheme_names = _require_scheme_names(req)

    user = await find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    from dpdp import profile_store
    full_profile = profile_store.load(user)

    # The Aadhaar (or any identity document) a citizen supplies for this fill is
    # transient: used to issue the document and never stored (profile_store
    # strips it, so full_profile carries none). It must be merged in *before the
    # eligibility gate*, or a citizen who gives their Aadhaar only at fill time
    # is wrongly refused for "no identity document". It is used to gate and to
    # fill; it is never written to the stored profile or the application record.
    fill_profile = dict(full_profile)
    txn_aadhaar = str(req.get("aadhaar_number") or "").strip()
    if txn_aadhaar:
        fill_profile["aadhaar_number"] = txn_aadhaar

    t0 = _time.time()
    pdf_urls = []
    refused = []
    flagged_for_review = []
    for sname in scheme_names:
        ft = await prisma.formtemplate.find_first(where={"schemeName": sname})
        if not ft:
            continue
        fields = ft.extractedFields if isinstance(ft.extractedFields, list) else json.loads(ft.extractedFields) if isinstance(ft.extractedFields, str) else []
        sections = ft.sections if isinstance(ft.sections, list) else json.loads(ft.sections) if isinstance(ft.sections, str) else []

        # Gate before issuing anything. A pre-filled government form is a real
        # artefact a citizen may submit at a CSC counter, so generating one for
        # an applicant who fails the scheme's own rules wastes their trip and
        # pollutes the department's intake.
        gate = None
        try:
            from data.gov_forms import get_by_name
            from services import application_guard

            catalog_entry = get_by_name(sname)
            if catalog_entry:
                scheme_for_gate = dict(catalog_entry)
                scheme_for_gate["extractedFields"] = fields
                gate = await application_guard.evaluate_application(
                    profile=fill_profile, scheme=scheme_for_gate,
                    user_id=user_id, check_fraud=True,
                )
        except Exception as e:
            # A fault in the guard must not deny a citizen their form; log it
            # and fall through to the previous behaviour.
            logger.warning(f"Application guard failed for {sname}: {e}")
            gate = None

        if gate is not None:
            logger.info("Gate %s for %s: %s (risk=%s)", gate.outcome.value, sname,
                        user_id, gate.risk.get("risk_score", 0))
            if not gate.may_issue_form:
                refused.append({
                    "scheme_name": sname,
                    "outcome": gate.outcome.value,
                    "reasons_en": gate.reasons_en,
                    "reasons_hi": gate.reasons_hi,
                })
                continue
            if gate.risk.get("requires_human_review"):
                # Raise a case so a person actually sees this. enqueue() returns
                # None rather than raising if the queue is down - the citizen
                # still gets their form; only the review record is lost.
                from services import review_queue
                case_id = await review_queue.enqueue(user_id, gate)
                flagged_for_review.append({
                    "scheme_name": sname,
                    "risk_score": gate.risk.get("risk_score", 0),
                    "signals": [s["code"] for s in gate.risk.get("signals", [])],
                    "review_case_id": case_id,
                })

        pid = str(uuid.uuid4())
        out_path = str(PDF_DIR / f"{pid}.pdf")
        # Record who this document belongs to before it exists on disk, so it
        # is never briefly downloadable by anyone holding the identifier.
        from dpdp import ownership
        await ownership.record_owner(pid, user_id, ownership.ArtefactKind.PDF)
        fill_method = "generated"

        # Fill onto the real published government PDF when one exists - a local
        # upload or the official URL, fetched and cached on first use. Only if
        # there is no live form to fill do we synthesise a generic one.
        source_pdf_path = _ensure_local_source(ft.officialPdfUrl or "")

        # fill_profile (built above, before the gate) carries the transient
        # Aadhaar for this one document. The fill engine prints only the masked
        # form - last four digits - never the full number (Aadhaar Act s29(4)).
        fill_detail: dict = {}
        if source_pdf_path:
            fill_result = fill_pdf_form(
                source_pdf_path=source_pdf_path, output_path=out_path,
                field_values=fill_profile, form_fields=fields,
            )
            if fill_result.get("success"):
                fill_method = fill_result.get("method", "filled")
                # What went on the page, and what the form has no slot for and
                # so must be written by hand - told to the citizen rather than
                # dropped silently.
                fill_detail = {
                    "filled_count": fill_result.get("filled_count", 0),
                    "to_write_by_hand": sorted(
                        {u.get("profileKey") for u in fill_result.get("unplaced", [])
                         if u.get("profileKey")}),
                }
                logger.info(f"PDF filled via {fill_method} for '{sname}': {fill_result.get('filled_count', 0)} fields")

        if fill_method == "generated":
            # Aadhaar is never printed in full. Section 29(4) forbids
            # displaying the number, and these PDFs sit on disk and are shared;
            # UIDAI permits only the masked form. The citizen writes the full
            # number onto the printed form themselves.
            is_draft = True
            generate_real_filled_form_pdf(
                filled_fields=full_profile, scheme_name=sname,
                scheme_name_hindi=ft.schemeNameHindi or "",
                sections=sections, form_fields=fields,
                output_path=out_path, is_draft=is_draft,
            )

        # Encrypt the freshly written document before it is linked. The
        # ownership check gates who may fetch it; this protects it if the disk
        # itself is obtained.
        from dpdp import file_vault
        file_vault.encrypt_in_place(out_path)

        pdf_urls.append({
            "pdf_url": f"/api/pdf/{pid}", "scheme_name": sname,
            "scheme_name_hindi": ft.schemeNameHindi or "",
            "fill_method": fill_method,
            **fill_detail,
        })

        scheme = await prisma.scheme.find_first(where={"name": sname})
        if scheme:
            await prisma.application.create(data={
                "userId": user_id, "schemeId": scheme.id,
                "status": "form_generated", "formUrl": f"/api/pdf/{pid}",
                "filledFields": Json(full_profile),
            })

    if AGNOST_WRITE_KEY:
        try:
            import agnost
            agnost.track(user_id=user_id, agent_name="nagarik_tool",
                         input="generate_real_filled_forms", output=str(len(pdf_urls)),
                         properties={"tool": "v2_pdf_gen", "schemes": scheme_names, "pdf_count": len(pdf_urls)},
                         success=True, latency=int((_time.time() - t0) * 1000))
        except Exception:
            pass

    return {
        "pdf_urls": pdf_urls,
        "count": len(pdf_urls),
        "profile_fields_used": len(full_profile),
        # Schemes the applicant was refused, each with a translated reason so
        # the UI can explain rather than silently omitting them.
        "refused": refused,
        # Issued, but held for verification before the benefit is released.
        "flagged_for_review": flagged_for_review,
    }


@api_router.post("/v2/extract-form-fields")
async def api_extract_form_fields(req: dict = {}):
    """Extract form fields from a PDF URL using Claude Sonnet 4.5."""
    from form_extractor import extract_form_fields

    pdf_url = req.get("pdf_url", "")
    scheme_hint = req.get("scheme_hint", "")
    if not pdf_url:
        raise HTTPException(status_code=400, detail="pdf_url is required")

    t0 = _time.time()
    result = await extract_form_fields(pdf_url=pdf_url, scheme_hint=scheme_hint)

    if "error" in result:
        if AGNOST_WRITE_KEY:
            try:
                import agnost
                agnost.track(user_id="system", agent_name="nagarik_tool",
                             input="extract_form_fields", output=result["error"],
                             properties={"tool": "form_extractor", "pdf_url": pdf_url},
                             success=False, latency=int((_time.time() - t0) * 1000))
            except Exception:
                pass
        raise HTTPException(status_code=422, detail=result["error"])

    if result.get("schemeName") and req.get("save_to_db", True):
        from prisma import Json
        existing = await prisma.formtemplate.find_first(where={"schemeName": result["schemeName"]})
        data = {
            "schemeName": result["schemeName"],
            "schemeNameHindi": result.get("schemeNameHindi", ""),
            "officialPdfUrl": pdf_url,
            "category": result.get("category", "general"),
            "totalFields": result.get("totalFields", len(result.get("extractedFields", []))),
            "extractedFields": Json(result.get("extractedFields", [])),
            "sections": Json(result.get("sections", [])),
        }
        if existing:
            await prisma.formtemplate.update(where={"id": existing.id}, data=data)
        else:
            await prisma.formtemplate.create(data=data)

    if AGNOST_WRITE_KEY:
        try:
            import agnost
            agnost.track(user_id="system", agent_name="nagarik_tool",
                         input="extract_form_fields", output=str(result.get("totalFields", 0)),
                         properties={"tool": "form_extractor", "scheme": result.get("schemeName", ""),
                                     "fields": result.get("totalFields", 0)},
                         success=True, latency=int((_time.time() - t0) * 1000))
        except Exception:
            pass

    return result
