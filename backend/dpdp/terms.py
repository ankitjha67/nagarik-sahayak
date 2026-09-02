"""Terms of service — IT Rules 2021 rule 3(1)(a), and DPDP s15.

Rule 3(1)(a) requires an intermediary to publish its rules, privacy policy and
user agreement. The privacy notice covers data; this covers the service itself.

What matters most here is not the liability boilerplate but four disclosures
that protect the citizen rather than the operator, because the failure mode this
app invites is a person believing they have applied for a benefit when they have
not, or paying someone who claims they can secure one:

  1. This is **not** a government website, and using it is not an application.
  2. Nothing here **guarantees** a benefit. Only the department decides.
  3. **No fee is ever payable.** Anyone demanding money in the app's name is
     defrauding you.
  4. The citizen must **submit the form themselves**. The app fills it in.

Section 15 of the DPDP Act also places duties on the Data Principal — not to
impersonate, not to suppress material information, to furnish authentic
particulars. Those appear as user obligations because they are the citizen's
statutory duties, not merely house rules.

Text is bilingual throughout. Terms a person cannot read are not terms they have
agreed to, and this service exists for people who read Hindi.
"""
from __future__ import annotations

# Bumped whenever the substance changes. Recorded against acceptance, so it is
# always possible to say which version a given citizen agreed to.
TERMS_VERSION = "1.0"
EFFECTIVE_DATE = "2026-09-01"


CRITICAL_DISCLOSURES = [
    {
        "id": "not_government",
        "en": "This is not a government website. It helps you find schemes and "
              "fill in official forms, but it is not run by any ministry or "
              "department.",
        "hi": "यह सरकारी वेबसाइट नहीं है। यह आपको योजनाएं खोजने और सरकारी फॉर्म "
              "भरने में मदद करता है, परंतु इसे कोई मंत्रालय या विभाग नहीं चलाता।",
    },
    {
        "id": "no_guarantee",
        "en": "Using this app does not guarantee you will receive any benefit. "
              "Only the concerned department decides who qualifies, and its "
              "decision is final.",
        "hi": "इस ऐप के उपयोग से किसी लाभ की गारंटी नहीं है। पात्रता का निर्णय "
              "केवल संबंधित विभाग करता है और उसका निर्णय अंतिम है।",
    },
    {
        "id": "never_pay",
        "en": "This service is free. No fee is ever payable to us or to anyone "
              "claiming to act for us. If someone asks you for money to get a "
              "scheme approved, it is fraud — report it.",
        "hi": "यह सेवा निःशुल्क है। हमें या हमारे नाम पर किसी को कोई शुल्क नहीं "
              "देना है। यदि कोई योजना स्वीकृत कराने के लिए पैसे मांगे, तो यह "
              "धोखाधड़ी है — इसकी शिकायत करें।",
    },
    {
        "id": "you_must_submit",
        "en": "We fill in the form; you must submit it yourself at the "
              "department, a Common Service Centre, or the official portal. "
              "Downloading a form here is not an application.",
        "hi": "हम फॉर्म भरते हैं; आपको इसे स्वयं विभाग, कॉमन सर्विस सेंटर या "
              "आधिकारिक पोर्टल पर जमा करना होगा। यहाँ से फॉर्म डाउनलोड करना "
              "आवेदन नहीं है।",
    },
]


USER_OBLIGATIONS = [
    {
        "id": "authentic_information",
        "basis": "DPDP Act 2023, s15(b) and s15(d)",
        "en": "Give true and complete information. Suppressing material "
              "information, or furnishing false particulars, when applying for "
              "a benefit is an offence.",
        "hi": "सत्य और पूर्ण जानकारी दें। लाभ हेतु आवेदन करते समय महत्वपूर्ण "
              "जानकारी छिपाना या गलत विवरण देना अपराध है।",
    },
    {
        "id": "no_impersonation",
        "basis": "DPDP Act 2023, s15(a)",
        "en": "Apply only for yourself, or for someone you are lawfully "
              "entitled to represent. Do not use another person's Aadhaar, "
              "bank account or documents.",
        "hi": "केवल अपने लिए, या जिसका आप वैध रूप से प्रतिनिधित्व करते हैं, "
              "उसके लिए आवेदन करें। किसी अन्य व्यक्ति का आधार, बैंक खाता या "
              "दस्तावेज़ उपयोग न करें।",
    },
    {
        "id": "own_bank_account",
        "en": "Give a bank account that belongs to you or to the beneficiary. "
              "Routing someone else's benefit to your account is diversion of "
              "public funds.",
        "hi": "वही बैंक खाता दें जो आपका या लाभार्थी का हो। किसी और का लाभ अपने "
              "खाते में लेना सार्वजनिक धन का दुरुपयोग है।",
    },
    {
        "id": "guardian_consent",
        "basis": "DPDP Act 2023, s9",
        "en": "If you enter a child's details, you must be that child's parent "
              "or lawful guardian.",
        "hi": "यदि आप किसी बच्चे का विवरण दर्ज करते हैं, तो आपको उस बच्चे का "
              "माता-पिता या वैध अभिभावक होना चाहिए।",
    },
    {
        "id": "keep_credentials_safe",
        "en": "Do not share the one-time password sent to your phone. Nobody "
              "from this service will ever ask you for it.",
        "hi": "अपने फोन पर आया ओटीपी किसी को न बताएं। इस सेवा का कोई भी व्यक्ति "
              "आपसे ओटीपी नहीं मांगेगा।",
    },
]


