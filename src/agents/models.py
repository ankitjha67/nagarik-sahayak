"""
GovScheme SuperAgent â€” Data Models
Pydantic models for scheme data, agent messages, and storage.
"""
from __future__ import annotations
import hashlib
from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field, computed_field
class SchemeLevel(str, Enum):
    CENTRAL = "Central"
    STATE = "State"
    UNION_TERRITORY = "Union_Territory"
class SchemeSector(str, Enum):
    EDUCATION = "Education"
    AGRICULTURE = "Agriculture"
    FISHERIES = "Fisheries"
    MSME = "MSME"
    STARTUP = "Startup"
    SCIENCE_TECHNOLOGY = "Science_Technology"
    HEALTH = "Health"
    WOMEN_CHILD = "Women_Child_Development"
    SOCIAL_JUSTICE = "Social_Justice"
    TRIBAL_AFFAIRS = "Tribal_Affairs"
    MINORITY_AFFAIRS = "Minority_Affairs"
    RURAL_DEVELOPMENT = "Rural_Development"
    URBAN_DEVELOPMENT = "Urban_Development"
    LABOUR_EMPLOYMENT = "Labour_Employment"
    SKILL_DEVELOPMENT = "Skill_Development"
    HOUSING = "Housing"
    FINANCE = "Finance"
    INDUSTRY = "Industry"
    IT_ELECTRONICS = "IT_Electronics"
    TEXTILES = "Textiles"
    FOOD_PROCESSING = "Food_Processing"
    ENVIRONMENT = "Environment"
    ENERGY = "Energy"
    TRANSPORT = "Transport"
    TOURISM = "Tourism"
    SPORTS_YOUTH = "Sports_Youth"
    CULTURE = "Culture"
    DEFENCE = "Defence"
    DISABILITY = "Disability"
    GENERAL = "General"
class SchemeType(str, Enum):
    SCHOLARSHIP = "Scholarship"
    GRANT = "Grant"
    STARTUP_FUND = "Startup_Fund"
    SUBSIDY = "Subsidy"
    LOAN = "Loan"
    PENSION = "Pension"
    INSURANCE = "Insurance"
    FELLOWSHIP = "Fellowship"
    AWARD = "Award"
    STIPEND = "Stipend"
    OTHER = "Other"
class CrawlStatus(str, Enum):
    PENDING = "pending"
    CRAWLING = "crawling"
    CRAWLED = "crawled"
    CLASSIFYING = "classifying"
    CLASSIFIED = "classified"
    STORED = "stored"
    FAILED = "failed"
    DUPLICATE = "duplicate"
class SchemeStatus(str, Enum):
    """Lifecycle status of a scheme across daily runs."""
    ACTIVE = "Active"
    CLOSED = "Closed"
    UPCOMING = "Upcoming"
    EXPIRED = "Expired"
    UNKNOWN = "Unknown"
class ChangeType(str, Enum):
    """Type of change detected in daily delta crawl."""
    NEW = "New"
    UPDATED = "Updated"
    DEADLINE_APPROACHING = "Deadline_Approaching"
    CLOSED = "Closed"
    REOPENED = "Reopened"
    UNCHANGED = "Unchanged"
class RawSchemeData(BaseModel):
    """Raw data extracted by discovery crawlers before classification."""
    source_portal: str
    source_url: str
    scheme_name: str
    scheme_detail_url: Optional[str] = None
    raw_description: Optional[str] = None
    raw_eligibility: Optional[str] = None
    raw_benefits: Optional[str] = None
    raw_application_process: Optional[str] = None
    raw_documents_required: Optional[str] = None
    raw_ministry: Optional[str] = None
    raw_state: Optional[str] = None
    raw_category: Optional[str] = None
    pdf_urls: list[str] = Field(default_factory=list)
    form_urls: list[str] = Field(default_factory=list)
    crawled_at: datetime = Field(default_factory=datetime.utcnow)
    raw_html: Optional[str] = None
    # â”€â”€ NEW: Date, Fee, and Status Fields â”€â”€
    raw_start_date: Optional[str] = None
    raw_end_date: Optional[str] = None
    raw_application_deadline: Optional[str] = None
    raw_fee: Optional[str] = None
    raw_fund_amount: Optional[str] = None
    raw_contact_info: Optional[str] = None
    raw_website_official: Optional[str] = None
    raw_last_updated: Optional[str] = None
    raw_frequency: Optional[str] = None  # Annual, One-time, Quarterly, etc.
    @computed_field
    @property
    def content_hash(self) -> str:
        """Generate hash for deduplication."""
        content = f"{self.scheme_name}|{self.source_url}|{self.raw_description or ''}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    @computed_field
    @property
    def detail_hash(self) -> str:
        """Hash of full detail content for change detection across daily runs."""
        content = (
            f"{self.scheme_name}|{self.raw_description or ''}|"
            f"{self.raw_eligibility or ''}|{self.raw_benefits or ''}|"
            f"{self.raw_start_date or ''}|{self.raw_end_date or ''}|"
            f"{self.raw_fee or ''}|{self.raw_fund_amount or ''}"
        )
        return hashlib.sha256(content.encode()).hexdigest()[:24]
