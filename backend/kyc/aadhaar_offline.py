"""Aadhaar Offline e-KYC — the highest assurance reachable without a licence.

UIDAI publishes two offline artefacts a citizen can hand over directly:

* a **share-code-protected ZIP** containing a UIDAI-signed XML, downloaded from
  myaadhaar.uidai.gov.in;
* the **Secure QR code** printed on the e-Aadhaar letter and the PVC card.

Both are *offline verification* under Aadhaar Act s8A. Reading them needs no
AUA/KUA appointment, no UIDAI contract and no network call, because UIDAI's
signature travels inside the artefact. That matters here for a reason beyond
convenience: it is the only route by which this application can establish an
identity to a real standard without becoming a regulated entity.

Two properties are enforced throughout.

**The full Aadhaar number is never present and never reconstructed.** UIDAI
deliberately omits it; only the last four digits appear, at the head of the
reference ID. Section 29(4) of the Aadhaar Act makes publishing an Aadhaar
number a criminal offence, so :func:`parse_offline_xml` returns
``aadhaar_number_last4`` and nothing that could be assembled back into twelve
digits.

**A signature that was not checked is never reported as checked.** Verifying
UIDAI's XML signature requires UIDAI's public certificate, which this repository
does not and must not bundle. Where the certificate is absent the parsed record
comes back at DOCUMENTED assurance with ``signature_verified=False`` and an
explicit reason — not at VERIFIED. Silently treating an unverified document as
verified is the failure mode that makes an identity system worse than no
identity system, because everyone downstream then trusts it.
"""
from __future__ import annotations

import base64
import gzip
import io
import logging
import os
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field as dc_field

from kyc.methods import Assurance

logger = logging.getLogger(__name__)

# Absolute cap on an offline e-KYC upload. The real files are a few kilobytes;
# anything larger is either not an e-KYC file or an attempt at a zip bomb.
MAX_ZIP_BYTES = 2 * 1024 * 1024
MAX_XML_BYTES = 8 * 1024 * 1024

# Environment variable naming a PEM certificate for UIDAI's signing key. When
# unset, signatures are parsed but not verified, and assurance is reduced.
UIDAI_CERT_ENV = "UIDAI_SIGNING_CERT"


class OfflineKycError(Exception):
    """A citizen-facing failure. `message_hi` is shown alongside."""

    def __init__(self, message_en: str, message_hi: str, code: str = "invalid"):
        super().__init__(message_en)
        self.message_en = message_en
        self.message_hi = message_hi
        self.code = code

    def as_dict(self) -> dict:
        return {"code": self.code, "error": self.message_en,
                "errorHindi": self.message_hi}


@dataclass
class OfflineKycRecord:
    """A parsed UIDAI offline record.

    `demographics` uses this application's profileKeys, so it drops straight
    into a profile without a second mapping layer.
    """
    reference_id: str
    demographics: dict
    signature_verified: bool
    signature_note_en: str
    signature_note_hi: str
    source: str                       # "offline_xml" | "secure_qr"
    has_photo: bool = False
    mobile_hash: str = ""             # UIDAI's hash, never a number
    email_hash: str = ""
    warnings: list[str] = dc_field(default_factory=list)

    @property
    def aadhaar_last4(self) -> str:
        """First four characters of the reference ID are the last four digits."""
        return self.reference_id[:4] if len(self.reference_id) >= 4 else ""

    @property
    def assurance(self) -> Assurance:
        """VERIFIED only when UIDAI's signature was actually checked."""
        return Assurance.VERIFIED if self.signature_verified else Assurance.DOCUMENTED

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "referenceId": self.reference_id,
            "aadhaarLast4": self.aadhaar_last4,
            "demographics": dict(self.demographics),
            "signatureVerified": self.signature_verified,
            "signatureNote": self.signature_note_en,
            "signatureNoteHindi": self.signature_note_hi,
            "assurance": int(self.assurance),
            "assuranceLabel": self.assurance.label_en,
            "assuranceLabelHindi": self.assurance.label_hi,
            "hasPhoto": self.has_photo,
            "warnings": list(self.warnings),
        }


# ── ZIP handling ─────────────────────────────────────────────────────────