PROHIBITED_USES = [
    {"en": "Applying on behalf of people who have not asked you to, in order to "
           "collect their benefits.",
     "hi": "बिना अनुमति दूसरों की ओर से आवेदन करके उनका लाभ लेना।"},
    {"en": "Using automated tools to file applications in bulk.",
     "hi": "स्वचालित साधनों से थोक में आवेदन दायर करना।"},
    {"en": "Attempting to access another person's documents or data.",
     "hi": "किसी अन्य व्यक्ति के दस्तावेज़ या डेटा तक पहुँचने का प्रयास करना।"},
    {"en": "Charging anyone a fee for using this free service.",
     "hi": "इस निःशुल्क सेवा के उपयोग हेतु किसी से शुल्क लेना।"},
]


OUR_COMMITMENTS = [
    {"en": "We will never ask you to pay anything.",
     "hi": "हम आपसे कभी कोई भुगतान नहीं मांगेंगे।"},
    {"en": "We will tell you plainly why you do not qualify for a scheme, "
           "rather than simply omitting it.",
     "hi": "यदि आप किसी योजना के लिए पात्र नहीं हैं, तो हम आपको स्पष्ट कारण "
           "बताएंगे।"},
    {"en": "We store your Aadhaar number nowhere — only its last four digits.",
     "hi": "हम आपका आधार नंबर कहीं संग्रहीत नहीं करते — केवल उसके अंतिम चार अंक।"},
    {"en": "You can see everything we hold about you, correct it, or have it "
           "erased, at any time.",
     "hi": "आप कभी भी अपना संपूर्ण डेटा देख सकते हैं, सुधार सकते हैं, या मिटवा "
           "सकते हैं।"},
]


LIMITATIONS = [
    {
        "id": "scheme_information_accuracy",
        "en": "Scheme details are taken from government sources and may be out "
              "of date if a department changes them. Always check the official "
              "portal before relying on a deadline or an amount.",
        "hi": "योजना का विवरण सरकारी स्रोतों से लिया गया है और विभाग द्वारा बदलने "
              "पर पुराना हो सकता है। किसी समय-सीमा या राशि पर निर्भर होने से पहले "
              "आधिकारिक पोर्टल अवश्य देखें।",
    },
    {
        "id": "form_accuracy",
        "en": "We fill forms from what you tell us. Check the completed form "
              "before you sign and submit it — you are responsible for what it "
              "says.",
        "hi": "हम आपके दिए विवरण से फॉर्म भरते हैं। हस्ताक्षर और जमा करने से पहले "
              "भरा हुआ फॉर्म जाँच लें — उसमें लिखी बातों के लिए आप उत्तरदायी हैं।",
    },
    {
        "id": "eligibility_is_indicative",
        "en": "Our eligibility check is based on the conditions the scheme "
              "publishes and the details you give. It is a guide, not a "
              "decision.",
        "hi": "हमारी पात्रता जाँच योजना की प्रकाशित शर्तों और आपके दिए विवरण पर "
              "आधारित है। यह मार्गदर्शन है, निर्णय नहीं।",
    },
]


def terms() -> dict:
    """The full user agreement, for publication and for acceptance."""
    from dpdp import grievance

    return {
        "version": TERMS_VERSION,
        "effective_date": EFFECTIVE_DATE,
        "service_name": "Nagarik Sahayak",
        "summary_en": "This app helps you find government schemes you may "
                      "qualify for and fills in the application forms. It is "
                      "free, it is not the government, and you submit the "
                      "completed form yourself.",
        "summary_hi": "यह ऐप आपको उन सरकारी योजनाओं को खोजने में मदद करता है "
                      "जिनके लिए आप पात्र हो सकते हैं, और आवेदन फॉर्म भरता है। "
                      "यह निःशुल्क है, यह सरकार नहीं है, और भरा हुआ फॉर्म आपको "
                      "स्वयं जमा करना होता है।",
        "critical_disclosures": CRITICAL_DISCLOSURES,
        "your_obligations": USER_OBLIGATIONS,
        "prohibited_uses": PROHIBITED_USES,
        "our_commitments": OUR_COMMITMENTS,
        "limitations": LIMITATIONS,
        "grievance": grievance.officer(),
        "governing_law": {
            "en": "These terms are governed by the laws of India.",
            "hi": "ये शर्तें भारत के कानूनों द्वारा शासित हैं।",
        },
        "changes": {
            "en": "If these terms change materially, you will be asked to read "
                  "and accept the new version before continuing.",
            "hi": "यदि इन शर्तों में महत्वपूर्ण बदलाव होता है, तो आगे बढ़ने से "
                  "पहले आपसे नया संस्करण पढ़ने और स्वीकार करने को कहा जाएगा।",
        },
        "related": {
            "privacy_notice": "/api/dpdp/notice",
            "accessibility_statement": "/api/dpdp/accessibility",
        },
    }
