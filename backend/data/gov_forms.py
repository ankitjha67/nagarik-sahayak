"""Real Indian government scheme form catalog.

Each entry pairs a live government PDF URL with a curated, hand-verified field
definition. The curated fields serve three purposes:

1. **Offline/demo operation** — the app is fully functional with no LLM key and
   no network access, because every catalog scheme already has its fields.
2. **Extraction fallback** — if a live PDF is unreachable (government URLs rot
   often) or OCR quality is poor, we still have usable field definitions.
3. **Quality baseline** — LLM extraction of a catalog scheme is merged against
   these fields so a bad LLM run cannot regress a known-good form.

`source_verified` records the date the `official_pdf_url` was last confirmed to
return a real PDF (HTTP 200 + %PDF magic bytes).

Field schema matches what FormTemplate.extractedFields stores and what
SmartProfiler/pdf_filler consume:
    fieldName, labelEnglish, labelHindi, type, required, section, profileKey,
    options (select only), maxLength/pattern (validation, optional)
"""
from __future__ import annotations

# ── Shared field builders ────────────────────────────────────────────────
# Indian government forms repeat the same identity/bank/address blocks. Defining
# them once keeps profileKeys consistent so the profiler can reuse an answer
# across schemes (the whole point of profileKey).


def _f(name, en, hi, ftype="text", required=True, section="", profile_key=None, **extra):
    field = {
        "fieldName": name,
        "labelEnglish": en,
        "labelHindi": hi,
        "type": ftype,
        "required": required,
        "section": section,
        "profileKey": profile_key or name,
    }
    field.update(extra)
    return field


def identity_fields(section="Applicant Details"):
    """Name / Aadhaar / DOB / gender / category — present on nearly every form."""
    return [
        _f("applicant_name", "Full Name (as per Aadhaar)", "पूरा नाम (आधार के अनुसार)",
           section=section, profile_key="name", maxLength=100),
        _f("father_husband_name", "Father's / Husband's Name", "पिता / पति का नाम",
           section=section, profile_key="father_husband_name", maxLength=100),
        _f("aadhaar_number", "Aadhaar Number", "आधार संख्या", "aadhaar",
           section=section, profile_key="aadhaar_number", pattern=r"^\d{12}$"),
        _f("date_of_birth", "Date of Birth", "जन्म तिथि", "date",
           section=section, profile_key="date_of_birth"),
        _f("gender", "Gender", "लिंग", "select", section=section,
           profile_key="gender", options=["Male", "Female", "Transgender"]),
        _f("category", "Category", "श्रेणी", "select", section=section,
           profile_key="category", options=["General", "OBC", "SC", "ST", "EWS"]),
        _f("mobile_number", "Mobile Number", "मोबाइल नंबर", "phone",
           section=section, profile_key="mobile_number", pattern=r"^[6-9]\d{9}$"),
    ]


def address_fields(section="Address"):
    return [
        _f("address_line", "Address (House No., Street, Village)",
           "पता (मकान नं., गली, गाँव)", "textarea", section=section,
           profile_key="address_line", maxLength=250),
        _f("district", "District", "जिला", section=section, profile_key="district"),
        _f("state", "State", "राज्य", section=section, profile_key="state"),
        _f("pincode", "PIN Code", "पिन कोड", "number", section=section,
           profile_key="pincode", pattern=r"^\d{6}$"),
    ]


