# ðŸ† GovScheme SuperAgent â€” OpenClaw Buildathon Entry
## Zero to 700+ Government Schemes in 8 Hours
A multi-agent system that crawls across **Central, State, and Union Territory** government websites to discover, classify, and store **every scholarship, grant, startup fund, and welfare scheme** in India â€” organized into intelligent folder hierarchies.
---
## ðŸŽ¯ What It Does
1. **Discovery Agents** crawl 50+ government portals (myScheme.gov.in, scholarships.gov.in, Startup India, state portals, ministry websites)
2. **Classification Agent** uses LLM to categorize each scheme by level (Central/State/UT), sector (Education, Agriculture, Fisheries, MSME, etc.), and type (Scholarship, Grant, Startup Fund, Subsidy)
3. **Storage Agent** organizes everything into structured folders with downloaded PDFs, guidelines, forms, and metadata
4. **Deduplication Agent** ensures no duplicates across sources
5. **Dashboard** provides real-time monitoring of crawl progress
## ðŸ“Š Architecture
```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    ORCHESTRATOR (CEO)                     â”‚
â”‚  Coordinates all agents, manages queue, tracks progress  â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ DISCOVERYâ”‚ CLASSIFY â”‚ STORAGE  â”‚  DEDUP   â”‚  DASHBOARD  â”‚
â”‚  AGENTS  â”‚  AGENT   â”‚  AGENT   â”‚  AGENT   â”‚   AGENT     â”‚
â”‚ (Devs)   â”‚ (BA)     â”‚ (PM)     â”‚ (QA)     â”‚  (Growth)   â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚              SHARED MESSAGE QUEUE (Redis/In-Memory)       â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                    DATA LAYER                             â”‚
â”‚  SQLite DB  â”‚  File System  â”‚  JSON Metadata  â”‚  PDFs    â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```
## ðŸ—‚ï¸ Folder Structure Output
```
output/
â”œâ”€â”€ Central/
â”‚   â”œâ”€â”€ Education/
â”‚   â”‚   â”œâ”€â”€ Central_Sector_Scholarship_CSSS/
â”‚   â”‚   â”‚   â”œâ”€â”€ metadata.json
â”‚   â”‚   â”‚   â”œâ”€â”€ guidelines.pdf
â”‚   â”‚   â”‚   â”œâ”€â”€ application_form.pdf
â”‚   â”‚   â”‚   â””â”€â”€ scheme_details.md
â”‚   â”‚   â”œâ”€â”€ PM_Research_Fellowship/
â”‚   â”‚   â””â”€â”€ ...
â”‚   â”œâ”€â”€ MSME/
â”‚   â”œâ”€â”€ Agriculture/
â”‚   â”œâ”€â”€ Science_Technology/
â”‚   â”œâ”€â”€ Women_Child_Development/
â”‚   â”œâ”€â”€ Social_Justice/
â”‚   â”œâ”€â”€ Tribal_Affairs/
â”‚   â””â”€â”€ Startup/
â”œâ”€â”€ State/
â”‚   â”œâ”€â”€ Tamil_Nadu/
â”‚   â”‚   â”œâ”€â”€ Fisheries/
â”‚   â”‚   â”œâ”€â”€ Education/
â”‚   â”‚   â”œâ”€â”€ Agriculture/
â”‚   â”‚   â””â”€â”€ Startup/
â”‚   â”œâ”€â”€ Karnataka/
â”‚   â”œâ”€â”€ Maharashtra/
â”‚   â”œâ”€â”€ Kerala/
â”‚   â””â”€â”€ ... (28 states)
â”œâ”€â”€ Union_Territory/
â”‚   â”œâ”€â”€ Delhi/
â”‚   â”œâ”€â”€ Puducherry/
â”‚   â””â”€â”€ ... (8 UTs)
â””â”€â”€ reports/
    â”œâ”€â”€ crawl_summary.json
    â”œâ”€â”€ sector_distribution.json
    â””â”€â”€ duplicate_report.json
```
## ðŸš€ Quick Start
```bash
# Install dependencies
pip install -r requirements.txt
# Set environment variables
export ANTHROPIC_API_KEY="your-key"  # or OPENAI_API_KEY
# Run the full agent pipeline
python -m src.orchestrator --mode full
# Run specific agents
python -m src.orchestrator --mode discover   # Discovery only
python -m src.orchestrator --mode classify   # Classification only
python -m src.orchestrator --mode dashboard  # Launch dashboard
```
## ðŸ”‘ Key Data Sources
| Source | URL | Expected Schemes |
|--------|-----|-----------------|
| myScheme Portal | myscheme.gov.in | 2300+ |
| National Scholarship Portal | scholarships.gov.in | 150+ |
| Startup India | startupindia.gov.in | 80+ |
| API Setu | apisetu.gov.in | API access |
| State Portals (28) | Various | 1800+ |
| Ministry Websites (30+) | Various | 500+ |
## ðŸ’¡ Why This Wins
- **Real utility**: Solves a genuine problem â€” citizens struggle to find schemes they're eligible for
- **Scale**: 700+ schemes organized and downloadable
- **Agent architecture**: True multi-agent coordination, not just sequential scripts
- **LLM-powered classification**: Intelligent categorization that understands sector context
- **Production-ready**: Resumable crawls, deduplication, error handling
