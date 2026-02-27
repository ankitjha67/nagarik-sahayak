"""Seed the database with 4 real government schemes and their official form fields."""
import asyncio
from prisma import Prisma


# ──────────────────────────────────────────────────────────────
# SCHEME DATA (real official sources)
# ──────────────────────────────────────────────────────────────

SCHEMES = [
    {
        "name": "Pradhan Mantri Awas Yojana (PMAY-U)",
        "nameHindi": "प्रधानमंत्री आवास योजना (शहरी)",
        "category": "housing",
        "eligibilityCriteriaText": (
            "EWS: Annual household income up to Rs 3 lakh. "
            "LIG: Rs 3-6 lakh. MIG-I: Rs 6-12 lakh. MIG-II: Rs 12-18 lakh. "
            "Must not own a pucca house anywhere in India. "
            "Women ownership/co-ownership mandatory for EWS/LIG."
        ),
        "description": "Central government housing scheme providing financial assistance for construction or purchase of houses for urban poor and middle class.",
        "descriptionHindi": "शहरी गरीब और मध्यम वर्ग के लिए घर निर्माण या खरीद हेतु केंद्र सरकार की आवास योजना।",
        "officialWebsite": "https://pmaymis.gov.in",
        "pdfUrl": "https://pmay-urban.gov.in/uploads/guidelines/Operational-Guidelines-of-PMAY-U-2.pdf",
    },
    {
        "name": "Vidyasiri Scholarship",
        "nameHindi": "विद्यासिरी छात्रवृत्ति",
        "category": "education",
        "eligibilityCriteriaText": (
            "Karnataka domicile. Category: SC/ST/OBC/BC/Minority/PwD. "
            "Annual family income below Rs 2 lakh (SC/ST) or Rs 1.5 lakh (OBC/BC). "
            "Must have passed previous qualifying exam (10th/12th/Degree). "
            "Currently enrolled in recognized institution in Karnataka."
        ),
        "description": "Karnataka state scholarship for students from backward classes pursuing pre-matric and post-matric education.",
        "descriptionHindi": "कर्नाटक राज्य की पिछड़ा वर्ग के छात्रों के लिए प्री-मैट्रिक और पोस्ट-मैट्रिक शिक्षा छात्रवृत्ति।",
        "officialWebsite": "https://bcw.karnataka.gov.in/64/vidyasiri/en",
        "pdfUrl": "https://bcw.karnataka.gov.in/storage/pdf-files/vidyasiri_guidelines.pdf",
    },
    {
        "name": "Startup India Seed Fund Scheme",
        "nameHindi": "स्टार्टअप इंडिया सीड फंड योजना",
        "category": "startup",
        "eligibilityCriteriaText": (
            "DPIIT-recognized startup. Incorporated not more than 2 years ago. "
            "Must have a business idea for a product/service with market fit. "
            "Startup should not have received more than Rs 10 lakh monetary support "
            "under any other central/state government scheme. Indian-registered entity."
        ),
        "description": "Central government scheme providing seed funding up to Rs 50 lakh for startups through approved incubators for proof of concept, prototype development, and market entry.",
        "descriptionHindi": "स्टार्टअप्स को अनुमोदित इन्क्यूबेटरों के माध्यम से 50 लाख रुपये तक की सीड फंडिंग प्रदान करने वाली केंद्र सरकार की योजना।",
        "officialWebsite": "https://seedfund.startupindia.gov.in",
        "pdfUrl": "https://seedfundapi.startupindia.gov.in:3535/filestorage/samplefiles/Guidelines_for_Startup_India_Seed_Fund_Scheme.pdf",
    },
    {
        "name": "PM-KISAN Samman Nidhi",
        "nameHindi": "पीएम-किसान सम्मान निधि",
        "category": "agriculture",
        "eligibilityCriteriaText": (
            "Small and marginal farmer families with cultivable landholding. "
            "Family defined as husband, wife and minor children. "
            "Excludes: institutional land holders, farmer families with govt employees "
            "(except Class 4), income tax payers, pensioners above Rs 10,000/month, "
            "professionals (doctors, engineers, lawyers, CAs), and constitutional post holders."
        ),
        "description": "Central government scheme providing Rs 6,000 per year in three installments to all eligible farmer families across India.",
        "descriptionHindi": "सभी पात्र किसान परिवारों को प्रति वर्ष 6,000 रुपये तीन किस्तों में प्रदान करने वाली केंद्र सरकार की योजना।",
        "officialWebsite": "https://pmkisan.gov.in",
        "pdfUrl": "https://pmkisan.gov.in/documents/RevisedPM-KISANOperationalGuidelines(English).pdf",
    },
]


