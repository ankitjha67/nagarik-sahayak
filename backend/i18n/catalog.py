"""Message catalogue for the citizen-facing interface.

Organised by language rather than by key, because a translator works through
one language at a time and a per-key layout makes a whole language impossible
to read or review.

**On the quality of what is here.** Every non-English string below was written
by the system that built this application, not by a native speaker, and is
marked ``DRAFT``. That marking is load-bearing and must not be quietly upgraded:
these strings tell people whether they qualify for a pension and whether they
should hand over an Aadhaar number, and confidently wrong text in a language
nobody on the team reads would harm exactly the people it is meant to serve.
``/api/i18n/coverage`` reports the marking so it reaches an operator rather
than dying in a comment.

**On the eight languages that are absent.** Bodo, Dogri, Kashmiri, Konkani,
Maithili, Manipuri, Santali and Sindhi are Eighth Schedule languages with no
entries here. That is deliberate. Producing text in a language whose
orthography and register I cannot check would not be partial coverage — it
would be plausible-looking nonsense that a citizen has no way to identify as
nonsense, which is strictly worse than an honest English fallback plus a
banner saying so. :data:`UNTRANSLATED_REASON` is served to the UI so the gap
is visible and can be commissioned.

**On legal text.** The privacy notice, the terms of service and the statutory
rights language are *not* in this catalogue and must not be machine-translated
into it. Those are served from dpdp/ in English and Hindi only. A mistranslated
consent notice is a defective consent, and s6(3) of the DPDP Act gives the
Data Principal the right to the notice in a language they choose — which is a
reason to commission real translations, not a reason to fabricate them.
"""
from __future__ import annotations

from enum import Enum


class Quality(str, Enum):
    """How much weight a translation can bear."""
    SOURCE = "source"          # the English original
    REVIEWED = "reviewed"      # checked by a native speaker; none yet
    DRAFT = "draft"            # generated here; usable, needs native review
    MISSING = "missing"        # absent; the fallback is used and disclosed


UNTRANSLATED_REASON = (
    "No translation is offered in this language yet. Text generated without a "
    "native speaker to check it would look correct and could be wrong about "
    "an entitlement, which is worse for the reader than an honest fallback. "
    "A reviewed translation can be commissioned and dropped in as data."
)

# Keys the interface uses. Declared separately from the translations so a key
# added to one language and forgotten in another is caught by a test rather
# than surfacing as a blank label in front of a citizen.
KEYS: tuple[str, ...] = (
    "app.name", "app.tagline",
    "nav.home", "nav.chat", "nav.schemes", "nav.exams", "nav.profile",
    "nav.identity", "nav.documents", "nav.privacy", "nav.help",
    "action.continue", "action.back", "action.submit", "action.save",
    "action.download", "action.upload", "action.verify_identity", "action.skip",
    "status.eligible", "status.not_eligible", "status.incomplete",
    "status.under_review", "status.verified", "status.not_verified",
    "label.name", "label.date_of_birth", "label.mobile", "label.district",
    "label.state", "label.annual_income",
    "msg.no_fee", "msg.not_government", "msg.aadhaar_optional",
    "msg.language_unavailable", "msg.error_generic",
    "rights.summary", "help.call_helpline",
)


MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "app.name": "Nagarik Sahayak",
        "app.tagline": "Government schemes, made simple",
        "nav.home": "Home",
        "nav.chat": "Chat",
        "nav.schemes": "Schemes",
        "nav.exams": "Exams",
        "nav.profile": "My Profile",
        "nav.identity": "Identity",
        "nav.documents": "Documents",
        "nav.privacy": "Privacy and Rights",
        "nav.help": "Help",
        "action.continue": "Continue",
        "action.back": "Back",
        "action.submit": "Submit",
        "action.save": "Save",
        "action.download": "Download",
        "action.upload": "Upload",
        "action.verify_identity": "Verify your identity",
        "action.skip": "Skip for now",
        "status.eligible": "You may be eligible",
        "status.not_eligible": "You do not meet this scheme's conditions",
        "status.incomplete": "More information is needed",
        "status.under_review": "An officer is checking this",
        "status.verified": "Verified",
        "status.not_verified": "Not verified",
        "label.name": "Full name",
        "label.date_of_birth": "Date of birth",
        "label.mobile": "Mobile number",
        "label.district": "District",
        "label.state": "State",
        "label.annual_income": "Annual family income",
        "msg.no_fee": "This service is free. Never pay anyone to use it.",
        "msg.not_government": "This app is not run by the government. It helps "
                              "you prepare your application; you must submit it "
                              "yourself.",
        "msg.aadhaar_optional": "Aadhaar is one option among several. A voter ID, "
                                "ration card or job card also works.",
        "msg.language_unavailable": "This is not yet available in your language, "
                                    "so it is being shown in English.",
        "msg.error_generic": "Something went wrong. Your information is safe. "
                             "Please try again.",
        "rights.summary": "You can see, correct or delete your information at "
                          "any time.",
        "help.call_helpline": "Call the helpline",
    },

    "hi": {
        "app.name": "नागरिक सहायक",
        "app.tagline": "सरकारी योजनाएँ, आसान भाषा में",
        "nav.home": "होम",
        "nav.chat": "चैट",
        "nav.schemes": "योजनाएँ",
        "nav.exams": "परीक्षाएँ",
        "nav.profile": "मेरी प्रोफ़ाइल",
        "nav.identity": "पहचान",
        "nav.documents": "दस्तावेज़",
        "nav.privacy": "गोपनीयता और अधिकार",
        "nav.help": "सहायता",
        "action.continue": "आगे बढ़ें",
        "action.back": "पीछे",
        "action.submit": "जमा करें",
        "action.save": "सहेजें",
        "action.download": "डाउनलोड करें",
        "action.upload": "अपलोड करें",
        "action.verify_identity": "अपनी पहचान सत्यापित करें",
        "action.skip": "अभी छोड़ें",
        "status.eligible": "आप पात्र हो सकते हैं",
        "status.not_eligible": "आप इस योजना की शर्तें पूरी नहीं करते",
        "status.incomplete": "और जानकारी चाहिए",
        "status.under_review": "अधिकारी इसकी जाँच कर रहे हैं",
        "status.verified": "सत्यापित",
        "status.not_verified": "सत्यापित नहीं",
        "label.name": "पूरा नाम",
        "label.date_of_birth": "जन्म तिथि",
        "label.mobile": "मोबाइल नंबर",
        "label.district": "जिला",
        "label.state": "राज्य",
        "label.annual_income": "वार्षिक पारिवारिक आय",
        "msg.no_fee": "यह सेवा निःशुल्क है। इसके उपयोग के लिए किसी को पैसे न दें।",
        "msg.not_government": "यह ऐप सरकार द्वारा संचालित नहीं है। यह आपका आवेदन "
                              "तैयार करने में सहायता करता है; आवेदन आपको स्वयं जमा "
                              "करना होगा।",
        "msg.aadhaar_optional": "आधार कई विकल्पों में से एक है। मतदाता पहचान पत्र, "
                                "राशन कार्ड अथवा जॉब कार्ड भी चलेगा।",
        "msg.language_unavailable": "यह अभी आपकी भाषा में उपलब्ध नहीं है, इसलिए "
                                    "अंग्रेज़ी में दिखाया जा रहा है।",
        "msg.error_generic": "कुछ गड़बड़ हुई। आपकी जानकारी सुरक्षित है। कृपया पुनः "
                             "प्रयास करें।",
        "rights.summary": "आप अपनी जानकारी कभी भी देख, सुधार अथवा मिटा सकते हैं।",
        "help.call_helpline": "हेल्पलाइन पर कॉल करें",
    },

    "bn": {
        "app.name": "নাগরিক সহায়ক",
        "app.tagline": "সরকারি প্রকল্প, সহজ ভাষায়",
        "nav.home": "হোম",
        "nav.chat": "চ্যাট",
        "nav.schemes": "প্রকল্পসমূহ",
        "nav.exams": "পরীক্ষা",
        "nav.profile": "আমার প্রোফাইল",
        "nav.identity": "পরিচয়",
        "nav.documents": "নথিপত্র",
        "nav.privacy": "গোপনীয়তা ও অধিকার",
        "nav.help": "সহায়তা",
        "action.continue": "এগিয়ে যান",
        "action.back": "পিছনে",
        "action.submit": "জমা দিন",
        "action.save": "সংরক্ষণ করুন",
        "action.download": "ডাউনলোড করুন",
        "action.upload": "আপলোড করুন",
        "action.verify_identity": "আপনার পরিচয় যাচাই করুন",
        "action.skip": "আপাতত এড়িয়ে যান",
        "status.eligible": "আপনি যোগ্য হতে পারেন",
        "status.not_eligible": "আপনি এই প্রকল্পের শর্ত পূরণ করেন না",
        "status.incomplete": "আরও তথ্য প্রয়োজন",
        "status.under_review": "একজন আধিকারিক এটি যাচাই করছেন",
        "status.verified": "যাচাই করা হয়েছে",
        "status.not_verified": "যাচাই করা হয়নি",
        "label.name": "পুরো নাম",
        "label.date_of_birth": "জন্ম তারিখ",
        "label.mobile": "মোবাইল নম্বর",
        "label.district": "জেলা",
        "label.state": "রাজ্য",
        "label.annual_income": "বার্ষিক পারিবারিক আয়",
        "msg.no_fee": "এই পরিষেবা বিনামূল্যে। এটি ব্যবহারের জন্য কাউকে টাকা দেবেন না।",
        "msg.not_government": "এই অ্যাপটি সরকার পরিচালিত নয়। এটি আপনার আবেদন প্রস্তুত "
                              "করতে সাহায্য করে; আবেদন আপনাকে নিজেই জমা দিতে হবে।",
        "msg.aadhaar_optional": "আধার অনেক বিকল্পের মধ্যে একটি। ভোটার কার্ড, রেশন "
                                "কার্ড বা জব কার্ডও চলবে।",
        "msg.language_unavailable": "এটি এখনও আপনার ভাষায় উপলব্ধ নয়, তাই ইংরেজিতে "
                                    "দেখানো হচ্ছে।",
        "msg.error_generic": "কিছু ভুল হয়েছে। আপনার তথ্য সুরক্ষিত আছে। অনুগ্রহ করে "
                             "আবার চেষ্টা করুন।",
        "rights.summary": "আপনি যেকোনো সময় আপনার তথ্য দেখতে, সংশোধন করতে বা মুছে "
                          "ফেলতে পারেন।",
        "help.call_helpline": "হেল্পলাইনে ফোন করুন",
    },

    "mr": {
        "app.name": "नागरिक सहाय्यक",
        "app.tagline": "सरकारी योजना, सोप्या भाषेत",
        "nav.home": "मुख्यपृष्ठ",
        "nav.chat": "चॅट",
        "nav.schemes": "योजना",
        "nav.exams": "परीक्षा",
        "nav.profile": "माझी प्रोफाइल",
        "nav.identity": "ओळख",
        "nav.documents": "कागदपत्रे",
        "nav.privacy": "गोपनीयता व हक्क",
        "nav.help": "मदत",
        "action.continue": "पुढे जा",
        "action.back": "मागे",
        "action.submit": "सादर करा",
        "action.save": "जतन करा",
        "action.download": "डाउनलोड करा",
        "action.upload": "अपलोड करा",
        "action.verify_identity": "तुमची ओळख पडताळा",
        "action.skip": "आत्ता वगळा",
        "status.eligible": "तुम्ही पात्र असू शकता",
        "status.not_eligible": "तुम्ही या योजनेच्या अटी पूर्ण करत नाही",
        "status.incomplete": "अधिक माहिती हवी आहे",
        "status.under_review": "अधिकारी याची तपासणी करत आहेत",
        "status.verified": "पडताळणी झाली",
        "status.not_verified": "पडताळणी झाली नाही",
        "label.name": "पूर्ण नाव",
        "label.date_of_birth": "जन्मतारीख",
        "label.mobile": "मोबाइल क्रमांक",
        "label.district": "जिल्हा",
        "label.state": "राज्य",
        "label.annual_income": "वार्षिक कौटुंबिक उत्पन्न",
        "msg.no_fee": "ही सेवा विनामूल्य आहे. वापरासाठी कोणालाही पैसे देऊ नका.",
        "msg.not_government": "हे ॲप सरकार चालवत नाही. ते तुमचा अर्ज तयार करण्यास मदत "
                              "करते; अर्ज तुम्हाला स्वतः सादर करावा लागेल.",
        "msg.aadhaar_optional": "आधार हा अनेक पर्यायांपैकी एक आहे. मतदार ओळखपत्र, "
                                "शिधापत्रिका किंवा जॉब कार्डही चालेल.",
        "msg.language_unavailable": "हे अद्याप तुमच्या भाषेत उपलब्ध नाही, म्हणून "
                                    "इंग्रजीत दाखवले जात आहे.",
        "msg.error_generic": "काहीतरी चूक झाली. तुमची माहिती सुरक्षित आहे. कृपया "
                             "पुन्हा प्रयत्न करा.",
        "rights.summary": "तुम्ही तुमची माहिती कधीही पाहू, दुरुस्त करू किंवा हटवू शकता.",
        "help.call_helpline": "हेल्पलाइनवर कॉल करा",
    },

    "gu": {
        "app.name": "નાગરિક સહાયક",
        "app.tagline": "સરકારી યોજનાઓ, સરળ ભાષામાં",
        "nav.home": "હોમ",
        "nav.chat": "ચેટ",
        "nav.schemes": "યોજનાઓ",
        "nav.exams": "પરીક્ષાઓ",
        "nav.profile": "મારી પ્રોફાઇલ",
        "nav.identity": "ઓળખ",
        "nav.documents": "દસ્તાવેજો",
        "nav.privacy": "ગોપનીયતા અને અધિકારો",
        "nav.help": "મદદ",
        "action.continue": "આગળ વધો",
        "action.back": "પાછળ",
        "action.submit": "સબમિટ કરો",
        "action.save": "સાચવો",
        "action.download": "ડાઉનલોડ કરો",
        "action.upload": "અપલોડ કરો",
        "action.verify_identity": "તમારી ઓળખ ચકાસો",
        "action.skip": "હમણાં છોડો",
        "status.eligible": "તમે પાત્ર હોઈ શકો છો",
        "status.not_eligible": "તમે આ યોજનાની શરતો પૂરી કરતા નથી",
        "status.incomplete": "વધુ માહિતી જરૂરી છે",
        "status.under_review": "અધિકારી આની ચકાસણી કરી રહ્યા છે",
        "status.verified": "ચકાસાયેલ",
        "status.not_verified": "ચકાસાયેલ નથી",
        "label.name": "પૂરું નામ",
        "label.date_of_birth": "જન્મ તારીખ",
        "label.mobile": "મોબાઇલ નંબર",
        "label.district": "જિલ્લો",
        "label.state": "રાજ્ય",
        "label.annual_income": "વાર્ષિક કૌટુંબિક આવક",
        "msg.no_fee": "આ સેવા મફત છે. તેના ઉપયોગ માટે કોઈને પૈસા ન આપો.",
        "msg.not_government": "આ એપ સરકાર દ્વારા ચલાવવામાં આવતી નથી. તે તમારી અરજી "
                              "તૈયાર કરવામાં મદદ કરે છે; અરજી તમારે જાતે સબમિટ કરવાની "
                              "રહેશે.",
        "msg.aadhaar_optional": "આધાર અનેક વિકલ્પોમાંનો એક છે. મતદાર ઓળખપત્ર, રેશન "
                                "કાર્ડ કે જોબ કાર્ડ પણ ચાલશે.",
        "msg.language_unavailable": "આ હજુ તમારી ભાષામાં ઉપલબ્ધ નથી, તેથી અંગ્રેજીમાં "
                                    "બતાવવામાં આવે છે.",
        "msg.error_generic": "કંઈક ખોટું થયું. તમારી માહિતી સુરક્ષિત છે. કૃપા કરીને "
                             "ફરી પ્રયાસ કરો.",
        "rights.summary": "તમે તમારી માહિતી કોઈપણ સમયે જોઈ, સુધારી કે કાઢી શકો છો.",
        "help.call_helpline": "હેલ્પલાઇન પર કૉલ કરો",
    },

    "pa": {
        "app.name": "ਨਾਗਰਿਕ ਸਹਾਇਕ",
        "app.tagline": "ਸਰਕਾਰੀ ਸਕੀਮਾਂ, ਸੌਖੀ ਭਾਸ਼ਾ ਵਿੱਚ",
        "nav.home": "ਹੋਮ",
        "nav.chat": "ਗੱਲਬਾਤ",
        "nav.schemes": "ਸਕੀਮਾਂ",
        "nav.exams": "ਪ੍ਰੀਖਿਆਵਾਂ",
        "nav.profile": "ਮੇਰੀ ਪ੍ਰੋਫ਼ਾਈਲ",
        "nav.identity": "ਪਛਾਣ",
        "nav.documents": "ਦਸਤਾਵੇਜ਼",
        "nav.privacy": "ਨਿੱਜਤਾ ਅਤੇ ਹੱਕ",
        "nav.help": "ਮਦਦ",
        "action.continue": "ਅੱਗੇ ਵਧੋ",
        "action.back": "ਪਿੱਛੇ",
        "action.submit": "ਜਮ੍ਹਾਂ ਕਰੋ",
        "action.save": "ਸੰਭਾਲੋ",
        "action.download": "ਡਾਊਨਲੋਡ ਕਰੋ",
        "action.upload": "ਅੱਪਲੋਡ ਕਰੋ",
        "action.verify_identity": "ਆਪਣੀ ਪਛਾਣ ਦੀ ਪੁਸ਼ਟੀ ਕਰੋ",
        "action.skip": "ਹੁਣੇ ਛੱਡੋ",
        "status.eligible": "ਤੁਸੀਂ ਯੋਗ ਹੋ ਸਕਦੇ ਹੋ",
        "status.not_eligible": "ਤੁਸੀਂ ਇਸ ਸਕੀਮ ਦੀਆਂ ਸ਼ਰਤਾਂ ਪੂਰੀਆਂ ਨਹੀਂ ਕਰਦੇ",
        "status.incomplete": "ਹੋਰ ਜਾਣਕਾਰੀ ਚਾਹੀਦੀ ਹੈ",
        "status.under_review": "ਅਧਿਕਾਰੀ ਇਸ ਦੀ ਜਾਂਚ ਕਰ ਰਹੇ ਹਨ",
        "status.verified": "ਪੁਸ਼ਟੀ ਹੋ ਗਈ",
        "status.not_verified": "ਪੁਸ਼ਟੀ ਨਹੀਂ ਹੋਈ",
        "label.name": "ਪੂਰਾ ਨਾਂ",
        "label.date_of_birth": "ਜਨਮ ਮਿਤੀ",
        "label.mobile": "ਮੋਬਾਈਲ ਨੰਬਰ",
        "label.district": "ਜ਼ਿਲ੍ਹਾ",
        "label.state": "ਰਾਜ",
        "label.annual_income": "ਸਾਲਾਨਾ ਪਰਿਵਾਰਕ ਆਮਦਨ",
        "msg.no_fee": "ਇਹ ਸੇਵਾ ਮੁਫ਼ਤ ਹੈ। ਇਸ ਦੀ ਵਰਤੋਂ ਲਈ ਕਿਸੇ ਨੂੰ ਪੈਸੇ ਨਾ ਦਿਓ।",
        "msg.not_government": "ਇਹ ਐਪ ਸਰਕਾਰ ਵੱਲੋਂ ਨਹੀਂ ਚਲਾਈ ਜਾਂਦੀ। ਇਹ ਤੁਹਾਡੀ ਅਰਜ਼ੀ "
                              "ਤਿਆਰ ਕਰਨ ਵਿੱਚ ਮਦਦ ਕਰਦੀ ਹੈ; ਅਰਜ਼ੀ ਤੁਹਾਨੂੰ ਆਪ ਜਮ੍ਹਾਂ "
                              "ਕਰਨੀ ਪਵੇਗੀ।",
        "msg.aadhaar_optional": "ਆਧਾਰ ਕਈ ਬਦਲਾਂ ਵਿੱਚੋਂ ਇੱਕ ਹੈ। ਵੋਟਰ ਕਾਰਡ, ਰਾਸ਼ਨ ਕਾਰਡ "
                                "ਜਾਂ ਜੌਬ ਕਾਰਡ ਵੀ ਚੱਲੇਗਾ।",
        "msg.language_unavailable": "ਇਹ ਹਾਲੇ ਤੁਹਾਡੀ ਭਾਸ਼ਾ ਵਿੱਚ ਉਪਲਬਧ ਨਹੀਂ, ਇਸ ਲਈ "
                                    "ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਦਿਖਾਇਆ ਜਾ ਰਿਹਾ ਹੈ।",
        "msg.error_generic": "ਕੁਝ ਗ਼ਲਤ ਹੋਇਆ। ਤੁਹਾਡੀ ਜਾਣਕਾਰੀ ਸੁਰੱਖਿਅਤ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ "
                             "ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ।",
        "rights.summary": "ਤੁਸੀਂ ਆਪਣੀ ਜਾਣਕਾਰੀ ਕਿਸੇ ਵੀ ਸਮੇਂ ਵੇਖ, ਸੁਧਾਰ ਜਾਂ ਮਿਟਾ ਸਕਦੇ ਹੋ।",
        "help.call_helpline": "ਹੈਲਪਲਾਈਨ ਉੱਤੇ ਕਾਲ ਕਰੋ",
    },

    "ta": {
        "app.name": "நாகரிக் சகாயக்",
        "app.tagline": "அரசுத் திட்டங்கள், எளிய மொழியில்",
        "nav.home": "முகப்பு",
        "nav.chat": "உரையாடல்",
        "nav.schemes": "திட்டங்கள்",
        "nav.exams": "தேர்வுகள்",
        "nav.profile": "என் சுயவிவரம்",
        "nav.identity": "அடையாளம்",
        "nav.documents": "ஆவணங்கள்",
        "nav.privacy": "தனியுரிமையும் உரிமைகளும்",
        "nav.help": "உதவி",
        "action.continue": "தொடரவும்",
        "action.back": "பின்செல்",
        "action.submit": "சமர்ப்பிக்கவும்",
        "action.save": "சேமிக்கவும்",
        "action.download": "பதிவிறக்கவும்",
        "action.upload": "பதிவேற்றவும்",
        "action.verify_identity": "உங்கள் அடையாளத்தைச் சரிபார்க்கவும்",
        "action.skip": "இப்போதைக்குத் தவிர்",
        "status.eligible": "நீங்கள் தகுதி பெறலாம்",
        "status.not_eligible": "இந்தத் திட்டத்தின் நிபந்தனைகளை நீங்கள் பூர்த்தி செய்யவில்லை",
        "status.incomplete": "மேலும் தகவல் தேவை",
        "status.under_review": "ஓர் அலுவலர் இதைச் சரிபார்த்து வருகிறார்",
        "status.verified": "சரிபார்க்கப்பட்டது",
        "status.not_verified": "சரிபார்க்கப்படவில்லை",
        "label.name": "முழுப் பெயர்",
        "label.date_of_birth": "பிறந்த தேதி",
        "label.mobile": "கைபேசி எண்",
        "label.district": "மாவட்டம்",
        "label.state": "மாநிலம்",
        "label.annual_income": "ஆண்டு குடும்ப வருமானம்",
        "msg.no_fee": "இந்தச் சேவை இலவசம். இதைப் பயன்படுத்த யாருக்கும் பணம் தர வேண்டாம்.",
        "msg.not_government": "இந்தச் செயலி அரசால் நடத்தப்படுவதில்லை. உங்கள் "
                              "விண்ணப்பத்தைத் தயார் செய்ய இது உதவுகிறது; விண்ணப்பத்தை "
                              "நீங்களே சமர்ப்பிக்க வேண்டும்.",
        "msg.aadhaar_optional": "ஆதார் பல வழிகளில் ஒன்று மட்டுமே. வாக்காளர் அட்டை, "
                                "ரேஷன் அட்டை அல்லது வேலை அட்டையும் ஏற்கப்படும்.",
        "msg.language_unavailable": "இது இன்னும் உங்கள் மொழியில் கிடைக்கவில்லை, எனவே "
                                    "ஆங்கிலத்தில் காட்டப்படுகிறது.",
        "msg.error_generic": "ஏதோ தவறு நடந்தது. உங்கள் தகவல் பாதுகாப்பாக உள்ளது. "
                             "மீண்டும் முயற்சிக்கவும்.",
        "rights.summary": "உங்கள் தகவலை எப்போது வேண்டுமானாலும் பார்க்கலாம், திருத்தலாம் "
                          "அல்லது நீக்கலாம்.",
        "help.call_helpline": "உதவி எண்ணை அழைக்கவும்",
    },

    "te": {
        "app.name": "నాగరిక్ సహాయక్",
        "app.tagline": "ప్రభుత్వ పథకాలు, సులభ భాషలో",
        "nav.home": "హోమ్",
        "nav.chat": "చాట్",
        "nav.schemes": "పథకాలు",
        "nav.exams": "పరీక్షలు",
        "nav.profile": "నా ప్రొఫైల్",
        "nav.identity": "గుర్తింపు",
        "nav.documents": "పత్రాలు",
        "nav.privacy": "గోప్యత మరియు హక్కులు",
        "nav.help": "సహాయం",
        "action.continue": "కొనసాగించు",
        "action.back": "వెనుకకు",
        "action.submit": "సమర్పించు",
        "action.save": "భద్రపరచు",
        "action.download": "డౌన్‌లోడ్ చేయి",
        "action.upload": "అప్‌లోడ్ చేయి",
        "action.verify_identity": "మీ గుర్తింపును ధృవీకరించండి",
        "action.skip": "ప్రస్తుతానికి వదిలేయి",
        "status.eligible": "మీరు అర్హులు కావచ్చు",
        "status.not_eligible": "మీరు ఈ పథకం షరతులను నెరవేర్చడం లేదు",
        "status.incomplete": "మరింత సమాచారం అవసరం",
        "status.under_review": "ఒక అధికారి దీన్ని పరిశీలిస్తున్నారు",
        "status.verified": "ధృవీకరించబడింది",
        "status.not_verified": "ధృవీకరించబడలేదు",
        "label.name": "పూర్తి పేరు",
        "label.date_of_birth": "పుట్టిన తేదీ",
        "label.mobile": "మొబైల్ నంబర్",
        "label.district": "జిల్లా",
        "label.state": "రాష్ట్రం",
        "label.annual_income": "వార్షిక కుటుంబ ఆదాయం",
        "msg.no_fee": "ఈ సేవ ఉచితం. దీని కోసం ఎవరికీ డబ్బు ఇవ్వవద్దు.",
        "msg.not_government": "ఈ యాప్‌ను ప్రభుత్వం నడపడం లేదు. ఇది మీ దరఖాస్తును "
                              "సిద్ధం చేయడంలో సహాయపడుతుంది; దరఖాస్తును మీరే "
                              "సమర్పించాలి.",
        "msg.aadhaar_optional": "ఆధార్ అనేక ఎంపికలలో ఒకటి మాత్రమే. ఓటరు కార్డు, రేషన్ "
                                "కార్డు లేదా జాబ్ కార్డు కూడా పనిచేస్తుంది.",
        "msg.language_unavailable": "ఇది ఇంకా మీ భాషలో అందుబాటులో లేదు, అందుకే "
                                    "ఆంగ్లంలో చూపబడుతోంది.",
        "msg.error_generic": "ఏదో పొరపాటు జరిగింది. మీ సమాచారం సురక్షితం. దయచేసి "
                             "మళ్లీ ప్రయత్నించండి.",
        "rights.summary": "మీరు మీ సమాచారాన్ని ఎప్పుడైనా చూడవచ్చు, సరిచేయవచ్చు లేదా "
                          "తొలగించవచ్చు.",
        "help.call_helpline": "హెల్ప్‌లైన్‌కు కాల్ చేయండి",
    },

    "kn": {
        "app.name": "ನಾಗರಿಕ ಸಹಾಯಕ",
        "app.tagline": "ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು, ಸರಳ ಭಾಷೆಯಲ್ಲಿ",
        "nav.home": "ಮುಖಪುಟ",
        "nav.chat": "ಚಾಟ್",
        "nav.schemes": "ಯೋಜನೆಗಳು",
        "nav.exams": "ಪರೀಕ್ಷೆಗಳು",
        "nav.profile": "ನನ್ನ ಪ್ರೊಫೈಲ್",
        "nav.identity": "ಗುರುತು",
        "nav.documents": "ದಾಖಲೆಗಳು",
        "nav.privacy": "ಗೌಪ್ಯತೆ ಮತ್ತು ಹಕ್ಕುಗಳು",
        "nav.help": "ಸಹಾಯ",
        "action.continue": "ಮುಂದುವರಿಯಿರಿ",
        "action.back": "ಹಿಂದೆ",
        "action.submit": "ಸಲ್ಲಿಸಿ",
        "action.save": "ಉಳಿಸಿ",
        "action.download": "ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ",
        "action.upload": "ಅಪ್‌ಲೋಡ್ ಮಾಡಿ",
        "action.verify_identity": "ನಿಮ್ಮ ಗುರುತನ್ನು ಪರಿಶೀಲಿಸಿ",
        "action.skip": "ಸದ್ಯಕ್ಕೆ ಬಿಟ್ಟುಬಿಡಿ",
        "status.eligible": "ನೀವು ಅರ್ಹರಾಗಿರಬಹುದು",
        "status.not_eligible": "ನೀವು ಈ ಯೋಜನೆಯ ಷರತ್ತುಗಳನ್ನು ಪೂರೈಸುತ್ತಿಲ್ಲ",
        "status.incomplete": "ಇನ್ನಷ್ಟು ಮಾಹಿತಿ ಬೇಕಾಗಿದೆ",
        "status.under_review": "ಅಧಿಕಾರಿಯೊಬ್ಬರು ಇದನ್ನು ಪರಿಶೀಲಿಸುತ್ತಿದ್ದಾರೆ",
        "status.verified": "ಪರಿಶೀಲಿಸಲಾಗಿದೆ",
        "status.not_verified": "ಪರಿಶೀಲಿಸಲಾಗಿಲ್ಲ",
        "label.name": "ಪೂರ್ಣ ಹೆಸರು",
        "label.date_of_birth": "ಹುಟ್ಟಿದ ದಿನಾಂಕ",
        "label.mobile": "ಮೊಬೈಲ್ ಸಂಖ್ಯೆ",
        "label.district": "ಜಿಲ್ಲೆ",
        "label.state": "ರಾಜ್ಯ",
        "label.annual_income": "ವಾರ್ಷಿಕ ಕುಟುಂಬ ಆದಾಯ",
        "msg.no_fee": "ಈ ಸೇವೆ ಉಚಿತ. ಇದನ್ನು ಬಳಸಲು ಯಾರಿಗೂ ಹಣ ನೀಡಬೇಡಿ.",
        "msg.not_government": "ಈ ಆ್ಯಪ್ ಸರ್ಕಾರದಿಂದ ನಡೆಸಲ್ಪಡುತ್ತಿಲ್ಲ. ಇದು ನಿಮ್ಮ ಅರ್ಜಿ "
                              "ಸಿದ್ಧಪಡಿಸಲು ಸಹಾಯ ಮಾಡುತ್ತದೆ; ಅರ್ಜಿಯನ್ನು ನೀವೇ ಸಲ್ಲಿಸಬೇಕು.",
        "msg.aadhaar_optional": "ಆಧಾರ್ ಹಲವು ಆಯ್ಕೆಗಳಲ್ಲಿ ಒಂದು. ಮತದಾರರ ಗುರುತಿನ ಚೀಟಿ, "
                                "ಪಡಿತರ ಚೀಟಿ ಅಥವಾ ಜಾಬ್ ಕಾರ್ಡ್ ಕೂಡ ನಡೆಯುತ್ತದೆ.",
        "msg.language_unavailable": "ಇದು ಇನ್ನೂ ನಿಮ್ಮ ಭಾಷೆಯಲ್ಲಿ ಲಭ್ಯವಿಲ್ಲ, ಆದ್ದರಿಂದ "
                                    "ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ ತೋರಿಸಲಾಗುತ್ತಿದೆ.",
        "msg.error_generic": "ಏನೋ ತಪ್ಪಾಗಿದೆ. ನಿಮ್ಮ ಮಾಹಿತಿ ಸುರಕ್ಷಿತವಾಗಿದೆ. ದಯವಿಟ್ಟು "
                             "ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
        "rights.summary": "ನಿಮ್ಮ ಮಾಹಿತಿಯನ್ನು ಯಾವಾಗ ಬೇಕಾದರೂ ನೋಡಬಹುದು, ಸರಿಪಡಿಸಬಹುದು "
                          "ಅಥವಾ ಅಳಿಸಬಹುದು.",
        "help.call_helpline": "ಸಹಾಯವಾಣಿಗೆ ಕರೆ ಮಾಡಿ",
    },

    "ml": {
        "app.name": "നാഗരിക് സഹായക്",
        "app.tagline": "സർക്കാർ പദ്ധതികൾ, ലളിതമായ ഭാഷയിൽ",
        "nav.home": "ഹോം",
        "nav.chat": "ചാറ്റ്",
        "nav.schemes": "പദ്ധതികൾ",
        "nav.exams": "പരീക്ഷകൾ",
        "nav.profile": "എന്റെ പ്രൊഫൈൽ",
        "nav.identity": "ഐഡന്റിറ്റി",
        "nav.documents": "രേഖകൾ",
        "nav.privacy": "സ്വകാര്യതയും അവകാശങ്ങളും",
        "nav.help": "സഹായം",
        "action.continue": "തുടരുക",
        "action.back": "പിന്നോട്ട്",
        "action.submit": "സമർപ്പിക്കുക",
        "action.save": "സംരക്ഷിക്കുക",
        "action.download": "ഡൗൺലോഡ് ചെയ്യുക",
        "action.upload": "അപ്‌ലോഡ് ചെയ്യുക",
        "action.verify_identity": "നിങ്ങളുടെ ഐഡന്റിറ്റി പരിശോധിക്കുക",
        "action.skip": "ഇപ്പോൾ ഒഴിവാക്കുക",
        "status.eligible": "നിങ്ങൾ അർഹനായേക്കാം",
        "status.not_eligible": "ഈ പദ്ധതിയുടെ വ്യവസ്ഥകൾ നിങ്ങൾ പാലിക്കുന്നില്ല",
        "status.incomplete": "കൂടുതൽ വിവരങ്ങൾ ആവശ്യമാണ്",
        "status.under_review": "ഒരു ഉദ്യോഗസ്ഥൻ ഇത് പരിശോധിക്കുന്നു",
        "status.verified": "പരിശോധിച്ചു",
        "status.not_verified": "പരിശോധിച്ചിട്ടില്ല",
        "label.name": "പൂർണ്ണ നാമം",
        "label.date_of_birth": "ജനന തീയതി",
        "label.mobile": "മൊബൈൽ നമ്പർ",
        "label.district": "ജില്ല",
        "label.state": "സംസ്ഥാനം",
        "label.annual_income": "വാർഷിക കുടുംബ വരുമാനം",
        "msg.no_fee": "ഈ സേവനം സൗജന്യമാണ്. ഇത് ഉപയോഗിക്കാൻ ആർക്കും പണം നൽകരുത്.",
        "msg.not_government": "ഈ ആപ്പ് സർക്കാർ നടത്തുന്നതല്ല. നിങ്ങളുടെ അപേക്ഷ "
                              "തയ്യാറാക്കാൻ ഇത് സഹായിക്കുന്നു; അപേക്ഷ നിങ്ങൾ തന്നെ "
                              "സമർപ്പിക്കണം.",
        "msg.aadhaar_optional": "ആധാർ പല മാർഗങ്ങളിൽ ഒന്ന് മാത്രമാണ്. വോട്ടർ ഐഡി, റേഷൻ "
                                "കാർഡ് അല്ലെങ്കിൽ ജോബ് കാർഡും സ്വീകാര്യമാണ്.",
        "msg.language_unavailable": "ഇത് ഇനിയും നിങ്ങളുടെ ഭാഷയിൽ ലഭ്യമല്ല, അതിനാൽ "
                                    "ഇംഗ്ലീഷിൽ കാണിക്കുന്നു.",
        "msg.error_generic": "എന്തോ പിഴവ് സംഭവിച്ചു. നിങ്ങളുടെ വിവരങ്ങൾ സുരക്ഷിതമാണ്. "
                             "വീണ്ടും ശ്രമിക്കുക.",
        "rights.summary": "നിങ്ങളുടെ വിവരങ്ങൾ എപ്പോൾ വേണമെങ്കിലും കാണാനും തിരുത്താനും "
                          "ഇല്ലാതാക്കാനും കഴിയും.",
        "help.call_helpline": "ഹെൽപ്‌ലൈനിൽ വിളിക്കുക",
    },

    "or": {
        "app.name": "ନାଗରିକ ସହାୟକ",
        "app.tagline": "ସରକାରୀ ଯୋଜନା, ସହଜ ଭାଷାରେ",
        "nav.home": "ହୋମ",
        "nav.chat": "ଚାଟ",
        "nav.schemes": "ଯୋଜନାମାନ",
        "nav.exams": "ପରୀକ୍ଷା",
        "nav.profile": "ମୋ ପ୍ରୋଫାଇଲ",
        "nav.identity": "ପରିଚୟ",
        "nav.documents": "ଦଲିଲ",
        "nav.privacy": "ଗୋପନୀୟତା ଓ ଅଧିକାର",
        "nav.help": "ସହାୟତା",
        "action.continue": "ଆଗକୁ ଯାଆନ୍ତୁ",
        "action.back": "ପଛକୁ",
        "action.submit": "ଦାଖଲ କରନ୍ତୁ",
        "action.save": "ସଞ୍ଚୟ କରନ୍ତୁ",
        "action.download": "ଡାଉନଲୋଡ କରନ୍ତୁ",
        "action.upload": "ଅପଲୋଡ କରନ୍ତୁ",
        "action.verify_identity": "ଆପଣଙ୍କ ପରିଚୟ ଯାଞ୍ଚ କରନ୍ତୁ",
        "action.skip": "ବର୍ତ୍ତମାନ ଛାଡ଼ନ୍ତୁ",
        "status.eligible": "ଆପଣ ଯୋଗ୍ୟ ହୋଇପାରନ୍ତି",
        "status.not_eligible": "ଆପଣ ଏହି ଯୋଜନାର ସର୍ତ୍ତ ପୂରଣ କରୁନାହାନ୍ତି",
        "status.incomplete": "ଅଧିକ ସୂଚନା ଆବଶ୍ୟକ",
        "status.under_review": "ଜଣେ ଅଧିକାରୀ ଏହା ଯାଞ୍ଚ କରୁଛନ୍ତି",
        "status.verified": "ଯାଞ୍ଚ ହୋଇଛି",
        "status.not_verified": "ଯାଞ୍ଚ ହୋଇନାହିଁ",
        "label.name": "ପୂରା ନାମ",
        "label.date_of_birth": "ଜନ୍ମ ତାରିଖ",
        "label.mobile": "ମୋବାଇଲ ନମ୍ବର",
        "label.district": "ଜିଲ୍ଲା",
        "label.state": "ରାଜ୍ୟ",
        "label.annual_income": "ବାର୍ଷିକ ପାରିବାରିକ ଆୟ",
        "msg.no_fee": "ଏହି ସେବା ମାଗଣା। ଏହାର ବ୍ୟବହାର ପାଇଁ କାହାକୁ ଟଙ୍କା ଦିଅନ୍ତୁ ନାହିଁ।",
        "msg.not_government": "ଏହି ଆପ ସରକାର ଚଳାଉ ନାହାନ୍ତି। ଏହା ଆପଣଙ୍କ ଆବେଦନ ପ୍ରସ୍ତୁତ "
                              "କରିବାରେ ସାହାଯ୍ୟ କରେ; ଆବେଦନ ଆପଣ ନିଜେ ଦାଖଲ କରିବେ।",
        "msg.aadhaar_optional": "ଆଧାର ଅନେକ ବିକଳ୍ପ ମଧ୍ୟରୁ ଗୋଟିଏ। ଭୋଟର କାର୍ଡ, ରାସନ "
                                "କାର୍ଡ କିମ୍ବା ଜବ କାର୍ଡ ମଧ୍ୟ ଚଳିବ।",
        "msg.language_unavailable": "ଏହା ଏପର୍ଯ୍ୟନ୍ତ ଆପଣଙ୍କ ଭାଷାରେ ଉପଲବ୍ଧ ନାହିଁ, ତେଣୁ "
                                    "ଇଂରାଜୀରେ ଦେଖାଯାଉଛି।",
        "msg.error_generic": "କିଛି ଭୁଲ ହୋଇଛି। ଆପଣଙ୍କ ସୂଚନା ସୁରକ୍ଷିତ ଅଛି। ଦୟାକରି ପୁଣି "
                             "ଚେଷ୍ଟା କରନ୍ତୁ।",
        "rights.summary": "ଆପଣ ଯେକୌଣସି ସମୟରେ ଆପଣଙ୍କ ସୂଚନା ଦେଖି, ସଂଶୋଧନ କରି କିମ୍ବା "
                          "ବିଲୋପ କରିପାରିବେ।",
        "help.call_helpline": "ହେଲ୍ପଲାଇନକୁ କଲ କରନ୍ତୁ",
    },

    "as": {
        "app.name": "নাগৰিক সহায়ক",
        "app.tagline": "চৰকাৰী আঁচনি, সহজ ভাষাত",
        "nav.home": "হোম",
        "nav.chat": "চেট",
        "nav.schemes": "আঁচনিসমূহ",
        "nav.exams": "পৰীক্ষা",
        "nav.profile": "মোৰ প্ৰ’ফাইল",
        "nav.identity": "পৰিচয়",
        "nav.documents": "নথি-পত্ৰ",
        "nav.privacy": "গোপনীয়তা আৰু অধিকাৰ",
        "nav.help": "সহায়",
        "action.continue": "আগবাঢ়ক",
        "action.back": "পিছলৈ",
        "action.submit": "দাখিল কৰক",
        "action.save": "সংৰক্ষণ কৰক",
        "action.download": "ডাউনল’ড কৰক",
        "action.upload": "আপল’ড কৰক",
        "action.verify_identity": "আপোনাৰ পৰিচয় সত্যাপন কৰক",
        "action.skip": "এতিয়াৰ বাবে এৰি দিয়ক",
        "status.eligible": "আপুনি যোগ্য হ’ব পাৰে",
        "status.not_eligible": "আপুনি এই আঁচনিৰ চৰ্তসমূহ পূৰণ কৰা নাই",
        "status.incomplete": "অধিক তথ্যৰ প্ৰয়োজন",
        "status.under_review": "এজন বিষয়াই ইয়াক পৰীক্ষা কৰি আছে",
        "status.verified": "সত্যাপিত",
        "status.not_verified": "সত্যাপিত নহয়",
        "label.name": "সম্পূৰ্ণ নাম",
        "label.date_of_birth": "জন্ম তাৰিখ",
        "label.mobile": "মোবাইল নম্বৰ",
        "label.district": "জিলা",
        "label.state": "ৰাজ্য",
        "label.annual_income": "বাৰ্ষিক পাৰিবাৰিক আয়",
        "msg.no_fee": "এই সেৱা বিনামূলীয়া। ইয়াক ব্যৱহাৰ কৰিবলৈ কাকো ধন নিদিব।",
        "msg.not_government": "এই এপ্‌টো চৰকাৰে চলোৱা নহয়। ই আপোনাৰ আবেদন প্ৰস্তুত "
                              "কৰাত সহায় কৰে; আবেদন আপুনি নিজেই দাখিল কৰিব লাগিব।",
        "msg.aadhaar_optional": "আধাৰ বহুতো বিকল্পৰ ভিতৰত এটা। ভোটাৰ কাৰ্ড, ৰেচন "
                                "কাৰ্ড বা জব কাৰ্ডো চলিব।",
        "msg.language_unavailable": "এইটো এতিয়াও আপোনাৰ ভাষাত উপলব্ধ নহয়, সেয়েহে "
                                    "ইংৰাজীত দেখুওৱা হৈছে।",
        "msg.error_generic": "কিবা ভুল হ’ল। আপোনাৰ তথ্য সুৰক্ষিত। অনুগ্ৰহ কৰি পুনৰ "
                             "চেষ্টা কৰক।",
        "rights.summary": "আপুনি যিকোনো সময়তে আপোনাৰ তথ্য চাব, শুধৰাব বা মচিব পাৰে।",
        "help.call_helpline": "হেল্পলাইনলৈ ফোন কৰক",
    },

    "ur": {
        "app.name": "ناگرک سہایک",
        "app.tagline": "سرکاری اسکیمیں، آسان زبان میں",
        "nav.home": "ہوم",
        "nav.chat": "چیٹ",
        "nav.schemes": "اسکیمیں",
        "nav.exams": "امتحانات",
        "nav.profile": "میری پروفائل",
        "nav.identity": "شناخت",
        "nav.documents": "دستاویزات",
        "nav.privacy": "رازداری اور حقوق",
        "nav.help": "مدد",
        "action.continue": "آگے بڑھیں",
        "action.back": "پیچھے",
        "action.submit": "جمع کریں",
        "action.save": "محفوظ کریں",
        "action.download": "ڈاؤن لوڈ کریں",
        "action.upload": "اپ لوڈ کریں",
        "action.verify_identity": "اپنی شناخت کی تصدیق کریں",
        "action.skip": "ابھی چھوڑ دیں",
        "status.eligible": "آپ اہل ہو سکتے ہیں",
        "status.not_eligible": "آپ اس اسکیم کی شرائط پوری نہیں کرتے",
        "status.incomplete": "مزید معلومات درکار ہیں",
        "status.under_review": "ایک افسر اس کی جانچ کر رہے ہیں",
        "status.verified": "تصدیق شدہ",
        "status.not_verified": "تصدیق نہیں ہوئی",
        "label.name": "پورا نام",
        "label.date_of_birth": "تاریخ پیدائش",
        "label.mobile": "موبائل نمبر",
        "label.district": "ضلع",
        "label.state": "ریاست",
        "label.annual_income": "سالانہ خاندانی آمدنی",
        "msg.no_fee": "یہ خدمت مفت ہے۔ اس کے استعمال کے لیے کسی کو پیسے نہ دیں۔",
        "msg.not_government": "یہ ایپ حکومت نہیں چلاتی۔ یہ آپ کی درخواست تیار کرنے "
                              "میں مدد کرتی ہے؛ درخواست آپ کو خود جمع کرنی ہوگی۔",
        "msg.aadhaar_optional": "آدھار کئی اختیارات میں سے ایک ہے۔ ووٹر کارڈ، راشن "
                                "کارڈ یا جاب کارڈ بھی چلے گا۔",
        "msg.language_unavailable": "یہ ابھی آپ کی زبان میں دستیاب نہیں، اس لیے "
                                    "انگریزی میں دکھایا جا رہا ہے۔",
        "msg.error_generic": "کچھ غلط ہو گیا۔ آپ کی معلومات محفوظ ہیں۔ براہ کرم "
                             "دوبارہ کوشش کریں۔",
        "rights.summary": "آپ اپنی معلومات کسی بھی وقت دیکھ، درست یا حذف کر سکتے ہیں۔",
        "help.call_helpline": "ہیلپ لائن پر کال کریں",
    },

    "ne": {
        "app.name": "नागरिक सहायक",
        "app.tagline": "सरकारी योजनाहरू, सरल भाषामा",
        "nav.home": "गृहपृष्ठ",
        "nav.chat": "कुराकानी",
        "nav.schemes": "योजनाहरू",
        "nav.exams": "परीक्षाहरू",
        "nav.profile": "मेरो प्रोफाइल",
        "nav.identity": "परिचय",
        "nav.documents": "कागजातहरू",
        "nav.privacy": "गोपनीयता र अधिकार",
        "nav.help": "सहयोग",
        "action.continue": "अगाडि बढ्नुहोस्",
        "action.back": "पछाडि",
        "action.submit": "पेस गर्नुहोस्",
        "action.save": "सुरक्षित गर्नुहोस्",
        "action.download": "डाउनलोड गर्नुहोस्",
        "action.upload": "अपलोड गर्नुहोस्",
        "action.verify_identity": "आफ्नो परिचय प्रमाणित गर्नुहोस्",
        "action.skip": "अहिलेलाई छोड्नुहोस्",
        "status.eligible": "तपाईं योग्य हुन सक्नुहुन्छ",
        "status.not_eligible": "तपाईं यस योजनाका सर्तहरू पूरा गर्नुहुन्न",
        "status.incomplete": "थप जानकारी चाहिन्छ",
        "status.under_review": "एक अधिकारीले यसको जाँच गर्दै हुनुहुन्छ",
        "status.verified": "प्रमाणित",
        "status.not_verified": "प्रमाणित छैन",
        "label.name": "पूरा नाम",
        "label.date_of_birth": "जन्म मिति",
        "label.mobile": "मोबाइल नम्बर",
        "label.district": "जिल्ला",
        "label.state": "राज्य",
        "label.annual_income": "वार्षिक पारिवारिक आय",
        "msg.no_fee": "यो सेवा निःशुल्क छ। यसको प्रयोगका लागि कसैलाई पैसा नदिनुहोस्।",
        "msg.not_government": "यो एप सरकारले चलाएको होइन। यसले तपाईंको आवेदन तयार "
                              "गर्न मद्दत गर्छ; आवेदन तपाईं आफैंले पेस गर्नुपर्छ।",
        "msg.aadhaar_optional": "आधार धेरै विकल्पमध्ये एक हो। मतदाता परिचयपत्र, राशन "
                                "कार्ड वा जब कार्ड पनि चल्छ।",
        "msg.language_unavailable": "यो अझै तपाईंको भाषामा उपलब्ध छैन, त्यसैले "
                                    "अङ्ग्रेजीमा देखाइएको छ।",
        "msg.error_generic": "केही गडबड भयो। तपाईंको जानकारी सुरक्षित छ। कृपया फेरि "
                             "प्रयास गर्नुहोस्।",
        "rights.summary": "तपाईं आफ्नो जानकारी जुनसुकै बेला हेर्न, सच्याउन वा मेटाउन "
                          "सक्नुहुन्छ।",
        "help.call_helpline": "हेल्पलाइनमा फोन गर्नुहोस्",
    },

    "sa": {
        "app.name": "नागरिकसहायकः",
        "app.tagline": "शासकीययोजनाः, सरलभाषया",
        "nav.home": "मुख्यपृष्ठम्",
        "nav.chat": "संवादः",
        "nav.schemes": "योजनाः",
        "nav.exams": "परीक्षाः",
        "nav.profile": "मम विवरणम्",
        "nav.identity": "परिचयः",
        "nav.documents": "अभिलेखाः",
        "nav.privacy": "गोपनीयता अधिकाराश्च",
        "nav.help": "साहाय्यम्",
        "action.continue": "अग्रे गच्छतु",
        "action.back": "पृष्ठतः",
        "action.submit": "समर्पयतु",
        "action.save": "रक्षतु",
        "action.download": "अवतारयतु",
        "action.upload": "उत्थापयतु",
        "action.verify_identity": "स्वपरिचयं प्रमाणयतु",
        "action.skip": "इदानीं त्यजतु",
        "status.eligible": "भवान् योग्यः भवितुम् अर्हति",
        "status.not_eligible": "भवान् अस्याः योजनायाः शर्तान् न पूरयति",
        "status.incomplete": "अधिकं विवरणम् आवश्यकम्",
        "status.under_review": "अधिकारी इदं परीक्षते",
        "status.verified": "प्रमाणितम्",
        "status.not_verified": "अप्रमाणितम्",
        "label.name": "पूर्णं नाम",
        "label.date_of_birth": "जन्मदिनाङ्कः",
        "label.mobile": "चलभाषसङ्ख्या",
        "label.district": "मण्डलम्",
        "label.state": "राज्यम्",
        "label.annual_income": "वार्षिकं कौटुम्बिकम् आयः",
        "msg.no_fee": "एषा सेवा निःशुल्का। अस्य उपयोगाय कस्मैचित् धनं मा ददातु।",
        "msg.not_government": "अयम् अनुप्रयोगः शासनेन न चाल्यते। एतत् भवतः आवेदनं "
                              "सज्जीकर्तुं साहाय्यं करोति; आवेदनं भवता स्वयमेव "
                              "समर्पणीयम्।",
        "msg.aadhaar_optional": "आधारः बहुषु विकल्पेषु एकः। मतदातृपत्रम्, अन्नपत्रम् "
                                "अथवा कार्यपत्रम् अपि स्वीकार्यम्।",
        "msg.language_unavailable": "इदम् अद्यापि भवतः भाषायां न उपलब्धम्, अतः "
                                    "आङ्ग्लभाषायां दर्श्यते।",
        "msg.error_generic": "कश्चन दोषः अभवत्। भवतः विवरणं सुरक्षितम् अस्ति। कृपया "
                             "पुनः प्रयत्नं करोतु।",
        "rights.summary": "भवान् स्वविवरणं कदापि द्रष्टुं, संशोधयितुं, लोपयितुं वा "
                          "शक्नोति।",
        "help.call_helpline": "साहाय्यदूरवाणीम् आह्वयतु",
    },
}


def quality_of(code: str) -> Quality:
    if code == "en":
        return Quality.SOURCE
    return Quality.DRAFT if MESSAGES.get(code) else Quality.MISSING


def coverage(code: str) -> dict:
    """How much of the interface exists in this language, and how good it is."""
    strings = MESSAGES.get(code) or {}
    present = sum(1 for k in KEYS if strings.get(k))
    quality = quality_of(code)
    return {
        "quality": quality.value,
        "translatedKeys": present,
        "totalKeys": len(KEYS),
        "percent": round(100 * present / len(KEYS)) if KEYS else 0,
        "needsNativeReview": quality is Quality.DRAFT,
        "reason": UNTRANSLATED_REASON if quality is Quality.MISSING else "",
    }
