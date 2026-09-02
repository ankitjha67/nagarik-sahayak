"""The languages this application recognises, and what it can honestly serve.

Two statutes converge here. DPDP Act s5(3) entitles a Data Principal to the
privacy notice in English or any Eighth Schedule language. The Official
Languages Act and the State Reorganisation Acts make a State's own language the
one its citizens actually deal with government in. A person applying for a
Tamil Nadu scheme should not have to read Hindi to do it.

The registry below is the full Eighth Schedule, plus English, with each
language's endonym — the name in its own script, which is what a person looks
for in a language picker. A list that says "Bengali" to someone who reads
বাংলা is a list they cannot use.

`fallback_chain` deliberately does *not* route one Indian language to another.
It is tempting to fall back Bhojpuri-ward, or to send Maithili to Hindi because
both use Devanagari, but sharing a script is not sharing a language and a
half-understood benefit notice is worse than an honest English one. The chain
is: the requested language, then English, and the response always states which
one the reader is actually getting.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str            # ISO 639-1 where one exists, else 639-3
    name_en: str
    endonym: str         # the language's name in its own script
    script: str
    rtl: bool = False
    # States and Union Territories where this is an official language. Used to
    # offer the right language first when a citizen has named their State.
    regions: tuple[str, ...] = ()
    eighth_schedule: bool = True


LANGUAGES: tuple[Language, ...] = (
    # English is not an Eighth Schedule language, but it *is* the declared
    # official language of these States and Union Territories — in several of
    # the North-East it is the only one, because the languages people actually
    # speak there are outside the Schedule entirely. Listing the regions is
    # therefore a fact about those States, not a fallback dressed up as one.
    Language("en", "English", "English", "Latin",
             regions=("Arunachal Pradesh", "Meghalaya", "Mizoram", "Nagaland",
                      "Chandigarh", "Andaman and Nicobar Islands", "Ladakh"),
             eighth_schedule=False),
    Language("hi", "Hindi", "हिन्दी", "Devanagari",
             regions=("Uttar Pradesh", "Bihar", "Madhya Pradesh", "Rajasthan",
                      "Jharkhand", "Chhattisgarh", "Haryana", "Delhi",
                      "Himachal Pradesh", "Uttarakhand", "Chandigarh",
                      "Andaman and Nicobar Islands")),
    Language("as", "Assamese", "অসমীয়া", "Bengali-Assamese",
             regions=("Assam",)),
    Language("bn", "Bengali", "বাংলা", "Bengali-Assamese",
             regions=("West Bengal", "Tripura", "Andaman and Nicobar Islands")),
    Language("brx", "Bodo", "बर’", "Devanagari", regions=("Assam",)),
    Language("doi", "Dogri", "डोगरी", "Devanagari", regions=("Jammu and Kashmir",)),
    Language("gu", "Gujarati", "ગુજરાતી", "Gujarati",
             regions=("Gujarat", "Dadra and Nagar Haveli and Daman and Diu")),
    Language("kn", "Kannada", "ಕನ್ನಡ", "Kannada", regions=("Karnataka",)),
    Language("ks", "Kashmiri", "کٲشُر", "Perso-Arabic", rtl=True,
             regions=("Jammu and Kashmir",)),
    Language("gom", "Konkani", "कोंकणी", "Devanagari", regions=("Goa",)),
    Language("mai", "Maithili", "मैथिली", "Devanagari", regions=("Bihar",)),
    Language("ml", "Malayalam", "മലയാളം", "Malayalam",
             regions=("Kerala", "Lakshadweep", "Puducherry")),
    Language("mni", "Manipuri", "ꯃꯤꯇꯩ ꯂꯣꯟ", "Meitei Mayek", regions=("Manipur",)),
    Language("mr", "Marathi", "मराठी", "Devanagari", regions=("Maharashtra", "Goa")),
    Language("ne", "Nepali", "नेपाली", "Devanagari", regions=("Sikkim",)),
    Language("or", "Odia", "ଓଡ଼ିଆ", "Odia", regions=("Odisha",)),
    Language("pa", "Punjabi", "ਪੰਜਾਬੀ", "Gurmukhi",
             regions=("Punjab", "Delhi", "Chandigarh")),
    Language("sa", "Sanskrit", "संस्कृतम्", "Devanagari", regions=()),
    Language("sat", "Santali", "ᱥᱟᱱᱛᱟᱲᱤ", "Ol Chiki",
             regions=("Jharkhand", "West Bengal", "Odisha")),
    Language("sd", "Sindhi", "سنڌي", "Perso-Arabic", rtl=True, regions=()),
    Language("ta", "Tamil", "தமிழ்", "Tamil",
             regions=("Tamil Nadu", "Puducherry", "Andaman and Nicobar Islands")),
    Language("te", "Telugu", "తెలుగు", "Telugu",
             regions=("Andhra Pradesh", "Telangana")),
    Language("ur", "Urdu", "اردو", "Perso-Arabic", rtl=True,
             regions=("Jammu and Kashmir", "Telangana", "Uttar Pradesh", "Bihar",
                      "Jharkhand", "Delhi", "West Bengal")),
)

BY_CODE: dict[str, Language] = {l.code: l for l in LANGUAGES}

DEFAULT = "en"

# Aliases people and browsers actually send. `ori`/`ory` and `kok` are the older
# or alternative ISO codes for Odia and Konkani; a citizen whose browser sends
# one must not be silently dropped to English.
ALIASES = {
    "ori": "or", "ory": "or", "kok": "gom", "kon": "gom",
    "asm": "as", "ben": "bn", "guj": "gu", "kan": "kn", "mal": "ml",
    "mar": "mr", "nep": "ne", "pan": "pa", "san": "sa", "snd": "sd",
    "tam": "ta", "tel": "te", "urd": "ur", "hin": "hi", "eng": "en",
    "bod": "brx", "brx-in": "brx", "mtei": "mni", "sat-in": "sat",
    "pnb": "pa", "bh": "hi", "bho": "hi",  # Bhojpuri is not scheduled separately
}


def normalise(code) -> str:
    """Map anything a browser or a user might send to a known code.

    Accepts "hi", "hi-IN", "HI_in", "hin" and an Accept-Language fragment.
    Returns DEFAULT for anything unrecognised rather than raising: a strange
    locale header must not be able to break a page load.
    """
    raw = str(code or "").strip().lower().replace("_", "-")
    if not raw:
        return DEFAULT
    raw = raw.split(";")[0].strip()
    if raw in BY_CODE:
        return raw
    if raw in ALIASES:
        return ALIASES[raw]
    base = raw.split("-")[0]
    if base in BY_CODE:
        return base
    return ALIASES.get(base, DEFAULT)


def parse_accept_language(header: str) -> list[str]:
    """Ordered, deduplicated language codes from an Accept-Language header."""
    out: list[str] = []
    for part in (header or "").split(","):
        part = part.strip()
        if not part:
            continue
        tag = part.split(";")[0].strip()
        code = normalise(tag)
        # normalise() falls back to English for anything unknown; only keep that
        # if English was genuinely asked for, so an unrecognised first choice
        # does not out-rank a recognised second one.
        if code == DEFAULT and not tag.lower().startswith("en"):
            continue
        if code not in out:
            out.append(code)
    return out


def get(code) -> Language:
    return BY_CODE.get(normalise(code), BY_CODE[DEFAULT])


def fallback_chain(code) -> list[str]:
    """Which languages to try, in order.

    Never routes one Indian language to another. Sharing a script is not
    sharing a language, and a half-understood notice about somebody's
    entitlement is worse than an honest English one.
    """
    primary = normalise(code)
    return [primary] if primary == DEFAULT else [primary, DEFAULT]


def for_state(state: str) -> list[str]:
    """Languages official in a State, most specific first, English last.

    A citizen who has told the app they live in Tamil Nadu should be offered
    Tamil before they are offered Hindi.
    """
    target = (state or "").strip().lower()
    if not target:
        return [DEFAULT]
    local = [l.code for l in LANGUAGES
             if any(r.lower() == target for r in l.regions)]
    return local + [c for c in (DEFAULT,) if c not in local]


# Languages that are official, or dominant, in a State and are *not* in the
# Eighth Schedule. No s5(3) entitlement attaches to them, which is a fact about
# the Schedule rather than about their speakers: a Mizo speaker in Aizawl has no
# statutory claim to a notice in Mizo. Recorded so the gap is visible in the
# coverage report instead of showing up as "this State is fully covered by
# English" — which is true administratively and false for the reader.
NON_SCHEDULED_REGIONAL: dict[str, tuple[str, ...]] = {
    "Mizoram": ("Mizo (Lushai)",),
    "Meghalaya": ("Khasi", "Garo"),
    "Nagaland": ("Nagamese", "Ao", "Angami", "Konyak"),
    "Arunachal Pradesh": ("Nyishi", "Adi", "Galo", "Apatani"),
    "Sikkim": ("Bhutia", "Lepcha", "Limbu"),
    "Tripura": ("Kokborok",),
    "Ladakh": ("Ladakhi", "Purgi"),
    "Andaman and Nicobar Islands": ("Nicobarese",),
    "Lakshadweep": ("Jeseri (Dweep Bhasha)",),
    "Assam": ("Karbi", "Mising", "Dimasa"),
}


def unscheduled_languages_for(state: str) -> tuple[str, ...]:
    """Languages spoken in a State that the Eighth Schedule does not cover."""
    for name, langs in NON_SCHEDULED_REGIONAL.items():
        if name.lower() == (state or "").strip().lower():
            return langs
    return ()


def rtl_codes() -> set[str]:
    return {l.code for l in LANGUAGES if l.rtl}


def as_dict(language: Language, *, coverage: dict | None = None) -> dict:
    data = {
        "code": language.code,
        "name": language.name_en,
        "endonym": language.endonym,
        "script": language.script,
        "direction": "rtl" if language.rtl else "ltr",
        "eighthSchedule": language.eighth_schedule,
        "regions": list(language.regions),
    }
    if coverage is not None:
        data.update(coverage)
    return data
