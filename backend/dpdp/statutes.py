"""Every law and guideline this application is subject to, and where it stands.

The DPDP Act is not the only instrument that binds an app handling Aadhaar,
bank details and government benefits. This module is the register of all of
them, with an honest status per obligation, so that "are we compliant?" has a
checkable answer rather than an opinion.

Status values are deliberately blunt. PARTIAL and NON_COMPLIANT are used where
they are true; a register that grades everything COMPLIANT is worthless, and the
most dangerous entry here is the one nobody wrote down.

Sources are cited so each entry can be checked against the instrument rather
than trusted. Where an obligation turns on a fact only the operator knows —
whether this is run by or for the State, for instance — the entry says so
instead of guessing.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from enum import Enum


class Status(str, Enum):
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    NOT_APPLICABLE = "not_applicable"
    NEEDS_LEGAL_INPUT = "needs_legal_input"   # turns on a fact we cannot decide


class Exposure(str, Enum):
    """What non-compliance actually costs. Criminal exposure ranks above all."""
    CRIMINAL = "criminal"        # imprisonment possible
    PENALTY = "penalty"          # monetary penalty
    DIRECTION = "direction"      # regulator may direct/block
    GUIDELINE = "guideline"      # mandatory standard, softer enforcement


@dataclass
class Obligation:
    statute: str
    provision: str
    requirement: str
    status: Status
    exposure: Exposure
    evidence: str = ""           # what in this codebase satisfies or fails it
    remediation: str = ""
    source: str = ""

    def as_dict(self) -> dict:
        return {
            "statute": self.statute, "provision": self.provision,
            "requirement": self.requirement, "status": self.status.value,
            "exposure": self.exposure.value, "evidence": self.evidence,
            "remediation": self.remediation, "source": self.source,
        }


S, E = Status, Exposure

OBLIGATIONS: tuple[Obligation, ...] = (

    # ══ Aadhaar Act 2016 (as amended 2019) ═══════════════════════════════
    # The most serious instrument here: breach carries imprisonment, not just
    # a penalty.
    Obligation(
        "Aadhaar Act 2016", "s29(4)",
        "No Aadhaar number shall be published, displayed or posted publicly, "
        "except as specified by regulations. UIDAI permits only masked display "
        "— first 8 digits replaced, last 4 visible.",
        S.COMPLIANT, E.CRIMINAL,
        evidence="dpdp/aadhaar_policy.py masks on every display path; "
                 "pdf_generator never emits an unmasked number.",
        source="https://uidai.gov.in/images/Aadhaar_Act_2016_as_amended.pdf",
    ),
    Obligation(
        "Aadhaar (Authentication and Offline Verification) Regulations 2021",
        "reg 26 / Auth Regs 2016",
        "An entity that is not a Requesting Entity/KUA must not store the "
        "Aadhaar number. Only eKYC data may be retained, on consent.",
        S.COMPLIANT, E.CRIMINAL,
        evidence="Aadhaar is accepted transiently to fill a form and is never "
                 "persisted: only the last four digits and a keyed fingerprint "
                 "are stored (dpdp/aadhaar_policy.py, identity_index.py).",
        source="https://uidai.gov.in/",
    ),
    Obligation(
        "Aadhaar Act 2016", "s7",
        "Aadhaar may be required for receipt of a subsidy or benefit funded "
        "from the Consolidated Fund. An alternative route must exist for a "
        "person without Aadhaar.",
        S.PARTIAL, E.DIRECTION,
        evidence="Aadhaar is treated as required by the catalog's field "
                 "definitions.",
        remediation="Mark Aadhaar optional where the scheme permits an "
                    "alternative identity document, and collect that instead.",
    ),

    # ══ IT Act 2000 and rules ════════════════════════════════════════════
    Obligation(
        "IT Act 2000 / SPDI Rules 2011", "rule 4",
        "A body corporate handling sensitive personal data must publish a "
        "privacy policy covering the type of data, purpose, and disclosure.",
        S.COMPLIANT, E.PENALTY,
        evidence="GET /api/dpdp/notice, served publicly and pre-consent.",
    ),
    Obligation(
        "IT Act 2000 / SPDI Rules 2011", "rule 8 / s43A",
        "Reasonable security practices proportionate to the data held; "
        "negligence causing wrongful loss attracts compensation.",
        S.PARTIAL, E.PENALTY,
        evidence="Ownership checks, hashed identifiers, redaction and leak "
                 "scanning are in place.",
        remediation="Encryption at rest for stored profiles and generated "
                    "documents is still missing, as is a documented ISO 27001 "
                    "or equivalent control set.",
    ),
    Obligation(
        "CERT-In Directions 2022", "direction (i)",
        "Cyber security incidents must be reported to CERT-In within 6 hours "
        "of becoming aware of them.",
        S.PARTIAL, E.DIRECTION,
        evidence="dpdp/incident.py maintains the register and computes the "
                 "6-hour deadline with escalation.",
        remediation="Actual transmission to CERT-In is a manual step until an "
                    "operator supplies the reporting channel and credentials.",
        source="https://www.cert-in.org.in/",
    ),
    Obligation(
        "CERT-In Directions 2022", "direction (iv)",
        "ICT system logs must be maintained for a rolling 180 days and stored "
        "within Indian jurisdiction.",
        S.PARTIAL, E.DIRECTION,
        evidence="dpdp/incident.py declares and checks the 180-day policy.",
        remediation="Enforcement depends on the deployment's log store; the "
                    "policy is asserted here but must be configured there, "
                    "including in-India residency.",
    ),
    Obligation(
        "CERT-In Directions 2022", "direction (ii)",
        "System clocks must be synchronised to NIC or NPL NTP servers.",
        S.NEEDS_LEGAL_INPUT, E.DIRECTION,
        evidence="Infrastructure concern, outside the application.",
        remediation="Configure NTP to time.nplindia.org / samay1.nic.in on the "
                    "hosts running this service.",
    ),
    Obligation(
        "IT (Intermediary Guidelines) Rules 2021", "rule 3(1)(a)",
        "Publish rules, privacy policy and user agreement.",
        S.PARTIAL, E.DIRECTION,
        evidence="Privacy notice is published.",
        remediation="Terms of service / user agreement is still missing.",
    ),
    Obligation(
        "IT (Intermediary Guidelines) Rules 2021", "rule 3(2)",
        "Appoint a Grievance Officer, publish their name and contact, "
        "acknowledge a complaint within 24 hours and resolve within 15 days.",
        S.COMPLIANT, E.DIRECTION,
        evidence="dpdp/grievance.py tracks both deadlines and exposes the "
                 "officer's details; GET /api/dpdp/grievance-officer.",
        remediation="The published officer name and email must be set via "
                    "GRIEVANCE_OFFICER_* environment variables.",
    ),

    # ══ DPDP Act 2023 ════════════════════════════════════════════════════
    Obligation(
        "DPDP Act 2023", "s5",
        "Notice of the personal data collected, the purpose, how to exercise "
        "rights, and how to complain to the Board.",
        S.COMPLIANT, E.PENALTY,
        evidence="GET /api/dpdp/notice; purposes generated from the processing "
                 "register so the notice cannot drift from what is collected.",
    ),
    Obligation(
        "DPDP Act 2023", "s5(3)",
        "The notice must be available in English or any language in the Eighth "
        "Schedule to the Constitution, at the Data Principal's option.",
        S.PARTIAL, E.PENALTY,
        evidence="Notice is served in Hindi and English; the endpoint accepts a "
                 "language parameter and declares the 22 Eighth Schedule "
                 "languages it can be requested in.",
        remediation="Translations beyond Hindi and English are not yet written; "
                    "the endpoint reports which are available rather than "
                    "silently returning English.",
    ),
    Obligation(
        "DPDP Act 2023", "s6",
        "Consent must be free, specific, informed, unconditional and "
        "unambiguous, limited to necessary data, withdrawable as easily as "
        "given.",
        S.COMPLIANT, E.PENALTY,
        evidence="Per-purpose consent with plain-language explanations; "
                 "withdrawal requires no reason (dpdp/consent.py, PrivacyPage).",
    ),
    Obligation(
        "DPDP Act 2023", "s8(3)",
        "Data used to make a decision affecting the Data Principal must be "
        "accurate, complete and consistent.",
        S.COMPLIANT, E.PENALTY,
        evidence="Decisional fields are flagged in the register and checked for "
                 "placeholder values (dpdp/engine.py check_row).",
    ),
    Obligation(
        "DPDP Act 2023", "s8(4)",
        "Reasonable security safeguards to prevent personal data breach.",
        S.PARTIAL, E.PENALTY,
        evidence="Artefact ownership checks, hashed identifiers, redaction "
                 "before logging and third-party calls, automated leak scanning.",
        remediation="Encryption at rest still outstanding.",
    ),
    Obligation(
        "DPDP Act 2023", "s8(5)",
        "Notify the Board and each affected Data Principal of a personal data "
        "breach.",
        S.PARTIAL, E.PENALTY,
        evidence="dpdp/incident.py records breaches and tracks both "
                 "notification obligations separately.",
        remediation="Transmission to the Board and to affected principals is "
                    "operator-driven until a channel is configured.",
    ),
    Obligation(
        "DPDP Act 2023", "s8(6)",
        "Erase personal data when consent is withdrawn or the purpose is no "
        "longer served, unless retention is required by law.",
        S.COMPLIANT, E.PENALTY,
        evidence="Per-field retention in the register; sweep and erasure in "
                 "dpdp/retention.py; citizen-initiated erasure in PrivacyPage.",
    ),
    Obligation(
        "DPDP Act 2023", "s8(7)",
        "Publish the contact details of the Data Protection Officer or the "
        "person able to answer questions about processing.",
        S.COMPLIANT, E.PENALTY,
        evidence="GET /api/dpdp/grievance-officer, also surfaced in the notice.",
    ),
    Obligation(
        "DPDP Act 2023", "s9",
        "Verifiable consent of a parent or lawful guardian before processing a "
        "child's data; no tracking, behavioural advertising or detrimental "
        "processing of children.",
        S.PARTIAL, E.PENALTY,
        evidence="Child-data fields are marked in the register and checked; "
                 "parental consent is recorded and gates processing.",
        remediation="Consent is self-declared. 'Verifiable' implies an "
                    "independent check of guardianship, which is not "
                    "implemented. No tracking or advertising exists, so the "
                    "second limb holds.",
    ),
    Obligation(
        "DPDP Act 2023", "s11-s14",
        "Rights to access information, correction and erasure, grievance "
        "redressal, and nomination.",
        S.PARTIAL, E.PENALTY,
        evidence="s11, s12 and s13 are implemented end to end.",
        remediation="s14 nomination is recorded as a request but the nominee is "
                    "not yet able to act on the account.",
    ),

    # ══ Accessibility ════════════════════════════════════════════════════
    # A benefits app that a blind citizen cannot use denies them the benefit,
    # so this ranks with the identity obligations rather than below them.
    Obligation(
        "RPwD Act 2016", "s40, s42, s46",
        "Information and communication technology must be accessible to "
        "persons with disabilities, to the standards notified.",
        S.PARTIAL, E.DIRECTION,
        evidence="Accessibility pass applied: landmarks, skip link, document "
                 "language, focus visibility, minimum text sizes, and labels "
                 "on icon-only controls.",
        remediation="A full WCAG 2.1 AA audit with assistive technology has not "
                    "been run; colour contrast on light-grey secondary text is "
                    "the likeliest remaining failure.",
    ),
    Obligation(
        "GIGW 3.0 (MeitY/NIC)", "accessibility baseline",
        "Government websites and apps must meet WCAG 2.1 Level AA and publish "
        "an accessibility statement.",
        S.PARTIAL, E.GUIDELINE,
        evidence="Accessibility statement served at GET /api/dpdp/accessibility.",
        remediation="Conformance is claimed as partial and stated honestly "
                    "rather than asserted as full.",
        source="https://guidelines.india.gov.in/",
    ),

    # ══ Other ════════════════════════════════════════════════════════════
    Obligation(
        "Official Languages Act 1963", "s3 / rule 3",
        "Central government communication in Hindi and English.",
        S.COMPLIANT, E.GUIDELINE,
        evidence="All citizen-facing text is bilingual Hindi/English.",
    ),
    Obligation(
        "RBI Storage of Payment System Data 2018", "para 2",
        "Payment system data must be stored only in India.",
        S.NOT_APPLICABLE, E.DIRECTION,
        evidence="No payment is initiated or processed. Bank details are "
                 "collected solely to be written onto a government form the "
                 "citizen submits themselves.",
    ),
    Obligation(
        "Consumer Protection (E-Commerce) Rules 2020", "rule 4",
        "Grievance officer and redress timelines for e-commerce entities.",
        S.NEEDS_LEGAL_INPUT, E.PENALTY,
        evidence="Applies only if this is characterised as an e-commerce "
                 "entity. No goods or services are sold.",
        remediation="The grievance machinery built for IT Rules 3(2) would "
                    "satisfy this if it is held to apply.",
    ),
    Obligation(
        "RTI Act 2005", "s4(1)(b)",
        "Proactive disclosure obligations of a public authority.",
        S.NEEDS_LEGAL_INPUT, E.DIRECTION,
        evidence="Applies only if operated by or substantially financed by "
                 "government.",
        remediation="If this is run by a public authority, publish the s4(1)(b) "
                    "disclosures and designate a PIO.",
    ),
)


def by_status(status: Status) -> list[Obligation]:
    return [o for o in OBLIGATIONS if o.status == status]


def outstanding() -> list[Obligation]:
    """Everything not yet satisfied, worst exposure first."""
    order = {Exposure.CRIMINAL: 0, Exposure.PENALTY: 1,
             Exposure.DIRECTION: 2, Exposure.GUIDELINE: 3}
    gaps = [o for o in OBLIGATIONS
            if o.status in (Status.NON_COMPLIANT, Status.PARTIAL,
                            Status.NEEDS_LEGAL_INPUT)]
    return sorted(gaps, key=lambda o: order.get(o.exposure, 9))


def summary() -> dict:
    return {
        "total_obligations": len(OBLIGATIONS),
        "statutes": sorted({o.statute for o in OBLIGATIONS}),
        "counts": {s.value: len(by_status(s)) for s in Status},
        "criminal_exposure_unresolved": [
            o.as_dict() for o in OBLIGATIONS
            if o.exposure == Exposure.CRIMINAL and o.status != Status.COMPLIANT
        ],
        "obligations": [o.as_dict() for o in OBLIGATIONS],
    }
