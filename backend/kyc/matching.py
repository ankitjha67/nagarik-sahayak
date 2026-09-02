"""Comparing a claimed identity against a verified one.

The temptation is to compare strings. That fails constantly and it fails in one
direction: against the applicant. Indian names reach a form through
transliteration, so "Mohd. Rafiq", "Mohammad Rafique" and "Md Rafiq" are one
person. Married women's documents disagree with each other by design — a bank
account opened before marriage carries a maiden name and a different surname
from the ration card. Government records abbreviate to initials. Dates arrive in
five formats.

So every comparison here returns a score and a reason, never a boolean, and the
caller is expected to route a low score to a human rather than refuse. The only
hard rejections are on things that cannot legitimately differ: a date of birth
that disagrees by years, or a gender that flatly contradicts.

Precision is deliberately traded for recall. A false match sends a case to a
reviewer who catches it; a false mismatch sends a widow home without her
pension, and she does not come back.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime

# Honorifics and relational prefixes that carry no identifying information.
_NOISE = {
    "mr", "mrs", "ms", "miss", "shri", "sri", "smt", "smth", "km", "kumari",
    "sh", "dr", "prof", "late", "m", "s", "d", "w", "c", "o",  # s/o, d/o, w/o, c/o
    "so", "do", "wo", "co", "son", "daughter", "wife", "of",
}

# Common transliteration variants collapsed to one form. Not a general
# phonetic algorithm — a curated list of the substitutions that actually
# generate false mismatches on Indian government forms.
_TRANSLITERATION = [
    ("ph", "f"), ("gh", "g"), ("kh", "k"), ("bh", "b"), ("dh", "d"),
    ("th", "t"), ("ch", "c"), ("sh", "s"), ("zh", "j"), ("z", "j"),
    ("w", "v"), ("q", "k"), ("x", "ks"), ("ee", "i"), ("oo", "u"),
    ("aa", "a"), ("ii", "i"), ("uu", "u"), ("y", "i"),
]

# Abbreviations and spellings that appear so often on Indian records that
# scoring them as near-misses would send a large, and specific, share of
# applicants to manual review for no reason. Each maps to a canonical key.
_ALIASES = {
    "mohd": "mohamad", "md": "mohamad", "mohammad": "mohamad",
    "mohammed": "mohamad", "muhammad": "mohamad", "muhammed": "mohamad",
    "mohd.": "mohamad", "moh": "mohamad",
    "abd": "abdul", "abdool": "abdul",
    "lakshmi": "laksmi", "laxmi": "laksmi",
    "krishna": "krisna", "krishan": "krisna", "kishan": "krisna",
    "ram": "ram", "raam": "ram",
    "singh": "sing", "sing": "sing",
    "kumar": "kumar", "kr": "kumar",
    "devi": "devi", "debi": "devi",
    "prasad": "prasad", "parsad": "prasad",
    "chandra": "candra", "chander": "candra", "chandar": "candra",
    "sri": "sri", "shree": "sri", "shri": "sri",
    "begum": "begam", "begam": "begam",
    "bibi": "bibi", "bibee": "bibi",
}

_MONTHS = {m.lower(): i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


@dataclass
class MatchResult:
    """Outcome of one comparison.

    `score` is 0.0-1.0. `decisive` marks a contradiction that cannot be
    explained by transliteration or record-keeping drift — the only case where
    a caller may refuse without human review.
    """
    field: str
    score: float
    reason_en: str
    reason_hi: str
    decisive: bool = False

    @property
    def is_match(self) -> bool:
        return self.score >= 0.85

    @property
    def needs_review(self) -> bool:
        return 0.45 <= self.score < 0.85

    def as_dict(self) -> dict:
        return {
            "field": self.field,
            "score": round(self.score, 3),
            "match": self.is_match,
            "needsReview": self.needs_review,
            "decisive": self.decisive,
            "reason": self.reason_en,
            "reasonHindi": self.reason_hi,
        }


def normalise_name(value) -> str:
    """Strip accents, punctuation, honorifics and relational prefixes."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = [t for t in text.split() if t and t not in _NOISE]
    return " ".join(tokens)


def _phonetic(token: str) -> str:
    """Collapse a token to a transliteration-insensitive key."""
    if token in _ALIASES:
        return _ALIASES[token]
    t = token
    for a, b in _TRANSLITERATION:
        t = t.replace(a, b)
    # Drop repeated letters after substitution ("bhaarat" -> "barat" -> "barat")
    out = []
    for ch in t:
        if not out or out[-1] != ch:
            out.append(ch)
    return "".join(out)