def _open_zip(data: bytes, share_code: str) -> bytes:
    """Return the XML bytes from a share-code-protected e-KYC ZIP."""
    if len(data) > MAX_ZIP_BYTES:
        raise OfflineKycError(
            "That file is far larger than an Aadhaar e-KYC download. Please "
            "upload the ZIP file exactly as downloaded from UIDAI.",
            "यह फ़ाइल आधार ई-केवाईसी डाउनलोड से कहीं बड़ी है। कृपया यूआईडीएआई से "
            "डाउनलोड की गई ZIP फ़ाइल जैसी है वैसी ही अपलोड करें।", code="too_large")
    if not share_code:
        raise OfflineKycError(
            "The share code is needed to open the file. It is the four-character "
            "code you chose while downloading it from UIDAI.",
            "फ़ाइल खोलने हेतु शेयर कोड आवश्यक है। यह वही चार अक्षरों का कोड है जो "
            "आपने यूआईडीएआई से डाउनलोड करते समय चुना था।", code="share_code_required")

    password = share_code.strip().encode()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise OfflineKycError(
            "That file is not a ZIP archive. Please upload the file you "
            "downloaded from myaadhaar.uidai.gov.in without unzipping it.",
            "यह फ़ाइल ZIP नहीं है। कृपया myaadhaar.uidai.gov.in से डाउनलोड की गई "
            "फ़ाइल बिना अनज़िप किए अपलोड करें।", code="not_a_zip")

    names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
    if not names:
        raise OfflineKycError(
            "No Aadhaar e-KYC XML was found inside that ZIP file.",
            "उस ZIP फ़ाइल में कोई आधार ई-केवाईसी XML नहीं मिला।", code="no_xml")

    info = zf.getinfo(names[0])
    if info.file_size > MAX_XML_BYTES:
        raise OfflineKycError(
            "The file inside the archive is implausibly large and was not opened.",
            "संग्रह के भीतर की फ़ाइल असामान्य रूप से बड़ी है और खोली नहीं गई।",
            code="too_large")

    try:
        return zf.read(names[0], pwd=password)
    except RuntimeError as exc:
        # zipfile raises RuntimeError for a bad password and for AES archives,
        # which it cannot read at all. Distinguish them, because the citizen can
        # fix one and not the other.
        text = str(exc).lower()
        if "encryption" in text or "compress" in text:
            record = _try_pyzipper(data, password)
            if record is not None:
                return record
            raise OfflineKycError(
                "This archive uses an encryption this server cannot open. Ask "
                "the operator to install the 'pyzipper' package, or use the "
                "Aadhaar QR code option instead.",
                "यह संग्रह ऐसी एन्क्रिप्शन का उपयोग करता है जिसे यह सर्वर नहीं खोल "
                "सकता। संचालक से 'pyzipper' संस्थापित कराएँ, अथवा आधार क्यूआर कोड "
                "विकल्प का उपयोग करें।", code="unsupported_encryption")
        raise OfflineKycError(
            "The share code did not open the file. It is the four-character code "
            "you set while downloading — please check it and try again.",
            "शेयर कोड से फ़ाइल नहीं खुली। यह डाउनलोड करते समय आपके द्वारा निर्धारित "
            "चार अक्षरों का कोड है — कृपया जाँचकर पुनः प्रयास करें।",
            code="bad_share_code")


def _try_pyzipper(data: bytes, password: bytes) -> bytes | None:
    """AES-encrypted archives, when the optional dependency is installed."""
    try:
        import pyzipper  # type: ignore
    except ImportError:
        return None
    try:
        with pyzipper.AESZipFile(io.BytesIO(data)) as zf:
            zf.setpassword(password)
            names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
            if not names:
                return None
            return zf.read(names[0])
    except Exception:  # noqa: BLE001 — a wrong password surfaces many ways here
        raise OfflineKycError(
            "The share code did not open the file. Please check the "
            "four-character code you set while downloading and try again.",
            "शेयर कोड से फ़ाइल नहीं खुली। कृपया डाउनलोड करते समय निर्धारित चार "
            "अक्षरों का कोड जाँचकर पुनः प्रयास करें।", code="bad_share_code")


# ── XML parsing ──────────────────────────────────────────────────────────

def _text(node, *attrs) -> str:
    for a in attrs:
        v = (node.get(a) or "").strip()
        if v:
            return v
    return ""


def _address_from_poa(poa) -> dict:
    """Assemble UIDAI's address parts into this application's address fields."""
    parts = [_text(poa, "house"), _text(poa, "street"), _text(poa, "landmark"),
             _text(poa, "loc"), _text(poa, "vtc"), _text(poa, "po")]
    line = ", ".join(p for p in parts if p)
    return {
        "address_line": line,
        "district": _text(poa, "dist"),
        "state": _text(poa, "state"),
        "pincode": _text(poa, "pc"),
        "village": _text(poa, "vtc"),
        "father_husband_name": _text(poa, "careof").lstrip("C/O").lstrip("S/O") \
            .lstrip("D/O").lstrip("W/O").strip(" :").strip() or "",
    }


