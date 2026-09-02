"""
GovScheme SuperAgent â€” Configuration
All government portal sources, categories, and agent settings.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import os
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
INDIAN_STATES = [
    "Andhra_Pradesh", "Arunachal_Pradesh", "Assam", "Bihar",
    "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal_Pradesh",
    "Jharkhand", "Karnataka", "Kerala", "Madhya_Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil_Nadu", "Telangana", "Tripura",
    "Uttar_Pradesh", "Uttarakhand", "West_Bengal",
]
UNION_TERRITORIES = [
    "Andaman_Nicobar", "Chandigarh", "Dadra_Nagar_Haveli_Daman_Diu",
    "Delhi", "Jammu_Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]
@dataclass
class PortalSource:
    name: str
    base_url: str
    level: SchemeLevel
    state: Optional[str] = None
    crawl_strategy: str = "api"  # api, html, sitemap, paginated
    priority: int = 1  # 1=highest
    rate_limit_per_sec: float = 2.0
    needs_js: bool = False
    api_endpoint: Optional[str] = None
    pagination_param: Optional[str] = None
    max_pages: int = 200
    selectors: dict = field(default_factory=dict)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# PRIMARY DATA SOURCES (Priority 1 â€” API-backed)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
PORTAL_SOURCES: list[PortalSource] = [
    # â”€â”€ myScheme Portal (2300+ schemes, primary source) â”€â”€
    PortalSource(
        name="myScheme_Portal",
        base_url="https://www.myscheme.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="api",
        priority=1,
        api_endpoint="https://www.myscheme.gov.in/api/v1/schemes",
        pagination_param="page",
        max_pages=300,
        rate_limit_per_sec=1.0,
        selectors={
            "scheme_list": "div.scheme-card",
            "scheme_name": "h3.scheme-title",
            "scheme_link": "a.scheme-link",
            "category_nav": "ul.category-list li a",
            "state_nav": "select#state-select option",
            "search_url": "https://www.myscheme.gov.in/search?q={}",
            "scheme_detail": "div.scheme-detail-content",
        },
    ),
    # â”€â”€ National Scholarship Portal (150+ scholarships) â”€â”€
    PortalSource(
        name="National_Scholarship_Portal",
        base_url="https://scholarships.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=1,
        rate_limit_per_sec=1.5,
        needs_js=True,
        selectors={
            "scheme_list": "div.scholarship-list table tbody tr",
            "scheme_name": "td:nth-child(2)",
            "scheme_link": "td a[href]",
            "ministry_col": "td:nth-child(3)",
        },
    ),
    # â”€â”€ Startup India (80+ schemes for entrepreneurs) â”€â”€
    PortalSource(
        name="Startup_India",
        base_url="https://www.startupindia.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="api",
        priority=1,
        api_endpoint="https://www.startupindia.gov.in/content/sih/en/government-schemes.html",
        rate_limit_per_sec=1.0,
        selectors={
            "scheme_list": "div.scheme-card-wrapper",
            "scheme_name": "h3.scheme-name",
            "scheme_link": "a.scheme-detail-link",
            "filter_state": "select#state-filter option",
            "filter_sector": "select#sector-filter option",
        },
    ),
    # â”€â”€ API Setu / myScheme API (structured data) â”€â”€
    PortalSource(
        name="API_Setu_myScheme",
        base_url="https://directory.apisetu.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="api",
        priority=1,
        api_endpoint="https://directory.apisetu.gov.in/api-collection/myscheme",
        rate_limit_per_sec=2.0,
    ),
    # â”€â”€ India.gov.in Services Portal â”€â”€
    PortalSource(
        name="India_Gov_Services",
        base_url="https://services.india.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=2,
        rate_limit_per_sec=1.0,
        selectors={
            "scheme_list": "div.service-listing li",
            "scheme_link": "a[href*='service/detail']",
        },
    ),
    # â”€â”€ MSME Schemes â”€â”€
    PortalSource(
        name="MSME_Schemes",
        base_url="https://msme.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=2,
        selectors={
            "scheme_list": "div.scheme-section",
            "scheme_name": "h4",
            "scheme_link": "a[href*='scheme']",
        },
    ),
    # â”€â”€ DST (Dept of Science & Tech) Scholarships â”€â”€
    PortalSource(
        name="DST_Scholarships",
        base_url="https://dst.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=2,
        selectors={
            "scheme_list": "div.field-items div.field-item",
            "scheme_link": "a[href*='scheme']",
        },
    ),
    # â”€â”€ Ministry of Education Scholarships â”€â”€
    PortalSource(
        name="Ministry_Education",
        base_url="https://www.education.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=2,
        selectors={
            "scheme_list": "div.view-content div.views-row",
            "scheme_name": "span.field-content",
            "scheme_link": "a[href]",
        },
    ),
    # â”€â”€ Ministry of Social Justice â”€â”€
    PortalSource(
        name="Ministry_Social_Justice",
        base_url="https://socialjustice.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=2,
    ),
    # â”€â”€ Ministry of Tribal Affairs â”€â”€
    PortalSource(
        name="Ministry_Tribal_Affairs",
        base_url="https://tribal.nic.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=2,
    ),
    # â”€â”€ Ministry of Minority Affairs â”€â”€
    PortalSource(
        name="Ministry_Minority_Affairs",
        base_url="https://minorityaffairs.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=2,
    ),
    # â”€â”€ PM Scholarship Scheme (WARB) â”€â”€
    PortalSource(
        name="PM_Scholarship_WARB",
        base_url="https://ksb.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=2,
    ),
    # â”€â”€ UGC Scholarships â”€â”€
    PortalSource(
        name="UGC_Scholarships",
        base_url="https://www.ugc.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=2,
    ),
    # â”€â”€ AICTE Scholarships â”€â”€
    PortalSource(
        name="AICTE_Scholarships",
        base_url="https://www.aicte-india.org",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=2,
    ),
    # â”€â”€ Buddy4Study (aggregator â€” good for discovery) â”€â”€
    PortalSource(
        name="Buddy4Study",
        base_url="https://www.buddy4study.com",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=3,
        pagination_param="page",
        max_pages=50,
        selectors={
            "scheme_list": "div.scholarship-card",
            "scheme_name": "h3.scholarship-title a",
            "scheme_link": "h3.scholarship-title a[href]",
        },
    ),
]
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STATE PORTAL TEMPLATES
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
STATE_PORTAL_TEMPLATES = {
    "Tamil_Nadu": [
        PortalSource(
            name="TN_Scholarships",
            base_url="https://www.tn.gov.in",
            level=SchemeLevel.STATE,
            state="Tamil_Nadu",
            crawl_strategy="html",
            priority=2,
        ),
        PortalSource(
            name="TN_eDist",
            base_url="https://edistrict.tn.gov.in",
            level=SchemeLevel.STATE,
            state="Tamil_Nadu",
            crawl_strategy="html",
            priority=2,
        ),
    ],
    "Karnataka": [
        PortalSource(
            name="KA_Scholarships",
            base_url="https://karepass.cgg.gov.in",
            level=SchemeLevel.STATE,
            state="Karnataka",
            crawl_strategy="html",
            priority=2,
        ),
    ],
    "Maharashtra": [
        PortalSource(
            name="MH_Mahadbt",
            base_url="https://mahadbt.maharashtra.gov.in",
            level=SchemeLevel.STATE,
            state="Maharashtra",
            crawl_strategy="html",
            priority=2,
        ),
    ],
    "Kerala": [
        PortalSource(
            name="KL_eGrants",
            base_url="https://egrantz.kerala.gov.in",
            level=SchemeLevel.STATE,
            state="Kerala",
            crawl_strategy="html",
            priority=2,
        ),
    ],
}
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# myScheme CATEGORY URLs (direct crawl paths)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
MYSCHEME_CATEGORIES = [
    "agriculture-rural-environment",
    "banking-financial-services-insurance",
    "business-entrepreneurship",
    "education-learning",
    "health-wellness",
    "housing-shelter",
    "public-safety-law-justice",
    "science-it-communications",
    "skills-employment",
    "social-welfare-empowerment",
    "sports-culture",
    "transport-infrastructure",
    "travel-tourism",
    "utility-sanitation",
    "women-child",
]
MYSCHEME_STATE_SLUGS = {
    "Andhra_Pradesh": "andhra-pradesh",
    "Arunachal_Pradesh": "arunachal-pradesh",
    "Assam": "assam",
    "Bihar": "bihar",
    "Chhattisgarh": "chhattisgarh",
    "Goa": "goa",
    "Gujarat": "gujarat",
    "Haryana": "haryana",
    "Himachal_Pradesh": "himachal-pradesh",
    "Jharkhand": "jharkhand",
    "Karnataka": "karnataka",
    "Kerala": "kerala",
    "Madhya_Pradesh": "madhya-pradesh",
    "Maharashtra": "maharashtra",
    "Manipur": "manipur",
    "Meghalaya": "meghalaya",
    "Mizoram": "mizoram",
    "Nagaland": "nagaland",
    "Odisha": "odisha",
    "Punjab": "punjab",
    "Rajasthan": "rajasthan",
    "Sikkim": "sikkim",
    "Tamil_Nadu": "tamil-nadu",
    "Telangana": "telangana",
    "Tripura": "tripura",
    "Uttar_Pradesh": "uttar-pradesh",
    "Uttarakhand": "uttarakhand",
    "West_Bengal": "west-bengal",
    "Delhi": "delhi",
    "Puducherry": "puducherry",
    "Jammu_Kashmir": "jammu-and-kashmir",
    "Ladakh": "ladakh",
    "Chandigarh": "chandigarh",
    "Andaman_Nicobar": "andaman-and-nicobar-islands",
    "Dadra_Nagar_Haveli_Daman_Diu": "dadra-and-nagar-haveli-and-daman-and-diu",
    "Lakshadweep": "lakshadweep",
}
@dataclass
class AgentConfig:
    """Global configuration for the agent system."""
    # LLM Settings
    llm_provider: str = os.getenv("LLM_PROVIDER", "anthropic")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    model_name: str = os.getenv("MODEL_NAME", "claude-sonnet-4-5-20250929")
    max_tokens: int = 4096
    # Crawl Settings
    max_concurrent_crawlers: int = 5
    request_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 2.0
    respect_robots_txt: bool = True
    download_pdfs: bool = True
    download_forms: bool = True
    max_pdf_size_mb: int = 50
    # Storage
    output_dir: str = os.getenv("OUTPUT_DIR", "./output")
    db_path: str = os.getenv("DB_PATH", "./data/schemes.db")
    log_dir: str = "./logs"
    # Agent Communication
    queue_backend: str = "memory"  # memory, redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    # Rate Limiting
    global_rate_limit: float = 5.0  # requests per second across all agents
    per_domain_rate_limit: float = 2.0
    # Dedup
    similarity_threshold: float = 0.85  # fuzzy match threshold
    # Exam Pipeline (V3)
    exam_db_path: str = os.getenv("EXAM_DB_PATH", "./data/exams.db")
    exam_output_dir: str = os.getenv("EXAM_OUTPUT_DIR", "./output/examinations")
    run_exam_pipeline: bool = os.getenv("RUN_EXAM_PIPELINE", "true").lower() == "true"
    exam_llm_max_concurrent: int = int(os.getenv("EXAM_LLM_MAX_CONCURRENT", "5"))
    exam_pdf_download: bool = os.getenv("EXAM_PDF_DOWNLOAD", "true").lower() == "true"
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# V3: EXAMINATION MODULE â€” PORTAL SOURCES, CONDUCTING BODIES, STATE PSCs
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@dataclass
class ExamPortalSource:
    """Configuration for a single exam portal to crawl."""
    body_code: str
    name: str
    base_url: str
    exam_category: str
    exam_level: str
    state: Optional[str] = None
    crawl_strategy: str = "html"
    priority: int = 1
    rate_limit_per_sec: float = 1.0
    notification_urls: list = field(default_factory=list)
    rss_url: Optional[str] = None
    selectors: dict = field(default_factory=dict)
    needs_js: bool = False
    max_pages: int = 10
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# EXAM_BODIES â€” Maps body_code â†’ metadata for all conducting organisations
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
EXAM_BODIES: dict[str, dict] = {
    # â”€â”€ CENTRAL RECRUITMENT BODIES â”€â”€
    "UPSC": {
        "full_name": "Union Public Service Commission",
        "website": "https://upsc.gov.in",
        "career_url": "https://upsc.gov.in/examinations/active-examinations",
        "notifications_url": "https://upsc.gov.in/examinations/notifications",
        "rss_url": "https://upsc.gov.in/rss/notifications",
    },
    "SSC": {
        "full_name": "Staff Selection Commission",
        "website": "https://ssc.gov.in",
        "career_url": "https://ssc.gov.in/portal/exams",
        "notifications_url": "https://ssc.gov.in/portal/notifications",
        "latest_news_url": "https://ssc.gov.in/portal/latestnews",
        "rss_url": None,
    },
    "IBPS": {
        "full_name": "Institute of Banking Personnel Selection",
        "website": "https://www.ibps.in",
        "career_url": "https://www.ibps.in/crp-examination-schedule/",
        "notifications_url": "https://www.ibps.in/notification/",
        "rss_url": None,
    },
    "SBI": {
        "full_name": "State Bank of India",
        "website": "https://sbi.co.in",
        "career_url": "https://sbi.co.in/web/careers",
        "notifications_url": "https://sbi.co.in/web/careers/recruitment-in-sbi",
        "rss_url": None,
    },
    "RBI": {
        "full_name": "Reserve Bank of India",
        "website": "https://rbi.org.in",
        "career_url": "https://rbi.org.in/Scripts/Opportunities.aspx",
        "notifications_url": "https://rbi.org.in/Scripts/Opportunities.aspx",
        "rss_url": "https://rbi.org.in/rss/RSSFeed.aspx?Type=Others",
    },
    "NTA": {
        "full_name": "National Testing Agency",
        "website": "https://nta.ac.in",
        "career_url": "https://nta.ac.in/Examinations",
        "exam_list_url": "https://nta.ac.in/Examinations",
        "rss_url": None,
    },
    # â”€â”€ DEFENCE BODIES â”€â”€
    "ARMY": {
        "full_name": "Indian Army Recruitment",
        "website": "https://joinindianarmy.nic.in",
        "career_url": "https://joinindianarmy.nic.in/english/Registration.htm",
        "notifications_url": "https://joinindianarmy.nic.in/english/ArmyGD.htm",
        "rss_url": None,
    },
    "AIRFORCE": {
        "full_name": "Indian Air Force Recruitment",
        "website": "https://airmenselection.cdac.in",
        "career_url": "https://airmenselection.cdac.in",
        "afcat_url": "https://afcat.cdac.in",
        "rss_url": None,
    },
    "NAVY": {
        "full_name": "Indian Navy Recruitment",
        "website": "https://joinindiannavy.gov.in",
        "career_url": "https://joinindiannavy.gov.in",
        "notifications_url": "https://joinindiannavy.gov.in/en/pages/latest-news",
        "rss_url": None,
    },
    "COAST_GUARD": {
        "full_name": "Indian Coast Guard",
        "website": "https://joinindiancoastguard.gov.in",
        "career_url": "https://joinindiancoastguard.gov.in/cgept/index.html",
        "rss_url": None,
    },
    "OTA": {
        "full_name": "Officers Training Academy (Army SSCCO)",
        "website": "https://joinindianarmy.nic.in",
        "career_url": "https://joinindianarmy.nic.in/english/OfficerTrainingAcademy.htm",
        "rss_url": None,
    },
    # â”€â”€ PARAMILITARY / POLICE FORCES â”€â”€
    "BSF": {
        "full_name": "Border Security Force",
        "website": "https://bsf.gov.in",
        "career_url": "https://bsf.gov.in/recruitment.html",
        "rss_url": None,
    },
    "CRPF": {
        "full_name": "Central Reserve Police Force",
        "website": "https://crpf.gov.in",
        "career_url": "https://crpf.gov.in/recruitment.htm",
        "rss_url": None,
    },
    "CISF": {
        "full_name": "Central Industrial Security Force",
        "website": "https://cisf.gov.in",
        "career_url": "https://cisf.gov.in/recruitment",
        "rss_url": None,
    },
    "SSB_FORCE": {
        "full_name": "Sashastra Seema Bal",
        "website": "https://ssb.nic.in",
        "career_url": "https://ssb.nic.in/SSBPortal/PublicPages/Recruitment.aspx",
        "rss_url": None,
    },
    "ITBP": {
        "full_name": "Indo-Tibetan Border Police",
        "website": "https://itbpolice.nic.in",
        "career_url": "https://itbpolice.nic.in/itbpWeb/Recruitment.do",
        "rss_url": None,
    },
    "ASSAM_RIFLES": {
        "full_name": "Assam Rifles",
        "website": "https://assamrifles.gov.in",
        "career_url": "https://assamrifles.gov.in/Recruitments",
        "rss_url": None,
    },
    "NSG": {
        "full_name": "National Security Guard",
        "website": "https://nsg.gov.in",
        "career_url": "https://nsg.gov.in/recruitment",
        "rss_url": None,
    },
    # â”€â”€ INTELLIGENCE / INVESTIGATIVE â”€â”€
    "IB": {
        "full_name": "Intelligence Bureau â€” MHA",
        "website": "https://mha.gov.in",
        "career_url": "https://mha.gov.in/en/commentsbox/recruitment",
        "notifications_url": "https://mha.gov.in/division_of_mha/intelligence-bureau",
        "rss_url": None,
    },
    "CBI": {
        "full_name": "Central Bureau of Investigation",
        "website": "https://cbi.gov.in",
        "career_url": "https://cbi.gov.in/recruitment.php",
        "rss_url": None,
    },
    "NCB": {
        "full_name": "Narcotics Control Bureau",
        "website": "https://narcoticsindia.nic.in",
        "career_url": "https://narcoticsindia.nic.in/recruitment.php",
        "rss_url": None,
    },
    "ED": {
        "full_name": "Enforcement Directorate",
        "website": "https://enforcementdirectorate.gov.in",
        "career_url": "https://enforcementdirectorate.gov.in/recruitment",
        "rss_url": None,
    },
    # â”€â”€ SCIENCE / RESEARCH / DEFENCE PSU â”€â”€
    "DRDO": {
        "full_name": "Defence Research & Development Organisation â€” CEPTAM",
        "website": "https://drdo.gov.in",
        "career_url": "https://ceptam.drdo.gov.in",
        "ceptam_url": "https://ceptam.drdo.gov.in/ceptam-latest-news.php",
        "rss_url": None,
    },
    "ISRO": {
        "full_name": "Indian Space Research Organisation",
        "website": "https://isro.gov.in",
        "career_url": "https://isro.gov.in/careers.html",
        "rss_url": None,
    },
    "BARC": {
        "full_name": "Bhabha Atomic Research Centre â€” OCES/DGFS",
        "website": "https://barc.gov.in",
        "career_url": "https://www.barc.gov.in/careers/",
        "oces_url": "https://oces.hbni.ac.in",
        "rss_url": None,
    },
    "CSIR": {
        "full_name": "Council of Scientific & Industrial Research",
        "website": "https://www.csir.res.in",
        "career_url": "https://csirhrdg.res.in/",
        "net_url": "https://csirhrdg.res.in/Home/Index/1/Default/2616/60",
        "rss_url": None,
    },
    "DAE": {
        "full_name": "Department of Atomic Energy â€” NPCIL/IGCAR etc.",
        "website": "https://dae.gov.in",
        "career_url": "https://dae.gov.in/?q=node/244",
        "rss_url": None,
    },
    "ICMR": {
        "full_name": "Indian Council of Medical Research",
        "website": "https://icmr.gov.in",
        "career_url": "https://main.icmr.nic.in/content/recruitment",
        "rss_url": None,
    },
    "ICAR": {
        "full_name": "Indian Council of Agricultural Research",
        "website": "https://icar.org.in",
        "career_url": "https://icar.org.in/content/recruitment",
        "rss_url": None,
    },
    # â”€â”€ BANKING / FINANCIAL REGULATORS â”€â”€
    "NABARD": {
        "full_name": "National Bank for Agriculture and Rural Development",
        "website": "https://nabard.org",
        "career_url": "https://www.nabard.org/careers.aspx",
        "rss_url": None,
    },
    "SEBI": {
        "full_name": "Securities and Exchange Board of India",
        "website": "https://sebi.gov.in",
        "career_url": "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecruit=yes",
        "rss_url": None,
    },
    "SIDBI": {
        "full_name": "Small Industries Development Bank of India",
        "website": "https://www.sidbi.in",
        "career_url": "https://www.sidbi.in/en/careers",
        "rss_url": None,
    },
    "EXIM": {
        "full_name": "Export-Import Bank of India",
        "website": "https://www.eximbankindia.in",
        "career_url": "https://www.eximbankindia.in/careers",
        "rss_url": None,
    },
    "NHB": {
        "full_name": "National Housing Bank",
        "website": "https://nhb.org.in",
        "career_url": "https://nhb.org.in/Careers.aspx",
        "rss_url": None,
    },
    # â”€â”€ PSU â€” ENERGY & INFRASTRUCTURE â”€â”€
    "ONGC": {
        "full_name": "Oil & Natural Gas Corporation",
        "website": "https://ongcindia.com",
        "career_url": "https://ongcindia.com/web/eng/careers",
        "rss_url": None,
    },
    "NTPC_PSU": {
        "full_name": "National Thermal Power Corporation",
        "website": "https://ntpc.co.in",
        "career_url": "https://careers.ntpccareers.com",
        "rss_url": None,
    },
    "GAIL": {
        "full_name": "Gas Authority of India Ltd",
        "website": "https://gail.nic.in",
        "career_url": "https://gail.nic.in/recruitment",
        "rss_url": None,
    },
    "BPCL": {
        "full_name": "Bharat Petroleum Corporation Ltd",
        "website": "https://bharatpetroleum.in",
        "career_url": "https://www.bharatpetroleum.in/Job-Seekers/Careers.aspx",
        "rss_url": None,
    },
    "HPCL": {
        "full_name": "Hindustan Petroleum Corporation Ltd",
        "website": "https://hindustanpetroleum.com",
        "career_url": "https://hindustanpetroleum.com/careers",
        "rss_url": None,
    },
    "IOC": {
        "full_name": "Indian Oil Corporation Ltd",
        "website": "https://iocl.com",
        "career_url": "https://iocl.com/pages/recruitment-recruitment-overview",
        "rss_url": None,
    },
    "COAL_INDIA": {
        "full_name": "Coal India Ltd",
        "website": "https://coalindia.in",
        "career_url": "https://coalindia.in/Career.aspx",
        "rss_url": None,
    },
    "NMDC": {
        "full_name": "NMDC Ltd",
        "website": "https://nmdc.co.in",
        "career_url": "https://nmdc.co.in/Pages/recruitment.aspx",
        "rss_url": None,
    },
    # â”€â”€ PSU â€” MANUFACTURING & DEFENCE â”€â”€
    "BHEL": {
        "full_name": "Bharat Heavy Electricals Ltd",
        "website": "https://bhel.com",
        "career_url": "https://careers.bhel.in",
        "rss_url": None,
    },
    "BEL": {
        "full_name": "Bharat Electronics Ltd",
        "website": "https://bel-india.in",
        "career_url": "https://bel-india.in/recruitment",
        "rss_url": None,
    },
    "HAL": {
        "full_name": "Hindustan Aeronautics Ltd",
        "website": "https://hal-india.co.in",
        "career_url": "https://hal-india.co.in/M_Careers.aspx",
        "rss_url": None,
    },
    "BDL": {
        "full_name": "Bharat Dynamics Ltd",
        "website": "https://bdl-india.in",
        "career_url": "https://bdl-india.in/CAREER.html",
        "rss_url": None,
    },
    "SAIL": {
        "full_name": "Steel Authority of India Ltd",
        "website": "https://sail.co.in",
        "career_url": "https://sail.co.in/en/careers",
        "rss_url": None,
    },
    "NALCO": {
        "full_name": "National Aluminium Company",
        "website": "https://nalcoindia.com",
        "career_url": "https://nalcoindia.com/careers/",
        "rss_url": None,
    },
    "MECL": {
        "full_name": "Mineral Exploration & Consultancy Ltd",
        "website": "https://mecl.gov.in",
        "career_url": "https://mecl.gov.in/Vacancy.html",
        "rss_url": None,
    },
    # â”€â”€ RAILWAYS â”€â”€
    "RRB": {
        "full_name": "Railway Recruitment Boards (All 21)",
        "website": "https://indianrailways.gov.in",
        "career_url": "https://indianrailways.gov.in/railwayboard/view_section.jsp?lang=0&id=0,1,304,366,533",
        "rss_url": None,
    },
    "RPF": {
        "full_name": "Railway Protection Force",
        "website": "https://rpf.indianrailways.gov.in",
        "career_url": "https://rpf.indianrailways.gov.in/view_section.jsp?lang=0&id=0,5,268",
        "rss_url": None,
    },
    # â”€â”€ EDUCATION / TESTING AGENCIES â”€â”€
    "KVS": {
        "full_name": "Kendriya Vidyalaya Sangathan",
        "website": "https://kvsangathan.nic.in",
        "career_url": "https://kvsangathan.nic.in/RecruitmentNode",
        "rss_url": None,
    },
    "NVS": {
        "full_name": "Navodaya Vidyalaya Samiti",
        "website": "https://navodaya.gov.in",
        "career_url": "https://navodaya.gov.in/nvs/en/Recruitment1",
        "rss_url": None,
    },
    "CTET": {
        "full_name": "Central Teacher Eligibility Test â€” CBSE",
        "website": "https://ctet.nic.in",
        "career_url": "https://ctet.nic.in",
        "rss_url": None,
    },
    # â”€â”€ INSURANCE â”€â”€
    "LIC": {
        "full_name": "Life Insurance Corporation of India",
        "website": "https://licindia.in",
        "career_url": "https://licindia.in/Home/Careers",
        "rss_url": None,
    },
    "GIC_RE": {
        "full_name": "General Insurance Corporation of India (Re)",
        "website": "https://gicofindia.com",
        "career_url": "https://gicofindia.com/en/career-at-gic.aspx",
        "rss_url": None,
    },
    "NIACL": {
        "full_name": "New India Assurance Company Ltd",
        "website": "https://newindia.co.in",
        "career_url": "https://www.newindia.co.in/career.htm",
        "rss_url": None,
    },
    "UIIC": {
        "full_name": "United India Insurance Company Ltd",
        "website": "https://uiic.co.in",
        "career_url": "https://uiic.co.in/career_opportunities",
        "rss_url": None,
    },
    # â”€â”€ LABOUR / SOCIAL SECURITY â”€â”€
    "ESIC": {
        "full_name": "Employees' State Insurance Corporation",
        "website": "https://esic.in",
        "career_url": "https://esic.in/recruitment/",
        "rss_url": None,
    },
    "EPFO": {
        "full_name": "Employees' Provident Fund Organisation",
        "website": "https://epfindia.gov.in",
        "career_url": "https://www.epfindia.gov.in/site_en/Recruitment.php",
        "rss_url": None,
    },
    # â”€â”€ FOOD / AGRICULTURE / RURAL â”€â”€
    "FCI": {
        "full_name": "Food Corporation of India",
        "website": "https://fci.gov.in",
        "career_url": "https://fci.gov.in/recruitments.php",
        "rss_url": None,
    },
    "NDDB": {
        "full_name": "National Dairy Development Board",
        "website": "https://nddb.coop",
        "career_url": "https://nddb.coop/careers",
        "rss_url": None,
    },
    "NHM": {
        "full_name": "National Health Mission",
        "website": "https://nhm.gov.in",
        "career_url": "https://nhm.gov.in/index4.php?lang=1&level=0&linkid=190&lid=391",
        "rss_url": None,
    },
    "AIIMS": {
        "full_name": "All India Institute of Medical Sciences (Exam Portal)",
        "website": "https://aiimsexams.ac.in",
        "career_url": "https://aiimsexams.ac.in",
        "rss_url": None,
    },
}
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STATE PSC PORTAL REGISTRY â€” All 28 States + Delhi + J&K
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
STATE_PSC_PORTALS: dict[str, dict] = {
    "Andhra_Pradesh": {
        "psc_name": "Andhra Pradesh Public Service Commission",
        "psc_url": "https://psc.ap.gov.in",
        "career_url": "https://psc.ap.gov.in/APPSC/Default/notifications.aspx",
        "police_url": "https://slprb.ap.gov.in",
        "subordinate_url": "https://appsc.gov.in",
    },
    "Arunachal_Pradesh": {
        "psc_name": "Arunachal Pradesh Public Service Commission",
        "psc_url": "https://appsc.gov.in",
        "career_url": "https://appsc.gov.in/notifications",
        "police_url": None,
        "subordinate_url": None,
    },
    "Assam": {
        "psc_name": "Assam Public Service Commission",
        "psc_url": "https://apsc.nic.in",
        "career_url": "https://apsc.nic.in/Advertisement.aspx",
        "police_url": "https://slprbassam.in",
        "subordinate_url": "https://sebaonline.org",
    },
    "Bihar": {
        "psc_name": "Bihar Public Service Commission",
        "psc_url": "https://bpsc.bih.nic.in",
        "career_url": "https://onlinebpsc.bihar.gov.in",
        "police_url": "https://csbc.bih.nic.in",
        "subordinate_url": "https://bssc.bihar.gov.in",
    },
    "Chhattisgarh": {
        "psc_name": "Chhattisgarh Public Service Commission",
        "psc_url": "https://psc.cg.gov.in",
        "career_url": "https://psc.cg.gov.in/Notifications.html",
        "police_url": "https://cgpolice.gov.in",
        "subordinate_url": "https://vyapam.cgstate.gov.in",
    },
    "Goa": {
        "psc_name": "Goa Public Service Commission",
        "psc_url": "https://gpsc.goa.gov.in",
        "career_url": "https://gpsc.goa.gov.in/notifications",
        "police_url": None,
        "subordinate_url": None,
    },
    "Gujarat": {
        "psc_name": "Gujarat Public Service Commission",
        "psc_url": "https://gpsc.gujarat.gov.in",
        "career_url": "https://gpsc.gujarat.gov.in/CurrentNotifications.aspx",
        "police_url": "https://ojas.gujarat.gov.in",
        "subordinate_url": "https://gsssb.gujarat.gov.in",
    },
    "Haryana": {
        "psc_name": "Haryana Public Service Commission",
        "psc_url": "https://hpsc.gov.in",
        "career_url": "https://hpsc.gov.in/Adv_Files_HF/",
        "police_url": "https://hssc.gov.in",
        "subordinate_url": "https://hssc.gov.in",
    },
    "Himachal_Pradesh": {
        "psc_name": "Himachal Pradesh Public Service Commission",
        "psc_url": "https://hppsc.hp.gov.in",
        "career_url": "https://hppsc.hp.gov.in/hppsc/notifications",
        "police_url": "https://hppolice.gov.in",
        "subordinate_url": "https://hpsssb.hp.gov.in",
    },
    "Jharkhand": {
        "psc_name": "Jharkhand Public Service Commission",
        "psc_url": "https://jpsc.gov.in",
        "career_url": "https://jpsc.gov.in/newsnotificationdisplay",
        "police_url": "https://jhpolice.gov.in",
        "subordinate_url": "https://jssc.nic.in",
    },
    "Karnataka": {
        "psc_name": "Karnataka Public Service Commission",
        "psc_url": "https://kpsc.kar.nic.in",
        "career_url": "https://kpsc.kar.nic.in/recruitment/list",
        "police_url": "https://ksp.gov.in",
        "subordinate_url": "https://kssb.gov.in",
    },
    "Kerala": {
        "psc_name": "Kerala Public Service Commission",
        "psc_url": "https://keralapsc.gov.in",
        "career_url": "https://www.keralapsc.gov.in/notification",
        "police_url": None,
        "subordinate_url": None,
    },
    "Madhya_Pradesh": {
        "psc_name": "Madhya Pradesh Public Service Commission",
        "psc_url": "https://mppsc.mp.gov.in",
        "career_url": "https://mppsc.mp.gov.in/en-us/Examination",
        "police_url": "https://mppolice.gov.in",
        "subordinate_url": "https://peb.mp.gov.in",
    },
    "Maharashtra": {
        "psc_name": "Maharashtra Public Service Commission",
        "psc_url": "https://mpsc.gov.in",
        "career_url": "https://mpsc.gov.in/examinations",
        "police_url": "https://mahapolice.gov.in",
        "subordinate_url": "https://maharecruitment.org",
    },
    "Manipur": {
        "psc_name": "Manipur Public Service Commission",
        "psc_url": "https://mpscmanipur.gov.in",
        "career_url": "https://mpscmanipur.gov.in",
        "police_url": None,
        "subordinate_url": None,
    },
    "Meghalaya": {
        "psc_name": "Meghalaya Public Service Commission",
        "psc_url": "https://mpsc.nic.in",
        "career_url": "https://mpsc.nic.in/advertisements.html",
        "police_url": None,
        "subordinate_url": None,
    },
    "Mizoram": {
        "psc_name": "Mizoram Public Service Commission",
        "psc_url": "https://mpsc.mizoram.gov.in",
        "career_url": "https://mpsc.mizoram.gov.in/page/notifications",
        "police_url": None,
        "subordinate_url": None,
    },
    "Nagaland": {
        "psc_name": "Nagaland Public Service Commission",
        "psc_url": "https://npsc.gov.in",
        "career_url": "https://npsc.gov.in/notifications",
        "police_url": None,
        "subordinate_url": None,
    },
    "Odisha": {
        "psc_name": "Odisha Public Service Commission",
        "psc_url": "https://opsc.gov.in",
        "career_url": "https://opsc.gov.in/Advertisements.aspx",
        "police_url": "https://odishapolice.gov.in",
        "subordinate_url": "https://ossc.gov.in",
    },
    "Punjab": {
        "psc_name": "Punjab Public Service Commission",
        "psc_url": "https://ppsc.gov.in",
        "career_url": "https://ppsc.gov.in/RecruitmentNotification.aspx",
        "police_url": "https://punjabpolice.gov.in",
        "subordinate_url": "https://sssb.punjab.gov.in",
    },
    "Rajasthan": {
        "psc_name": "Rajasthan Public Service Commission",
        "psc_url": "https://rpsc.rajasthan.gov.in",
        "career_url": "https://rpsc.rajasthan.gov.in/Recruitment.aspx",
        "police_url": "https://police.rajasthan.gov.in",
        "subordinate_url": "https://rsmssb.rajasthan.gov.in",
    },
    "Sikkim": {
        "psc_name": "Sikkim Public Service Commission",
        "psc_url": "https://spsc.gov.in",
        "career_url": "https://spsc.gov.in/notifications.html",
        "police_url": None,
        "subordinate_url": None,
    },
    "Tamil_Nadu": {
        "psc_name": "Tamil Nadu Public Service Commission",
        "psc_url": "https://tnpsc.gov.in",
        "career_url": "https://www.tnpsc.gov.in/Notifications.html",
        "police_url": "https://tnusrb.tn.gov.in",
        "subordinate_url": "https://tnpsc.gov.in",
    },
    "Telangana": {
        "psc_name": "Telangana State Public Service Commission",
        "psc_url": "https://tspsc.gov.in",
        "career_url": "https://tspsc.gov.in/Notifications.aspx",
        "police_url": "https://tsslprb.gov.in",
        "subordinate_url": "https://tspsc.gov.in",
    },
    "Tripura": {
        "psc_name": "Tripura Public Service Commission",
        "psc_url": "https://tpsc.tripura.gov.in",
        "career_url": "https://tpsc.tripura.gov.in/recruitment",
        "police_url": None,
        "subordinate_url": None,
    },
    "Uttar_Pradesh": {
        "psc_name": "Uttar Pradesh Public Service Commission",
        "psc_url": "https://uppsc.up.nic.in",
        "career_url": "https://uppsc.up.nic.in/CandidateNotifications.aspx",
        "police_url": "https://uppbpb.gov.in",
        "subordinate_url": "https://upsssc.gov.in",
    },
    "Uttarakhand": {
        "psc_name": "Uttarakhand Public Service Commission",
        "psc_url": "https://ukpsc.gov.in",
        "career_url": "https://ukpsc.gov.in/recruitments",
        "police_url": "https://ubse.gov.in",
        "subordinate_url": "https://sssc.uk.gov.in",
    },
    "West_Bengal": {
        "psc_name": "West Bengal Public Service Commission",
        "psc_url": "https://pscwbapplication.in",
        "career_url": "https://pscwbapplication.in/notice/index.html",
        "police_url": "https://wbpolice.gov.in",
        "subordinate_url": "https://wbssc.gov.in",
    },
    "Delhi": {
        "psc_name": "Delhi Subordinate Services Selection Board",
        "psc_url": "https://dsssb.delhi.gov.in",
        "career_url": "https://dsssb.delhi.gov.in/ddssb/recruitment",
        "police_url": "https://www.delhipolice.gov.in",
        "subordinate_url": "https://dsssb.delhi.gov.in",
    },
    "Jammu_Kashmir": {
        "psc_name": "Jammu & Kashmir Services Selection Board",
        "psc_url": "https://jkssb.nic.in",
        "career_url": "https://jkssb.nic.in/notifications",
        "police_url": "https://jkpolice.gov.in",
        "subordinate_url": "https://jkssb.nic.in",
    },
}
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# COMMON CSS SELECTORS FOR EXAM PORTALS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
UPSC_SELECTORS = {
    "exam_list": "table.views-table tbody tr, div.field-content a",
    "exam_link": "td a[href]",
    "exam_name": "td.views-field-title a",
    "notification_link": "a[href*='.pdf'], a[href*='notification']",
}
SSC_SELECTORS = {
    "exam_list": "div.ssc-exam-card, table.table tbody tr, div.card-body",
    "exam_link": "a[href*='advertisement'], a[href*='exam'], a.btn",
    "exam_name": "h4, h5, td:first-child, div.card-title",
}
IBPS_SELECTORS = {
    "exam_list": "table.table tbody tr, div.ibps-notification",
    "exam_link": "td a[href]",
    "exam_name": "td:nth-child(1), h4",
}
RRB_SELECTORS = {
    "exam_list": "table tbody tr, div.notification, li.notification-item",
    "notification_link": "a[href*='.pdf'], a[href*='notification']",
    "exam_name": "td:nth-child(1) a, div.title",
}
PSU_SELECTORS = {
    "exam_list": "table.table tbody tr, div.career-listing li, div.job-listing",
    "exam_link": "a[href*='recruitment'], a[href*='career'], a[href*='.pdf']",
    "exam_name": "td:first-child, li a, div.job-title",
    "date_col": "td:nth-child(2), td:nth-child(3), span.date",
}
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# RRB BOARDS â€” all 21 Railway Recruitment Boards
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
RRB_BOARDS: list[tuple[str, str]] = [
    ("RRB_Ahmedabad", "https://www.rrbahmedabad.gov.in"),
    ("RRB_Ajmer", "https://www.rrbajmer.gov.in"),
    ("RRB_Allahabad", "https://www.rrbald.gov.in"),
    ("RRB_Bangalore", "https://www.rrbbnc.gov.in"),
    ("RRB_Bhopal", "https://www.rrbbpl.nic.in"),
    ("RRB_Bhubaneswar", "https://www.rrbbbs.gov.in"),
    ("RRB_Bilaspur", "https://www.rrbbilaspur.gov.in"),
    ("RRB_Chandigarh", "https://www.rrbcdg.gov.in"),
    ("RRB_Chennai", "https://www.rrbchennai.gov.in"),
    ("RRB_Gorakhpur", "https://www.rrbgkp.gov.in"),
    ("RRB_Guwahati", "https://www.rrbguwahati.gov.in"),
    ("RRB_Jammu", "https://www.rrbjammu.nic.in"),
    ("RRB_Kolkata", "https://www.rrbkolkata.gov.in"),
    ("RRB_Malda", "https://www.rrbmalda.gov.in"),
    ("RRB_Mumbai", "https://www.rrbmumbai.gov.in"),
    ("RRB_Muzaffarpur", "https://www.rrbmuzaffarpur.gov.in"),
    ("RRB_Patna", "https://www.rrbpatna.gov.in"),
    ("RRB_Ranchi", "https://www.rrbranchi.gov.in"),
    ("RRB_Secunderabad", "https://www.rrbsecunderabad.nic.in"),
    ("RRB_Siliguri", "https://www.rrbsiliguri.org"),
    ("RRB_Thiruvananthapuram", "https://www.rrbthiruvananthapuram.gov.in"),
]
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# EXAM_PORTAL_SOURCES â€” Complete list of 150+ exam portal source configs
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
EXAM_PORTAL_SOURCES: list[ExamPortalSource] = []
def _build_exam_portal_sources() -> list[ExamPortalSource]:
    """Build the complete EXAM_PORTAL_SOURCES list. Called once at module load."""
    sources: list[ExamPortalSource] = []
    # â”€â”€ Group A: UPSC (Priority 1) â”€â”€
    sources.append(ExamPortalSource(
        body_code="UPSC", name="UPSC_Active_Exams",
        base_url="https://upsc.gov.in",
        notification_urls=["https://upsc.gov.in/examinations/active-examinations", "https://upsc.gov.in/examinations/notifications"],
        exam_category="Civil_Services", exam_level="Central",
        priority=1, selectors=UPSC_SELECTORS,
        rss_url="https://upsc.gov.in/rss/notifications",
    ))
    sources.append(ExamPortalSource(
        body_code="UPSC", name="UPSC_NDA_CDS",
        base_url="https://upsc.gov.in",
        notification_urls=["https://upsc.gov.in/examinations/active-examinations"],
        exam_category="Defence", exam_level="Central",
        priority=1, selectors=UPSC_SELECTORS,
    ))
    sources.append(ExamPortalSource(
        body_code="UPSC", name="UPSC_CAPF",
        base_url="https://upsc.gov.in",
        notification_urls=["https://upsc.gov.in/examinations/active-examinations"],
        exam_category="Police", exam_level="Central",
        priority=1, selectors=UPSC_SELECTORS,
    ))
    # â”€â”€ Group B: SSC (Priority 1) â”€â”€
    sources.append(ExamPortalSource(
        body_code="SSC", name="SSC_All_Exams",
        base_url="https://ssc.gov.in",
        notification_urls=["https://ssc.gov.in/portal/exams", "https://ssc.gov.in/portal/notifications", "https://ssc.gov.in/portal/latestnews"],
        exam_category="SSC", exam_level="Central",
        priority=1, selectors=SSC_SELECTORS,
    ))
    # â”€â”€ Group C: IBPS (Priority 1) â”€â”€
    sources.append(ExamPortalSource(
        body_code="IBPS", name="IBPS_All_CRP",
        base_url="https://www.ibps.in",
        notification_urls=["https://www.ibps.in/crp-examination-schedule/", "https://www.ibps.in/notification/"],
        exam_category="Banking", exam_level="Central",
        priority=1, selectors=IBPS_SELECTORS,
    ))
    # â”€â”€ Group D: SBI / RBI (Priority 1) â”€â”€
    sources.append(ExamPortalSource(
        body_code="SBI", name="SBI_Recruitment",
        base_url="https://sbi.co.in",
        notification_urls=["https://sbi.co.in/web/careers/recruitment-in-sbi"],
        exam_category="Banking", exam_level="Central", priority=1,
    ))
    sources.append(ExamPortalSource(
        body_code="RBI", name="RBI_Recruitment",
        base_url="https://rbi.org.in",
        notification_urls=["https://rbi.org.in/Scripts/Opportunities.aspx"],
        exam_category="Banking", exam_level="Central", priority=1,
        rss_url="https://rbi.org.in/rss/RSSFeed.aspx?Type=Others",
    ))
    # â”€â”€ Group E: NTA Exams (Priority 1) â”€â”€
    for nta_name, nta_urls, nta_cat in [
        ("NTA_All_Exams", ["https://nta.ac.in/Examinations", "https://nta.ac.in/Notification"], "Engineering"),
        ("NTA_JEE_Main", ["https://jeemain.nta.ac.in"], "Engineering"),
        ("NTA_NEET_UG", ["https://neet.nta.ac.in"], "Medical"),
        ("NTA_UGC_NET", ["https://ugcnet.nta.ac.in"], "Teaching"),
        ("NTA_CUET_UG", ["https://cuet.nta.nic.in"], "Engineering"),
    ]:
        sources.append(ExamPortalSource(
            body_code="NTA", name=nta_name,
            base_url="https://nta.ac.in",
            notification_urls=nta_urls,
            exam_category=nta_cat, exam_level="Central", priority=1,
        ))
    # â”€â”€ Group F: Defence Bodies (Priority 1) â”€â”€
    sources.append(ExamPortalSource(
        body_code="ARMY", name="Army_All_Recruitment",
        base_url="https://joinindianarmy.nic.in",
        notification_urls=["https://joinindianarmy.nic.in/english/Registration.htm", "https://joinindianarmy.nic.in/english/ArmyGD.htm"],
        exam_category="Defence", exam_level="Central", priority=1,
    ))
    sources.append(ExamPortalSource(
        body_code="AIRFORCE", name="Airforce_AFCAT",
        base_url="https://afcat.cdac.in",
        notification_urls=["https://afcat.cdac.in"],
        exam_category="Defence", exam_level="Central", priority=1,
    ))
    sources.append(ExamPortalSource(
        body_code="AIRFORCE", name="Airforce_Airmen_X_Y",
        base_url="https://airmenselection.cdac.in",
        notification_urls=["https://airmenselection.cdac.in"],
        exam_category="Defence", exam_level="Central", priority=1,
    ))
    sources.append(ExamPortalSource(
        body_code="NAVY", name="Navy_All_Recruitment",
        base_url="https://joinindiannavy.gov.in",
        notification_urls=["https://joinindiannavy.gov.in", "https://joinindiannavy.gov.in/en/pages/latest-news"],
        exam_category="Defence", exam_level="Central", priority=1,
    ))
    sources.append(ExamPortalSource(
        body_code="COAST_GUARD", name="CoastGuard_Navik_Yantrik",
        base_url="https://joinindiancoastguard.gov.in",
        notification_urls=["https://joinindiancoastguard.gov.in/cgept/index.html"],
        exam_category="Defence", exam_level="Central", priority=1,
    ))
    # â”€â”€ Group G: Paramilitary (Priority 1) â”€â”€
    for body, name, url in [
        ("BSF", "BSF_Recruitment", "https://bsf.gov.in/recruitment.html"),
        ("CRPF", "CRPF_Recruitment", "https://crpf.gov.in/recruitment.htm"),
        ("CISF", "CISF_Recruitment", "https://cisf.gov.in/recruitment"),
        ("SSB_FORCE", "SSB_Recruitment", "https://ssb.nic.in/SSBPortal/PublicPages/Recruitment.aspx"),
        ("ITBP", "ITBP_Recruitment", "https://itbpolice.nic.in/itbpWeb/Recruitment.do"),
        ("ASSAM_RIFLES", "AssamRifles_Recruitment", "https://assamrifles.gov.in/Recruitments"),
        ("NSG", "NSG_Recruitment", "https://nsg.gov.in/recruitment"),
    ]:
        sources.append(ExamPortalSource(
            body_code=body, name=name,
            base_url=url, notification_urls=[url],
            exam_category="Police", exam_level="Central", priority=1,
        ))
    # â”€â”€ Group H: Railways â€” 21 RRBs + RPF (Priority 1) â”€â”€
    for rrb_name, rrb_url in RRB_BOARDS:
        sources.append(ExamPortalSource(
            body_code="RRB", name=rrb_name,
            base_url=rrb_url, notification_urls=[rrb_url],
            exam_category="Railway", exam_level="Central",
            priority=1, selectors=RRB_SELECTORS,
        ))
    sources.append(ExamPortalSource(
        body_code="RPF", name="RPF_Constable_SI",
        base_url="https://rpf.indianrailways.gov.in",
        notification_urls=["https://rpf.indianrailways.gov.in/view_section.jsp?lang=0&id=0,5,268"],
        exam_category="Railway", exam_level="Central", priority=1,
    ))
    # â”€â”€ Group I: Intelligence (Priority 1) â”€â”€
    sources.append(ExamPortalSource(
        body_code="IB", name="IB_ACIO_JIO",
        base_url="https://mha.gov.in",
        notification_urls=["https://mha.gov.in/en/commentsbox/recruitment", "https://mha.gov.in/division_of_mha/intelligence-bureau"],
        exam_category="Intelligence", exam_level="Central", priority=1,
    ))
    sources.append(ExamPortalSource(
        body_code="CBI", name="CBI_Recruitment",
        base_url="https://cbi.gov.in",
        notification_urls=["https://cbi.gov.in/recruitment.php"],
        exam_category="Intelligence", exam_level="Central", priority=1,
    ))
    # â”€â”€ Group J: Science & Research PSUs (Priority 1) â”€â”€
    for body, name, url, cat in [
        ("DRDO", "DRDO_CEPTAM", "https://ceptam.drdo.gov.in", "PSU"),
        ("ISRO", "ISRO_Careers", "https://isro.gov.in/careers.html", "PSU"),
        ("BARC", "BARC_OCES_DGFS", "https://www.barc.gov.in/careers/", "PSU"),
        ("CSIR", "CSIR_NET", "https://csirhrdg.res.in/", "Engineering"),
        ("ICMR", "ICMR_Recruitment", "https://main.icmr.nic.in/content/recruitment", "Medical"),
        ("ICAR", "ICAR_Recruitment", "https://icar.org.in/content/recruitment", "Agriculture"),
        ("DAE", "DAE_Recruitment", "https://dae.gov.in/?q=node/244", "PSU"),
    ]:
        sources.append(ExamPortalSource(
            body_code=body, name=name,
            base_url=url, notification_urls=[url],
            exam_category=cat, exam_level="Central", priority=1,
        ))
    # â”€â”€ Group K: Energy & Manufacturing PSUs (Priority 2) â”€â”€
    psu_energy = [
        ("ONGC", "ONGC_Recruitment", "https://ongcindia.com/web/eng/careers"),
        ("NTPC_PSU", "NTPC_Recruitment", "https://careers.ntpccareers.com"),
        ("GAIL", "GAIL_Recruitment", "https://gail.nic.in/recruitment"),
        ("BPCL", "BPCL_Recruitment", "https://www.bharatpetroleum.in/Job-Seekers/Careers.aspx"),
        ("HPCL", "HPCL_Recruitment", "https://hindustanpetroleum.com/careers"),
        ("IOC", "IOC_Recruitment", "https://iocl.com/pages/recruitment-recruitment-overview"),
        ("COAL_INDIA", "CoalIndia_Recruitment", "https://coalindia.in/Career.aspx"),
        ("BHEL", "BHEL_Recruitment", "https://careers.bhel.in"),
        ("BEL", "BEL_Recruitment", "https://bel-india.in/recruitment"),
        ("HAL", "HAL_Recruitment", "https://hal-india.co.in/M_Careers.aspx"),
        ("BDL", "BDL_Recruitment", "https://bdl-india.in/CAREER.html"),
        ("SAIL", "SAIL_Recruitment", "https://sail.co.in/en/careers"),
        ("NALCO", "NALCO_Recruitment", "https://nalcoindia.com/careers/"),
    ]
    for body, name, url in psu_energy:
        sources.append(ExamPortalSource(
            body_code=body, name=name,
            base_url=url, notification_urls=[url],
            exam_category="PSU", exam_level="Central",
            priority=2, selectors=PSU_SELECTORS,
        ))
    # â”€â”€ Group L: Banking & Finance (Priority 1) â”€â”€
    for body, name, url in [
        ("NABARD", "NABARD_Recruitment", "https://www.nabard.org/careers.aspx"),
        ("SEBI", "SEBI_Recruitment", "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecruit=yes"),
        ("SIDBI", "SIDBI_Recruitment", "https://www.sidbi.in/en/careers"),
        ("EXIM", "EXIM_Bank_Recruitment", "https://www.eximbankindia.in/careers"),
        ("NHB", "NHB_Recruitment", "https://nhb.org.in/Careers.aspx"),
    ]:
        sources.append(ExamPortalSource(
            body_code=body, name=name,
            base_url=url, notification_urls=[url],
            exam_category="Banking", exam_level="Central", priority=1,
        ))
    # â”€â”€ Group M: Insurance (Priority 2) â”€â”€
    for body, name, url in [
        ("LIC", "LIC_AAO_ADO", "https://licindia.in/Home/Careers"),
        ("GIC_RE", "GIC_Recruitment", "https://gicofindia.com/en/career-at-gic.aspx"),
        ("NIACL", "NIACL_Recruitment", "https://www.newindia.co.in/career.htm"),
        ("UIIC", "UIIC_Recruitment", "https://uiic.co.in/career_opportunities"),
    ]:
        sources.append(ExamPortalSource(
            body_code=body, name=name,
            base_url=url, notification_urls=[url],
            exam_category="Insurance", exam_level="Central", priority=2,
        ))
    # â”€â”€ Group N: Education / Teaching (Priority 2) â”€â”€
    for body, name, url, cat in [
        ("KVS", "KVS_Recruitment", "https://kvsangathan.nic.in/RecruitmentNode", "Teaching"),
        ("NVS", "NVS_Recruitment", "https://navodaya.gov.in/nvs/en/Recruitment1", "Teaching"),
        ("CTET", "CTET_Exam", "https://ctet.nic.in", "Teaching"),
        ("AIIMS", "AIIMS_All_Exams", "https://aiimsexams.ac.in", "Medical"),
    ]:
        sources.append(ExamPortalSource(
            body_code=body, name=name,
            base_url=url, notification_urls=[url],
            exam_category=cat, exam_level="Central", priority=2,
        ))
    # â”€â”€ Group O: Labour & Food (Priority 2) â”€â”€
    for body, name, url, cat in [
        ("ESIC", "ESIC_Recruitment", "https://esic.in/recruitment/", "Other_Central"),
        ("EPFO", "EPFO_Recruitment", "https://www.epfindia.gov.in/site_en/Recruitment.php", "Other_Central"),
        ("FCI", "FCI_Recruitment", "https://fci.gov.in/recruitments.php", "Agriculture"),
        ("NHM", "NHM_Recruitment", "https://nhm.gov.in/index4.php?lang=1&level=0&linkid=190&lid=391", "Medical"),
        ("NDDB", "NDDB_Recruitment", "https://nddb.coop/careers", "Agriculture"),
    ]:
        sources.append(ExamPortalSource(
            body_code=body, name=name,
            base_url=url, notification_urls=[url],
            exam_category=cat, exam_level="Central", priority=2,
        ))
    # â”€â”€ Group P: State PSCs + State Police + Subordinate Services â”€â”€
    for state_name, portal_info in STATE_PSC_PORTALS.items():
        # State PSC
        sources.append(ExamPortalSource(
            body_code=f"PSC_{state_name.upper()[:3]}",
            name=f"{state_name}_PSC",
            base_url=portal_info["psc_url"],
            notification_urls=[portal_info["career_url"]],
            exam_category="State_PSC", exam_level="State",
            state=state_name, priority=2,
        ))
        # State Police (if URL exists)
        if portal_info.get("police_url"):
            sources.append(ExamPortalSource(
                body_code=f"POLICE_{state_name.upper()[:3]}",
                name=f"{state_name}_Police_Recruitment",
                base_url=portal_info["police_url"],
                notification_urls=[portal_info["police_url"]],
                exam_category="State_Police", exam_level="State",
                state=state_name, priority=2,
            ))
        # Subordinate Services (if URL exists and differs from PSC)
        if portal_info.get("subordinate_url") and portal_info["subordinate_url"] != portal_info["psc_url"]:
            sources.append(ExamPortalSource(
                body_code=f"SSB_{state_name.upper()[:3]}",
                name=f"{state_name}_Subordinate_Services",
                base_url=portal_info["subordinate_url"],
                notification_urls=[portal_info["subordinate_url"]],
                exam_category="State_Subordinate", exam_level="State",
                state=state_name, priority=3,
            ))
    return sources
# Build at module load
EXAM_PORTAL_SOURCES = _build_exam_portal_sources()
