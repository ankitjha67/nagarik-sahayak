"""
GovScheme SuperAgent â€” Exam Data Models (V3)
Complete Pydantic models for the Government Examinations pipeline.
Covers: UPSC, SSC, IBPS, NTA, Defence, Railways, State PSCs, PSUs, and 150+ portals.
"""
from __future__ import annotations
import hashlib
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, computed_field
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ENUMS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class ExamCategory(str, Enum):
    Civil_Services = "Civil_Services"
    Banking = "Banking"
    Railway = "Railway"
    Defence = "Defence"
    Police = "Police"
    Intelligence = "Intelligence"
    SSC = "SSC"
    PSU = "PSU"
    Medical = "Medical"
    Engineering = "Engineering"
    Teaching = "Teaching"
    Insurance = "Insurance"
    Revenue = "Revenue"
    Judiciary = "Judiciary"
    Agriculture = "Agriculture"
    State_PSC = "State_PSC"
    State_Police = "State_Police"
    State_Teaching = "State_Teaching"
    State_Subordinate = "State_Subordinate"
    Other_Central = "Other_Central"
class ExamLevel(str, Enum):
    Central = "Central"
    State = "State"
    UT = "UT"
class ExamStatus(str, Enum):
    Upcoming = "Upcoming"
    Application_Open = "Application_Open"
    Application_Closed = "Application_Closed"
    Admit_Card_Out = "Admit_Card_Out"
    Exam_Ongoing = "Exam_Ongoing"
    Result_Awaited = "Result_Awaited"
    Completed = "Completed"
class ExamChangeType(str, Enum):
    New_Notification = "New_Notification"
    Date_Revised = "Date_Revised"
    Vacancy_Revised = "Vacancy_Revised"
    Fee_Revised = "Fee_Revised"
    Status_Changed = "Status_Changed"
    Notification_Amended = "Notification_Amended"
    Unchanged = "Unchanged"
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# NESTED MODELS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class ExamFee(BaseModel):
    """Fee structure by reservation category. All amounts in INR."""
    general: Optional[float] = None
    obc: Optional[float] = None
    sc_st: Optional[float] = None
    female: Optional[float] = None
    ews: Optional[float] = None
    ex_serviceman: Optional[float] = None
    pwd: Optional[float] = None
    fee_note: Optional[str] = None
    fee_payment_url: Optional[str] = None
    is_free: bool = False
    raw_fee_text: Optional[str] = None
class ExamPhaseDate(BaseModel):
    """One phase of a multi-phase exam (Prelims, Mains, Interview, CBT-1, etc.)."""
    phase_name: str
    exam_date_start: Optional[str] = None
    exam_date_end: Optional[str] = None
    admit_card_date: Optional[str] = None
    result_date: Optional[str] = None
    venue: Optional[str] = None
    mode: Optional[str] = None
class ExamVacancy(BaseModel):
    """Vacancy details for one post/grade within an exam."""
    post_name: str
    total_vacancies: Optional[int] = None
    general_vacancies: Optional[int] = None
    obc_vacancies: Optional[int] = None
    sc_vacancies: Optional[int] = None
    st_vacancies: Optional[int] = None
    ews_vacancies: Optional[int] = None
    pwd_vacancies: Optional[int] = None
    ex_sm_vacancies: Optional[int] = None
    pay_scale: Optional[str] = None
    pay_band: Optional[str] = None
    grade_pay: Optional[str] = None
    job_location: Optional[str] = None