def parse_offline_xml(zip_bytes: bytes, share_code: str) -> OfflineKycRecord:
    """Open and parse a UIDAI offline e-KYC ZIP.

    Raises OfflineKycError with a bilingual, actionable message on every
    failure — a citizen who mistyped a share code must be told exactly that,
    not shown a stack trace or a generic "verification failed".
    """
    xml_bytes = _open_zip(zip_bytes, share_code)
    return parse_offline_xml_bytes(xml_bytes)


def parse_offline_xml_bytes(xml_bytes: bytes) -> OfflineKycRecord:
    """Parse the XML itself. Separate from the ZIP layer so it is testable."""
    try:
        # `defusedxml` if present; the stdlib parser here has entity expansion
        # disabled by default in supported Python versions, but the file is
        # attacker-supplied so prefer the hardened parser when available.
        try:
            from defusedxml.ElementTree import fromstring  # type: ignore
            root = fromstring(xml_bytes)
        except ImportError:
            root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        raise OfflineKycError(
            "The file could not be read as an Aadhaar e-KYC document.",
            "फ़ाइल को आधार ई-केवाईसी दस्तावेज़ के रूप में पढ़ा नहीं जा सका।",
            code="unparseable")

    if not root.tag.endswith("OfflinePaperlessKyc"):
        raise OfflineKycError(
            "That is a valid XML file but not an Aadhaar offline e-KYC document.",
            "यह वैध XML फ़ाइल है किंतु आधार ऑफ़लाइन ई-केवाईसी दस्तावेज़ नहीं।",
            code="wrong_document")

    reference_id = (root.get("referenceId") or "").strip()
    uid_data = next((c for c in root if c.tag.endswith("UidData")), None)
    if uid_data is None:
        raise OfflineKycError(
            "The e-KYC document contains no identity data.",
            "ई-केवाईसी दस्तावेज़ में कोई पहचान विवरण नहीं है।", code="empty")

    poi = next((c for c in uid_data if c.tag.endswith("Poi")), None)
    poa = next((c for c in uid_data if c.tag.endswith("Poa")), None)
    pht = next((c for c in uid_data if c.tag.endswith("Pht")), None)

    demographics: dict = {}
    warnings: list[str] = []
    if poi is not None:
        demographics["name"] = _text(poi, "name")
        dob = _text(poi, "dob")
        if dob:
            demographics["date_of_birth"] = dob
            if re.fullmatch(r"(19|20)\d{2}", dob):
                warnings.append(
                    "UIDAI holds only a year of birth for this person, not a full "
                    "date. Any age check is accurate to within a year.")
        demographics["gender"] = {"M": "Male", "F": "Female", "T": "Transgender"} \
            .get(_text(poi, "gender").upper(), _text(poi, "gender"))
    if poa is not None:
        demographics.update({k: v for k, v in _address_from_poa(poa).items() if v})

    if reference_id[:4].isdigit():
        demographics["aadhaar_number_last4"] = reference_id[:4]
    else:
        warnings.append("The reference ID does not carry the last four Aadhaar "
                        "digits in the expected position.")

    verified, note_en, note_hi = _verify_xml_signature(xml_bytes, root)

    return OfflineKycRecord(
        reference_id=reference_id,
        demographics=demographics,
        signature_verified=verified,
        signature_note_en=note_en,
        signature_note_hi=note_hi,
        source="offline_xml",
        has_photo=bool(pht is not None and (pht.text or "").strip()),
        mobile_hash=_text(uid_data, "m") if uid_data is not None else "",
        email_hash=_text(uid_data, "e") if uid_data is not None else "",
        warnings=warnings,
    )


