"""What to carry to the counter — the documents a scheme's form implies.

The form-filling engine tells a citizen what to *write*. This tells them what
to *bring*. The single most common reason an application is turned away at the
counter is a missing enclosure — an income certificate that was at home, a
caste certificate nobody mentioned — and the citizen has already spent a day
and a bus fare to get there. A form lists its fields; it rarely lists, in one
place and in the citizen's language, the papers those fields stand for. So this
derives that list from the fields themselves.

The mapping is deliberately conservative. A document is listed only when a
field, or the scheme's own eligibility rules, genuinely implies it, and each
entry says *why* it is needed so the citizen can judge it against their own
case. Where the law allows a choice — most importantly, Aadhaar is one option
among several identity documents under the Aadhaar Act s7 proviso, never the
only one — the alternatives are named rather than hidden.

Pure data in, pure data out: no database, no network, no model. It is derived
from the bundled catalog and can be unit-tested on its own.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field


@dataclass(frozen=True)
class Document:
    """One paper to bring, with why and whether it is essential."""

    key: str
    name_english: str
    name_hindi: str
    reason_english: str
    reason_hindi: str
    mandatory: bool = True
    # Other documents the counter will accept in this one's place. Naming them
    # matters most for identity: a citizen without Aadhaar is entitled to
    # apply, and must not be told Aadhaar is compulsory when it is not.
    alternatives: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "nameEnglish": self.name_english,
            "nameHindi": self.name_hindi,
            "reasonEnglish": self.reason_english,
            "reasonHindi": self.reason_hindi,
            "mandatory": self.mandatory,
            "alternatives": list(self.alternatives),
        }


# ── The documents, each keyed so a rule can reference it once ──────────────

_DOCS: dict[str, Document] = {
    "photo": Document(
        "photo", "Passport-size photograph", "पासपोर्ट साइज़ फोटो",
        "Almost every application form has a box for a recent photograph.",
        "लगभग हर आवेदन फॉर्म में हाल की फोटो लगती है।",
    ),
    "identity": Document(
        "identity", "Aadhaar card", "आधार कार्ड",
        "To confirm who you are. Aadhaar is one accepted option, not the only "
        "one — a benefit cannot be refused for not having it.",
        "अपनी पहचान के लिए। आधार एक विकल्प है, एकमात्र नहीं — आधार न होने पर "
        "लाभ से इनकार नहीं किया जा सकता।",
        alternatives=("Voter ID (EPIC)", "Ration card", "MGNREGA job card",
                      "Driving licence", "Passport"),
    ),
    "bank": Document(
        "bank", "Bank passbook (first page)", "बैंक पासबुक (पहला पृष्ठ)",
        "The benefit is paid into your own account, so the form needs your "
        "account number and IFSC. Bring a passbook photocopy or a cancelled "
        "cheque.",
        "लाभ आपके अपने खाते में आता है, इसलिए खाता संख्या और IFSC चाहिए। "
        "पासबुक की फोटोकॉपी या रद्द चेक लाएँ।",
    ),
    "income": Document(
        "income", "Income certificate", "आय प्रमाण पत्र",
        "This scheme has an income limit, so you must show your family's "
        "annual income. Issued by the Tehsildar or an SDM office.",
        "इस योजना में आय सीमा है, इसलिए परिवार की वार्षिक आय दिखानी होगी। "
        "तहसीलदार या SDM कार्यालय से जारी।",
        alternatives=("BPL card", "Ration card (for BPL status)"),
    ),
    "caste": Document(
        "caste", "Caste / community certificate", "जाति प्रमाण पत्र",
        "You have indicated a reserved category (SC, ST or OBC), which the "
        "counter will want proof of.",
        "आपने आरक्षित श्रेणी (SC, ST या OBC) चुनी है, जिसका प्रमाण काउंटर पर "
        "माँगा जाएगा।",
    ),
    "domicile": Document(
        "domicile", "Domicile / residence certificate", "निवास प्रमाण पत्र",
        "A State scheme is for residents of that State, so you must prove where "
        "you live.",
        "राज्य की योजना उस राज्य के निवासियों के लिए है, इसलिए निवास का प्रमाण "
        "देना होगा।",
        alternatives=("Ration card", "Voter ID", "Electricity or water bill"),
    ),
    "age": Document(
        "age", "Proof of date of birth", "जन्म तिथि का प्रमाण",
        "The form asks your date of birth, and the scheme may have an age "
        "limit.",
        "फॉर्म में जन्म तिथि माँगी गई है, और योजना में आयु सीमा हो सकती है।",
        alternatives=("Birth certificate", "School leaving certificate",
                      "Class 10 marksheet"),
    ),
    "study": Document(
        "study", "Bonafide / study certificate", "अध्ययन प्रमाण पत्र",
        "A scholarship needs proof that you are currently enrolled, from your "
        "school or college.",
        "छात्रवृत्ति के लिए यह प्रमाण चाहिए कि आप वर्तमान में नामांकित हैं, "
        "आपके विद्यालय या कॉलेज से।",
    ),
    "marksheet": Document(
        "marksheet", "Last examination marksheet", "पिछली परीक्षा की मार्कशीट",
        "The form records your most recent result, so bring that marksheet.",
        "फॉर्म में आपका पिछला परिणाम दर्ज होता है, इसलिए वह मार्कशीट लाएँ।",
    ),
    "fee_receipt": Document(
        "fee_receipt", "Original fee receipt", "मूल शुल्क रसीद",
        "A fee-reimbursement scheme pays back what you paid, so the original "
        "receipt from the institute is required.",
        "शुल्क-प्रतिपूर्ति योजना आपके भुगतान की वापसी करती है, इसलिए संस्थान की "
        "मूल रसीद आवश्यक है।",
    ),
    "land": Document(
        "land", "Land records (khasra / khatauni)", "भूमि रिकॉर्ड (खसरा/खतौनी)",
        "An agricultural scheme needs proof of your landholding — the survey "
        "or khasra number and the record of rights.",
        "कृषि योजना के लिए आपकी जोत का प्रमाण चाहिए — खसरा संख्या और अधिकार "
        "अभिलेख।",
    ),
    "death_certificate": Document(
        "death_certificate", "Husband's death certificate",
        "पति का मृत्यु प्रमाण पत्र",
        "A widow pension requires the death certificate of the husband.",
        "विधवा पेंशन के लिए पति का मृत्यु प्रमाण पत्र आवश्यक है।",
    ),
    "ration": Document(
        "ration", "Ration card", "राशन कार्ड",
        "The form records your ration card number, which also helps show "
        "residence and household.",
        "फॉर्म में राशन कार्ड संख्या दर्ज होती है, जो निवास और परिवार दिखाने "
        "में भी मदद करती है।",
    ),
    "job_card": Document(
        "job_card", "MGNREGA job card", "मनरेगा जॉब कार्ड",
        "The form records your job card number.",
        "फॉर्म में आपका जॉब कार्ड नंबर दर्ज होता है।",
    ),
    "family_id": Document(
        "family_id", "Family ID", "परिवार पहचान पत्र",
        "The form records your State family identifier (such as the Parivar "
        "Pehchan Patra or SECC household ID).",
        "फॉर्म में राज्य का परिवार पहचान पत्र (जैसे PPP या SECC आईडी) दर्ज "
        "होता है।",
    ),
    "application_form": Document(
        "application_form", "The filled application form", "भरा हुआ आवेदन फॉर्म",
        "Print the draft this app prepared, check every entry, sign it, and "
        "complete by hand anything left blank.",
        "इस ऐप द्वारा तैयार मसौदा प्रिंट करें, हर प्रविष्टि जाँचें, हस्ताक्षर "
        "करें, और खाली छूटी बातें हाथ से भरें।",
    ),
}


def _keys(scheme: dict) -> set[str]:
    return {f.get("profileKey") for f in scheme.get("extractedFields", [])}


def _category_options(scheme: dict) -> set[str]:
    for f in scheme.get("extractedFields", []):
        if f.get("profileKey") == "category":
            return {str(o).upper() for o in f.get("options", [])}
    return set()


def _has_income_limit(scheme: dict) -> bool:
    """True when the scheme turns on income, by rule or by its own words.

    A rule on annual_income or is_bpl is the clear signal. But a scheme can gate
    on income without modelling it as a rule — the Daman & Diu scholarship
    prints a "Parental income below/above 1.5 Lakh" tick on the form and says so
    in its eligibility summary — so the summary text is read too. The phrases
    are specific enough ("income", "lakh", "BPL") that a scheme which merely
    mentions money in passing is not swept in.
    """
    elig = scheme.get("eligibilityCriteria", {})
    rules = elig.get("rules", [])
    if any(r.get("field") in ("annual_income", "is_bpl") for r in rules):
        return True
    summary = str(elig.get("summary", "")).lower()
    return any(cue in summary for cue in ("income", "lakh", " bpl", "below poverty"))


def required_documents(scheme: dict) -> list[Document]:
    """The documents this scheme's form implies, most-essential first.

    A document earns its place only when a field or eligibility rule asks for
    it. The order is the order a citizen reasonably gathers them: the filled
    form and identity first, then money, then the scheme-specific proofs.
    """
    keys = _keys(scheme)
    out: list[Document] = [_DOCS["application_form"], _DOCS["photo"]]

    if "aadhaar_number" in keys or "name" in keys:
        out.append(_DOCS["identity"])

    if {"bank_account_number", "ifsc_code"} & keys:
        out.append(_DOCS["bank"])

    # Income proof: an explicit income-certificate field, or an income/BPL
    # eligibility limit, or a BPL flag on the form.
    if ("income_certificate_number" in keys or "annual_income" in keys
            or "is_bpl" in keys or _has_income_limit(scheme)):
        out.append(_DOCS["income"])

    # Caste certificate only where a reserved category is actually offered —
    # never ask a General-only form's applicant for one.
    reserved = {"SC", "ST", "OBC"}
    if "category" in keys and (_category_options(scheme) & reserved
                               or not _category_options(scheme)):
        out.append(_DOCS["caste"])

    # Domicile for a State/UT scheme, or where the form has a domicile field.
    if "domicile_certificate_number" in keys or scheme.get("level") == "State":
        out.append(_DOCS["domicile"])

    if "date_of_birth" in keys or "birth_certificate_number" in keys:
        out.append(_DOCS["age"])

    if {"institution_name", "current_class", "class_sought",
            "roll_number", "academic_session"} & keys:
        out.append(_DOCS["study"])
    if "last_exam_percentage" in keys:
        out.append(_DOCS["marksheet"])
    # Fee reimbursement: the scheme pays fees back, signalled in its text.
    text = " ".join(str(scheme.get(k, "")) for k in
                    ("description", "benefit")).lower()
    benefit = str(scheme.get("eligibilityCriteria", {}).get("benefit", "")).lower()
    if "reimburs" in text or "reimburs" in benefit or "fee" in benefit:
        out.append(_DOCS["fee_receipt"])

    if {"land_holding_acres", "survey_khasra_number",
            "land_ownership_type"} & keys:
        out.append(_DOCS["land"])

    if "husband_death_certificate_number" in keys:
        out.append(_DOCS["death_certificate"])
    if "ration_card_number" in keys:
        out.append(_DOCS["ration"])
    if "job_card_number" in keys:
        out.append(_DOCS["job_card"])
    if {"state_family_id", "secc_household_id"} & keys:
        out.append(_DOCS["family_id"])

    # De-duplicate while preserving order (a document can be implied twice).
    seen: set[str] = set()
    unique: list[Document] = []
    for d in out:
        if d.key not in seen:
            seen.add(d.key)
            unique.append(d)
    return unique


def checklist_for(scheme: dict) -> dict:
    """A serialisable checklist for one scheme, for the API and the UI."""
    docs = required_documents(scheme)
    return {
        "schemeName": scheme.get("schemeName", ""),
        "schemeNameHindi": scheme.get("schemeNameHindi", ""),
        "documents": [d.as_dict() for d in docs],
        "mandatoryCount": sum(1 for d in docs if d.mandatory),
        "total": len(docs),
        # Said once, plainly, because it is the thing most worth saying: this
        # is a preparation aid, and the citizen submits the application
        # themselves. It is not a government decision about their documents.
        "noticeEnglish":
            "This is a checklist to help you prepare. Carry the originals and "
            "one photocopy of each. Requirements can vary by office — if in "
            "doubt, ask at the counter.",
        "noticeHindi":
            "यह तैयारी में मदद के लिए सूची है। हर दस्तावेज़ की मूल प्रति और एक "
            "फोटोकॉपी ले जाएँ। कार्यालय अनुसार आवश्यकताएँ बदल सकती हैं — संदेह "
            "हो तो काउंटर पर पूछें।",
    }