def _token_similarity(a: str, b: str) -> float:
    """Similarity of two name tokens, tolerating initials and spelling drift."""
    if a == b:
        return 1.0
    pa, pb = _phonetic(a), _phonetic(b)
    if pa == pb:
        return 0.97
    # An initial matching a full token is a legitimate abbreviation, not a
    # mismatch — government records abbreviate constantly.
    if len(a) == 1 or len(b) == 1:
        return 0.8 if (pa[:1] == pb[:1]) else 0.0
    if pa.startswith(pb) or pb.startswith(pa):
        return 0.85
    return _ratio(pa, pb)


def _ratio(a: str, b: str) -> float:
    """Normalised edit distance, 1.0 identical."""
    if not a or not b:
        return 0.0
    la, lb = len(a), len(b)
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        for j in range(1, lb + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1,
                         prev[j - 1] + (a[i - 1] != b[j - 1]))
        prev = cur
    return 1.0 - prev[lb] / max(la, lb)


def compare_names(claimed, verified) -> MatchResult:
    """Compare a typed name against one from a verified source.

    Never decisive. Two genuinely different names are indistinguishable here
    from one woman's married and maiden records, so this always routes to a
    reviewer rather than refusing.
    """
    a, b = normalise_name(claimed), normalise_name(verified)
    if not a or not b:
        return MatchResult("name", 0.0,
                           "One of the names is missing, so no comparison was made.",
                           "एक नाम अनुपलब्ध है, अतः तुलना नहीं की गई।")
    if a == b:
        return MatchResult("name", 1.0, "Names match exactly.",
                           "नाम पूर्णतः मेल खाते हैं।")

    ta, tb = a.split(), b.split()
    # Greedy best-pair matching in both directions, so word order and a
    # dropped middle name do not cost a match.
    def directional(src, dst):
        if not src:
            return 0.0
        total = 0.0
        pool = list(dst)
        for token in src:
            if not pool:
                break
            scored = [(_token_similarity(token, p), i) for i, p in enumerate(pool)]
            best, best_i = max(scored)
            total += best
            pool.pop(best_i)
        return total / len(src)

    score = max(directional(ta, tb), directional(tb, ta))

    if score >= 0.85:
        reason_en = "Names match allowing for spelling and transliteration."
        reason_hi = "वर्तनी एवं लिप्यंतरण की छूट सहित नाम मेल खाते हैं।"
    elif score >= 0.45:
        reason_en = ("Names are similar but not the same. This is common and "
                     "usually innocent — a married name, an initial, or a "
                     "different transliteration. A reviewer should look.")
        reason_hi = ("नाम समान हैं किंतु एक नहीं। यह सामान्य एवं प्रायः निर्दोष है — "
                     "विवाह के बाद का नाम, आद्याक्षर अथवा भिन्न लिप्यंतरण। समीक्षक "
                     "देखें।")
    else:
        reason_en = ("Names do not appear to match. This still needs a human "
                     "decision, not an automatic refusal.")
        reason_hi = ("नाम मेल नहीं खाते प्रतीत होते। फिर भी निर्णय मानव द्वारा हो, "
                     "स्वतः अस्वीकृति नहीं।")
    return MatchResult("name", score, reason_en, reason_hi)