def _verify_xml_signature(xml_bytes: bytes, root) -> tuple[bool, str, str]:
    """Verify UIDAI's XML signature if a certificate is configured.

    Returns (verified, note_en, note_hi). Never raises: an unverifiable
    signature downgrades assurance, it does not reject the citizen's document.
    """
    has_signature = any(c.tag.endswith("Signature") for c in root)
    if not has_signature:
        return (False,
                "This document carries no UIDAI signature, so its contents could "
                "not be confirmed. It has been recorded as a submitted document "
                "for a reviewer to check.",
                "इस दस्तावेज़ पर यूआईडीएआई का हस्ताक्षर नहीं है, अतः इसकी विषयवस्तु "
                "की पुष्टि नहीं हो सकी। इसे समीक्षक हेतु जमा दस्तावेज़ के रूप में "
                "दर्ज किया गया है।")

    cert_path = os.getenv(UIDAI_CERT_ENV, "").strip()
    if not cert_path:
        return (False,
                "A UIDAI signature is present but was not checked, because no "
                "UIDAI signing certificate is configured on this server. The "
                "details have been read but are not treated as verified.",
                "यूआईडीएआई हस्ताक्षर उपस्थित है किंतु जाँचा नहीं गया, क्योंकि इस "
                "सर्वर पर यूआईडीएआई प्रमाणपत्र विन्यस्त नहीं है। विवरण पढ़ लिया गया "
                "है किंतु सत्यापित नहीं माना गया।")

    try:
        from signxml import XMLVerifier  # type: ignore
    except ImportError:
        logger.warning("UIDAI certificate configured but signxml is not installed")
        return (False,
                "A UIDAI signature is present but this server cannot check it "
                "because the signature library is not installed. The details "
                "have been read but are not treated as verified.",
                "यूआईडीएआई हस्ताक्षर उपस्थित है किंतु हस्ताक्षर लाइब्रेरी संस्थापित "
                "न होने से जाँच नहीं हो सकी। विवरण पढ़ लिया गया है किंतु सत्यापित "
                "नहीं माना गया।")

    try:
        with open(cert_path, "rb") as fh:
            cert = fh.read()
        XMLVerifier().verify(xml_bytes, x509_cert=cert)
        return (True,
                "UIDAI's digital signature on this document was checked and is valid.",
                "इस दस्तावेज़ पर यूआईडीएआई का डिजिटल हस्ताक्षर जाँचा गया और वैध है।")
    except FileNotFoundError:
        logger.error("UIDAI signing certificate not found at the configured path")
        return (False,
                "A UIDAI signature is present but the server's copy of UIDAI's "
                "certificate is missing, so it was not checked.",
                "यूआईडीएआई हस्ताक्षर उपस्थित है किंतु सर्वर पर यूआईडीएआई प्रमाणपत्र "
                "अनुपलब्ध होने से जाँच नहीं हुई।")
    except Exception:  # noqa: BLE001 — signxml raises a wide family
        # Deliberately not logging the exception text: it can echo document
        # content, and this document is somebody's identity record.
        logger.warning("UIDAI XML signature verification failed")
        return (False,
                "The signature on this document did not verify against UIDAI's "
                "certificate. Please download a fresh copy from "
                "myaadhaar.uidai.gov.in. A reviewer will look at this either way.",
                "इस दस्तावेज़ का हस्ताक्षर यूआईडीएआई प्रमाणपत्र से सत्यापित नहीं "
                "हुआ। कृपया myaadhaar.uidai.gov.in से नई प्रति डाउनलोड करें। "
                "किसी भी स्थिति में समीक्षक इसे देखेंगे।")


# ── Secure QR ────────────────────────────────────────────────────────────
# The QR on an e-Aadhaar letter or PVC card decodes to a large decimal integer.
# Converted to bytes it is a gzip stream whose payload is a run of UTF-8 fields
# separated by byte 255, followed by a JPEG2000 photo and a 256-byte RSA
# signature. Field order is fixed by UIDAI.

_QR_FIELDS = (
    "email_mobile_present", "reference_id", "name", "dob", "gender", "careof",
    "district", "landmark", "house", "location", "pincode", "postoffice",
    "state", "street", "subdistrict", "vtc",
)
_DELIM = 255
_SIGNATURE_BYTES = 256
MAX_QR_DIGITS = 20000