def bank_fields(section="Bank Details"):
    return [
        _f("bank_account_number", "Bank Account Number", "बैंक खाता संख्या",
           section=section, profile_key="bank_account_number", pattern=r"^\d{9,18}$"),
        _f("ifsc_code", "IFSC Code", "आईएफएससी कोड", section=section,
           profile_key="ifsc_code", pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$"),
        _f("bank_name", "Bank Name", "बैंक का नाम", section=section,
           profile_key="bank_name"),
        _f("branch_name", "Branch Name", "शाखा का नाम", section=section,
           profile_key="branch_name", required=False),
    ]


def income_field(section="Economic Details", required=True):
    return _f("annual_income", "Annual Family Income (₹)", "वार्षिक पारिवारिक आय (₹)",
              "number", required=required, section=section, profile_key="annual_income")


# ── The catalog ──────────────────────────────────────────────────────────
# official_pdf_url values below were verified live (HTTP 200 + %PDF) on the
# date in source_verified. `is_scanned` marks forms known to be image-only —
# these require OCR, which the extractor enables automatically.

GOV_FORM_CATALOG: list[dict] = [
    {
        "schemeName": "PM-KISAN Samman Nidhi",
        "schemeNameHindi": "पीएम-किसान सम्मान निधि",
        "category": "agriculture",
        "level": "Central", "state": None,
        "description": "Income support of ₹6,000 per year in three equal instalments to all landholding farmer families.",
        "descriptionHindi": "सभी भूमिधारक किसान परिवारों को तीन समान किस्तों में प्रति वर्ष ₹6,000 की आय सहायता।",
        "officialWebsite": "https://pmkisan.gov.in/",
        # PM-KISAN registration is online-only (portal or CSC); the ministry
        # publishes no downloadable application form. The PDF below is the
        # scheme booklet, so it is a reference document, not a form to extract.
        "official_pdf_url": "",
        "reference_pdf_url": "https://pmkisan.gov.in/Documents/PMKisanSamanNidhi.PDF",
        "source_verified": "2026-09-01",
        "is_scanned": True,
        "eligibilityCriteria": {
            "summary": "All landholding farmer families with cultivable land. Institutional landholders, income-tax payers, and serving/retired government employees (above Group D) are excluded.",
            "summaryHindi": "खेती योग्य भूमि वाले सभी भूमिधारक किसान परिवार। संस्थागत भूमिधारक, आयकर दाता और सरकारी कर्मचारी अपात्र हैं।",
            "rules": [
                {"field": "land_holding_acres", "op": ">", "value": 0},
                {"field": "is_income_tax_payer", "op": "==", "value": "No"},
            ],
            "benefit": "₹6,000 per year (₹2,000 × 3 instalments)",
        },
        "sections": [
            {"name": "Applicant Details", "nameHindi": "आवेदक का विवरण"},
            {"name": "Address", "nameHindi": "पता"},
            {"name": "Land Details", "nameHindi": "भूमि का विवरण"},
            {"name": "Bank Details", "nameHindi": "बैंक विवरण"},
            {"name": "Declaration", "nameHindi": "घोषणा"},
        ],
        "extractedFields": [
            *identity_fields(),
            *address_fields(),
            _f("farmer_category", "Farmer Category", "किसान श्रेणी", "select",
               section="Land Details", profile_key="farmer_category",
               options=["Small (< 2 hectare)", "Marginal (< 1 hectare)", "Other"]),
            _f("land_holding_acres", "Total Cultivable Land (in acres)",
               "कुल खेती योग्य भूमि (एकड़ में)", "number",
               section="Land Details", profile_key="land_holding_acres"),
            _f("survey_khasra_number", "Survey / Khasra Number", "सर्वे / खसरा नंबर",
               section="Land Details", profile_key="survey_khasra_number"),
            _f("land_ownership_type", "Land Ownership", "भूमि स्वामित्व", "select",
               section="Land Details", profile_key="land_ownership_type",
               options=["Owned", "Leased", "Share Cropper"]),
            *bank_fields(),
            _f("is_income_tax_payer", "Are you an income tax payer?",
               "क्या आप आयकर दाता हैं?", "select", section="Declaration",
               profile_key="is_income_tax_payer", options=["No", "Yes"]),
            _f("is_govt_employee", "Are you a government employee?",
               "क्या आप सरकारी कर्मचारी हैं?", "select", section="Declaration",
               profile_key="is_govt_employee", options=["No", "Yes"]),
        ],
    },
    {
        # Field set derived from the real OCR'd text of Kcc.pdf (ANNEXURE-II,
        # "LOAN APPLICATION FORM FOR AGRICULTURAL CREDIT FOR PM-KISAN BENEFICIARIES")
        "schemeName": "Kisan Credit Card (KCC)",
        "schemeNameHindi": "किसान क्रेडिट कार्ड",
        "category": "agriculture",
        "level": "Central", "state": None,
        "description": "Short-term crop loan facility for PM-KISAN beneficiaries at subsidised interest, including allied activities like dairy, poultry and fisheries.",
        "descriptionHindi": "पीएम-किसान लाभार्थियों के लिए रियायती ब्याज पर अल्पकालिक फसल ऋण सुविधा।",
        "officialWebsite": "https://pmkisan.gov.in/",
        "official_pdf_url": "https://pmkisan.gov.in/Documents/Kcc.pdf",
        "source_verified": "2026-09-01",
        "is_scanned": True,
        "eligibilityCriteria": {
            "summary": "PM-KISAN beneficiaries and farmers engaged in crop production or allied activities (dairy, poultry, fisheries).",
            "summaryHindi": "पीएम-किसान लाभार्थी और फसल उत्पादन या संबद्ध गतिविधियों में लगे किसान।",
            "rules": [{"field": "land_holding_acres", "op": ">", "value": 0}],
            "benefit": "Crop loan up to ₹3 lakh at 4% effective interest",
        },
        "sections": [
            {"name": "Bank Details", "nameHindi": "बैंक विवरण"},
            {"name": "Loan Requirement", "nameHindi": "ऋण आवश्यकता"},
            {"name": "Applicant Details", "nameHindi": "आवेदक का विवरण"},
            {"name": "Address", "nameHindi": "पता"},
            {"name": "Land Details", "nameHindi": "भूमि का विवरण"},
            {"name": "Crop Details", "nameHindi": "फसल विवरण"},
            {"name": "Declaration", "nameHindi": "घोषणा"},
        ],
        "extractedFields": [
            _f("bank_name", "Name of Bank", "बैंक का नाम", section="Bank Details",
               profile_key="bank_name"),
            _f("branch_name", "Branch", "शाखा", section="Bank Details",
               profile_key="branch_name"),
            _f("kcc_request_type", "Type of KCC Request", "केसीसी अनुरोध का प्रकार",
               "select", section="Loan Requirement", profile_key="kcc_request_type",
               options=["Issue of fresh KCC", "Enhancement of existing limit",
                        "Activation of inoperative KCC account"]),
            _f("loan_amount_required", "Amount of Loan Required (₹)",
               "आवश्यक ऋण राशि (₹)", "number", section="Loan Requirement",
               profile_key="loan_amount_required"),
            *identity_fields(),
            _f("pm_kisan_account_number", "PM-KISAN Beneficiary Account No.",
               "पीएम-किसान लाभार्थी खाता संख्या", section="Applicant Details",
               profile_key="bank_account_number"),
            *address_fields(),
            _f("land_holding_acres", "Area in Acres", "क्षेत्रफल (एकड़)", "number",
               section="Land Details", profile_key="land_holding_acres"),
            _f("land_ownership_type", "Owned / Leased / Share Cropper",
               "स्वामित्व / पट्टा / बटाईदार", "select", section="Land Details",
               profile_key="land_ownership_type",
               options=["Owned", "Leased", "Share Cropper"]),
            _f("village", "Village", "गाँव", section="Land Details",
               profile_key="village"),
            _f("kharif_crops", "Kharif Crops to be Grown", "खरीफ फसलें",
               section="Crop Details", profile_key="kharif_crops", required=False),
            _f("rabi_crops", "Rabi Crops to be Grown", "रबी फसलें",
               section="Crop Details", profile_key="rabi_crops", required=False),
            _f("existing_loan_outstanding", "Existing Loan Outstanding (₹)",
               "बकाया ऋण (₹)", "number", section="Declaration",
               profile_key="existing_loan_outstanding", required=False),
            _f("pmsby_consent", "Consent for PMSBY (₹20/year)",
               "पीएमएसबीवाई हेतु सहमति (₹20/वर्ष)", "select", section="Declaration",
               profile_key="pmsby_consent", options=["Yes", "No"], required=False),
            _f("pmjjby_consent", "Consent for PMJJBY (₹436/year)",
               "पीएमजेजेबीवाई हेतु सहमति (₹436/वर्ष)", "select",
               section="Declaration", profile_key="pmjjby_consent",
               options=["Yes", "No"], required=False),
        ],
    },
    {
        "schemeName": "Pradhan Mantri Awas Yojana - Gramin",
        "schemeNameHindi": "प्रधानमंत्री आवास योजना - ग्रामीण",
        "category": "housing",
        "level": "Central", "state": None,
        "description": "Financial assistance of ₹1.20–1.30 lakh for construction of a pucca house for rural households that are houseless or living in kutcha houses.",
        "descriptionHindi": "बेघर या कच्चे मकान में रहने वाले ग्रामीण परिवारों को पक्का मकान बनाने हेतु ₹1.20–1.30 लाख की सहायता।",
        "officialWebsite": "https://pmayg.nic.in/",
        "official_pdf_url": "",  # No stable public form PDF; curated fields used
        "source_verified": "",
        "is_scanned": False,
        "eligibilityCriteria": {
            "summary": "Houseless households or those living in kutcha/dilapidated houses as per SECC data. Households owning a pucca house, a motorised vehicle, or earning above ₹10,000/month are excluded.",
            "summaryHindi": "बेघर परिवार या कच्चे मकान में रहने वाले परिवार। पक्का मकान या वाहन के मालिक अपात्र हैं।",
            "rules": [
                {"field": "annual_income", "op": "<=", "value": 120000},
                {"field": "owns_pucca_house", "op": "==", "value": "No"},
            ],
            "benefit": "₹1,20,000 (plain areas) / ₹1,30,000 (hilly areas)",
        },
        "sections": [
            {"name": "Applicant Details", "nameHindi": "आवेदक का विवरण"},
            {"name": "Address", "nameHindi": "पता"},
            {"name": "Economic Details", "nameHindi": "आर्थिक विवरण"},
            {"name": "Housing Status", "nameHindi": "आवास स्थिति"},
            {"name": "Bank Details", "nameHindi": "बैंक विवरण"},
        ],
        "extractedFields": [
            *identity_fields(),
            *address_fields(),
            income_field(),
            _f("job_card_number", "MGNREGA Job Card Number", "मनरेगा जॉब कार्ड संख्या",
               section="Economic Details", profile_key="job_card_number",
               required=False),
            _f("ration_card_number", "Ration Card Number", "राशन कार्ड संख्या",
               section="Economic Details", profile_key="ration_card_number",
               required=False),
            _f("family_members", "Number of Family Members", "परिवार के सदस्यों की संख्या",
               "number", section="Economic Details", profile_key="family_members"),
            _f("owns_pucca_house", "Do you own a pucca house?",
               "क्या आपके पास पक्का मकान है?", "select", section="Housing Status",
               profile_key="owns_pucca_house", options=["No", "Yes"]),
            _f("current_house_type", "Current House Type", "वर्तमान मकान का प्रकार",
               "select", section="Housing Status", profile_key="current_house_type",
               options=["Houseless", "Kutcha", "Semi-Pucca", "Pucca"]),
            *bank_fields(),
        ],
    },
    {
        "schemeName": "Ayushman Bharat PM-JAY",
        "schemeNameHindi": "आयुष्मान भारत पीएम-जेएवाई",
        "category": "health",
        "level": "Central", "state": None,
        "description": "Health cover of ₹5 lakh per family per year for secondary and tertiary care hospitalisation, cashless at empanelled hospitals.",
        "descriptionHindi": "प्रति परिवार प्रति वर्ष ₹5 लाख का स्वास्थ्य कवर, सूचीबद्ध अस्पतालों में कैशलेस।",
        "officialWebsite": "https://pmjay.gov.in/",
        "official_pdf_url": "",
        "source_verified": "",
        "is_scanned": False,
        "eligibilityCriteria": {
            "summary": "Families identified through SECC 2011 deprivation criteria, and all households already covered under state health schemes. No cap on family size or age.",
            "summaryHindi": "एसईसीसी 2011 के अनुसार चिन्हित परिवार। परिवार के आकार या आयु पर कोई सीमा नहीं।",
            "rules": [{"field": "annual_income", "op": "<=", "value": 250000}],
            "benefit": "₹5,00,000 per family per year",
        },
        "sections": [
            {"name": "Applicant Details", "nameHindi": "आवेदक का विवरण"},
            {"name": "Address", "nameHindi": "पता"},
            {"name": "Family Details", "nameHindi": "परिवार का विवरण"},
        ],
        "extractedFields": [
            *identity_fields(),
            *address_fields(),
            _f("ration_card_number", "Ration Card Number", "राशन कार्ड संख्या",
               section="Family Details", profile_key="ration_card_number"),
            _f("family_members", "Number of Family Members", "परिवार के सदस्यों की संख्या",
               "number", section="Family Details", profile_key="family_members"),
            income_field(section="Family Details"),
            _f("secc_household_id", "SECC Household ID (if known)",
               "एसईसीसी परिवार आईडी (यदि ज्ञात हो)", section="Family Details",
               profile_key="secc_household_id", required=False),
        ],
    },
    {
        "schemeName": "National Scholarship - Post Matric",
        "schemeNameHindi": "राष्ट्रीय छात्रवृत्ति - पोस्ट मैट्रिक",
        "category": "education",
        "level": "Central", "state": None,
        "description": "Scholarship for SC/ST/OBC/Minority students studying at post-matriculation level, covering maintenance allowance and fee reimbursement.",
        "descriptionHindi": "पोस्ट-मैट्रिक स्तर पर पढ़ने वाले एससी/एसटी/ओबीसी/अल्पसंख्यक छात्रों के लिए छात्रवृत्ति।",
        "officialWebsite": "https://scholarships.gov.in/",
        "official_pdf_url": "",
        "source_verified": "",
        "is_scanned": False,
        "eligibilityCriteria": {
            "summary": "Student must have passed Class 10, be enrolled in a recognised post-matric course, and family income must not exceed ₹2.5 lakh per annum.",
            "summaryHindi": "छात्र ने कक्षा 10 उत्तीर्ण की हो, मान्यता प्राप्त पाठ्यक्रम में नामांकित हो, और पारिवारिक आय ₹2.5 लाख से अधिक न हो।",
            "rules": [
                {"field": "annual_income", "op": "<=", "value": 250000},
                {"field": "last_exam_percentage", "op": ">=", "value": 50},
            ],
            "benefit": "Maintenance allowance + full fee reimbursement",
        },
        "sections": [
            {"name": "Student Details", "nameHindi": "छात्र का विवरण"},
            {"name": "Address", "nameHindi": "पता"},
            {"name": "Academic Details", "nameHindi": "शैक्षणिक विवरण"},
            {"name": "Economic Details", "nameHindi": "आर्थिक विवरण"},
            {"name": "Bank Details", "nameHindi": "बैंक विवरण"},
        ],
        "extractedFields": [
            *identity_fields(section="Student Details"),
            *address_fields(),
            _f("institution_name", "Name of Institution", "संस्थान का नाम",
               section="Academic Details", profile_key="institution_name"),
            _f("course_name", "Course / Class of Study", "पाठ्यक्रम / कक्षा",
               section="Academic Details", profile_key="course_name"),
            _f("admission_year", "Year of Admission", "प्रवेश वर्ष", "number",
               section="Academic Details", profile_key="admission_year"),
            _f("last_exam_percentage", "Percentage in Last Examination",
               "पिछली परीक्षा में प्रतिशत", "number", section="Academic Details",
               profile_key="last_exam_percentage"),
            _f("roll_number", "Roll Number / Enrollment No.", "रोल नंबर / नामांकन संख्या",
               section="Academic Details", profile_key="roll_number", required=False),
            income_field(),
            _f("income_certificate_number", "Income Certificate Number",
               "आय प्रमाण पत्र संख्या", section="Economic Details",
               profile_key="income_certificate_number", required=False),
            *bank_fields(),
        ],
    },
    {
        "schemeName": "Sukanya Samriddhi Yojana",
        "schemeNameHindi": "सुकन्या समृद्धि योजना",
        "category": "finance",
        "level": "Central", "state": None,
        "description": "Small savings scheme for a girl child under 10 years, offering a high fixed interest rate with tax benefits under Section 80C.",
        "descriptionHindi": "10 वर्ष से कम आयु की बालिका के लिए उच्च ब्याज दर वाली लघु बचत योजना।",
        "officialWebsite": "https://www.indiapost.gov.in/Financial/Pages/Content/Post-Office-Saving-Schemes.aspx",
        "official_pdf_url": "",
        "source_verified": "",
        "is_scanned": False,
        "eligibilityCriteria": {
            "summary": "Account can be opened by a guardian for a girl child below 10 years of age. Maximum two accounts per family (three in case of twins).",
            "summaryHindi": "10 वर्ष से कम आयु की बालिका के लिए अभिभावक खाता खोल सकते हैं। प्रति परिवार अधिकतम दो खाते।",
            "rules": [{"field": "girl_child_age", "op": "<", "value": 10}],
            "benefit": "8.2% p.a. interest, tax-free maturity",
        },
        "sections": [
            {"name": "Girl Child Details", "nameHindi": "बालिका का विवरण"},
            {"name": "Guardian Details", "nameHindi": "अभिभावक का विवरण"},
            {"name": "Address", "nameHindi": "पता"},
            {"name": "Deposit Details", "nameHindi": "जमा विवरण"},
        ],
        "extractedFields": [
            _f("girl_child_name", "Name of Girl Child", "बालिका का नाम",
               section="Girl Child Details", profile_key="girl_child_name"),
            _f("girl_child_dob", "Girl Child Date of Birth", "बालिका की जन्म तिथि",
               "date", section="Girl Child Details", profile_key="girl_child_dob"),
            _f("girl_child_age", "Age of Girl Child (years)", "बालिका की आयु (वर्ष)",
               "number", section="Girl Child Details", profile_key="girl_child_age"),
            _f("birth_certificate_number", "Birth Certificate Number",
               "जन्म प्रमाण पत्र संख्या", section="Girl Child Details",
               profile_key="birth_certificate_number"),
            _f("guardian_name", "Name of Parent / Guardian", "माता-पिता / अभिभावक का नाम",
               section="Guardian Details", profile_key="name"),
            _f("guardian_aadhaar", "Guardian Aadhaar Number", "अभिभावक आधार संख्या",
               "aadhaar", section="Guardian Details", profile_key="aadhaar_number"),
            _f("relationship_with_child", "Relationship with Girl Child",
               "बालिका से संबंध", "select", section="Guardian Details",
               profile_key="relationship_with_child",
               options=["Father", "Mother", "Legal Guardian"]),
            _f("mobile_number", "Mobile Number", "मोबाइल नंबर", "phone",
               section="Guardian Details", profile_key="mobile_number"),
            *address_fields(),
            _f("initial_deposit", "Initial Deposit Amount (₹, min 250)",
               "प्रारंभिक जमा राशि (₹, न्यूनतम 250)", "number",
               section="Deposit Details", profile_key="initial_deposit"),
        ],
    },
    {
        "schemeName": "Indira Gandhi National Old Age Pension",
        "schemeNameHindi": "इंदिरा गांधी राष्ट्रीय वृद्धावस्था पेंशन",
        "category": "general",
        "level": "Central", "state": None,
        "description": "Monthly pension for BPL citizens aged 60 years and above under the National Social Assistance Programme.",
        "descriptionHindi": "राष्ट्रीय सामाजिक सहायता कार्यक्रम के तहत 60 वर्ष से अधिक आयु के बीपीएल नागरिकों के लिए मासिक पेंशन।",
        "officialWebsite": "https://nsap.nic.in/",
        "official_pdf_url": "",
        "source_verified": "",
        "is_scanned": False,
        "eligibilityCriteria": {
            "summary": "Applicant must be 60 years or older and belong to a Below Poverty Line (BPL) household.",
            "summaryHindi": "आवेदक की आयु 60 वर्ष या अधिक हो और वह बीपीएल परिवार से हो।",
            "rules": [
                {"field": "age", "op": ">=", "value": 60},
                {"field": "is_bpl", "op": "==", "value": "Yes"},
            ],
            "benefit": "₹200–₹500 per month (age-dependent, plus state top-up)",
        },
        "sections": [
            {"name": "Applicant Details", "nameHindi": "आवेदक का विवरण"},
            {"name": "Address", "nameHindi": "पता"},
            {"name": "Economic Details", "nameHindi": "आर्थिक विवरण"},
            {"name": "Bank Details", "nameHindi": "बैंक विवरण"},
        ],
        "extractedFields": [
            *identity_fields(),
            _f("age", "Age (years)", "आयु (वर्ष)", "number",
               section="Applicant Details", profile_key="age"),
            *address_fields(),
            _f("is_bpl", "Do you hold a BPL card?", "क्या आपके पास बीपीएल कार्ड है?",
               "select", section="Economic Details", profile_key="is_bpl",
               options=["Yes", "No"]),
            _f("bpl_card_number", "BPL / Ration Card Number", "बीपीएल / राशन कार्ड संख्या",
               section="Economic Details", profile_key="ration_card_number",
               required=False),
            income_field(required=False),
            *bank_fields(),
        ],
    },
    {
        "schemeName": "Kendriya Vidyalaya Admission",
        "schemeNameHindi": "केंद्रीय विद्यालय प्रवेश",
        "category": "education",
        "level": "Central", "state": None,
        "description": "Admission to Kendriya Vidyalaya schools. Seats are allotted by priority category and, where applications exceed seats, by lottery.",
        "descriptionHindi": "केंद्रीय विद्यालय में प्रवेश। सीटें प्राथमिकता श्रेणी और लॉटरी द्वारा आवंटित की जाती हैं।",
        "officialWebsite": "https://kvsangathan.nic.in/",
        "official_pdf_url": "https://cdnbbsr.s3waas.gov.in/s3kv0299485a92a762d96a1b35ca538738/uploads/2025/07/2025072174.pdf",
        "source_verified": "2026-09-01",
        "is_scanned": False,
        "eligibilityCriteria": {
            "summary": "Child must meet the minimum age for the class sought (6 years for Class 1). Admission priority follows the KVS category order, with children of transferable central government employees ranked highest.",
            "summaryHindi": "बच्चे की आयु कक्षा के अनुसार होनी चाहिए (कक्षा 1 हेतु 6 वर्ष)। केंद्र सरकार के स्थानांतरणीय कर्मचारियों के बच्चों को प्राथमिकता।",
            "rules": [],
            "benefit": "Admission to a Kendriya Vidyalaya with subsidised fees",
        },
        "sections": [
            {"name": "Student Details", "nameHindi": "छात्र का विवरण"},
            {"name": "Address", "nameHindi": "पता"},
            {"name": "Academic Details", "nameHindi": "शैक्षणिक विवरण"},
        ],
        "extractedFields": [
            *identity_fields(section="Student Details"),
            *address_fields(),
            _f("class_sought", "Class Sought for Admission", "प्रवेश हेतु कक्षा",
               "select", section="Academic Details", profile_key="class_sought",
               options=["Balvatika", "Class 1", "Class 2", "Class 3", "Class 4",
                        "Class 5", "Class 6", "Class 7", "Class 8", "Class 9",
                        "Class 10", "Class 11", "Class 12"]),
            _f("institution_name", "Previous School Attended", "पिछला विद्यालय",
               section="Academic Details", profile_key="institution_name",
               required=False),
            _f("last_exam_percentage", "Percentage in Last Examination",
               "पिछली परीक्षा में प्रतिशत", "number", section="Academic Details",
               profile_key="last_exam_percentage", required=False),
        ],
    },
    {
        "schemeName": "Saraswati Vidya Yojana Scholarship",
        "schemeNameHindi": "सरस्वती विद्या योजना छात्रवृत्ति",
        "category": "education",
        "level": "State", "state": "Goa",
        "description": "State scholarship for students in higher education, paid directly to the student's bank account on verification of enrolment and academic record.",
        "descriptionHindi": "उच्च शिक्षा के छात्रों हेतु राज्य छात्रवृत्ति, सत्यापन के बाद सीधे बैंक खाते में भुगतान।",
        "officialWebsite": "https://www.goa.gov.in/",
        "official_pdf_url": "https://cdnbbsr.s3waas.gov.in/s371e09b16e21f7b6919bbfc43f6a5b2f0/uploads/2023/10/202310091025593245.pdf",
        "source_verified": "2026-09-01",
        "is_scanned": False,
        "eligibilityCriteria": {
            "summary": "Student must be enrolled in a recognised institution and provide continuous schooling certificates for the preceding years, along with a domicile certificate.",
            "summaryHindi": "छात्र मान्यता प्राप्त संस्थान में नामांकित हो और पिछले वर्षों के निरंतर अध्ययन प्रमाण पत्र प्रस्तुत करे।",
            "rules": [
                {"field": "state", "op": "==", "value": "Goa"},
            ],
            "benefit": "Scholarship credited to the student's bank account",
        },
        "sections": [
            {"name": "Student Details", "nameHindi": "छात्र का विवरण"},
            {"name": "Address", "nameHindi": "पता"},
            {"name": "Academic Details", "nameHindi": "शैक्षणिक विवरण"},
            {"name": "Bank Details", "nameHindi": "बैंक विवरण"},
        ],
        "extractedFields": [
            *identity_fields(section="Student Details"),
            _f("email", "Email Address", "ईमेल पता", "email",
               section="Student Details", profile_key="email", required=False),
            _f("marital_status", "Marital Status", "वैवाहिक स्थिति", "select",
               section="Student Details", profile_key="marital_status",
               options=["Single", "Married", "Widowed", "Divorced"], required=False),
            *address_fields(),
            _f("tehsil", "Tehsil / Taluka", "तहसील / तालुका", section="Address",
               profile_key="tehsil", required=False),
            _f("institution_name", "Name of Institution", "संस्थान का नाम",
               section="Academic Details", profile_key="institution_name"),
            _f("course_name", "Course of Study", "अध्ययन पाठ्यक्रम",
               section="Academic Details", profile_key="course_name"),
            _f("roll_number", "Roll / Enrollment Number", "रोल / नामांकन संख्या",
               section="Academic Details", profile_key="roll_number", required=False),
            _f("last_exam_percentage", "Percentage in Last Examination",
               "पिछली परीक्षा में प्रतिशत", "number", section="Academic Details",
               profile_key="last_exam_percentage"),
            *bank_fields(),
        ],
    },
    {
        "schemeName": "Widow and Destitute Women Pension (Haryana)",
        "schemeNameHindi": "विधवा एवं निराश्रित महिला पेंशन (हरियाणा)",
        "category": "general",
        "level": "State", "state": "Haryana",
        "description": "Monthly pension for widowed or destitute women resident in Haryana, applied for through the Antyodaya-SARAL portal or a CSC centre.",
        "descriptionHindi": "हरियाणा में निवासरत विधवा या निराश्रित महिलाओं के लिए मासिक पेंशन।",
        "officialWebsite": "https://saralharyana.gov.in/",
        "official_pdf_url": "https://cdnbbsr.s3waas.gov.in/s392bbd31f8e0e43a7da8a6295b251725f/uploads/2021/11/20250423524146662.pdf",
        "source_verified": "2026-09-01",
        "is_scanned": False,
        "eligibilityCriteria": {
            "summary": "Woman aged 18 years or above, widowed or destitute, and a domicile of Haryana residing in the state for at least one year at the time of application. A husband's death certificate is required in the case of a widow.",
            "summaryHindi": "18 वर्ष या अधिक आयु की विधवा या निराश्रित महिला, जो कम से कम एक वर्ष से हरियाणा में निवासरत हो।",
            "rules": [
                {"field": "state", "op": "==", "value": "Haryana"},
                {"field": "age", "op": ">=", "value": 18},
                {"field": "gender", "op": "==", "value": "Female"},
            ],
            "benefit": "Monthly pension credited to the beneficiary's bank account",
        },
        "sections": [
            {"name": "Applicant Details", "nameHindi": "आवेदक का विवरण"},
            {"name": "Address", "nameHindi": "पता"},
            {"name": "Eligibility Documents", "nameHindi": "पात्रता दस्तावेज़"},
            {"name": "Bank Details", "nameHindi": "बैंक विवरण"},
        ],
        "extractedFields": [
            *identity_fields(),
            _f("age", "Age (years)", "आयु (वर्ष)", "number",
               section="Applicant Details", profile_key="age"),
            *address_fields(),
            _f("marital_status", "Marital Status", "वैवाहिक स्थिति", "select",
               section="Eligibility Documents", profile_key="marital_status",
               options=["Widowed", "Destitute", "Single", "Married"]),
            _f("husband_death_certificate_number",
               "Husband's Death Certificate Number (for widows)",
               "पति का मृत्यु प्रमाण पत्र संख्या (विधवा हेतु)",
               section="Eligibility Documents",
               profile_key="husband_death_certificate_number", required=False),
            _f("ration_card_number", "Ration Card Number", "राशन कार्ड संख्या",
               section="Eligibility Documents", profile_key="ration_card_number",
               required=False),
            _f("domicile_certificate_number", "Haryana Domicile Certificate Number",
               "हरियाणा अधिवास प्रमाण पत्र संख्या", section="Eligibility Documents",
               profile_key="domicile_certificate_number", required=False),
            income_field(section="Eligibility Documents", required=False),
            *bank_fields(),
        ],
    },
    {
        "schemeName": "Sports Achievement Scholarship (Haryana)",
        "schemeNameHindi": "खेल उपलब्धि छात्रवृत्ति (हरियाणा)",
        "category": "education",
        "level": "State", "state": "Haryana",
        "description": "Scholarship for students who won a position or participated in recognised sporting events, paid annually on verification by the head of the institution.",
        "descriptionHindi": "मान्यता प्राप्त खेल प्रतियोगिताओं में स्थान प्राप्त करने वाले छात्रों के लिए वार्षिक छात्रवृत्ति।",
        "officialWebsite": "https://haryanasports.gov.in/",
        "official_pdf_url": "https://cdnbbsr.s3waas.gov.in/s3e069ea4c9c233d36ff9c7f329bc08ff1/uploads/2024/06/202406272030716079.pdf",
        "source_verified": "2026-09-01",
        "is_scanned": False,
        "eligibilityCriteria": {
            "summary": "Student must hold a Haryana domicile certificate and have obtained a first, second, third or participation position in a recognised sporting event during the qualifying period. The claim must be attested by the head of the institution.",
            "summaryHindi": "छात्र के पास हरियाणा अधिवास प्रमाण पत्र हो और उसने मान्यता प्राप्त खेल प्रतियोगिता में स्थान प्राप्त किया हो।",
            "rules": [
                {"field": "state", "op": "==", "value": "Haryana"},
            ],
            "benefit": "Annual scholarship credited to the student's bank account",
        },
        "sections": [
            {"name": "Applicant Details", "nameHindi": "आवेदक का विवरण"},
            {"name": "Address", "nameHindi": "पता"},
            {"name": "Academic Details", "nameHindi": "शैक्षणिक विवरण"},
            {"name": "Sports Achievement", "nameHindi": "खेल उपलब्धि"},
            {"name": "Bank Details", "nameHindi": "बैंक विवरण"},
        ],
        "extractedFields": [
            *identity_fields(),
            _f("mother_name", "Mother's Name", "माता का नाम",
               section="Applicant Details", profile_key="mother_name",
               required=False),
            _f("email", "Email Address", "ईमेल पता", "email",
               section="Applicant Details", profile_key="email", required=False),
            *address_fields(),
            _f("institution_name", "Name of Institution", "संस्थान का नाम",
               section="Sports Achievement", profile_key="institution_name"),
            _f("sport_name", "Game / Sport", "खेल", section="Sports Achievement",
               profile_key="sport_name"),
            _f("achievement_position", "Position Obtained", "प्राप्त स्थान", "select",
               section="Sports Achievement", profile_key="achievement_position",
               options=["First", "Second", "Third", "Participation"]),
            _f("event_name", "Name of Event", "प्रतियोगिता का नाम",
               section="Sports Achievement", profile_key="event_name"),
            _f("event_date", "Date of Event", "प्रतियोगिता की तिथि", "date",
               section="Sports Achievement", profile_key="event_date"),
            _f("domicile_certificate_number", "Haryana Domicile Certificate Number",
               "हरियाणा अधिवास प्रमाण पत्र संख्या", section="Sports Achievement",
               profile_key="domicile_certificate_number", required=False),
            # The printed form asks for all of these and the catalog did not
            # model any of them, so they came out blank on every application
            # and nothing reported the gap. Found by auditing the form's own
            # labels against the catalog — see scripts/audit_forms.py.
            _f("father_occupation", "Father's Occupation", "पिता का व्यवसाय",
               section="Applicant Details", profile_key="father_occupation",
               required=False),
            _f("mother_occupation", "Mother's Occupation", "माता का व्यवसाय",
               section="Applicant Details", profile_key="mother_occupation",
               required=False),
            _f("state_family_id", "Parivar Pehchan Patra Number",
               "परिवार पहचान पत्र संख्या", section="Applicant Details",
               profile_key="state_family_id", required=False),
            _f("current_class", "Class", "कक्षा", section="Academic Details",
               profile_key="current_class", required=False),
            _f("academic_session", "Session", "सत्र", section="Academic Details",
               profile_key="academic_session", required=False),
            _f("admission_number", "Admission Number", "प्रवेश संख्या",
               section="Academic Details", profile_key="admission_number",
               required=False),
            *bank_fields(),
        ],
    },
]


# ── Lookup helpers ───────────────────────────────────────────────────────

def _all_sources() -> list[dict]:
    """Concatenate the three catalog files.

    Imported lazily inside the function because central_schemes and
    state_schemes import the field builders from this module — a top-level
    import either way would be circular.
    """
    from data.central_schemes import CENTRAL_SCHEMES
    from data.state_schemes import STATE_SCHEMES
    return [*GOV_FORM_CATALOG, *CENTRAL_SCHEMES, *STATE_SCHEMES]


def get_catalog(level: str | None = None, state: str | None = None) -> list[dict]:
    """Return the catalog with computed totalFields.

    `level` filters to "Central" or "State"; `state` filters to schemes a
    resident of that State can claim — which means Central schemes *plus* that
    State's own, because a citizen of Bihar is entitled to both. Filtering a
    State's residents down to only State schemes would hide most of the money
    available to them.
    """
    out = []
    for entry in _all_sources():
        item = dict(entry)
        item.setdefault("level", "Central")
        item.setdefault("state", None)
        item["totalFields"] = len(item.get("extractedFields", []))
        if level and item["level"] != level:
            continue
        if state and item["level"] == "State" and item["state"] != state:
            continue
        out.append(item)
    return out


def catalog_states() -> list[str]:
    """States that have at least one scheme in the catalog, sorted."""
    return sorted({e["state"] for e in get_catalog() if e.get("state")})


def get_by_name(scheme_name: str) -> dict | None:
    """Case-insensitive lookup of a catalog entry by scheme name."""
    target = (scheme_name or "").strip().lower()
    for entry in get_catalog():
        if entry["schemeName"].lower() == target:
            return entry
    # Substring fallback — handles "PM-KISAN" matching "PM-KISAN Samman Nidhi"
    for entry in get_catalog():
        if target and (target in entry["schemeName"].lower()
                       or entry["schemeName"].lower() in target):
            return entry
    return None


def all_profile_keys() -> dict[str, dict]:
    """Map every distinct profileKey to a representative field definition.

    Used by the profiler to ask each question once across all schemes.
    """
    keys: dict[str, dict] = {}
    for entry in get_catalog():
        for field in entry.get("extractedFields", []):
            key = field.get("profileKey") or field.get("fieldName")
            if key and key not in keys:
                keys[key] = field
    return keys
