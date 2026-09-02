"""Resolving a message in a language, and saying which language it came from.

The design point: a fallback is never silent. Every lookup reports the language
actually served, and every bundle reports the coverage and quality of what it
contains. A person reading English because Santali is unavailable must be told
that is what happened — otherwise the interface appears to be asserting that
English is their language, and they have no way to ask for better.
"""
from __future__ import annotations

from i18n import languages
from i18n.catalog import (
    KEYS, LOW_CONFIDENCE_REASON, LOW_CONFIDENCE_REASON_HI, MESSAGES, Quality,
    coverage, quality_of,
)


class Resolution:
    """One resolved string, plus where it came from."""

    __slots__ = ("key", "text", "language", "requested", "fell_back")

    def __init__(self, key: str, text: str, language: str, requested: str):
        self.key = key
        self.text = text
        self.language = language
        self.requested = requested
        self.fell_back = language != requested

    def __str__(self) -> str:
        return self.text

    def as_dict(self) -> dict:
        return {"key": self.key, "text": self.text, "language": self.language,
                "requested": self.requested, "fellBack": self.fell_back}


def resolve(key: str, code: str = "en") -> Resolution:
    """Look one key up, walking the fallback chain."""
    requested = languages.normalise(code)
    for candidate in languages.fallback_chain(requested):
        text = (MESSAGES.get(candidate) or {}).get(key)
        if text:
            return Resolution(key, text, candidate, requested)
    # An unknown key is a programming error, not a citizen-facing one. Return
    # the key itself rather than an empty string so it is visible in testing
    # instead of rendering as a blank label in production.
    return Resolution(key, key, languages.DEFAULT, requested)


def t(key: str, code: str = "en") -> str:
    """Shorthand for the text alone."""
    return resolve(key, code).text


def bundle(code: str) -> dict:
    """Every interface string for one language, with provenance.

    `fallbacks` names the keys that came from English rather than the requested
    language, so the UI can mark them rather than passing them off as
    translated.
    """
    requested = languages.normalise(code)
    language = languages.get(requested)
    strings: dict[str, str] = {}
    fallbacks: list[str] = []
    for key in KEYS:
        res = resolve(key, requested)
        strings[key] = res.text
        if res.fell_back:
            fallbacks.append(key)

    cov = coverage(requested)
    low = cov["quality"] == Quality.LOW_CONFIDENCE.value
    return {
        "language": languages.as_dict(language, coverage=cov),
        "strings": strings,
        "fallbacks": fallbacks,
        "fullyTranslated": not fallbacks,
        # The banner the UI should show when anything fell back. Served in the
        # fallback language, because that is the one the reader will be reading.
        "fallbackNotice": (t("msg.language_unavailable", languages.DEFAULT)
                           if fallbacks else ""),
        # A separate, standing warning for a language whose orthography could
        # not be checked. Distinct from a fallback: here the reader *is* being
        # served their language, and the caution is that it may be wrong in
        # ways only they can detect. Carried in English and Hindi because if
        # the translation is wrong, a warning inside it is wrong too.
        "lowConfidence": low,
        "qualityWarning": LOW_CONFIDENCE_REASON if low else "",
        "qualityWarningHindi": LOW_CONFIDENCE_REASON_HI if low else "",
    }


def catalogue() -> list[dict]:
    """Every language with its coverage — the language picker's data source.

    Ordered by how much of it exists, so a citizen sees usable languages first,
    with the rest still listed and honestly marked as unavailable.
    """
    out = [languages.as_dict(l, coverage=coverage(l.code))
           for l in languages.LANGUAGES]
    out.sort(key=lambda d: (-d["percent"], d["name"]))
    return out


def suggest(state: str = "", accept_language: str = "") -> dict:
    """Which language to offer, given what is known about the citizen.

    A State's own language comes first: someone applying for a Tamil Nadu
    scheme should be offered Tamil ahead of Hindi. The browser's preference is
    used next, and English only when nothing else is known.
    """
    ranked: list[str] = []
    # English is appended last, never seeded from the State list: for_state()
    # always terminates in English, and letting that through here would rank it
    # above a browser preference the citizen actually expressed.
    for code in languages.for_state(state):
        if code != languages.DEFAULT and code not in ranked:
            ranked.append(code)
    for code in languages.parse_accept_language(accept_language):
        if code != languages.DEFAULT and code not in ranked:
            ranked.append(code)
    ranked.append(languages.DEFAULT)

    available = [c for c in ranked if quality_of(c) is not Quality.MISSING]
    return {
        "recommended": available[0] if available else languages.DEFAULT,
        "ranked": ranked,
        "availableFromRanked": available,
        # Named explicitly so a caller does not mistake "we picked English"
        # for "this person reads English".
        "unavailableFromRanked": [c for c in ranked if c not in available],
        # Recommending one of these is still right — it is the citizen's
        # language — but the caller must show the standing warning with it.
        "lowConfidenceFromRanked": [
            c for c in available if quality_of(c) is Quality.LOW_CONFIDENCE],
        # Languages widely spoken in this State that the Eighth Schedule does
        # not cover, so no s5(3) entitlement reaches them and this application
        # cannot offer them. Reported rather than omitted: a Mizo speaker
        # offered only English should be able to see that the gap is in the
        # Schedule, not in what they asked for.
        "unscheduledLocalLanguages": list(
            languages.unscheduled_languages_for(state)),
    }


def summary() -> dict:
    """Coverage across the whole Eighth Schedule, for an operator."""
    langs = catalogue()
    scheduled = [d for d in langs if d["eighthSchedule"]]
    translated = [d for d in scheduled if d["quality"] != Quality.MISSING.value]
    reviewed = [d for d in scheduled if d["quality"] == Quality.REVIEWED.value]
    low = [d for d in scheduled if d["quality"] == Quality.LOW_CONFIDENCE.value]
    return {
        "interfaceKeys": len(KEYS),
        "eighthScheduleLanguages": len(scheduled),
        "withTranslations": len(translated),
        "nativelyReviewed": len(reviewed),
        # Reported separately from the total, so "22 of 22" can never be read
        # as "22 languages we stand behind".
        "lowConfidence": [d["code"] for d in low],
        "reviewPriority": [d["code"] for d in low],
        "missing": [d["code"] for d in scheduled
                    if d["quality"] == Quality.MISSING.value],
        "entitlement": ("DPDP Act 2023 s5(3) entitles a Data Principal to the "
                        "notice in English or any Eighth Schedule language. "
                        "Interface coverage below 100% is a gap against that "
                        "entitlement, not a nice-to-have."),
        "caveat": ("Translations marked 'draft' were generated without a native "
                   "speaker to check them. They are usable for interface text "
                   "and must not be relied on for legal notices until reviewed. "
                   "Those marked 'low_confidence' may additionally be wrong in "
                   "their orthography — the reader is warned, and these are "
                   "where a commissioned review buys the most."),
        "legalTextPolicy": ("The privacy notice, terms of service and statutory "
                            "rights text are served in English and Hindi only "
                            "and are deliberately excluded from this catalogue. "
                            "A mistranslated consent notice is a defective "
                            "consent."),
    }
