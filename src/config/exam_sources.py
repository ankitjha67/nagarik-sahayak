"""
GovScheme SuperAgent â€” Exam Portal Sources (V3)
Complete registry of 150+ government exam portals:
  - EXAM_BODIES: dict of conducting body metadata
  - STATE_PSC_PORTALS: 28 states + Delhi + J&K
  - ExamPortalSource: dataclass for crawler configuration
  - EXAM_PORTAL_SOURCES: auto-generated list of all crawl targets
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ExamPortalSource â€” one crawl target
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@dataclass
class ExamPortalSource:
    body_code: str                                   # "UPSC", "SSC", "IBPS"
    name: str                                        # Unique display name
    base_url: str
    exam_category: str                               # ExamCategory value
    exam_level: str = "Central"                      # ExamLevel value
    state: Optional[str] = None
    crawl_strategy: str = "html"                     # html | rss | pdf
    priority: int = 1                                # 1=critical, 2=important, 3=supplemental
    rate_limit_per_sec: float = 1.0
    notification_urls: list = field(default_factory=list)
    rss_url: Optional[str] = None
    selectors: dict = field(default_factory=dict)
    needs_js: bool = False
    max_pages: int = 10
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# EXAM_BODIES â€” Conducting body metadata
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
EXAM_BODIES: dict[str, dict] = {
    "UPSC": {"full_name": "Union Public Service Commission", "website": "https://upsc.gov.in",
             "career_url": "https://upsc.gov.in/examinations/active-examinations"},
    "SSC": {"full_name": "Staff Selection Commission", "website": "https://ssc.gov.in",
            "career_url": "https://ssc.gov.in/portal/exams"},
    "IBPS": {"full_name": "Institute of Banking Personnel Selection", "website": "https://www.ibps.in",
             "career_url": "https://www.ibps.in/crp-examination-schedule/"},
    "SBI": {"full_name": "State Bank of India", "website": "https://sbi.co.in",
            "career_url": "https://sbi.co.in/web/careers/recruitment-in-sbi"},
    "RBI": {"full_name": "Reserve Bank of India", "website": "https://rbi.org.in",
            "career_url": "https://rbi.org.in/Scripts/Opportunities.aspx"},
    "NTA": {"full_name": "National Testing Agency", "website": "https://nta.ac.in",
            "career_url": "https://nta.ac.in/Examinations"},
    "ARMY": {"full_name": "Indian Army Recruitment", "website": "https://joinindianarmy.nic.in",
             "career_url": "https://joinindianarmy.nic.in/english/Registration.htm"},
    "AIRFORCE": {"full_name": "Indian Air Force Recruitment", "website": "https://airmenselection.cdac.in",
                 "career_url": "https://afcat.cdac.in"},
    "NAVY": {"full_name": "Indian Navy Recruitment", "website": "https://joinindiannavy.gov.in",
             "career_url": "https://joinindiannavy.gov.in"},
    "COAST_GUARD": {"full_name": "Indian Coast Guard", "website": "https://joinindiancoastguard.gov.in",
                    "career_url": "https://joinindiancoastguard.gov.in/cgept/index.html"},
    "BSF": {"full_name": "Border Security Force", "website": "https://bsf.gov.in", "career_url": "https://bsf.gov.in/recruitment.html"},
    "CRPF": {"full_name": "Central Reserve Police Force", "website": "https://crpf.gov.in", "career_url": "https://crpf.gov.in/recruitment.htm"},
    "CISF": {"full_name": "Central Industrial Security Force", "website": "https://cisf.gov.in", "career_url": "https://cisf.gov.in/recruitment"},
    "SSB_FORCE": {"full_name": "Sashastra Seema Bal", "website": "https://ssb.nic.in", "career_url": "https://ssb.nic.in/SSBPortal/PublicPages/Recruitment.aspx"},
    "ITBP": {"full_name": "Indo-Tibetan Border Police", "website": "https://itbpolice.nic.in", "career_url": "https://itbpolice.nic.in/itbpWeb/Recruitment.do"},
    "ASSAM_RIFLES": {"full_name": "Assam Rifles", "website": "https://assamrifles.gov.in", "career_url": "https://assamrifles.gov.in/Recruitments"},
    "NSG": {"full_name": "National Security Guard", "website": "https://nsg.gov.in", "career_url": "https://nsg.gov.in/recruitment"},
    "IB": {"full_name": "Intelligence Bureau â€” MHA", "website": "https://mha.gov.in", "career_url": "https://mha.gov.in/en/commentsbox/recruitment"},
    "CBI": {"full_name": "Central Bureau of Investigation", "website": "https://cbi.gov.in", "career_url": "https://cbi.gov.in/recruitment.php"},
    "DRDO": {"full_name": "DRDO â€” CEPTAM", "website": "https://drdo.gov.in", "career_url": "https://ceptam.drdo.gov.in"},
    "ISRO": {"full_name": "Indian Space Research Organisation", "website": "https://isro.gov.in", "career_url": "https://isro.gov.in/careers.html"},
    "BARC": {"full_name": "Bhabha Atomic Research Centre", "website": "https://barc.gov.in", "career_url": "https://www.barc.gov.in/careers/"},
    "CSIR": {"full_name": "Council of Scientific & Industrial Research", "website": "https://www.csir.res.in", "career_url": "https://csirhrdg.res.in/"},
    "ICMR": {"full_name": "Indian Council of Medical Research", "website": "https://icmr.gov.in", "career_url": "https://main.icmr.nic.in/content/recruitment"},
    "ICAR": {"full_name": "Indian Council of Agricultural Research", "website": "https://icar.org.in", "career_url": "https://icar.org.in/content/recruitment"},
    "NABARD": {"full_name": "NABARD", "website": "https://nabard.org", "career_url": "https://www.nabard.org/careers.aspx"},
    "SEBI": {"full_name": "Securities and Exchange Board of India", "website": "https://sebi.gov.in", "career_url": "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecruit=yes"},
    "ONGC": {"full_name": "ONGC", "website": "https://ongcindia.com", "career_url": "https://ongcindia.com/web/eng/careers"},
    "NTPC_PSU": {"full_name": "NTPC Ltd", "website": "https://ntpc.co.in", "career_url": "https://careers.ntpccareers.com"},
    "BHEL": {"full_name": "BHEL", "website": "https://bhel.com", "career_url": "https://careers.bhel.in"},
    "BEL": {"full_name": "Bharat Electronics Ltd", "website": "https://bel-india.in", "career_url": "https://bel-india.in/recruitment"},
    "HAL": {"full_name": "Hindustan Aeronautics Ltd", "website": "https://hal-india.co.in", "career_url": "https://hal-india.co.in/M_Careers.aspx"},
    "SAIL": {"full_name": "Steel Authority of India Ltd", "website": "https://sail.co.in", "career_url": "https://sail.co.in/en/careers"},
    "LIC": {"full_name": "Life Insurance Corporation", "website": "https://licindia.in", "career_url": "https://licindia.in/Home/Careers"},
    "ESIC": {"full_name": "ESIC", "website": "https://esic.in", "career_url": "https://esic.in/recruitment/"},
    "EPFO": {"full_name": "EPFO", "website": "https://epfindia.gov.in", "career_url": "https://www.epfindia.gov.in/site_en/Recruitment.php"},
    "FCI": {"full_name": "Food Corporation of India", "website": "https://fci.gov.in", "career_url": "https://fci.gov.in/recruitments.php"},
    "KVS": {"full_name": "Kendriya Vidyalaya Sangathan", "website": "https://kvsangathan.nic.in", "career_url": "https://kvsangathan.nic.in/RecruitmentNode"},
    "NVS": {"full_name": "Navodaya Vidyalaya Samiti", "website": "https://navodaya.gov.in", "career_url": "https://navodaya.gov.in/nvs/en/Recruitment1"},
    "AIIMS": {"full_name": "AIIMS", "website": "https://aiimsexams.ac.in", "career_url": "https://aiimsexams.ac.in"},
    "RRB": {"full_name": "Railway Recruitment Boards", "website": "https://indianrailways.gov.in",
            "career_url": "https://indianrailways.gov.in/railwayboard/view_section.jsp?lang=0&id=0,1,304,366,533"},
    "RPF": {"full_name": "Railway Protection Force", "website": "https://rpf.indianrailways.gov.in",
            "career_url": "https://rpf.indianrailways.gov.in/view_section.jsp?lang=0&id=0,5,268"},
}
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STATE PSC PORTALS â€” 28 states + Delhi + J&K
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
STATE_PSC_PORTALS: dict[str, dict] = {
    "Andhra_Pradesh": {"psc_name": "APPSC", "psc_url": "https://psc.ap.gov.in", "career_url": "https://psc.ap.gov.in/APPSC/Default/notifications.aspx", "police_url": "https://slprb.ap.gov.in", "subordinate_url": "https://appsc.gov.in"},
    "Arunachal_Pradesh": {"psc_name": "APPSC-AR", "psc_url": "https://appsc.gov.in", "career_url": "https://appsc.gov.in/notifications", "police_url": None, "subordinate_url": None},
    "Assam": {"psc_name": "APSC", "psc_url": "https://apsc.nic.in", "career_url": "https://apsc.nic.in/Advertisement.aspx", "police_url": "https://slprbassam.in", "subordinate_url": "https://sebaonline.org"},
    "Bihar": {"psc_name": "BPSC", "psc_url": "https://bpsc.bih.nic.in", "career_url": "https://onlinebpsc.bihar.gov.in", "police_url": "https://csbc.bih.nic.in", "subordinate_url": "https://bssc.bihar.gov.in"},
    "Chhattisgarh": {"psc_name": "CGPSC", "psc_url": "https://psc.cg.gov.in", "career_url": "https://psc.cg.gov.in/Notifications.html", "police_url": "https://cgpolice.gov.in", "subordinate_url": "https://vyapam.cgstate.gov.in"},
    "Goa": {"psc_name": "GPSC-Goa", "psc_url": "https://gpsc.goa.gov.in", "career_url": "https://gpsc.goa.gov.in/notifications", "police_url": None, "subordinate_url": None},
    "Gujarat": {"psc_name": "GPSC", "psc_url": "https://gpsc.gujarat.gov.in", "career_url": "https://gpsc.gujarat.gov.in/CurrentNotifications.aspx", "police_url": "https://ojas.gujarat.gov.in", "subordinate_url": "https://gsssb.gujarat.gov.in"},
    "Haryana": {"psc_name": "HPSC", "psc_url": "https://hpsc.gov.in", "career_url": "https://hpsc.gov.in/Adv_Files_HF/", "police_url": "https://hssc.gov.in", "subordinate_url": "https://hssc.gov.in"},
    "Himachal_Pradesh": {"psc_name": "HPPSC", "psc_url": "https://hppsc.hp.gov.in", "career_url": "https://hppsc.hp.gov.in/hppsc/notifications", "police_url": "https://hppolice.gov.in", "subordinate_url": "https://hpsssb.hp.gov.in"},
    "Jharkhand": {"psc_name": "JPSC", "psc_url": "https://jpsc.gov.in", "career_url": "https://jpsc.gov.in/newsnotificationdisplay", "police_url": "https://jhpolice.gov.in", "subordinate_url": "https://jssc.nic.in"},
    "Karnataka": {"psc_name": "KPSC", "psc_url": "https://kpsc.kar.nic.in", "career_url": "https://kpsc.kar.nic.in/recruitment/list", "police_url": "https://ksp.gov.in", "subordinate_url": None},
    "Kerala": {"psc_name": "Kerala PSC", "psc_url": "https://keralapsc.gov.in", "career_url": "https://www.keralapsc.gov.in/notification", "police_url": None, "subordinate_url": None},
    "Madhya_Pradesh": {"psc_name": "MPPSC", "psc_url": "https://mppsc.mp.gov.in", "career_url": "https://mppsc.mp.gov.in/en-us/Examination", "police_url": "https://mppolice.gov.in", "subordinate_url": "https://peb.mp.gov.in"},
    "Maharashtra": {"psc_name": "MPSC", "psc_url": "https://mpsc.gov.in", "career_url": "https://mpsc.gov.in/examinations", "police_url": "https://mahapolice.gov.in", "subordinate_url": "https://maharecruitment.org"},
    "Manipur": {"psc_name": "Manipur PSC", "psc_url": "https://mpscmanipur.gov.in", "career_url": "https://mpscmanipur.gov.in", "police_url": None, "subordinate_url": None},
    "Meghalaya": {"psc_name": "Meghalaya PSC", "psc_url": "https://mpsc.nic.in", "career_url": "https://mpsc.nic.in/advertisements.html", "police_url": None, "subordinate_url": None},
    "Mizoram": {"psc_name": "Mizoram PSC", "psc_url": "https://mpsc.mizoram.gov.in", "career_url": "https://mpsc.mizoram.gov.in/page/notifications", "police_url": None, "subordinate_url": None},
    "Nagaland": {"psc_name": "Nagaland PSC", "psc_url": "https://npsc.gov.in", "career_url": "https://npsc.gov.in/notifications", "police_url": None, "subordinate_url": None},
    "Odisha": {"psc_name": "OPSC", "psc_url": "https://opsc.gov.in", "career_url": "https://opsc.gov.in/Advertisements.aspx", "police_url": "https://odishapolice.gov.in", "subordinate_url": "https://ossc.gov.in"},
    "Punjab": {"psc_name": "PPSC", "psc_url": "https://ppsc.gov.in", "career_url": "https://ppsc.gov.in/RecruitmentNotification.aspx", "police_url": "https://punjabpolice.gov.in", "subordinate_url": "https://sssb.punjab.gov.in"},
    "Rajasthan": {"psc_name": "RPSC", "psc_url": "https://rpsc.rajasthan.gov.in", "career_url": "https://rpsc.rajasthan.gov.in/Recruitment.aspx", "police_url": "https://police.rajasthan.gov.in", "subordinate_url": "https://rsmssb.rajasthan.gov.in"},
    "Sikkim": {"psc_name": "Sikkim PSC", "psc_url": "https://spsc.gov.in", "career_url": "https://spsc.gov.in/notifications.html", "police_url": None, "subordinate_url": None},
    "Tamil_Nadu": {"psc_name": "TNPSC", "psc_url": "https://tnpsc.gov.in", "career_url": "https://www.tnpsc.gov.in/Notifications.html", "police_url": "https://tnusrb.tn.gov.in", "subordinate_url": None},
    "Telangana": {"psc_name": "TSPSC", "psc_url": "https://tspsc.gov.in", "career_url": "https://tspsc.gov.in/Notifications.aspx", "police_url": "https://tsslprb.gov.in", "subordinate_url": None},
    "Tripura": {"psc_name": "Tripura PSC", "psc_url": "https://tpsc.tripura.gov.in", "career_url": "https://tpsc.tripura.gov.in/recruitment", "police_url": None, "subordinate_url": None},
    "Uttar_Pradesh": {"psc_name": "UPPSC", "psc_url": "https://uppsc.up.nic.in", "career_url": "https://uppsc.up.nic.in/CandidateNotifications.aspx", "police_url": "https://uppbpb.gov.in", "subordinate_url": "https://upsssc.gov.in"},
    "Uttarakhand": {"psc_name": "UKPSC", "psc_url": "https://ukpsc.gov.in", "career_url": "https://ukpsc.gov.in/recruitments", "police_url": None, "subordinate_url": "https://sssc.uk.gov.in"},
    "West_Bengal": {"psc_name": "WBPSC", "psc_url": "https://pscwbapplication.in", "career_url": "https://pscwbapplication.in/notice/index.html", "police_url": "https://wbpolice.gov.in", "subordinate_url": "https://wbssc.gov.in"},
    "Delhi": {"psc_name": "DSSSB", "psc_url": "https://dsssb.delhi.gov.in", "career_url": "https://dsssb.delhi.gov.in/ddssb/recruitment", "police_url": "https://www.delhipolice.gov.in", "subordinate_url": None},
    "Jammu_Kashmir": {"psc_name": "JKSSB", "psc_url": "https://jkssb.nic.in", "career_url": "https://jkssb.nic.in/notifications", "police_url": "https://jkpolice.gov.in", "subordinate_url": None},
}
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# RRB BOARDS â€” 21 Regional Railway Boards
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
RRB_BOARDS = [
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
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# GENERIC SELECTORS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
GENERIC_SELECTORS = {
    "exam_list": "table.table tbody tr, table tbody tr, div.notification, li.notification-item, div.card-body",
    "exam_link": "a[href*='.pdf'], a[href*='notification'], a[href*='recruitment'], a[href*='exam']",
    "exam_name": "td:first-child a, h4, h5, div.card-title, div.title, td:nth-child(1)",
    "date_col": "td:nth-child(2), td:nth-child(3), span.date",
}
PSU_SELECTORS = {
    "exam_list": "table.table tbody tr, div.career-listing li, div.job-listing",
    "exam_link": "a[href*='recruitment'], a[href*='career'], a[href*='.pdf']",
    "exam_name": "td:first-child, li a, div.job-title",
    "date_col": "td:nth-child(2), td:nth-child(3), span.date",
}
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# BUILD EXAM_PORTAL_SOURCES â€” auto-generated list
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def build_exam_portal_sources() -> list[ExamPortalSource]:
    """Generate the complete list of ExamPortalSource entries."""
    sources: list[ExamPortalSource] = []
    # â”€â”€ Group A: UPSC â”€â”€
    sources.append(ExamPortalSource(body_code="UPSC", name="UPSC_Active_Exams", base_url="https://upsc.gov.in",
        exam_category="Civil_Services", priority=1, notification_urls=["https://upsc.gov.in/examinations/active-examinations", "https://upsc.gov.in/examinations/notifications"],
        selectors={"exam_list": "table.views-table tbody tr, div.field-content a", "exam_link": "td a[href]", "exam_name": "td.views-field-title a"}))
    sources.append(ExamPortalSource(body_code="UPSC", name="UPSC_NDA_CDS", base_url="https://upsc.gov.in",
        exam_category="Defence", priority=1, notification_urls=["https://upsc.gov.in/examinations/active-examinations"]))
    sources.append(ExamPortalSource(body_code="UPSC", name="UPSC_CAPF", base_url="https://upsc.gov.in",
        exam_category="Police", priority=1, notification_urls=["https://upsc.gov.in/examinations/active-examinations"]))
    # â”€â”€ Group B: SSC â”€â”€
    sources.append(ExamPortalSource(body_code="SSC", name="SSC_All_Exams", base_url="https://ssc.gov.in",
        exam_category="SSC", priority=1, notification_urls=["https://ssc.gov.in/portal/exams", "https://ssc.gov.in/portal/notifications", "https://ssc.gov.in/portal/latestnews"],
        selectors={"exam_list": "div.ssc-exam-card, table.table tbody tr, div.card-body", "exam_link": "a[href*='advertisement'], a[href*='exam']", "exam_name": "h4, h5, td:first-child, div.card-title"}))
    # â”€â”€ Group C: IBPS â”€â”€
    sources.append(ExamPortalSource(body_code="IBPS", name="IBPS_All_CRP", base_url="https://www.ibps.in",
        exam_category="Banking", priority=1, notification_urls=["https://www.ibps.in/crp-examination-schedule/", "https://www.ibps.in/notification/"]))
    # â”€â”€ Group D: SBI / RBI â”€â”€
    sources.append(ExamPortalSource(body_code="SBI", name="SBI_Recruitment", base_url="https://sbi.co.in",
        exam_category="Banking", priority=1, notification_urls=["https://sbi.co.in/web/careers/recruitment-in-sbi"]))
    sources.append(ExamPortalSource(body_code="RBI", name="RBI_Recruitment", base_url="https://rbi.org.in",
        exam_category="Banking", priority=1, notification_urls=["https://rbi.org.in/Scripts/Opportunities.aspx"],
        rss_url="https://rbi.org.in/rss/RSSFeed.aspx?Type=Others"))
    # â”€â”€ Group E: NTA â”€â”€
    sources.append(ExamPortalSource(body_code="NTA", name="NTA_All_Exams", base_url="https://nta.ac.in",
        exam_category="Engineering", priority=1, notification_urls=["https://nta.ac.in/Examinations"]))
    sources.append(ExamPortalSource(body_code="NTA", name="NTA_JEE_Main", base_url="https://jeemain.nta.ac.in",
        exam_category="Engineering", priority=1, notification_urls=["https://jeemain.nta.ac.in"]))
    sources.append(ExamPortalSource(body_code="NTA", name="NTA_NEET_UG", base_url="https://neet.nta.ac.in",
        exam_category="Medical", priority=1, notification_urls=["https://neet.nta.ac.in"]))
    sources.append(ExamPortalSource(body_code="NTA", name="NTA_UGC_NET", base_url="https://ugcnet.nta.ac.in",
        exam_category="Teaching", priority=1, notification_urls=["https://ugcnet.nta.ac.in"]))
    sources.append(ExamPortalSource(body_code="NTA", name="NTA_CUET_UG", base_url="https://cuet.nta.nic.in",
        exam_category="Engineering", priority=1, notification_urls=["https://cuet.nta.nic.in"]))
    # â”€â”€ Group F: Defence â”€â”€
    sources.append(ExamPortalSource(body_code="ARMY", name="Army_All_Recruitment", base_url="https://joinindianarmy.nic.in",
        exam_category="Defence", priority=1, notification_urls=["https://joinindianarmy.nic.in/english/Registration.htm"]))
    sources.append(ExamPortalSource(body_code="AIRFORCE", name="Airforce_AFCAT", base_url="https://afcat.cdac.in",
        exam_category="Defence", priority=1, notification_urls=["https://afcat.cdac.in"]))
    sources.append(ExamPortalSource(body_code="AIRFORCE", name="Airforce_Airmen", base_url="https://airmenselection.cdac.in",
        exam_category="Defence", priority=1, notification_urls=["https://airmenselection.cdac.in"]))
    sources.append(ExamPortalSource(body_code="NAVY", name="Navy_All_Recruitment", base_url="https://joinindiannavy.gov.in",
        exam_category="Defence", priority=1, notification_urls=["https://joinindiannavy.gov.in/en/pages/latest-news"]))
    sources.append(ExamPortalSource(body_code="COAST_GUARD", name="CoastGuard_Navik", base_url="https://joinindiancoastguard.gov.in",
        exam_category="Defence", priority=1, notification_urls=["https://joinindiancoastguard.gov.in/cgept/index.html"]))
    # â”€â”€ Group G: Paramilitary â”€â”€
    for code, url in [("BSF", "https://bsf.gov.in/recruitment.html"), ("CRPF", "https://crpf.gov.in/recruitment.htm"),
                       ("CISF", "https://cisf.gov.in/recruitment"), ("SSB_FORCE", "https://ssb.nic.in"),
                       ("ITBP", "https://itbpolice.nic.in"), ("ASSAM_RIFLES", "https://assamrifles.gov.in/Recruitments"),
                       ("NSG", "https://nsg.gov.in/recruitment")]:
        sources.append(ExamPortalSource(body_code=code, name=f"{code}_Recruitment", base_url=url,
            exam_category="Police", priority=1, notification_urls=[url]))
    # â”€â”€ Group H: Railways (21 RRBs) â”€â”€
    for rrb_name, rrb_url in RRB_BOARDS:
        sources.append(ExamPortalSource(
            body_code="RRB", name=rrb_name, base_url=rrb_url,
            exam_category="Railway", priority=1,
            notification_urls=[rrb_url],
            selectors={"exam_list": "table tbody tr, div.notification, li.notification-item",
                        "notification_link": "a[href*='.pdf'], a[href*='notification']",
                        "exam_name": "td:nth-child(1) a, div.title"},
        ))
    sources.append(ExamPortalSource(body_code="RPF", name="RPF_Constable_SI", base_url="https://rpf.indianrailways.gov.in",
        exam_category="Railway", priority=1, notification_urls=["https://rpf.indianrailways.gov.in/view_section.jsp?lang=0&id=0,5,268"]))
    # â”€â”€ Group I: Intelligence â”€â”€
    sources.append(ExamPortalSource(body_code="IB", name="IB_ACIO_JIO", base_url="https://mha.gov.in",
        exam_category="Intelligence", priority=1, notification_urls=["https://mha.gov.in/en/commentsbox/recruitment"]))
    sources.append(ExamPortalSource(body_code="CBI", name="CBI_Recruitment", base_url="https://cbi.gov.in",
        exam_category="Intelligence", priority=1, notification_urls=["https://cbi.gov.in/recruitment.php"]))
    # â”€â”€ Group J: Science & Research PSUs â”€â”€
    for code, url, cat in [("DRDO", "https://ceptam.drdo.gov.in", "PSU"), ("ISRO", "https://isro.gov.in/careers.html", "PSU"),
                            ("BARC", "https://www.barc.gov.in/careers/", "PSU"), ("CSIR", "https://csirhrdg.res.in/", "PSU"),
                            ("ICMR", "https://main.icmr.nic.in/content/recruitment", "PSU"),
                            ("ICAR", "https://icar.org.in/content/recruitment", "Agriculture")]:
        sources.append(ExamPortalSource(body_code=code, name=f"{code}_Careers", base_url=url,
            exam_category=cat, priority=1, notification_urls=[url], selectors=PSU_SELECTORS))
    # â”€â”€ Group K: Energy & Manufacturing PSUs â”€â”€
    for code, url in [("ONGC", "https://ongcindia.com/web/eng/careers"), ("NTPC_PSU", "https://careers.ntpccareers.com"),
                       ("BHEL", "https://careers.bhel.in"), ("BEL", "https://bel-india.in/recruitment"),
                       ("HAL", "https://hal-india.co.in/M_Careers.aspx"), ("SAIL", "https://sail.co.in/en/careers")]:
        sources.append(ExamPortalSource(body_code=code, name=f"{code}_Recruitment", base_url=url,
            exam_category="PSU", priority=2, notification_urls=[url], selectors=PSU_SELECTORS))
    # â”€â”€ Group L: Banking & Finance â”€â”€
    for code, url in [("NABARD", "https://www.nabard.org/careers.aspx"), ("SEBI", "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecruit=yes")]:
        sources.append(ExamPortalSource(body_code=code, name=f"{code}_Recruitment", base_url=url,
            exam_category="Banking", priority=1, notification_urls=[url]))
    # â”€â”€ Group M: Insurance â”€â”€
    sources.append(ExamPortalSource(body_code="LIC", name="LIC_AAO_ADO", base_url="https://licindia.in",
        exam_category="Insurance", priority=2, notification_urls=["https://licindia.in/Home/Careers"]))
    # â”€â”€ Group N: Education / Teaching â”€â”€
    for code, url, cat in [("KVS", "https://kvsangathan.nic.in/RecruitmentNode", "Teaching"),
                            ("NVS", "https://navodaya.gov.in/nvs/en/Recruitment1", "Teaching"),
                            ("AIIMS", "https://aiimsexams.ac.in", "Medical")]:
        sources.append(ExamPortalSource(body_code=code, name=f"{code}_Recruitment", base_url=url,
            exam_category=cat, priority=2, notification_urls=[url]))
    # â”€â”€ Group O: Labour & Food â”€â”€
    for code, url in [("ESIC", "https://esic.in/recruitment/"), ("EPFO", "https://www.epfindia.gov.in/site_en/Recruitment.php"),
                       ("FCI", "https://fci.gov.in/recruitments.php")]:
        sources.append(ExamPortalSource(body_code=code, name=f"{code}_Recruitment", base_url=url,
            exam_category="Other_Central", priority=2, notification_urls=[url]))
    # â”€â”€ Group P: State PSCs (auto-generated) â”€â”€
    for state_name, portal in STATE_PSC_PORTALS.items():
        code_prefix = state_name.upper()[:4]
        # PSC
        sources.append(ExamPortalSource(
            body_code=f"PSC_{code_prefix}", name=f"{state_name}_PSC",
            base_url=portal["psc_url"],
            exam_category="State_PSC", exam_level="State", state=state_name,
            priority=2, notification_urls=[portal["career_url"]],
        ))
        # State Police
        if portal.get("police_url"):
            sources.append(ExamPortalSource(
                body_code=f"POL_{code_prefix}", name=f"{state_name}_Police_Recruitment",
                base_url=portal["police_url"],
                exam_category="State_Police", exam_level="State", state=state_name,
                priority=2, notification_urls=[portal["police_url"]],
            ))
        # State Subordinate
        if portal.get("subordinate_url") and portal["subordinate_url"] != portal["psc_url"]:
            sources.append(ExamPortalSource(
                body_code=f"SSB_{code_prefix}", name=f"{state_name}_Subordinate_Services",
                base_url=portal["subordinate_url"],
                exam_category="State_Subordinate", exam_level="State", state=state_name,
                priority=3, notification_urls=[portal["subordinate_url"]],
            ))
    return sources
# Pre-built list (imported by other modules)
EXAM_PORTAL_SOURCES: list[ExamPortalSource] = build_exam_portal_sources()