# ──────────────────────────────────────────────────────────────
# FORM TEMPLATES — Real fields from official application forms
# ──────────────────────────────────────────────────────────────

FORM_TEMPLATES = [
    {
        "schemeName": "Pradhan Mantri Awas Yojana (PMAY-U)",
        "schemeNameHindi": "प्रधानमंत्री आवास योजना (शहरी)",
        "officialPdfUrl": "https://pmay-urban.gov.in/uploads/guidelines/Operational-Guidelines-of-PMAY-U-2.pdf",
        "officialWebsite": "https://pmaymis.gov.in",
        "description": "Beneficiary-led construction/enhancement housing application",
        "descriptionHindi": "लाभार्थी के नेतृत्व में निर्माण/उन्नयन आवास आवेदन",
        "category": "housing",
        "totalFields": 22,
        "sections": [
            {"name": "Personal Details", "nameHindi": "व्यक्तिगत विवरण"},
            {"name": "Address Details", "nameHindi": "पता विवरण"},
            {"name": "Family Details", "nameHindi": "परिवार विवरण"},
            {"name": "Bank Details", "nameHindi": "बैंक विवरण"},
            {"name": "Housing Details", "nameHindi": "आवास विवरण"},
        ],
        "eligibilityCriteria": {
            "income_limit_ews": 300000,
            "income_limit_lig": 600000,
            "no_pucca_house": True,
            "women_ownership_mandatory_ews_lig": True,
        },
        "extractedFields": [
            {"fieldName": "applicant_name", "labelHindi": "आवेदक का नाम", "labelEnglish": "Applicant Name", "type": "text", "required": True, "section": "Personal Details", "profileKey": "name"},
            {"fieldName": "father_husband_name", "labelHindi": "पिता/पति का नाम", "labelEnglish": "Father's/Husband's Name", "type": "text", "required": True, "section": "Personal Details", "profileKey": "father_husband_name"},
            {"fieldName": "aadhaar_number", "labelHindi": "आधार संख्या", "labelEnglish": "Aadhaar Number", "type": "aadhaar", "required": True, "section": "Personal Details", "profileKey": "aadhaar_number"},
            {"fieldName": "date_of_birth", "labelHindi": "जन्म तिथि", "labelEnglish": "Date of Birth", "type": "date", "required": True, "section": "Personal Details", "profileKey": "date_of_birth"},
            {"fieldName": "gender", "labelHindi": "लिंग", "labelEnglish": "Gender", "type": "select", "required": True, "section": "Personal Details", "options": ["Male", "Female", "Other"], "profileKey": "gender"},
            {"fieldName": "caste_category", "labelHindi": "जाति वर्ग", "labelEnglish": "Caste Category", "type": "select", "required": True, "section": "Personal Details", "options": ["SC", "ST", "OBC", "General", "Minority"], "profileKey": "caste_category"},
            {"fieldName": "mobile_number", "labelHindi": "मोबाइल नंबर", "labelEnglish": "Mobile Number", "type": "phone", "required": True, "section": "Personal Details", "profileKey": "mobile_number"},
            {"fieldName": "annual_family_income", "labelHindi": "वार्षिक पारिवारिक आय (रुपये में)", "labelEnglish": "Annual Family Income (in Rs)", "type": "number", "required": True, "section": "Personal Details", "profileKey": "annual_income"},
            {"fieldName": "house_number", "labelHindi": "मकान संख्या / गली", "labelEnglish": "House No / Street", "type": "text", "required": True, "section": "Address Details", "profileKey": "house_number"},
            {"fieldName": "city_town", "labelHindi": "शहर / नगर", "labelEnglish": "City / Town", "type": "text", "required": True, "section": "Address Details", "profileKey": "city"},
            {"fieldName": "district", "labelHindi": "जिला", "labelEnglish": "District", "type": "text", "required": True, "section": "Address Details", "profileKey": "district"},
            {"fieldName": "state", "labelHindi": "राज्य", "labelEnglish": "State", "type": "text", "required": True, "section": "Address Details", "profileKey": "state"},
            {"fieldName": "pincode", "labelHindi": "पिनकोड", "labelEnglish": "Pincode", "type": "text", "required": True, "section": "Address Details", "profileKey": "pincode"},
            {"fieldName": "family_members_count", "labelHindi": "परिवार के सदस्यों की संख्या", "labelEnglish": "Number of Family Members", "type": "number", "required": True, "section": "Family Details", "profileKey": "family_members_count"},
            {"fieldName": "owns_pucca_house", "labelHindi": "क्या भारत में कहीं पक्का मकान है?", "labelEnglish": "Do you own a pucca house anywhere in India?", "type": "select", "required": True, "section": "Housing Details", "options": ["No", "Yes"], "profileKey": "owns_pucca_house"},
            {"fieldName": "employment_type", "labelHindi": "रोज़गार का प्रकार", "labelEnglish": "Employment Type", "type": "select", "required": True, "section": "Personal Details", "options": ["Self-employed", "Salaried", "Daily Wage", "Unemployed"], "profileKey": "employment_type"},
            {"fieldName": "availed_housing_scheme", "labelHindi": "क्या पहले कोई केंद्रीय आवास योजना का लाभ लिया?", "labelEnglish": "Have you availed any central housing scheme before?", "type": "select", "required": True, "section": "Housing Details", "options": ["No", "Yes"], "profileKey": "availed_housing_scheme"},
            {"fieldName": "bank_account_number", "labelHindi": "बैंक खाता संख्या", "labelEnglish": "Bank Account Number", "type": "text", "required": True, "section": "Bank Details", "profileKey": "bank_account_number"},
            {"fieldName": "bank_ifsc_code", "labelHindi": "IFSC कोड", "labelEnglish": "IFSC Code", "type": "text", "required": True, "section": "Bank Details", "profileKey": "bank_ifsc_code"},
            {"fieldName": "bank_name", "labelHindi": "बैंक का नाम", "labelEnglish": "Bank Name", "type": "text", "required": True, "section": "Bank Details", "profileKey": "bank_name"},
            {"fieldName": "bank_branch", "labelHindi": "शाखा का नाम", "labelEnglish": "Branch Name", "type": "text", "required": False, "section": "Bank Details", "profileKey": "bank_branch"},
            {"fieldName": "income_category", "labelHindi": "आय वर्ग", "labelEnglish": "Income Category (EWS/LIG/MIG-I/MIG-II)", "type": "select", "required": True, "section": "Housing Details", "options": ["EWS (up to 3L)", "LIG (3-6L)", "MIG-I (6-12L)", "MIG-II (12-18L)"], "profileKey": "income_category"},
        ],
    },
    {
        "schemeName": "Vidyasiri Scholarship",
        "schemeNameHindi": "विद्यासिरी छात्रवृत्ति",
        "officialPdfUrl": "https://bcw.karnataka.gov.in/storage/pdf-files/vidyasiri_guidelines.pdf",
        "officialWebsite": "https://bcw.karnataka.gov.in/64/vidyasiri/en",
        "description": "Pre-matric and Post-matric scholarship for backward classes in Karnataka",
        "descriptionHindi": "कर्नाटक में पिछड़ा वर्ग के लिए प्री-मैट्रिक और पोस्ट-मैट्रिक छात्रवृत्ति",
        "category": "education",
        "totalFields": 20,
        "sections": [
            {"name": "Student Details", "nameHindi": "छात्र विवरण"},
            {"name": "Academic Details", "nameHindi": "शैक्षिक विवरण"},
            {"name": "Family & Income", "nameHindi": "परिवार और आय"},
            {"name": "Bank Details", "nameHindi": "बैंक विवरण"},
            {"name": "Documents", "nameHindi": "दस्तावेज़"},
        ],
        "eligibilityCriteria": {
            "domicile": "Karnataka",
            "category": ["SC", "ST", "OBC", "BC", "Minority", "PwD"],
            "income_limit_sc_st": 200000,
            "income_limit_obc_bc": 150000,
        },
        "extractedFields": [
            {"fieldName": "student_name", "labelHindi": "छात्र का नाम", "labelEnglish": "Student Name", "type": "text", "required": True, "section": "Student Details", "profileKey": "name"},
            {"fieldName": "father_name", "labelHindi": "पिता का नाम", "labelEnglish": "Father's Name", "type": "text", "required": True, "section": "Student Details", "profileKey": "father_name"},
            {"fieldName": "mother_name", "labelHindi": "माता का नाम", "labelEnglish": "Mother's Name", "type": "text", "required": True, "section": "Student Details", "profileKey": "mother_name"},
            {"fieldName": "aadhaar_number", "labelHindi": "आधार संख्या", "labelEnglish": "Aadhaar Number", "type": "aadhaar", "required": True, "section": "Student Details", "profileKey": "aadhaar_number"},
            {"fieldName": "date_of_birth", "labelHindi": "जन्म तिथि", "labelEnglish": "Date of Birth", "type": "date", "required": True, "section": "Student Details", "profileKey": "date_of_birth"},
            {"fieldName": "gender", "labelHindi": "लिंग", "labelEnglish": "Gender", "type": "select", "required": True, "section": "Student Details", "options": ["Male", "Female", "Other"], "profileKey": "gender"},
            {"fieldName": "caste_category", "labelHindi": "जाति वर्ग", "labelEnglish": "Category (SC/ST/OBC/BC/Minority/PwD)", "type": "select", "required": True, "section": "Student Details", "options": ["SC", "ST", "OBC", "BC", "Minority", "PwD"], "profileKey": "caste_category"},
            {"fieldName": "mobile_number", "labelHindi": "मोबाइल नंबर", "labelEnglish": "Mobile Number", "type": "phone", "required": True, "section": "Student Details", "profileKey": "mobile_number"},
            {"fieldName": "email", "labelHindi": "ईमेल", "labelEnglish": "Email Address", "type": "email", "required": False, "section": "Student Details", "profileKey": "email"},
            {"fieldName": "permanent_address", "labelHindi": "स्थायी पता", "labelEnglish": "Permanent Address", "type": "text", "required": True, "section": "Student Details", "profileKey": "permanent_address"},
            {"fieldName": "state", "labelHindi": "राज्य", "labelEnglish": "State", "type": "text", "required": True, "section": "Student Details", "profileKey": "state"},
            {"fieldName": "district", "labelHindi": "जिला", "labelEnglish": "District", "type": "text", "required": True, "section": "Student Details", "profileKey": "district"},
            {"fieldName": "course_name", "labelHindi": "पाठ्यक्रम का नाम", "labelEnglish": "Course Name", "type": "text", "required": True, "section": "Academic Details", "profileKey": "course_name"},
            {"fieldName": "year_of_study", "labelHindi": "अध्ययन वर्ष", "labelEnglish": "Year of Study", "type": "text", "required": True, "section": "Academic Details", "profileKey": "year_of_study"},
            {"fieldName": "college_name", "labelHindi": "कॉलेज/संस्था का नाम", "labelEnglish": "College/Institution Name", "type": "text", "required": True, "section": "Academic Details", "profileKey": "college_name"},
            {"fieldName": "previous_exam_percentage", "labelHindi": "पिछली परीक्षा में प्रतिशत", "labelEnglish": "Previous Exam Percentage", "type": "number", "required": True, "section": "Academic Details", "profileKey": "previous_exam_percentage"},
            {"fieldName": "annual_family_income", "labelHindi": "वार्षिक पारिवारिक आय (रुपये में)", "labelEnglish": "Annual Family Income (in Rs)", "type": "number", "required": True, "section": "Family & Income", "profileKey": "annual_income"},
            {"fieldName": "receiving_other_scholarship", "labelHindi": "क्या कोई अन्य छात्रवृत्ति प्राप्त कर रहे हैं?", "labelEnglish": "Receiving any other scholarship?", "type": "select", "required": True, "section": "Family & Income", "options": ["No", "Yes"], "profileKey": "receiving_other_scholarship"},
            {"fieldName": "bank_account_number", "labelHindi": "बैंक खाता संख्या (छात्र के नाम पर)", "labelEnglish": "Bank Account Number (in student's name)", "type": "text", "required": True, "section": "Bank Details", "profileKey": "bank_account_number"},
            {"fieldName": "bank_ifsc_code", "labelHindi": "IFSC कोड", "labelEnglish": "IFSC Code", "type": "text", "required": True, "section": "Bank Details", "profileKey": "bank_ifsc_code"},
        ],
    },
    {
        "schemeName": "Startup India Seed Fund Scheme",
        "schemeNameHindi": "स्टार्टअप इंडिया सीड फंड योजना",
        "officialPdfUrl": "https://seedfundapi.startupindia.gov.in:3535/filestorage/samplefiles/Guidelines_for_Startup_India_Seed_Fund_Scheme.pdf",
        "officialWebsite": "https://seedfund.startupindia.gov.in",
        "description": "Seed funding up to Rs 50 lakh for DPIIT-recognized startups through incubators",
        "descriptionHindi": "DPIIT-मान्यता प्राप्त स्टार्टअप्स के लिए इन्क्यूबेटरों के माध्यम से 50 लाख रुपये तक की सीड फंडिंग",
        "category": "startup",
        "totalFields": 21,
        "sections": [
            {"name": "Entity Details", "nameHindi": "संस्था विवरण"},
            {"name": "Founder Details", "nameHindi": "संस्थापक विवरण"},
            {"name": "Business Details", "nameHindi": "व्यवसाय विवरण"},
            {"name": "Funding Details", "nameHindi": "फंडिंग विवरण"},
            {"name": "Bank Details", "nameHindi": "बैंक विवरण"},
        ],
        "eligibilityCriteria": {
            "dpiit_recognized": True,
            "max_age_years": 2,
            "max_prior_funding": 1000000,
            "indian_registered": True,
        },
        "extractedFields": [
            {"fieldName": "startup_name", "labelHindi": "स्टार्टअप/कंपनी का नाम", "labelEnglish": "Startup/Entity Name", "type": "text", "required": True, "section": "Entity Details", "profileKey": "startup_name"},
            {"fieldName": "dpiit_recognition_number", "labelHindi": "DPIIT मान्यता संख्या", "labelEnglish": "DPIIT Recognition Number", "type": "text", "required": True, "section": "Entity Details", "profileKey": "dpiit_recognition_number"},
            {"fieldName": "cin_number", "labelHindi": "CIN संख्या", "labelEnglish": "Company Identification Number (CIN)", "type": "text", "required": True, "section": "Entity Details", "profileKey": "cin_number"},
            {"fieldName": "date_of_incorporation", "labelHindi": "निगमन की तिथि", "labelEnglish": "Date of Incorporation", "type": "date", "required": True, "section": "Entity Details", "profileKey": "date_of_incorporation"},
            {"fieldName": "registered_address", "labelHindi": "पंजीकृत पता", "labelEnglish": "Registered Address", "type": "text", "required": True, "section": "Entity Details", "profileKey": "registered_address"},
            {"fieldName": "entity_pan", "labelHindi": "संस्था का PAN", "labelEnglish": "Entity PAN", "type": "text", "required": True, "section": "Entity Details", "profileKey": "entity_pan"},
            {"fieldName": "founder_name", "labelHindi": "संस्थापक/प्रमोटर का नाम", "labelEnglish": "Founder/Promoter Name", "type": "text", "required": True, "section": "Founder Details", "profileKey": "name"},
            {"fieldName": "founder_aadhaar", "labelHindi": "संस्थापक का आधार नंबर", "labelEnglish": "Founder's Aadhaar Number", "type": "aadhaar", "required": True, "section": "Founder Details", "profileKey": "aadhaar_number"},
            {"fieldName": "founder_mobile", "labelHindi": "संस्थापक का मोबाइल नंबर", "labelEnglish": "Founder's Mobile Number", "type": "phone", "required": True, "section": "Founder Details", "profileKey": "mobile_number"},
            {"fieldName": "founder_email", "labelHindi": "संस्थापक का ईमेल", "labelEnglish": "Founder's Email", "type": "email", "required": True, "section": "Founder Details", "profileKey": "email"},
            {"fieldName": "sector", "labelHindi": "क्षेत्र/उद्योग", "labelEnglish": "Sector/Industry", "type": "text", "required": True, "section": "Business Details", "profileKey": "sector"},
            {"fieldName": "product_description", "labelHindi": "उत्पाद/सेवा का विवरण", "labelEnglish": "Brief Description of Product/Service", "type": "textarea", "required": True, "section": "Business Details", "profileKey": "product_description"},
            {"fieldName": "current_stage", "labelHindi": "वर्तमान स्थिति", "labelEnglish": "Current Stage", "type": "select", "required": True, "section": "Business Details", "options": ["Ideation", "Prototype", "Early Revenue", "Growth"], "profileKey": "current_stage"},
            {"fieldName": "number_of_employees", "labelHindi": "कर्मचारियों की संख्या", "labelEnglish": "Number of Employees", "type": "number", "required": True, "section": "Business Details", "profileKey": "number_of_employees"},
            {"fieldName": "website_url", "labelHindi": "वेबसाइट URL", "labelEnglish": "Website URL", "type": "text", "required": False, "section": "Business Details", "profileKey": "website_url"},
            {"fieldName": "funding_amount_required", "labelHindi": "आवश्यक फंडिंग राशि (लाख में)", "labelEnglish": "Funding Amount Required (in Lakhs)", "type": "number", "required": True, "section": "Funding Details", "profileKey": "funding_amount_required"},
            {"fieldName": "funding_instrument", "labelHindi": "फंडिंग का प्रकार", "labelEnglish": "Funding Instrument", "type": "select", "required": True, "section": "Funding Details", "options": ["Grant", "Debt", "Convertible Debenture"], "profileKey": "funding_instrument"},
            {"fieldName": "use_of_funds", "labelHindi": "फंड के उपयोग का विवरण", "labelEnglish": "Proposed Use of Funds", "type": "textarea", "required": True, "section": "Funding Details", "profileKey": "use_of_funds"},
            {"fieldName": "previous_funding_received", "labelHindi": "क्या पहले कोई सरकारी फंडिंग मिली?", "labelEnglish": "Previous Govt Funding Received?", "type": "select", "required": True, "section": "Funding Details", "options": ["No", "Yes"], "profileKey": "previous_funding_received"},
            {"fieldName": "bank_account_number", "labelHindi": "बैंक खाता संख्या", "labelEnglish": "Bank Account Number", "type": "text", "required": True, "section": "Bank Details", "profileKey": "bank_account_number"},
            {"fieldName": "bank_ifsc_code", "labelHindi": "IFSC कोड", "labelEnglish": "IFSC Code", "type": "text", "required": True, "section": "Bank Details", "profileKey": "bank_ifsc_code"},
        ],
    },
    {
        "schemeName": "PM-KISAN Samman Nidhi",
        "schemeNameHindi": "पीएम-किसान सम्मान निधि",
        "officialPdfUrl": "https://pmkisan.gov.in/documents/RevisedPM-KISANOperationalGuidelines(English).pdf",
        "officialWebsite": "https://pmkisan.gov.in",
        "description": "Income support of Rs 6,000 per year to farmer families in three installments",
        "descriptionHindi": "किसान परिवारों को प्रति वर्ष 6,000 रुपये तीन किस्तों में आय सहायता",
        "category": "agriculture",
        "totalFields": 19,
        "sections": [
            {"name": "Farmer Details", "nameHindi": "किसान विवरण"},
            {"name": "Address Details", "nameHindi": "पता विवरण"},
            {"name": "Land Details", "nameHindi": "भूमि विवरण"},
            {"name": "Bank Details", "nameHindi": "बैंक विवरण"},
            {"name": "Self Declaration", "nameHindi": "स्व-घोषणा"},
        ],
        "eligibilityCriteria": {
            "must_own_cultivable_land": True,
            "excludes_institutional_landholders": True,
            "excludes_govt_employees_except_class4": True,
            "excludes_income_tax_payers": True,
            "excludes_pensioners_above_10k": True,
        },
        "extractedFields": [
            {"fieldName": "farmer_name", "labelHindi": "किसान का नाम", "labelEnglish": "Farmer Name", "type": "text", "required": True, "section": "Farmer Details", "profileKey": "name"},
            {"fieldName": "father_husband_name", "labelHindi": "पिता/पति का नाम", "labelEnglish": "Father's/Husband's Name", "type": "text", "required": True, "section": "Farmer Details", "profileKey": "father_husband_name"},
            {"fieldName": "gender", "labelHindi": "लिंग", "labelEnglish": "Gender", "type": "select", "required": True, "section": "Farmer Details", "options": ["Male", "Female", "Other"], "profileKey": "gender"},
            {"fieldName": "date_of_birth", "labelHindi": "जन्म तिथि", "labelEnglish": "Date of Birth", "type": "date", "required": True, "section": "Farmer Details", "profileKey": "date_of_birth"},
            {"fieldName": "aadhaar_number", "labelHindi": "आधार संख्या", "labelEnglish": "Aadhaar Number", "type": "aadhaar", "required": True, "section": "Farmer Details", "profileKey": "aadhaar_number"},
            {"fieldName": "caste_category", "labelHindi": "जाति वर्ग", "labelEnglish": "Caste Category", "type": "select", "required": True, "section": "Farmer Details", "options": ["SC", "ST", "OBC", "General"], "profileKey": "caste_category"},
            {"fieldName": "mobile_number", "labelHindi": "मोबाइल नंबर", "labelEnglish": "Mobile Number", "type": "phone", "required": True, "section": "Farmer Details", "profileKey": "mobile_number"},
            {"fieldName": "state", "labelHindi": "राज्य", "labelEnglish": "State", "type": "text", "required": True, "section": "Address Details", "profileKey": "state"},
            {"fieldName": "district", "labelHindi": "जिला", "labelEnglish": "District", "type": "text", "required": True, "section": "Address Details", "profileKey": "district"},
            {"fieldName": "sub_district", "labelHindi": "उप-जिला/तहसील", "labelEnglish": "Sub-District/Tehsil", "type": "text", "required": True, "section": "Address Details", "profileKey": "sub_district"},
            {"fieldName": "block", "labelHindi": "ब्लॉक", "labelEnglish": "Block", "type": "text", "required": True, "section": "Address Details", "profileKey": "block"},
            {"fieldName": "village", "labelHindi": "गांव", "labelEnglish": "Village", "type": "text", "required": True, "section": "Address Details", "profileKey": "village"},
            {"fieldName": "pincode", "labelHindi": "पिनकोड", "labelEnglish": "Pincode", "type": "text", "required": True, "section": "Address Details", "profileKey": "pincode"},
            {"fieldName": "khasra_khewat_number", "labelHindi": "खसरा/खेवट संख्या", "labelEnglish": "Khasra/Khewat Number", "type": "text", "required": True, "section": "Land Details", "profileKey": "khasra_khewat_number"},
            {"fieldName": "land_area_hectares", "labelHindi": "भूमि क्षेत्रफल (हेक्टेयर में)", "labelEnglish": "Land Area (in Hectares)", "type": "number", "required": True, "section": "Land Details", "profileKey": "land_area_hectares"},
            {"fieldName": "bank_account_number", "labelHindi": "बैंक खाता संख्या", "labelEnglish": "Bank Account Number", "type": "text", "required": True, "section": "Bank Details", "profileKey": "bank_account_number"},
            {"fieldName": "bank_ifsc_code", "labelHindi": "IFSC कोड", "labelEnglish": "IFSC Code", "type": "text", "required": True, "section": "Bank Details", "profileKey": "bank_ifsc_code"},
            {"fieldName": "bank_name", "labelHindi": "बैंक का नाम", "labelEnglish": "Bank Name", "type": "text", "required": True, "section": "Bank Details", "profileKey": "bank_name"},
            {"fieldName": "is_govt_employee", "labelHindi": "क्या परिवार में कोई सरकारी कर्मचारी है?", "labelEnglish": "Is any family member a Govt employee (except Class 4)?", "type": "select", "required": True, "section": "Self Declaration", "options": ["No", "Yes"], "profileKey": "is_govt_employee"},
        ],
    },
]


