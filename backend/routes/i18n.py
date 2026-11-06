"""Language routes.

Public and unauthenticated throughout: a person is entitled to read the
interface in their own language *before* they sign in or hand over anything.
Putting a language picker behind a login would be the same mistake as putting
the privacy notice there.
"""
import logging

from fastapi import HTTPException, Request

from routes import api_router
from i18n import languages, resolve
from i18n.catalog import KEYS

logger = logging.getLogger(__name__)


@api_router.get("/i18n/languages")
async def list_languages():
    """Every language, with its endonym, script, direction and real coverage.

    The endonym matters: a picker that offers "Bengali" to somebody who reads
    বাংলা is a picker they cannot use.
    """
    langs = resolve.catalogue()
    return {
        "languages": langs,
        "count": len(langs),
        "default": languages.DEFAULT,
        "summary": resolve.summary(),
    }


@api_router.get("/i18n/bundle/{code}")
async def language_bundle(code: str):
    """Every interface string for one language, with provenance.

    Keys that fell back to English are listed in `fallbacks` so the interface
    can mark them rather than passing them off as translated.
    """
    return resolve.bundle(code)


@api_router.get("/i18n/keys")
async def message_keys():
    """The message keys the interface uses. Useful to a translator."""
    return {"keys": list(KEYS), "count": len(KEYS)}


@api_router.get("/i18n/suggest")
async def suggest_language(request: Request, state: str = ""):
    """Which language to offer, from the citizen's State and browser.

    A State's own language ranks first — someone applying for a Tamil Nadu
    scheme should be offered Tamil ahead of Hindi.
    """
    return resolve.suggest(
        state=state,
        accept_language=request.headers.get("Accept-Language", ""))


@api_router.get("/i18n/coverage")
async def coverage_report():
    """Translation coverage against the s5(3) entitlement, for an operator.

    Reports the draft/reviewed distinction rather than a bare percentage,
    because 100% coverage in unreviewed text is not the same as 100% coverage,
    and an operator deciding whether to launch in a State needs to know which
    one they have.
    """
    return {
        "summary": resolve.summary(),
        "byLanguage": resolve.catalogue(),
    }


@api_router.post("/i18n/translate")
async def translate_keys(req: dict):
    """Resolve specific keys, reporting which language each actually came from.

    Body: {"keys": ["nav.schemes", ...], "language": "ta"}
    """
    keys = req.get("keys") or []
    if not isinstance(keys, list):
        raise HTTPException(status_code=400, detail="keys must be a list")
    if len(keys) > 500:
        raise HTTPException(status_code=400, detail="Too many keys in one request")
    code = str(req.get("language") or languages.DEFAULT)
    results = [resolve.resolve(str(k), code).as_dict() for k in keys]
    return {
        "language": languages.as_dict(languages.get(code)),
        "results": results,
        "fellBackCount": sum(1 for r in results if r["fellBack"]),
    }