def parse_date(value) -> date | None:
    """Parse the date formats government records actually use."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    # A bare year is what UIDAI stores when only a year of birth is known.
    if re.fullmatch(r"(19|20)\d{2}", text):
        return date(int(text), 7, 1)
    text = text.replace(",", " ")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y",
                "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y",
                "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    m = re.match(r"^(\d{1,2})[-/ ]([A-Za-z]{3,})[-/ ](\d{4})$", text)
    if m and m.group(2)[:3].lower() in _MONTHS:
        return date(int(m.group(3)), _MONTHS[m.group(2)[:3].lower()], int(m.group(1)))
    return None


def compare_dates_of_birth(claimed, verified) -> MatchResult:
    """Compare dates of birth.

    Decisive only on a disagreement of more than a year. Inside a year the
    disagreement is usually UIDAI's year-only record or a 1 January placeholder
    assigned when the holder did not know their birthday — refusing on that
    would exclude a large share of elderly applicants.
    """
    a, b = parse_date(claimed), parse_date(verified)
    if not a or not b:
        return MatchResult("date_of_birth", 0.0,
                           "A date of birth could not be read, so no comparison was made.",
                           "जन्म तिथि पढ़ी नहीं जा सकी, अतः तुलना नहीं की गई।")
    if a == b:
        return MatchResult("date_of_birth", 1.0, "Dates of birth match.",
                           "जन्म तिथि मेल खाती है।")
    days = abs((a - b).days)
    if a.year == b.year:
        return MatchResult(
            "date_of_birth", 0.9,
            "Same year of birth; the day or month differs, which is normal where "
            "only a year was ever recorded.",
            "जन्म वर्ष समान; दिन/माह भिन्न, जो तब सामान्य है जब केवल वर्ष ही दर्ज था।")
    if days <= 400:
        return MatchResult(
            "date_of_birth", 0.6,
            "Dates of birth differ by under a year. Worth a reviewer's eye.",
            "जन्म तिथि में एक वर्ष से कम का अंतर। समीक्षक देखें।")
    return MatchResult(
        "date_of_birth", 0.0,
        f"Dates of birth differ by about {days // 365} years. This cannot be a "
        "transcription difference.",
        f"जन्म तिथि में लगभग {days // 365} वर्ष का अंतर। यह लेखन-भिन्नता नहीं हो सकती।",
        decisive=True)


_GENDER = {"m": "male", "male": "male", "f": "female", "female": "female",
           "t": "transgender", "o": "transgender", "transgender": "transgender",
           "others": "transgender", "other": "transgender"}


def compare_genders(claimed, verified) -> MatchResult:
    """Compare gender.

    Not decisive. A transgender applicant may hold documents recording a gender
    they have since corrected, and the Transgender Persons (Protection of
    Rights) Act 2019 gives them the right to a self-perceived identity. Refusing
    a benefit over that mismatch would be both unlawful and cruel, so this
    routes to a human every time it disagrees.
    """
    a = _GENDER.get(str(claimed or "").strip().lower())
    b = _GENDER.get(str(verified or "").strip().lower())
    if not a or not b:
        return MatchResult("gender", 0.0,
                           "Gender was not recorded on one side, so no comparison was made.",
                           "एक ओर लिंग दर्ज नहीं, अतः तुलना नहीं की गई।")
    if a == b:
        return MatchResult("gender", 1.0, "Gender matches.", "लिंग मेल खाता है।")
    return MatchResult(
        "gender", 0.3,
        "Gender differs from the document. A transgender applicant may hold "
        "records they have since corrected; this is for a reviewer, not an "
        "automatic refusal.",
        "लिंग दस्तावेज़ से भिन्न। ट्रांसजेंडर आवेदक के पास पुराने अभिलेख हो सकते हैं; "
        "यह समीक्षक हेतु है, स्वतः अस्वीकृति नहीं।")


def compare_pincodes(claimed, verified) -> MatchResult:
    """Compare PIN codes, tolerating a move within the same district."""
    a = re.sub(r"\D", "", str(claimed or ""))
    b = re.sub(r"\D", "", str(verified or ""))
    if len(a) != 6 or len(b) != 6:
        return MatchResult("pincode", 0.0,
                           "A PIN code was missing or malformed.",
                           "पिन कोड अनुपलब्ध अथवा त्रुटिपूर्ण।")
    if a == b:
        return MatchResult("pincode", 1.0, "PIN codes match.", "पिन कोड मेल खाता है।")
    if a[:3] == b[:3]:
        return MatchResult(
            "pincode", 0.7,
            "PIN codes are in the same postal region — consistent with having "
            "moved locally since the document was issued.",
            "पिन कोड एक ही डाक क्षेत्र में — दस्तावेज़ जारी होने के बाद स्थानीय "
            "स्थानांतरण के अनुरूप।")
    return MatchResult(
        "pincode", 0.2,
        "PIN codes are in different regions. People do move; this needs a "
        "reviewer, not a refusal.",
        "पिन कोड भिन्न क्षेत्रों में। लोग स्थानांतरित होते हैं; समीक्षक देखें, "
        "अस्वीकृति नहीं।")


COMPARATORS = {
    "name": compare_names,
    "date_of_birth": compare_dates_of_birth,
    "gender": compare_genders,
    "pincode": compare_pincodes,
}


def compare_profile(claimed: dict, verified: dict) -> list[MatchResult]:
    """Compare every field both sides carry. Fields absent from either are skipped."""
    results = []
    for field, fn in COMPARATORS.items():
        if claimed.get(field) in (None, "") or verified.get(field) in (None, ""):
            continue
        results.append(fn(claimed[field], verified[field]))
    return results


def overall(results: list[MatchResult]) -> tuple[float, bool]:
    """Aggregate score and whether any comparison was decisively contradicted."""
    if not results:
        return 0.0, False
    return (sum(r.score for r in results) / len(results),
            any(r.decisive for r in results))