async def main():
    db = Prisma()
    await db.connect()

    # ── Seed Schemes ──
    print("Seeding Schemes...")
    for s in SCHEMES:
        existing = await db.scheme.find_first(where={"name": s["name"]})
        if existing:
            await db.scheme.update(where={"id": existing.id}, data=s)
            print(f"  Updated: {s['name']}")
        else:
            await db.scheme.create(data=s)
            print(f"  Created: {s['name']}")
    scheme_count = await db.scheme.count()
    print(f"Scheme table: {scheme_count} records\n")

    # ── Seed FormTemplates ──
    print("Seeding FormTemplates...")
    for ft in FORM_TEMPLATES:
        existing = await db.formtemplate.find_first(where={"schemeName": ft["schemeName"]})
        if existing:
            await db.formtemplate.update(where={"id": existing.id}, data=ft)
            print(f"  Updated: {ft['schemeName']} ({ft['totalFields']} fields)")
        else:
            await db.formtemplate.create(data=ft)
            print(f"  Created: {ft['schemeName']} ({ft['totalFields']} fields)")
    ft_count = await db.formtemplate.count()
    print(f"FormTemplate table: {ft_count} records\n")

    # ── Summary ──
    print("=== Seed Complete ===")
    print(f"  Schemes: {scheme_count}")
    print(f"  FormTemplates: {ft_count}")
    total_fields = sum(ft["totalFields"] for ft in FORM_TEMPLATES)
    print(f"  Total form fields across all schemes: {total_fields}")

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
