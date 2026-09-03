"""Record of processing — what personal data exists, why, and for how long.

DPDP obligations are per-purpose, not per-application. Section 5 requires the
notice to state what is collected and why; section 6 limits consent to data
*necessary* for that purpose; section 8(6) requires erasure once the purpose is
served. None of those can be evaluated, or proved to a regulator, without an
explicit inventory. This module is that inventory, and it is the thing the rest
of the engine checks rows against.

Every field the application can store is declared here with its category,
sensitivity, the purposes it serves, and its retention period. A field that
appears in stored data but not in this registry is itself a finding: it is
personal data being processed outside any declared purpose, which is precisely
what section 6(1) prohibits.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from enum import Enum

from dpdp.classifier import PIICategory, SENSITIVITY_OF, Sensitivity


class Purpose(str, Enum):
    """Declared purposes. Each must appear in the section 5 notice."""
    SCHEME_ELIGIBILITY = "scheme_eligibility"      # decide what a citizen qualifies for
    FORM_COMPLETION = "form_completion"            # pre-fill the government form
    BENEFIT_DISBURSEMENT = "benefit_disbursement"  # route the payment
    FRAUD_PREVENTION = "fraud_prevention"          # protect the public purse
    ACCOUNT_MANAGEMENT = "account_management"      # authenticate the citizen
    SERVICE_COMMUNICATION = "service_communication"  # deadline and status alerts


class LawfulBasis(str, Enum):
    """Section 4: consent, or a section 7 legitimate use."""
    CONSENT = "consent"                                    # s6
    LEGITIMATE_USE_STATE_BENEFIT = "legitimate_use_s7b"    # s7(b): State benefit/subsidy
    LEGITIMATE_USE_VOLUNTARY = "legitimate_use_s7a"        # s7(a): voluntarily provided


@dataclass
class FieldRecord:
    """One personal-data field, as declared to the Data Principal."""
    field: str
    category: PIICategory
    purposes: tuple[Purpose, ...]
    basis: LawfulBasis = LawfulBasis.CONSENT
    retention_days: int = 365
    # Data used to *decide* an entitlement carries the s8(3) accuracy duty:
    # it must be complete, accurate and consistent.
    decisional: bool = False
    # s9: data about a child, attracting verifiable parental consent.
    child_data: bool = False
    note: str = ""

    @property
    def sensitivity(self) -> Sensitivity:
        return SENSITIVITY_OF.get(self.category, Sensitivity.MODERATE)

    def as_dict(self) -> dict:
        return {
            "field": self.field,
            "category": self.category.value,
            "sensitivity": self.sensitivity.value,
            "purposes": [p.value for p in self.purposes],
            "lawful_basis": self.basis.value,
            "retention_days": self.retention_days,
            "decisional": self.decisional,
            "child_data": self.child_data,
            "note": self.note,
        }


P = Purpose
C = PIICategory
B = LawfulBasis

# Retention rationale: an application cycle plus an appeal window. Identity and
# payment details are kept only while an application can still be processed or
# contested; contact details persist longer because alerts are an ongoing
# service the citizen asked for.
_APPLICATION_CYCLE = 365
_APPEAL_WINDOW = 1095      # three years, matching typical grievance limits
_SESSION = 30

REGISTRY: tuple[FieldRecord, ...] = (
    # ── Identity ─────────────────────────────────────────────────────────
    FieldRecord("name", C.NAME, (P.FORM_COMPLETION, P.SCHEME_ELIGIBILITY),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("father_husband_name", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("mother_name", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("guardian_name", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("spouse_name", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("aadhaar_number", C.AADHAAR,
                (P.FORM_COMPLETION, P.FRAUD_PREVENTION),
                basis=B.LEGITIMATE_USE_STATE_BENEFIT,
                retention_days=_APPLICATION_CYCLE, decisional=True,
                note="Government forms require it; never displayed in full."),
    FieldRecord("guardian_aadhaar", C.AADHAAR, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("pan_number", C.PAN, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    # Aadhaar Act s7 proviso: alternatives a citizen may give instead of
    # Aadhaar, so nobody is denied a benefit for want of one.
    FieldRecord("voter_id_number", C.VOTER_ID, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE,
                note="Accepted in place of Aadhaar under the s7 proviso."),
    FieldRecord("driving_licence_number", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE,
                note="Accepted in place of Aadhaar under the s7 proviso."),
    FieldRecord("passport_number", C.PASSPORT, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE,
                note="Accepted in place of Aadhaar under the s7 proviso."),
    FieldRecord("date_of_birth", C.DATE_OF_BIRTH,
                (P.SCHEME_ELIGIBILITY, P.FORM_COMPLETION),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("age", C.DATE_OF_BIRTH, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("gender", C.NAME, (P.SCHEME_ELIGIBILITY, P.FORM_COMPLETION),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("category", C.CASTE_CATEGORY,
                (P.SCHEME_ELIGIBILITY, P.FORM_COMPLETION),
                retention_days=_APPLICATION_CYCLE, decisional=True,
                note="Caste category decides reserved-quota eligibility."),
    FieldRecord("marital_status", C.NAME, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("nationality", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("occupation", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),

    # ── Contact ──────────────────────────────────────────────────────────
    FieldRecord("mobile_number", C.MOBILE,
                (P.ACCOUNT_MANAGEMENT, P.SERVICE_COMMUNICATION, P.FRAUD_PREVENTION),
                retention_days=_APPEAL_WINDOW),
    FieldRecord("phone", C.MOBILE, (P.ACCOUNT_MANAGEMENT,),
                retention_days=_APPEAL_WINDOW),
    FieldRecord("email", C.EMAIL, (P.SERVICE_COMMUNICATION,),
                retention_days=_APPEAL_WINDOW),
    FieldRecord("address_line", C.ADDRESS, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("district", C.ADDRESS, (P.SCHEME_ELIGIBILITY, P.FORM_COMPLETION),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("state", C.ADDRESS, (P.SCHEME_ELIGIBILITY, P.FORM_COMPLETION),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("village", C.ADDRESS, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("tehsil", C.ADDRESS, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("pincode", C.ADDRESS, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("domicile_certificate_number", C.ADDRESS, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),

    # ── Financial ────────────────────────────────────────────────────────
    FieldRecord("bank_account_number", C.BANK_ACCOUNT,
                (P.BENEFIT_DISBURSEMENT, P.FRAUD_PREVENTION),
                basis=B.LEGITIMATE_USE_STATE_BENEFIT,
                retention_days=_APPLICATION_CYCLE,
                note="Benefit is credited directly; also the strongest "
                     "diversion signal."),
    FieldRecord("ifsc_code", C.IFSC, (P.BENEFIT_DISBURSEMENT,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("bank_name", C.FINANCIAL, (P.BENEFIT_DISBURSEMENT,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("branch_name", C.FINANCIAL, (P.BENEFIT_DISBURSEMENT,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("annual_income", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True,
                note="Means test — the single most decisional field."),
    FieldRecord("income_certificate_number", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("is_bpl", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("is_income_tax_payer", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("is_govt_employee", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True,
                note="PM-KISAN excludes serving and retired government "
                     "employees above Group D."),
    FieldRecord("ration_card_number", C.RATION_CARD,
                (P.SCHEME_ELIGIBILITY, P.FRAUD_PREVENTION),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("job_card_number", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("land_holding_acres", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("survey_khasra_number", C.FINANCIAL, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("land_ownership_type", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("loan_amount_required", C.FINANCIAL, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("existing_loan_outstanding", C.FINANCIAL, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("initial_deposit", C.FINANCIAL, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),

    # ── Household / education ────────────────────────────────────────────
    FieldRecord("family_members", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("owns_pucca_house", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("current_house_type", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("secc_household_id", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("institution_name", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("course_name", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("class_sought", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("roll_number", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("admission_year", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("last_exam_percentage", C.NAME, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),

    # ── Children (s9) ────────────────────────────────────────────────────
    FieldRecord("girl_child_name", C.CHILD_DATA, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE, child_data=True,
                note="s9: requires verifiable consent of a parent or guardian."),
    FieldRecord("girl_child_dob", C.CHILD_DATA,
                (P.SCHEME_ELIGIBILITY, P.FORM_COMPLETION),
                retention_days=_APPLICATION_CYCLE, decisional=True,
                child_data=True),
    FieldRecord("girl_child_age", C.CHILD_DATA, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True,
                child_data=True),
    FieldRecord("birth_certificate_number", C.CHILD_DATA, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE, child_data=True),
    FieldRecord("relationship_with_child", C.CHILD_DATA, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE, child_data=True),

    # ── Sports / misc scheme fields ──────────────────────────────────────
    FieldRecord("sport_name", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("event_discipline", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("event_name", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("event_date", C.DATE_OF_BIRTH, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("achievement_position", C.NAME, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("husband_death_certificate_number", C.NAME,
                (P.SCHEME_ELIGIBILITY,), retention_days=_APPLICATION_CYCLE,
                decisional=True),
    FieldRecord("kcc_request_type", C.FINANCIAL, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("farmer_category", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("kharif_crops", C.FINANCIAL, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("rabi_crops", C.FINANCIAL, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("pmsby_consent", C.FINANCIAL, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("pmjjby_consent", C.FINANCIAL, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("pm_kisan_account_number", C.BANK_ACCOUNT, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),

    # ── Health and disability ────────────────────────────────────────────
    # Classified HEALTH, not FINANCIAL, even though these fields are only ever
    # used to decide a pension. A disability certificate number and a maternity
    # card reveal a medical condition; leaking one harms the person in a way a
    # bank balance does not, so they inherit the strictest sensitivity the
    # classifier assigns and are redacted wherever it applies.
    FieldRecord("disability_type", C.HEALTH, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True,
                note="Sensitive. Collected only for disability-linked schemes."),
    FieldRecord("disability_percentage", C.HEALTH, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True,
                note="Sensitive. The statutory threshold for most schemes is 40%."),
    FieldRecord("udid_number", C.HEALTH, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE,
                note="Unique Disability ID. Sensitive by inference."),
    FieldRecord("lmp_date", C.HEALTH, (P.SCHEME_ELIGIBILITY, P.FORM_COMPLETION),
                retention_days=_APPLICATION_CYCLE, decisional=True,
                note="Last menstrual period, required by PMMVY. Sensitive."),
    FieldRecord("mcp_card_number", C.HEALTH, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE,
                note="Mother and Child Protection card. Sensitive."),

    # ── Bereavement ──────────────────────────────────────────────────────
    # Data about a deceased person, collected for family benefit and widow
    # pension claims. The deceased is not a Data Principal under the Act, but
    # the record identifies the surviving claimant's household, so it is held
    # to the same retention and access rules as the claimant's own data.
    FieldRecord("deceased_name", C.NAME, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("deceased_age", C.DATE_OF_BIRTH, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("death_date", C.DATE_OF_BIRTH, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("death_certificate_number", C.NAME, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("marriage_date", C.DATE_OF_BIRTH, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),

    # ── State scheme identifiers and means tests ─────────────────────────
    FieldRecord("state_family_id", C.RATION_CARD, (P.SCHEME_ELIGIBILITY,
                                                   P.FORM_COMPLETION),
                retention_days=_APPLICATION_CYCLE, decisional=True,
                note="Samagra ID, Jan Aadhaar, PPP, Swasthya Sathi and the like. "
                     "Resolves to a whole household, so treated as an identifier."),
    FieldRecord("ration_card_type", C.RATION_CARD, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("caste_certificate_number", C.CASTE_CATEGORY,
                (P.SCHEME_ELIGIBILITY, P.FORM_COMPLETION),
                retention_days=_APPLICATION_CYCLE, decisional=True,
                note="Sensitive. Collected only for reservation-linked schemes."),
    FieldRecord("residency_years", C.ADDRESS, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("number_of_daughters", C.CHILD_DATA, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True,
                child_data=True),
    FieldRecord("child_order", C.CHILD_DATA, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True,
                child_data=True),
    FieldRecord("current_class", C.CHILD_DATA, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE, child_data=True),
    FieldRecord("four_wheeler_owned", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("father_occupation", C.FINANCIAL, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE,
                note="Asked by scholarship forms to establish family means."),
    FieldRecord("mother_occupation", C.FINANCIAL, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE,
                note="Asked by scholarship forms to establish family means."),
    FieldRecord("applied_other_scholarship", C.NAME,
                (P.SCHEME_ELIGIBILITY, P.FRAUD_PREVENTION),
                retention_days=_APPLICATION_CYCLE, decisional=True,
                note="Several scholarships exclude an applicant already "
                     "holding another for the same achievement."),
    FieldRecord("academic_session", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("admission_number", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("residence_ownership", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    # A utility account number resolves to a dwelling, and past consumption is
    # a fine-grained record of when a household is at home. Treated as an
    # address-class identifier, not an inert reference.
    FieldRecord("electricity_account_number", C.ADDRESS,
                (P.SCHEME_ELIGIBILITY, P.FORM_COMPLETION),
                retention_days=_APPLICATION_CYCLE, decisional=True,
                note="Identifies a specific dwelling."),
    FieldRecord("pension_category", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("existing_benefit_amount", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True,
                note="Several schemes exclude applicants already drawing another "
                     "benefit above a threshold."),
    FieldRecord("existing_lpg_connection", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("pension_amount_chosen", C.FINANCIAL, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("nominee_name_aps", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE,
                note="Nominee named on an Atal Pension Yojana form. Distinct from "
                     "the s14 nominee for data-principal rights."),

    # ── Livelihood and enterprise ────────────────────────────────────────
    FieldRecord("business_name", C.NAME, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("business_activity", C.FINANCIAL, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("loan_category", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("udyam_registration_number", C.FINANCIAL, (P.FORM_COMPLETION,),
                retention_days=_APPLICATION_CYCLE),
    FieldRecord("trade_name", C.NAME, (P.SCHEME_ELIGIBILITY, P.FORM_COMPLETION),
                retention_days=_APPLICATION_CYCLE, decisional=True),
    FieldRecord("years_in_trade", C.FINANCIAL, (P.SCHEME_ELIGIBILITY,),
                retention_days=_APPLICATION_CYCLE, decisional=True),

    # ── Operational, non-scheme ──────────────────────────────────────────
    FieldRecord("language", C.NAME, (P.ACCOUNT_MANAGEMENT,),
                basis=B.LEGITIMATE_USE_VOLUNTARY, retention_days=_APPEAL_WINDOW),
)

BY_FIELD: dict[str, FieldRecord] = {r.field: r for r in REGISTRY}

# Keys that are internal bookkeeping, not personal data. Listing them explicitly
# stops the scanner reporting them as undeclared.
NON_PERSONAL_KEYS = frozenset({
    "_complete", "_llm_repair_penalty", "_extraction_method", "_source_url",
    "notifications", "scheme_deadline_alerts", "exam_deadline_alerts",
    "new_scheme_alerts",
})


def category_for_field(field_name: str) -> PIICategory | None:
    """Category for a field name, or None if it is not personal data."""
    key = (field_name or "").strip()
    record = BY_FIELD.get(key)
    if record:
        return record.category
    if key in NON_PERSONAL_KEYS:
        return None
    # Suffix conventions catch fields the registry has not yet enumerated —
    # better to over-protect an unknown `*_aadhaar` than to leak it.
    low = key.lower()
    if low.endswith("aadhaar") or low.endswith("aadhaar_number"):
        return PIICategory.AADHAAR
    if low.endswith("account_number"):
        return PIICategory.BANK_ACCOUNT
    if low.endswith("mobile_number") or low.endswith("phone"):
        return PIICategory.MOBILE
    return None


def record_for(field_name: str) -> FieldRecord | None:
    return BY_FIELD.get((field_name or "").strip())


def fields_for_purpose(purpose: Purpose) -> list[FieldRecord]:
    return [r for r in REGISTRY if purpose in r.purposes]


def decisional_fields() -> list[FieldRecord]:
    """Fields carrying the s8(3) accuracy duty."""
    return [r for r in REGISTRY if r.decisional]


def child_data_fields() -> list[FieldRecord]:
    """Fields attracting s9 verifiable parental consent."""
    return [r for r in REGISTRY if r.child_data]


def undeclared_fields(profile: dict) -> list[str]:
    """Stored keys that no registry entry covers.

    Each is personal data processed outside any declared purpose — the exact
    thing section 6(1) forbids — or an inventory gap. Either way it needs a
    human decision, so it is surfaced rather than silently permitted.
    """
    return sorted(
        key for key in (profile or {})
        if key not in BY_FIELD
        and key not in NON_PERSONAL_KEYS
        and not key.startswith("_")
    )


def notice_summary() -> list[dict]:
    """Per-purpose summary for the section 5 notice and the section 11 right."""
    out = []
    for purpose in Purpose:
        records = fields_for_purpose(purpose)
        if not records:
            continue
        out.append({
            "purpose": purpose.value,
            "field_count": len(records),
            "fields": [r.field for r in records],
            "lawful_bases": sorted({r.basis.value for r in records}),
            "max_retention_days": max(r.retention_days for r in records),
        })
    return out
