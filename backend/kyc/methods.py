"""Catalogue of KYC methods — what each proves, and what it actually costs.

Two things this module refuses to do.

**It does not pretend.** Every method carries an ``Availability``. A method
marked ``IMPLEMENTED`` runs here and now with nothing but this repository. One
marked ``NEEDS_CREDENTIALS`` has working code but is inert until an API key is
configured. One marked ``NEEDS_LICENCE`` cannot be switched on with a key at
all — it requires becoming a regulated entity (a KUA/AUA under the Aadhaar Act,
or an entity a bank will onboard). Presenting the third as though it were the
first is how an app ends up telling a citizen their identity is "verified" when
nothing was checked.

**It does not let any one method become the only door.** Biometric
authentication fails routinely for manual labourers and the elderly; video KYC
needs a smartphone and bandwidth; DigiLocker needs a working Aadhaar-linked
mobile. Each of those failures lands hardest on the people a welfare scheme
exists to serve, which is the exact exclusion the Aadhaar Act s7 proviso was
written to prevent. So the catalogue always retains an assisted and a
document-upload route, and :func:`available_methods` is asserted non-empty
without any online or biometric option.

Assurance is deliberately separated from availability. Assurance says how much
the claim is worth once made; availability says whether it can be made at all.
The fraud engine reads assurance; the UI reads availability.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class Assurance(int, Enum):
    """How strongly an identity claim has been established.

    Ordered, so ``a >= Assurance.VERIFIED`` is meaningful. The numbers are
    ordinal only — SUBSTANTIAL is not "twice" ASSERTED.
    """
    NONE = 0          # nothing checked
    ASSERTED = 1      # citizen typed it; format/checksum valid, source unchecked
    DOCUMENTED = 2    # a document image was supplied and stored for a human
    VERIFIED = 3      # checked against an issuer-signed artefact held offline
    SUBSTANTIAL = 4   # checked against the issuer live, or by a human in person
    HIGH = 5          # issuer-confirmed biometrically or face-to-face by an officer

    @property
    def label_en(self) -> str:
        return _ASSURANCE_LABELS[self][0]

    @property
    def label_hi(self) -> str:
        return _ASSURANCE_LABELS[self][1]


_ASSURANCE_LABELS: dict[Assurance, tuple[str, str]] = {
    Assurance.NONE: ("Not verified", "सत्यापित नहीं"),
    Assurance.ASSERTED: ("Self-declared", "स्वयं घोषित"),
    Assurance.DOCUMENTED: ("Document submitted", "दस्तावेज़ जमा किया गया"),
    Assurance.VERIFIED: ("Verified from a signed document", "हस्ताक्षरित दस्तावेज़ से सत्यापित"),
    Assurance.SUBSTANTIAL: ("Verified with the issuing authority", "जारीकर्ता प्राधिकरण से सत्यापित"),
    Assurance.HIGH: ("Verified in person", "व्यक्तिगत रूप से सत्यापित"),
}


class Availability(str, Enum):
    """Whether this deployment can actually run the method."""
    IMPLEMENTED = "implemented"
    # Code exists; needs an API key, endpoint or certificate in the environment.
    NEEDS_CREDENTIALS = "needs_credentials"
    # Cannot be enabled by configuration. Requires a licence, an appointment as
    # a KUA/AUA, or a contract with a regulated entity.
    NEEDS_LICENCE = "needs_licence"

    @property
    def is_usable(self) -> bool:
        return self is Availability.IMPLEMENTED


class Channel(str, Enum):
    """How the citizen reaches the method — the exclusion axis that matters."""
    SELF_ONLINE = "self_online"      # needs a device and connectivity
    SELF_OFFLINE = "self_offline"    # a file or card, no live connection needed
    ASSISTED = "assisted"            # a CSC operator, bank mitra or officer does it
    IN_PERSON = "in_person"          # the citizen appears before an official


@dataclass(frozen=True)
class KycMethod:
    key: str
    name_en: str
    name_hi: str
    assurance: Assurance
    availability: Availability
    channel: Channel
    # Which profile fields this method can establish if it succeeds.
    establishes: tuple[str, ...]
    legal_basis: str            # the provision that permits it
    what_it_proves_en: str
    what_it_proves_hi: str
    requirements_en: str        # what the citizen must have in hand
    requirements_hi: str
    # The population this method fails, stated plainly. A method with no
    # exclusion note has not been thought about.
    excludes_en: str
    excludes_hi: str
    # Env vars that must be set before availability can become IMPLEMENTED.
    config_keys: tuple[str, ...] = ()
    cost_note: str = ""

    @property
    def effective_availability(self) -> Availability:
        """What this deployment can run *right now*.

        A licence requirement cannot be satisfied by an environment variable, so
        NEEDS_LICENCE is absorbing. Everything else resolves against the
        environment: a credentialled method becomes usable once its keys are
        present, and an implemented one that grew a prerequisite goes inert
        rather than failing at the moment a citizen tries to use it.
        """
        if self.availability is Availability.NEEDS_LICENCE:
            return self.availability
        if self.config_keys and not all(os.getenv(k) for k in self.config_keys):
            return Availability.NEEDS_CREDENTIALS
        return Availability.IMPLEMENTED

    def as_dict(self) -> dict:
        eff = self.effective_availability
        return {
            "key": self.key,
            "name": self.name_en,
            "nameHindi": self.name_hi,
            "assurance": int(self.assurance),
            "assuranceLabel": self.assurance.label_en,
            "assuranceLabelHindi": self.assurance.label_hi,
            "availability": eff.value,
            "usable": eff.is_usable,
            "channel": self.channel.value,
            "establishes": list(self.establishes),
            "legalBasis": self.legal_basis,
            "whatItProves": self.what_it_proves_en,
            "whatItProvesHindi": self.what_it_proves_hi,
            "requirements": self.requirements_en,
            "requirementsHindi": self.requirements_hi,
            "excludes": self.excludes_en,
            "excludesHindi": self.excludes_hi,
            "missingConfig": [k for k in self.config_keys if not os.getenv(k)],
            "costNote": self.cost_note,
        }


# Fields a successful identity check can establish. Kept as a constant so a
# typo in a method definition is caught by a test rather than silently
# establishing nothing.
DEMOGRAPHIC_FIELDS = ("name", "date_of_birth", "gender", "address_line",
                      "district", "state", "pincode")


METHODS: tuple[KycMethod, ...] = (
    # ── Aadhaar, offline ─────────────────────────────────────────────────
    # The important one. UIDAI's own offline route: the citizen downloads a
    # signed XML from myaadhaar.uidai.gov.in, protected by a share code they
    # choose. Verifying it needs no licence and no call to UIDAI, because the
    # signature travels with the document. It is the highest assurance this
    # application can reach without becoming a regulated entity.
    KycMethod(
        key="aadhaar_offline_xml",
        name_en="Aadhaar Offline e-KYC (XML)",
        name_hi="आधार ऑफ़लाइन ई-केवाईसी (XML)",
        assurance=Assurance.VERIFIED,
        availability=Availability.IMPLEMENTED,
        channel=Channel.SELF_OFFLINE,
        establishes=DEMOGRAPHIC_FIELDS + ("aadhaar_number_last4",),
        legal_basis="Aadhaar Act s8A and the Aadhaar (Sharing of Information) "
                    "Regulations — offline verification, no AUA/KUA appointment "
                    "required. The full Aadhaar number is never present in the "
                    "file, only its last four digits.",
        what_it_proves_en="Name, date of birth, gender and address exactly as UIDAI "
                          "holds them, carrying UIDAI's digital signature.",
        what_it_proves_hi="नाम, जन्म तिथि, लिंग एवं पता ठीक वैसे ही जैसे यूआईडीएआई के "
                          "पास दर्ज हैं, यूआईडीएआई के डिजिटल हस्ताक्षर सहित।",
        requirements_en="The ZIP file downloaded from myaadhaar.uidai.gov.in and the "
                        "four-character share code you chose while downloading it.",
        requirements_hi="myaadhaar.uidai.gov.in से डाउनलोड की गई ZIP फ़ाइल तथा "
                        "डाउनलोड करते समय चुना गया चार अक्षरों का शेयर कोड।",
        excludes_en="Requires an Aadhaar-linked mobile number to receive the OTP at "
                    "download time, and a device to download on. Someone whose "
                    "mobile is not linked cannot produce this file.",
        excludes_hi="डाउनलोड के समय ओटीपी हेतु आधार से जुड़ा मोबाइल नंबर तथा एक "
                    "डिवाइस आवश्यक है। जिनका मोबाइल आधार से नहीं जुड़ा, वे यह फ़ाइल "
                    "प्राप्त नहीं कर सकते।",
    ),
    KycMethod(
        key="aadhaar_secure_qr",
        name_en="Aadhaar Secure QR Code",
        name_hi="आधार सुरक्षित क्यूआर कोड",
        assurance=Assurance.VERIFIED,
        availability=Availability.IMPLEMENTED,
        channel=Channel.SELF_OFFLINE,
        establishes=DEMOGRAPHIC_FIELDS + ("aadhaar_number_last4",),
        legal_basis="Aadhaar Act s8A — offline verification of the QR printed on "
                    "the e-Aadhaar letter and the PVC card.",
        what_it_proves_en="The same UIDAI-signed demographic record as the offline "
                          "XML, read from the QR code on your Aadhaar letter or card.",
        what_it_proves_hi="वही यूआईडीएआई-हस्ताक्षरित विवरण जो ऑफ़लाइन XML में है, "
                          "आपके आधार पत्र या कार्ड पर छपे क्यूआर कोड से पढ़ा गया।",
        requirements_en="A printed e-Aadhaar letter or PVC card with a QR code, and a "
                        "photo or scan of it.",
        requirements_hi="क्यूआर कोड वाला मुद्रित ई-आधार पत्र अथवा पीवीसी कार्ड, तथा "
                        "उसका फ़ोटो या स्कैन।",
        excludes_en="Older Aadhaar letters carry a QR that holds no signature and "
                    "cannot be verified. A worn or poorly photographed card will not "
                    "scan; the citizen must not be refused for that.",
        excludes_hi="पुराने आधार पत्रों का क्यूआर हस्ताक्षरित नहीं होता और सत्यापित "
                    "नहीं किया जा सकता। घिसा हुआ या धुंधला कार्ड स्कैन नहीं होगा; "
                    "इस कारण नागरिक को मना नहीं किया जाना चाहिए।",
    ),

    # ── Aadhaar, online — requires being a regulated entity ──────────────
    KycMethod(
        key="aadhaar_otp_ekyc",
        name_en="Aadhaar OTP e-KYC",
        name_hi="आधार ओटीपी ई-केवाईसी",
        assurance=Assurance.SUBSTANTIAL,
        availability=Availability.NEEDS_LICENCE,
        channel=Channel.SELF_ONLINE,
        establishes=DEMOGRAPHIC_FIELDS + ("aadhaar_number_last4",),
        legal_basis="Aadhaar Act s4(3) read with the Aadhaar (Authentication and "
                    "Offline Verification) Regulations. Only a KUA appointed by "
                    "UIDAI, or an entity operating through one, may perform this.",
        what_it_proves_en="UIDAI confirms the demographic record live, in response to "
                          "an OTP sent to the Aadhaar-linked mobile.",
        what_it_proves_hi="आधार से जुड़े मोबाइल पर भेजे गए ओटीपी के उत्तर में "
                          "यूआईडीएआई विवरण की तत्काल पुष्टि करता है।",
        requirements_en="An Aadhaar-linked mobile number in the citizen's possession.",
        requirements_hi="नागरिक के पास आधार से जुड़ा मोबाइल नंबर।",
        excludes_en="Fails for anyone whose linked mobile has changed, lapsed or "
                    "belongs to a relative — common among migrant workers and "
                    "elderly applicants.",
        excludes_hi="जिनका जुड़ा मोबाइल बदल गया, बंद हो गया अथवा किसी संबंधी का है, "
                    "उनके लिए विफल — प्रवासी श्रमिकों एवं वृद्धजनों में सामान्य।",
        cost_note="Requires UIDAI KUA appointment or a licensed intermediary; "
                  "per-transaction charges apply.",
    ),
    KycMethod(
        key="aadhaar_biometric",
        name_en="Aadhaar Biometric Authentication",
        name_hi="आधार बायोमेट्रिक प्रमाणीकरण",
        assurance=Assurance.HIGH,
        availability=Availability.NEEDS_LICENCE,
        channel=Channel.ASSISTED,
        establishes=("aadhaar_number_last4",),
        legal_basis="Aadhaar Act s4(3); requires an AUA appointment and a UIDAI-"
                    "certified registered fingerprint or iris device.",
        what_it_proves_en="That the person present is the Aadhaar holder.",
        what_it_proves_hi="कि उपस्थित व्यक्ति ही आधार धारक है।",
        requirements_en="Attendance at a centre with a certified biometric device.",
        requirements_hi="प्रमाणित बायोमेट्रिक उपकरण वाले केंद्र पर उपस्थिति।",
        excludes_en="Fingerprints of manual labourers and the elderly frequently fail "
                    "to read. This method must never be the only route to a benefit; "
                    "UIDAI's own circulars require an alternative to be offered.",
        excludes_hi="श्रमिकों एवं वृद्धजनों के फ़िंगरप्रिंट प्रायः नहीं पढ़े जाते। "
                    "यह विधि किसी लाभ का एकमात्र मार्ग नहीं हो सकती; यूआईडीएआई के "
                    "परिपत्र विकल्प देना अनिवार्य करते हैं।",
        cost_note="AUA appointment plus certified device hardware at each centre.",
    ),

    # ── DigiLocker ───────────────────────────────────────────────────────
    KycMethod(
        key="digilocker",
        name_en="DigiLocker Issued Documents",
        name_hi="डिजिलॉकर जारी दस्तावेज़",
        assurance=Assurance.SUBSTANTIAL,
        availability=Availability.NEEDS_CREDENTIALS,
        channel=Channel.SELF_ONLINE,
        establishes=DEMOGRAPHIC_FIELDS + (
            "driving_licence_number", "pan_number", "caste_certificate_number",
            "income_certificate_number", "domicile_certificate_number",
            "birth_certificate_number", "udid_number", "ration_card_number"),
        legal_basis="IT Act s4 and the Information Technology (Preservation and "
                    "Retention) Rules — a DigiLocker issued document is at par with "
                    "the original. Requires registration as a Requester Organisation "
                    "with a client ID and secret.",
        what_it_proves_en="Documents pulled straight from the issuing department, so "
                          "an income or caste certificate cannot be forged in transit.",
        what_it_proves_hi="जारीकर्ता विभाग से सीधे प्राप्त दस्तावेज़, अतः आय अथवा "
                          "जाति प्रमाण पत्र में छेड़छाड़ संभव नहीं।",
        requirements_en="A DigiLocker account and the Aadhaar-linked mobile used to "
                        "sign in.",
        requirements_hi="डिजिलॉकर खाता तथा साइन-इन हेतु आधार से जुड़ा मोबाइल।",
        excludes_en="Needs a smartphone or computer and a working data connection. "
                    "Many State departments still do not push certificates into "
                    "DigiLocker, so a genuine certificate may simply not be there.",
        excludes_hi="स्मार्टफ़ोन/कंप्यूटर तथा डेटा कनेक्शन आवश्यक। कई राज्य विभाग "
                    "अब भी डिजिलॉकर में प्रमाण पत्र नहीं भेजते, अतः असली प्रमाण पत्र "
                    "वहाँ न होना संभव है।",
        config_keys=("DIGILOCKER_CLIENT_ID", "DIGILOCKER_CLIENT_SECRET"),
        cost_note="Free, but requires MeitY Requester Organisation onboarding.",
    ),

    # ── Bank ─────────────────────────────────────────────────────────────
    KycMethod(
        key="penny_drop",
        name_en="Bank Account Name Match (Penny Drop)",
        name_hi="बैंक खाता नाम मिलान (पेनी ड्रॉप)",
        assurance=Assurance.SUBSTANTIAL,
        availability=Availability.NEEDS_CREDENTIALS,
        channel=Channel.SELF_ONLINE,
        establishes=("bank_account_number", "ifsc_code", "name"),
        legal_basis="Not an identity check under any statute — a payment-rail "
                    "confirmation that the account exists and whose name it carries. "
                    "Needs a bank or payment aggregator relationship.",
        what_it_proves_en="That the account number and IFSC are real and that the name "
                          "on the account matches the applicant. This is what stops a "
                          "benefit being routed to someone else's account.",
        what_it_proves_hi="कि खाता संख्या एवं आईएफएससी वास्तविक हैं और खाते पर दर्ज "
                          "नाम आवेदक से मेल खाता है। यही लाभ को किसी और के खाते में "
                          "जाने से रोकता है।",
        requirements_en="An account number and IFSC code.",
        requirements_hi="खाता संख्या एवं आईएफएससी कोड।",
        excludes_en="Names differ legitimately — a married woman's account may carry "
                    "her maiden name, and transliteration varies. A mismatch must "
                    "raise a review, never an automatic refusal.",
        excludes_hi="नाम वैध रूप से भिन्न हो सकते हैं — विवाहित महिला के खाते में "
                    "कुँवारेपन का नाम हो सकता है, लिप्यंतरण भी भिन्न होता है। असमानता "
                    "पर समीक्षा हो, स्वतः अस्वीकृति कभी नहीं।",
        config_keys=("PENNY_DROP_API_URL", "PENNY_DROP_API_KEY"),
        cost_note="Charged per verification by the payment aggregator.",
    ),

    # ── Government document databases ────────────────────────────────────
    KycMethod(
        key="pan_verification",
        name_en="PAN Verification",
        name_hi="पैन सत्यापन",
        assurance=Assurance.SUBSTANTIAL,
        availability=Availability.NEEDS_CREDENTIALS,
        channel=Channel.SELF_ONLINE,
        establishes=("pan_number", "name"),
        legal_basis="Income Tax Act s139A; verification through the Protean/UTIITSL "
                    "online PAN verification service, which requires registration.",
        what_it_proves_en="That the PAN exists and the name on it matches.",
        what_it_proves_hi="कि पैन विद्यमान है तथा उस पर दर्ज नाम मेल खाता है।",
        requirements_en="A PAN card.",
        requirements_hi="पैन कार्ड।",
        excludes_en="Most applicants for a welfare scheme have no PAN, and being "
                    "asked for one can read as a signal they are not wanted. Never "
                    "make it mandatory.",
        excludes_hi="कल्याणकारी योजना के अधिकांश आवेदकों के पास पैन नहीं होता, और "
                    "इसकी माँग यह संकेत दे सकती है कि वे अपेक्षित नहीं हैं। इसे कभी "
                    "अनिवार्य न करें।",
        config_keys=("PAN_VERIFY_API_URL", "PAN_VERIFY_API_KEY"),
    ),
    KycMethod(
        key="voter_id_verification",
        name_en="Voter ID (EPIC) Verification",
        name_hi="मतदाता पहचान पत्र (ईपीआईसी) सत्यापन",
        assurance=Assurance.SUBSTANTIAL,
        availability=Availability.NEEDS_CREDENTIALS,
        channel=Channel.SELF_ONLINE,
        establishes=("voter_id_number", "name", "district", "state"),
        legal_basis="Representation of the People Act; the electoral roll is public, "
                    "but programmatic access needs ECI/NVSP API authorisation.",
        what_it_proves_en="That the EPIC number appears on the electoral roll with a "
                          "matching name and constituency.",
        what_it_proves_hi="कि ईपीआईसी संख्या मतदाता सूची में मेल खाते नाम एवं "
                          "निर्वाचन क्षेत्र सहित दर्ज है।",
        requirements_en="A voter ID card.",
        requirements_hi="मतदाता पहचान पत्र।",
        excludes_en="Excludes everyone under 18 and anyone whose name was struck off "
                    "or never added — which disproportionately affects migrants.",
        excludes_hi="18 वर्ष से कम आयु के सभी तथा जिनका नाम हटा दिया गया या कभी "
                    "जोड़ा ही नहीं गया, वे बाहर — इससे प्रवासी सर्वाधिक प्रभावित।",
        config_keys=("EPIC_VERIFY_API_URL", "EPIC_VERIFY_API_KEY"),
    ),
    KycMethod(
        key="driving_licence_verification",
        name_en="Driving Licence Verification",
        name_hi="ड्राइविंग लाइसेंस सत्यापन",
        assurance=Assurance.SUBSTANTIAL,
        availability=Availability.NEEDS_CREDENTIALS,
        channel=Channel.SELF_ONLINE,
        establishes=("driving_licence_number", "name", "date_of_birth"),
        legal_basis="Motor Vehicles Act; verification through the Parivahan Sarathi "
                    "service, which requires API authorisation.",
        what_it_proves_en="That the licence is live and carries a matching name and "
                          "date of birth.",
        what_it_proves_hi="कि लाइसेंस वैध है तथा उस पर नाम एवं जन्म तिथि मेल खाती है।",
        requirements_en="A driving licence number and date of birth.",
        requirements_hi="ड्राइविंग लाइसेंस संख्या एवं जन्म तिथि।",
        excludes_en="Held by a small and skewed slice of the applicant population.",
        excludes_hi="आवेदकों के एक छोटे एवं असंतुलित हिस्से के पास ही उपलब्ध।",
        config_keys=("DL_VERIFY_API_URL", "DL_VERIFY_API_KEY"),
    ),

    # ── Human routes — the ones that must never be switched off ──────────
    KycMethod(
        key="video_kyc",
        name_en="Video KYC",
        name_hi="वीडियो केवाईसी",
        assurance=Assurance.SUBSTANTIAL,
        availability=Availability.NEEDS_CREDENTIALS,
        channel=Channel.SELF_ONLINE,
        establishes=DEMOGRAPHIC_FIELDS,
        legal_basis="Modelled on the RBI Video-based Customer Identification Process "
                    "directions: a live, recorded, geotagged session with an official.",
        what_it_proves_en="That a live person holding the document is the person in it, "
                          "confirmed by an official on a recorded call.",
        what_it_proves_hi="कि दस्तावेज़ धारण किए जीवित व्यक्ति ही उसमें दर्ज व्यक्ति "
                          "है, रिकॉर्ड की गई कॉल पर अधिकारी द्वारा पुष्ट।",
        requirements_en="A smartphone with a camera and a stable data connection.",
        requirements_hi="कैमरा युक्त स्मार्टफ़ोन तथा स्थिर डेटा कनेक्शन।",
        excludes_en="Excludes anyone without a smartphone or reliable bandwidth, and "
                    "is hard for applicants with a hearing or speech disability unless "
                    "a sign-language option is offered.",
        excludes_hi="स्मार्टफ़ोन या भरोसेमंद बैंडविड्थ के बिना सभी बाहर; श्रवण अथवा "
                    "वाणी दिव्यांगता वाले आवेदकों हेतु सांकेतिक भाषा विकल्प के बिना "
                    "कठिन।",
        config_keys=("VIDEO_KYC_PROVIDER_URL", "VIDEO_KYC_API_KEY"),
    ),
    KycMethod(
        key="csc_assisted",
        name_en="Assisted Verification at a Common Service Centre",
        name_hi="सामान्य सेवा केंद्र पर सहायता-प्राप्त सत्यापन",
        assurance=Assurance.SUBSTANTIAL,
        availability=Availability.IMPLEMENTED,
        channel=Channel.ASSISTED,
        establishes=DEMOGRAPHIC_FIELDS,
        legal_basis="A Village Level Entrepreneur or scheme functionary records that "
                    "they saw the original documents. Their identity is recorded "
                    "alongside, so the attestation is attributable.",
        what_it_proves_en="That a named operator saw the original documents and the "
                          "applicant in person.",
        what_it_proves_hi="कि एक नामित संचालक ने मूल दस्तावेज़ एवं आवेदक को स्वयं "
                          "देखा।",
        requirements_en="A visit to a CSC with your original documents.",
        requirements_hi="मूल दस्तावेज़ों सहित सीएससी पर उपस्थिति।",
        excludes_en="Depends on the operator's honesty, so it is scored — a single "
                    "operator attesting an implausible number of applications is "
                    "exactly what the fraud engine watches for. It must still be "
                    "offered, because for many applicants it is the only route.",
        excludes_hi="संचालक की ईमानदारी पर निर्भर, अतः इसका स्कोर रखा जाता है — एक ही "
                    "संचालक द्वारा असंभव संख्या में सत्यापन पर धोखाधड़ी इंजन की दृष्टि "
                    "रहती है। फिर भी यह विकल्प रहना चाहिए, क्योंकि कई आवेदकों हेतु "
                    "यही एकमात्र मार्ग है।",
    ),
    KycMethod(
        key="officer_attestation",
        name_en="Attestation by a Gazetted Officer or Panchayat",
        name_hi="राजपत्रित अधिकारी अथवा पंचायत द्वारा प्रमाणन",
        assurance=Assurance.HIGH,
        availability=Availability.IMPLEMENTED,
        channel=Channel.IN_PERSON,
        establishes=DEMOGRAPHIC_FIELDS,
        legal_basis="The long-standing administrative route, expressly preserved by "
                    "the Aadhaar Act s7 proviso: where authentication fails or is "
                    "unavailable, an alternative means of identification must be "
                    "offered rather than the benefit refused.",
        what_it_proves_en="That a named public official has certified the applicant's "
                          "identity and residence on the record.",
        what_it_proves_hi="कि एक नामित लोक सेवक ने अभिलेख पर आवेदक की पहचान एवं "
                          "निवास प्रमाणित किया है।",
        requirements_en="A signed and stamped certificate from a gazetted officer, "
                        "sarpanch, ward member or school headmaster.",
        requirements_hi="राजपत्रित अधिकारी, सरपंच, वार्ड सदस्य अथवा प्रधानाध्यापक का "
                        "हस्ताक्षरित एवं मुद्रांकित प्रमाण पत्र।",
        excludes_en="Slow, and dependent on reaching an official who will sign. It is "
                    "kept because it is the last route that works when everything "
                    "digital has failed.",
        excludes_hi="धीमा तथा हस्ताक्षर करने वाले अधिकारी तक पहुँच पर निर्भर। यह इसलिए "
                    "रखा गया है क्योंकि जब सब डिजिटल विकल्प विफल हों तो यही अंतिम "
                    "कार्यशील मार्ग है।",
    ),
    KycMethod(
        key="document_upload",
        name_en="Document Upload for Manual Review",
        name_hi="मैनुअल समीक्षा हेतु दस्तावेज़ अपलोड",
        assurance=Assurance.DOCUMENTED,
        availability=Availability.IMPLEMENTED,
        channel=Channel.SELF_OFFLINE,
        establishes=(),
        legal_basis="No statutory verification — the document is stored encrypted and "
                    "placed before a human reviewer.",
        what_it_proves_en="Nothing on its own. It puts a readable document in front of "
                          "a reviewer, who decides.",
        what_it_proves_hi="स्वयं में कुछ नहीं। यह समीक्षक के समक्ष एक पठनीय दस्तावेज़ "
                          "रखता है, निर्णय वही करता है।",
        requirements_en="A photo or scan of any accepted identity document.",
        requirements_hi="किसी भी स्वीकृत पहचान दस्तावेज़ का फ़ोटो अथवा स्कैन।",
        excludes_en="Excludes nobody, which is the point — it is the floor beneath "
                    "every other method.",
        excludes_hi="किसी को बाहर नहीं करता, यही इसका उद्देश्य है — यह हर अन्य विधि "
                    "के नीचे का आधार है।",
    ),
    KycMethod(
        key="self_declaration",
        name_en="Self-Declaration",
        name_hi="स्व-घोषणा",
        assurance=Assurance.ASSERTED,
        availability=Availability.IMPLEMENTED,
        channel=Channel.SELF_OFFLINE,
        establishes=(),
        legal_basis="Format and checksum validation only. Recorded as self-declared "
                    "and never presented as verified.",
        what_it_proves_en="Only that the number is well formed — an Aadhaar passes its "
                          "checksum, an IFSC matches the bank code pattern.",
        what_it_proves_hi="केवल यह कि संख्या का प्रारूप सही है — आधार का चेकसम सही है, "
                          "आईएफएससी बैंक कोड प्रारूप से मेल खाता है।",
        requirements_en="Nothing beyond the number itself.",
        requirements_hi="संख्या के अतिरिक्त कुछ नहीं।",
        excludes_en="Excludes nobody and proves nothing. It exists so an application "
                    "can be started, not so it can be approved on this basis alone.",
        excludes_hi="किसी को बाहर नहीं करता और कुछ सिद्ध नहीं करता। यह आवेदन आरंभ "
                    "करने हेतु है, केवल इसी आधार पर स्वीकृति हेतु नहीं।",
    ),
)

BY_KEY: dict[str, KycMethod] = {m.key: m for m in METHODS}


def get(key: str) -> KycMethod | None:
    return BY_KEY.get(key)


def available_methods() -> list[KycMethod]:
    """Methods this deployment can actually run right now."""
    return [m for m in METHODS if m.effective_availability.is_usable]


def methods_for_channel(channel: Channel) -> list[KycMethod]:
    return [m for m in METHODS if m.channel is channel]


def best_available_assurance() -> Assurance:
    """Highest assurance reachable without further configuration."""
    usable = available_methods()
    return max((m.assurance for m in usable), default=Assurance.NONE)


def options(include_unavailable: bool = True) -> list[dict]:
    """Serialisable method list for the UI.

    Unavailable methods are included by default and marked, rather than hidden.
    A citizen who is told "verify with DigiLocker" by a leaflet and cannot find
    it here deserves to be told it is not switched on, not to be left hunting.
    """
    out = [m.as_dict() for m in METHODS]
    if not include_unavailable:
        out = [d for d in out if d["usable"]]
    # Strongest first, then by how few people the method shuts out: offline and
    # assisted routes rank above ones that need a smartphone.
    channel_rank = {Channel.SELF_OFFLINE.value: 0, Channel.ASSISTED.value: 1,
                    Channel.IN_PERSON.value: 2, Channel.SELF_ONLINE.value: 3}
    out.sort(key=lambda d: (not d["usable"], -d["assurance"],
                            channel_rank[d["channel"]]))
    return out