def parse_secure_qr(qr_value: str) -> OfflineKycRecord:
    """Parse the Secure QR code from an e-Aadhaar letter or PVC card."""
    raw = re.sub(r"\s", "", qr_value or "")
    if not raw:
        raise OfflineKycError(
            "No QR code data was supplied.",
            "कोई क्यूआर कोड डेटा प्राप्त नहीं हुआ।", code="empty")
    if not raw.isdigit():
        raise OfflineKycError(
            "That does not look like an Aadhaar Secure QR code. Scan the QR "
            "printed on your e-Aadhaar letter or PVC card.",
            "यह आधार सुरक्षित क्यूआर कोड प्रतीत नहीं होता। अपने ई-आधार पत्र अथवा "
            "पीवीसी कार्ड पर छपा क्यूआर स्कैन करें।", code="not_secure_qr")
    if len(raw) > MAX_QR_DIGITS:
        raise OfflineKycError(
            "The QR data is implausibly long and was not processed.",
            "क्यूआर डेटा असामान्य रूप से लंबा है और संसाधित नहीं किया गया।",
            code="too_large")

    value = int(raw)
    data = value.to_bytes((value.bit_length() + 7) // 8, "big")
    try:
        payload = gzip.decompress(data)
    except (OSError, EOFError, struct.error):
        raise OfflineKycError(
            "This QR code is an older, unsigned format that cannot be verified. "
            "Please use the Aadhaar offline e-KYC file instead, or upload your "
            "Aadhaar letter for review.",
            "यह क्यूआर कोड पुराना, अहस्ताक्षरित प्रारूप है जिसे सत्यापित नहीं किया "
            "जा सकता। कृपया आधार ऑफ़लाइन ई-केवाईसी फ़ाइल का उपयोग करें, अथवा समीक्षा "
            "हेतु आधार पत्र अपलोड करें।", code="legacy_qr")

    fields: list[str] = []
    start = 0
    for _ in range(len(_QR_FIELDS)):
        idx = payload.find(_DELIM, start)
        if idx == -1:
            break
        fields.append(payload[start:idx].decode("utf-8", "replace"))
        start = idx + 1
    if len(fields) < len(_QR_FIELDS):
        raise OfflineKycError(
            "The QR code did not contain a complete Aadhaar record.",
            "क्यूआर कोड में पूर्ण आधार अभिलेख नहीं मिला।", code="incomplete_qr")

    values = dict(zip(_QR_FIELDS, fields))
    reference_id = values["reference_id"]

    parts = [values.get("house"), values.get("street"), values.get("landmark"),
             values.get("location"), values.get("vtc"), values.get("postoffice")]
    demographics = {
        "name": values.get("name", ""),
        "date_of_birth": values.get("dob", ""),
        "gender": {"M": "Male", "F": "Female", "T": "Transgender"}
                  .get((values.get("gender") or "").upper(), values.get("gender", "")),
        "address_line": ", ".join(p for p in parts if p),
        "district": values.get("district", ""),
        "state": values.get("state", ""),
        "pincode": values.get("pincode", ""),
        "village": values.get("vtc", ""),
    }
    demographics = {k: v for k, v in demographics.items() if v}
    if reference_id[:4].isdigit():
        demographics["aadhaar_number_last4"] = reference_id[:4]

    # The trailing bytes hold the photo and then the RSA signature. Verifying
    # it needs UIDAI's public key, which this server does not bundle, so the
    # record is honest about not having checked it.
    tail = payload[start:]
    has_signature = len(tail) >= _SIGNATURE_BYTES
    has_photo = len(tail) > _SIGNATURE_BYTES

    return OfflineKycRecord(
        reference_id=reference_id,
        demographics=demographics,
        signature_verified=False,
        signature_note_en=(
            "The QR code carries a UIDAI signature. This server does not hold "
            "UIDAI's public key, so the signature was not checked and the "
            "details are recorded as submitted rather than verified."
            if has_signature else
            "This QR code carries no signature, so its contents could not be "
            "confirmed."),
        signature_note_hi=(
            "क्यूआर कोड पर यूआईडीएआई हस्ताक्षर है। इस सर्वर के पास यूआईडीएआई की "
            "सार्वजनिक कुंजी नहीं है, अतः हस्ताक्षर जाँचा नहीं गया और विवरण "
            "सत्यापित के स्थान पर जमा किया गया माना गया है।"
            if has_signature else
            "इस क्यूआर कोड पर कोई हस्ताक्षर नहीं है, अतः विषयवस्तु की पुष्टि नहीं "
            "हो सकी।"),
        source="secure_qr",
        has_photo=has_photo,
        warnings=([] if has_signature else
                  ["No signature block was found in the QR payload."]),
    )


def build_test_qr(values: dict, *, photo: bytes = b"", signature: bytes = b"") -> str:
    """Build a Secure-QR-shaped payload. Test helper, never used in production.

    Kept beside the parser so the two cannot drift: a change to the field order
    breaks the round-trip test immediately.
    """
    parts = [str(values.get(f, "")).encode() for f in _QR_FIELDS]
    payload = bytes([_DELIM]).join(parts) + bytes([_DELIM]) + photo + signature
    packed = gzip.compress(payload)
    return str(int.from_bytes(packed, "big"))


def to_profile(record: OfflineKycRecord) -> dict:
    """Demographic fields as a profile patch, ready to merge.

    Contains no full Aadhaar number by construction: UIDAI never puts one in
    these artefacts, and nothing here reassembles one.
    """
    patch = dict(record.demographics)
    from dpdp import aadhaar_policy
    aadhaar_policy.assert_no_stored_aadhaar(patch)
    return patch


def _b64_photo(record_xml_photo: str) -> bytes:
    """Decode the embedded photo. Not stored — used only for reviewer display."""
    try:
        return base64.b64decode(record_xml_photo)
    except Exception:  # noqa: BLE001
        return b""