class ClassifiedScheme(BaseModel):
    """Scheme after LLM classification."""
    raw_data: RawSchemeData
    level: SchemeLevel
    state: Optional[str] = None
    sector: SchemeSector
    scheme_type: SchemeType
    clean_name: str
    summary: str
    eligibility_summary: Optional[str] = None
    benefit_amount: Optional[str] = None
    application_deadline: Optional[str] = None
    target_group: Optional[str] = None
    folder_path: str = ""  # computed during storage
    classification_confidence: float = 0.0
    classified_at: datetime = Field(default_factory=datetime.utcnow)
    # â”€â”€ NEW: Extracted Dates, Fees, Status â”€â”€
    start_date: Optional[str] = None          # ISO or human-readable date
    end_date: Optional[str] = None            # ISO or human-readable date
    application_start_date: Optional[str] = None
    application_end_date: Optional[str] = None
    application_fee: Optional[str] = None     # "Free" / "â‚¹100" / "â‚¹500 (General), â‚¹0 (SC/ST)"
    fund_amount_min: Optional[str] = None     # "â‚¹10,000" or "â‚¹50,000 per annum"
    fund_amount_max: Optional[str] = None     # "â‚¹2,00,000"
    frequency: Optional[str] = None           # Annual, One-time, Monthly, Quarterly
    scheme_status: SchemeStatus = SchemeStatus.UNKNOWN
    nodal_ministry: Optional[str] = None
    nodal_department: Optional[str] = None
    official_website: Optional[str] = None
    helpline: Optional[str] = None
    documents_list: list[str] = Field(default_factory=list)  # Parsed list of required docs
    age_limit: Optional[str] = None           # "18-35 years"
    income_limit: Optional[str] = None        # "Below â‚¹8 lakh per annum"
    gender_eligibility: Optional[str] = None  # "All" / "Female only" / "Male only"
    caste_eligibility: Optional[str] = None   # "SC/ST/OBC" / "All" / "EWS"
    # â”€â”€ Change Detection â”€â”€
    change_type: ChangeType = ChangeType.NEW
    previous_detail_hash: Optional[str] = None
    first_seen_date: datetime = Field(default_factory=datetime.utcnow)
    last_seen_date: datetime = Field(default_factory=datetime.utcnow)
    days_until_deadline: Optional[int] = None
    @computed_field
    @property
    def scheme_id(self) -> str:
        """Unique identifier for the scheme."""
        slug = self.clean_name.replace(" ", "_")[:50]
        return f"{self.level.value}_{self.sector.value}_{slug}_{self.raw_data.content_hash[:8]}"
class StoredScheme(BaseModel):
    """Final stored scheme with file paths."""
    classified: ClassifiedScheme
    folder_path: str
    metadata_path: str
    detail_markdown_path: Optional[str] = None
    downloaded_pdfs: list[str] = Field(default_factory=list)
    downloaded_forms: list[str] = Field(default_factory=list)
    stored_at: datetime = Field(default_factory=datetime.utcnow)
# â”€â”€â”€ Agent Communication Messages â”€â”€â”€
class AgentMessageType(str, Enum):
    DISCOVER = "discover"
    RAW_SCHEME = "raw_scheme"
    CLASSIFY = "classify"
    CLASSIFIED_SCHEME = "classified_scheme"
    STORE = "store"
    STORED_SCHEME = "stored_scheme"
    DEDUP_CHECK = "dedup_check"
    DEDUP_RESULT = "dedup_result"
    STATUS_UPDATE = "status_update"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
class AgentMessage(BaseModel):
    """Message passed between agents via the queue."""
    msg_type: AgentMessageType
    sender: str
    payload: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    priority: int = 5  # 1=highest
    retry_count: int = 0
class CrawlProgress(BaseModel):
    """Real-time crawl progress tracking."""
    total_sources: int = 0
    sources_completed: int = 0
    total_schemes_discovered: int = 0
    schemes_classified: int = 0
    schemes_stored: int = 0
    duplicates_found: int = 0
    errors: int = 0
    start_time: Optional[datetime] = None
    last_update: Optional[datetime] = None
    # â”€â”€ Daily Run Tracking â”€â”€
    new_schemes_found: int = 0
    updated_schemes: int = 0
    closed_schemes: int = 0
    deadlines_approaching: int = 0  # Schemes with deadline within 7 days
    run_date: Optional[str] = None  # ISO date of this daily run
    @computed_field
    @property
    def progress_pct(self) -> float:
        if self.total_schemes_discovered == 0:
            return 0.0
        return (self.schemes_stored / self.total_schemes_discovered) * 100
    @computed_field
    @property
    def elapsed_minutes(self) -> float:
        if not self.start_time:
            return 0.0
        delta = (self.last_update or datetime.utcnow()) - self.start_time
        return delta.total_seconds() / 60
    def sector_distribution(self) -> dict[str, int]:
        """Placeholder â€” populated by orchestrator from DB."""
        return {}
class DailyRunReport(BaseModel):
    """Summary of a single daily crawl run."""
    run_id: str
    run_date: str                  # ISO date
    run_started_at: datetime
    run_completed_at: Optional[datetime] = None
    total_schemes_in_db: int = 0
    new_schemes: int = 0
    updated_schemes: int = 0
    closed_schemes: int = 0
    unchanged_schemes: int = 0
    deadlines_within_7_days: int = 0
    deadlines_within_30_days: int = 0
    active_schemes: int = 0
    expired_schemes: int = 0
    errors: int = 0
    elapsed_seconds: float = 0.0
    new_scheme_names: list[str] = Field(default_factory=list)
    updated_scheme_names: list[str] = Field(default_factory=list)
    approaching_deadline_names: list[str] = Field(default_factory=list)
    excel_report_path: Optional[str] = None