class ExamEligibility(BaseModel):
    """Eligibility criteria for the exam."""
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    age_relaxation_obc: Optional[int] = None
    age_relaxation_sc_st: Optional[int] = None
    age_relaxation_pwd: Optional[int] = None
    age_relaxation_ex_sm: Optional[int] = None
    age_as_on_date: Optional[str] = None
    qualification: Optional[str] = None
    min_percentage: Optional[float] = None
    experience_years: Optional[int] = None
    physical_standards: Optional[str] = None
    nationality: str = "Indian"
    domicile_required: Optional[str] = None
    gender_restriction: Optional[str] = None
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# RAW EXAM DATA (crawler output)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class RawExamData(BaseModel):
    """Raw data as scraped from an exam portal. Fields are unprocessed strings."""
    # Identity
    source_portal: str
    source_url: str
    exam_name: str
    exam_code: Optional[str] = None
    conducting_body: str
    notification_url: Optional[str] = None
    apply_url: Optional[str] = None
    syllabus_url: Optional[str] = None
    raw_notification_text: Optional[str] = None
    # Raw date strings (to be parsed by ExamParser)
    raw_notification_date: Optional[str] = None
    raw_application_start: Optional[str] = None
    raw_application_end: Optional[str] = None
    raw_fee_payment_deadline: Optional[str] = None
    raw_correction_window: Optional[str] = None
    raw_admit_card_date: Optional[str] = None
    raw_exam_date: Optional[str] = None
    raw_result_date: Optional[str] = None
    raw_interview_date: Optional[str] = None
    raw_final_result_date: Optional[str] = None
    raw_joining_date: Optional[str] = None
    # Vacancy / Post
    raw_total_vacancies: Optional[str] = None
    raw_vacancy_text: Optional[str] = None
    raw_pay_scale: Optional[str] = None
    # Fee / Eligibility
    raw_fee: Optional[str] = None
    raw_eligibility: Optional[str] = None
    raw_age_limit: Optional[str] = None
    raw_qualification: Optional[str] = None
    raw_physical_standards: Optional[str] = None
    # Metadata
    pdf_urls: list[str] = Field(default_factory=list)
    crawled_at: datetime = Field(default_factory=datetime.utcnow)
    raw_html: Optional[str] = None
    @computed_field
    @property
    def content_hash(self) -> str:
        """Hash for dedup within a single crawl run."""
        content = f"{self.exam_name}|{self.conducting_body}|{self.raw_application_end or ''}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    @computed_field
    @property
    def detail_hash(self) -> str:
        """Hash for change detection across daily runs. Uses more fields."""
        content = (
            f"{self.exam_name}|{self.raw_application_start or ''}|"
            f"{self.raw_application_end or ''}|{self.raw_exam_date or ''}|"
            f"{self.raw_total_vacancies or ''}|{self.raw_fee or ''}"
        )
        return hashlib.sha256(content.encode()).hexdigest()[:24]
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# PARSED EXAM DATA (ExamParser output)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class ParsedExamData(BaseModel):
    """Structured exam data after LLM/regex parsing."""
    raw: RawExamData
    # Identity
    exam_category: ExamCategory = ExamCategory.Other_Central
    exam_level: ExamLevel = ExamLevel.Central
    state: Optional[str] = None
    clean_exam_name: str = ""
    short_name: Optional[str] = None
    exam_cycle: Optional[str] = None
    # Parsed dates (ISO YYYY-MM-DD)
    notification_date: Optional[str] = None
    application_start_date: Optional[str] = None
    application_end_date: Optional[str] = None
    fee_payment_deadline: Optional[str] = None
    correction_window_start: Optional[str] = None
    correction_window_end: Optional[str] = None
    phases: list[ExamPhaseDate] = Field(default_factory=list)
    result_date: Optional[str] = None
    interview_date: Optional[str] = None
    final_result_date: Optional[str] = None
    joining_date: Optional[str] = None
    # Fees
    fee: ExamFee = Field(default_factory=ExamFee)
    # Vacancies
    vacancies: list[ExamVacancy] = Field(default_factory=list)
    total_vacancies: Optional[int] = None
    # Eligibility
    eligibility: ExamEligibility = Field(default_factory=ExamEligibility)
    # Links
    official_notification_url: Optional[str] = None
    apply_online_url: Optional[str] = None
    admit_card_url: Optional[str] = None
    result_url: Optional[str] = None
    syllabus_url: Optional[str] = None
    official_website: Optional[str] = None
    # Status & tracking
    exam_status: ExamStatus = ExamStatus.Upcoming
    change_type: ExamChangeType = ExamChangeType.New_Notification
    days_until_application_close: Optional[int] = None
    days_until_exam: Optional[int] = None
    first_seen_date: Optional[str] = None
    last_seen_date: Optional[str] = None
    # Storage
    folder_path: str = ""
    parsing_confidence: float = 0.0
    parsed_at: datetime = Field(default_factory=datetime.utcnow)
    @computed_field
    @property
    def exam_id(self) -> str:
        """Stable identifier for this exam across runs."""
        slug = re.sub(r'[^a-zA-Z0-9]+', '_', self.clean_exam_name or self.raw.exam_name)[:50]
        cycle = (self.exam_cycle or "").replace("-", "_").replace(" ", "_")
        return f"{self.exam_level.value}_{self.exam_category.value}_{slug}_{cycle}_{self.raw.content_hash[:8]}".rstrip("_")
import re  # needed by exam_id computed field
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STORED EXAM DATA
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class StoredExamData(BaseModel):
    """Exam after being stored in the folder hierarchy."""
    parsed: ParsedExamData
    folder_path: str
    metadata_path: str
    detail_markdown_path: Optional[str] = None
    downloaded_notification_pdfs: list[str] = Field(default_factory=list)
    stored_at: datetime = Field(default_factory=datetime.utcnow)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# EXAM DAILY REPORT
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class ExamDailyReport(BaseModel):
    """Summary of a single daily exam crawl run."""
    run_id: str
    run_date: str
    run_started_at: Optional[datetime] = None
    run_completed_at: Optional[datetime] = None
    total_exams_in_db: int = 0
    new_exams: int = 0
    updated_exams: int = 0
    date_revised_exams: int = 0
    vacancy_revised_exams: int = 0
    closed_exams: int = 0
    application_open_exams: int = 0
    deadlines_within_7_days: int = 0
    deadlines_within_30_days: int = 0
    exams_in_7_days: int = 0
    exams_in_30_days: int = 0
    errors: int = 0
    elapsed_seconds: float = 0.0
    new_exam_names: list[str] = Field(default_factory=list)
    approaching_deadline_exams: list[str] = Field(default_factory=list)
    excel_sheet_path: Optional[str] = None
