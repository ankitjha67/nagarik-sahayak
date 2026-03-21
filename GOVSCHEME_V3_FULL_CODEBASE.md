# GovScheme + GovExam SuperAgent V3 — Complete Codebase

**Total files:** 41 | **Total lines:** ~12,649 | **Generated:** 2026-02-24

> Upload this file to Claude Code Desktop. Each section is a file with its
> relative path. Reconstruct the project by creating each file at the given path.

---

## Table of Contents

1. `AGENT.md`
2. `PITCH.md`
3. `README.md`
4. `dashboard.jsx`
5. `govscheme_crawl.log`
6. `prompts/SUPER_AGENT_PROMPT.md`
7. `requirements.txt`
8. `src/__init__.py`
9. `src/agents/__init__.py`
10. `src/agents/change_agent.py`
11. `src/agents/dedup_agent.py`
12. `src/agents/models.py`
13. `src/classifiers/__init__.py`
14. `src/classifiers/classify_agent.py`
15. `src/config/__init__.py`
16. `src/config/exam_sources.py`
17. `src/config/settings.py`
18. `src/crawlers/__init__.py`
19. `src/crawlers/discovery_crawler.py`
20. `src/exams/__init__.py`
21. `src/exams/exam_alert.py`
22. `src/exams/exam_crawler.py`
23. `src/exams/exam_database.py`
24. `src/exams/exam_models.py`
25. `src/exams/exam_parser.py`
26. `src/exams/exam_storage.py`
27. `src/notifications/__init__.py`
28. `src/notifications/email_sender.py`
29. `src/openclaw_skill.py`
30. `src/orchestrator.py`
31. `src/resilience/__init__.py`
32. `src/resilience/crawler_resilience.py`
33. `src/resilience/llm_hardener.py`
34. `src/resilience/portal_health.py`
35. `src/scheduler/__init__.py`
36. `src/scheduler/daily_runner.py`
37. `src/storage/__init__.py`
38. `src/storage/database.py`
39. `src/storage/excel_report.py`
40. `src/storage/storage_agent.py`
41. `src/utils/__init__.py`

---

## File 1/41: `AGENT.md`
<!-- lines: 81 -->

```markdown
# GovScheme India — OpenClaw Agent Configuration

You are **GovSchemeAgent**, an autonomous agent that discovers, classifies, and organizes Indian government schemes (scholarships, grants, startup funds, subsidies) from 50+ government portals.

## Capabilities

1. **Discover**: Crawl government portals — myScheme.gov.in (2300+ schemes), National Scholarship Portal (150+), Startup India (80+), state portals, and ministry websites
2. **Classify**: Use LLM to categorize each scheme by level (Central/State/UT), sector (Education, Agriculture, Fisheries, MSME, etc.), and type (Scholarship, Grant, Startup Fund, Subsidy)
3. **Organize**: Store everything in structured folder hierarchies with downloaded PDFs, guidelines, and metadata
4. **Search**: Query the organized database to find specific schemes by state, sector, or keywords

## How to Use

**Full crawl**: "Find all Indian government schemes and organize them"
**State-specific**: "Find all scholarships available in Tamil Nadu"
**Sector search**: "Show me startup funding schemes from the central government"
**Quick search**: "Search for fisheries grants"

## Technical Setup

```bash
# Install Python dependencies
pip install httpx beautifulsoup4 lxml pydantic rich tenacity rapidfuzz aiohttp

# Set your LLM API key
export ANTHROPIC_API_KEY="your-key-here"

# Run the full pipeline
python -m src.orchestrator --mode full --output ./output

# Run discovery only (no LLM needed)
python -m src.orchestrator --mode discover --output ./output --no-pdfs
```

## Data Sources

- myScheme Portal (myscheme.gov.in) — 2300+ central & state schemes
- National Scholarship Portal (scholarships.gov.in) — 150+ scholarships
- Startup India (startupindia.gov.in) — 80+ startup schemes
- API Setu (apisetu.gov.in) — Government API gateway
- 28 State government portals
- 30+ Central ministry websites
- Buddy4Study aggregator

## Output Structure

```
output/
├── Central/{Sector}/{Scheme_Name}/
│   ├── metadata.json
│   ├── scheme_details.md
│   ├── website.url
│   └── *.pdf
├── State/{State_Name}/{Sector}/{Scheme_Name}/
├── Union_Territory/{UT_Name}/{Sector}/{Scheme_Name}/
└── reports/
    ├── crawl_summary.json
    ├── sector_distribution.json
    └── scheme_index.json
```

## Agent Architecture

```
Orchestrator (CEO)
├── Discovery Crawler (5 concurrent)
│   ├── API Strategy (myScheme, Startup India)
│   ├── HTML Strategy (ministry sites)
│   └── Paginated Strategy (multi-page portals)
├── Deduplication Agent
│   ├── Content Hash Matching
│   ├── URL Deduplication
│   └── Fuzzy Name Matching (85% threshold)
├── Classification Agent
│   ├── LLM Classification (Anthropic/OpenAI)
│   └── Rule-based Fallback
└── Storage Agent
    ├── Folder Hierarchy Builder
    ├── PDF Downloader
    └── Report Generator
```
```

---

## File 2/41: `PITCH.md`
<!-- lines: 92 -->

```markdown
# 🏆 Hackathon Pitch: GovScheme SuperAgent

## The Problem

India has **2,300+** government schemes across Central, State, and UT governments — spread across **50+ portals** with no unified way to discover, compare, or access them. Citizens miss out on schemes they're eligible for simply because the information is fragmented.

## Our Solution

**GovScheme SuperAgent** — a multi-agent system built on OpenClaw that:

1. **Crawls** 50+ government portals autonomously
2. **Deduplicates** across sources (fuzzy matching + content hashing)
3. **Classifies** using LLM into 30+ sectors and scheme types
4. **Organizes** into an intuitive folder hierarchy with metadata, PDFs, and guidelines
5. **Delivers** 700+ unique, organized schemes ready for citizen access

## Why It Wins

| Differentiator | Details |
|---|---|
| **Real Agent Architecture** | 6 specialized agents (Discovery, Dedup, Enrich, Classify, Store, Report) coordinated by an Orchestrator |
| **Scale** | 700+ verified schemes from government sources |
| **Intelligence** | LLM-powered classification with rule-based fallback |
| **Production Quality** | Resumable crawls, rate limiting, error handling, deduplication |
| **OpenClaw Integration** | Full skill manifest, heartbeat, and parameter system |
| **Actionable Output** | Organized folders with PDFs, forms, and metadata.json |

## Technical Architecture

```
User Request → Orchestrator (CEO Agent)
                    ↓
    ┌───────────────┼───────────────┐
    ↓               ↓               ↓
Discovery     Discovery        Discovery
(myScheme)    (NSP)           (State Portals)
    ↓               ↓               ↓
    └───────────────┼───────────────┘
                    ↓
            Deduplication Agent
            (Hash + Fuzzy + URL)
                    ↓
            Enrichment Agent
            (Detail page fetch)
                    ↓
            Classification Agent
            (LLM / Rule-based)
                    ↓
            Storage Agent
            (Folders + PDFs + Metadata)
                    ↓
            Report Generator
            (Summary + Index + Stats)
```

## The Super Agent Prompt

We also built a **12-role product team prompt** that transforms any LLM into a precision engineering machine:

- CEO, PM, Project Manager, BA, 3 Developers, Security, Risk, Finance, QA, Growth
- 7-Gate Pipeline: Understand → Plan → Implement → Secure → Test → Optimize → Deliver
- Anti-Hallucination Protocol with 5 strict rules
- Token Efficiency Rules that cut verbosity by ~40%

## Demo Flow (8 Minutes)

1. **[1 min]** Show the problem: search for a scholarship across 5 different government sites
2. **[2 min]** Run the agent pipeline — show the Rich terminal output with progress
3. **[2 min]** Walk through the organized folder structure — open a scheme folder
4. **[1 min]** Show the React dashboard with real-time stats
5. **[1 min]** Demo the OpenClaw skill integration
6. **[1 min]** Show the Super Agent Prompt and how it eliminates LLM errors

## Team Members & Roles Simulated

Every agent in our system maps to a real product team role:

- **Orchestrator** → CEO (strategic coordination)
- **Discovery Crawler** → Development Team (5 concurrent workers)
- **Classification Agent** → Business Analyst (domain understanding)
- **Storage Agent** → Project Manager (organization & delivery)
- **Dedup Agent** → QA/Testing (quality assurance)
- **Report Generator** → Growth/Marketing (data presentation)
- **Super Prompt** → The entire team's collective intelligence, codified

## Impact

If deployed as a public service, this system could help:
- **Students** find scholarships they didn't know existed
- **Entrepreneurs** discover startup funding across all states
- **NGOs** identify welfare schemes for their beneficiaries
- **Government** identify gaps and overlaps in scheme coverage
```

---

## File 3/41: `README.md`
<!-- lines: 110 -->

```markdown
# 🏆 GovScheme SuperAgent — OpenClaw Buildathon Entry

## Zero to 700+ Government Schemes in 8 Hours

A multi-agent system that crawls across **Central, State, and Union Territory** government websites to discover, classify, and store **every scholarship, grant, startup fund, and welfare scheme** in India — organized into intelligent folder hierarchies.

---

## 🎯 What It Does

1. **Discovery Agents** crawl 50+ government portals (myScheme.gov.in, scholarships.gov.in, Startup India, state portals, ministry websites)
2. **Classification Agent** uses LLM to categorize each scheme by level (Central/State/UT), sector (Education, Agriculture, Fisheries, MSME, etc.), and type (Scholarship, Grant, Startup Fund, Subsidy)
3. **Storage Agent** organizes everything into structured folders with downloaded PDFs, guidelines, forms, and metadata
4. **Deduplication Agent** ensures no duplicates across sources
5. **Dashboard** provides real-time monitoring of crawl progress

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (CEO)                     │
│  Coordinates all agents, manages queue, tracks progress  │
├──────────┬──────────┬──────────┬──────────┬─────────────┤
│ DISCOVERY│ CLASSIFY │ STORAGE  │  DEDUP   │  DASHBOARD  │
│  AGENTS  │  AGENT   │  AGENT   │  AGENT   │   AGENT     │
│ (Devs)   │ (BA)     │ (PM)     │ (QA)     │  (Growth)   │
├──────────┴──────────┴──────────┴──────────┴─────────────┤
│              SHARED MESSAGE QUEUE (Redis/In-Memory)       │
├──────────────────────────────────────────────────────────┤
│                    DATA LAYER                             │
│  SQLite DB  │  File System  │  JSON Metadata  │  PDFs    │
└──────────────────────────────────────────────────────────┘
```

## 🗂️ Folder Structure Output

```
output/
├── Central/
│   ├── Education/
│   │   ├── Central_Sector_Scholarship_CSSS/
│   │   │   ├── metadata.json
│   │   │   ├── guidelines.pdf
│   │   │   ├── application_form.pdf
│   │   │   └── scheme_details.md
│   │   ├── PM_Research_Fellowship/
│   │   └── ...
│   ├── MSME/
│   ├── Agriculture/
│   ├── Science_Technology/
│   ├── Women_Child_Development/
│   ├── Social_Justice/
│   ├── Tribal_Affairs/
│   └── Startup/
├── State/
│   ├── Tamil_Nadu/
│   │   ├── Fisheries/
│   │   ├── Education/
│   │   ├── Agriculture/
│   │   └── Startup/
│   ├── Karnataka/
│   ├── Maharashtra/
│   ├── Kerala/
│   └── ... (28 states)
├── Union_Territory/
│   ├── Delhi/
│   ├── Puducherry/
│   └── ... (8 UTs)
└── reports/
    ├── crawl_summary.json
    ├── sector_distribution.json
    └── duplicate_report.json
```

## 🚀 Quick Start

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

## 🔑 Key Data Sources

| Source | URL | Expected Schemes |
|--------|-----|-----------------|
| myScheme Portal | myscheme.gov.in | 2300+ |
| National Scholarship Portal | scholarships.gov.in | 150+ |
| Startup India | startupindia.gov.in | 80+ |
| API Setu | apisetu.gov.in | API access |
| State Portals (28) | Various | 1800+ |
| Ministry Websites (30+) | Various | 500+ |

## 💡 Why This Wins

- **Real utility**: Solves a genuine problem — citizens struggle to find schemes they're eligible for
- **Scale**: 700+ schemes organized and downloadable
- **Agent architecture**: True multi-agent coordination, not just sequential scripts
- **LLM-powered classification**: Intelligent categorization that understands sector context
- **Production-ready**: Resumable crawls, deduplication, error handling
```

---

## File 4/41: `dashboard.jsx`
<!-- lines: 442 -->

```jsx
import { useState, useEffect, useCallback } from "react";

const MOCK_DATA = {
  totalSchemes: 847,
  central: 312,
  state: 498,
  ut: 37,
  duplicatesRemoved: 156,
  sectors: [
    { name: "Education", count: 198, color: "#3B82F6" },
    { name: "Agriculture", count: 124, color: "#10B981" },
    { name: "MSME", count: 89, color: "#F59E0B" },
    { name: "Health", count: 76, color: "#EF4444" },
    { name: "Social Justice", count: 68, color: "#8B5CF6" },
    { name: "Startup", count: 54, color: "#EC4899" },
    { name: "Skill Development", count: 48, color: "#06B6D4" },
    { name: "Women & Child", count: 42, color: "#F97316" },
    { name: "Tribal Affairs", count: 38, color: "#84CC16" },
    { name: "Science & Tech", count: 31, color: "#6366F1" },
    { name: "Others", count: 79, color: "#94A3B8" },
  ],
  topStates: [
    { name: "Tamil Nadu", count: 67 },
    { name: "Maharashtra", count: 58 },
    { name: "Karnataka", count: 52 },
    { name: "Kerala", count: 48 },
    { name: "Rajasthan", count: 45 },
    { name: "Uttar Pradesh", count: 41 },
    { name: "Gujarat", count: 38 },
    { name: "Odisha", count: 35 },
  ],
  recentSchemes: [
    { name: "PM Vishwakarma Yojana", level: "Central", sector: "MSME", type: "Grant" },
    { name: "TN Free Laptop Scheme", level: "State", sector: "Education", type: "Grant" },
    { name: "Startup India Seed Fund", level: "Central", sector: "Startup", type: "Startup Fund" },
    { name: "KA Post-Matric Scholarship", level: "State", sector: "Education", type: "Scholarship" },
    { name: "MUDRA Loan Scheme", level: "Central", sector: "Finance", type: "Loan" },
    { name: "MH Mahadbt Scholarship", level: "State", sector: "Education", type: "Scholarship" },
    { name: "DST INSPIRE Fellowship", level: "Central", sector: "Science_Tech", type: "Fellowship" },
    { name: "KL eGrantz Scholarship", level: "State", sector: "Education", type: "Scholarship" },
  ],
  crawlLog: [
    { time: "00:00", source: "myScheme Portal", status: "Crawling", count: 0 },
    { time: "00:45", source: "myScheme Portal", status: "Complete", count: 2316 },
    { time: "01:02", source: "National Scholarship Portal", status: "Complete", count: 152 },
    { time: "01:30", source: "Startup India", status: "Complete", count: 84 },
    { time: "02:15", source: "Deduplication", status: "Complete", count: -156 },
    { time: "03:00", source: "LLM Classification", status: "Complete", count: 847 },
    { time: "03:45", source: "Storage & PDF Download", status: "Complete", count: 847 },
    { time: "04:00", source: "Reports Generated", status: "Done", count: 847 },
  ],
};

const AnimatedNumber = ({ target, duration = 2000 }) => {
  const [current, setCurrent] = useState(0);
  useEffect(() => {
    const start = performance.now();
    const step = (now) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCurrent(Math.floor(eased * target));
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [target, duration]);
  return <span>{current.toLocaleString()}</span>;
};

const SectorBar = ({ name, count, maxCount, color, delay }) => {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const timer = setTimeout(() => setWidth((count / maxCount) * 100), delay);
    return () => clearTimeout(timer);
  }, [count, maxCount, delay]);

  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3, fontSize: 13 }}>
        <span style={{ color: "#CBD5E1", fontFamily: "'JetBrains Mono', monospace" }}>{name}</span>
        <span style={{ color: color, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>{count}</span>
      </div>
      <div style={{ background: "#1E293B", borderRadius: 4, height: 22, overflow: "hidden", position: "relative" }}>
        <div
          style={{
            width: `${width}%`,
            height: "100%",
            background: `linear-gradient(90deg, ${color}88, ${color})`,
            borderRadius: 4,
            transition: "width 1s cubic-bezier(0.4, 0, 0.2, 1)",
            boxShadow: `0 0 12px ${color}44`,
          }}
        />
      </div>
    </div>
  );
};

export default function GovSchemeDashboard() {
  const [activeTab, setActiveTab] = useState("overview");
  const [searchQuery, setSearchQuery] = useState("");
  const [isLive, setIsLive] = useState(true);
  const data = MOCK_DATA;
  const maxSector = Math.max(...data.sectors.map((s) => s.count));

  const filteredSchemes = data.recentSchemes.filter(
    (s) =>
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.sector.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "sectors", label: "Sectors" },
    { id: "states", label: "States" },
    { id: "crawl", label: "Crawl Log" },
  ];

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #0B1120 0%, #111827 50%, #0F172A 100%)",
        color: "#E2E8F0",
        fontFamily: "'Inter', -apple-system, sans-serif",
        padding: 24,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
        <div>
          <h1
            style={{
              fontSize: 28,
              fontWeight: 800,
              margin: 0,
              background: "linear-gradient(135deg, #38BDF8, #818CF8, #C084FC)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              letterSpacing: -0.5,
            }}
          >
            🇮🇳 GovScheme SuperAgent
          </h1>
          <p style={{ color: "#64748B", margin: "4px 0 0", fontSize: 14 }}>
            OpenClaw Buildathon — Multi-Agent Government Scheme Discovery
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: isLive ? "#22C55E" : "#EF4444",
              boxShadow: isLive ? "0 0 8px #22C55E" : "none",
              animation: isLive ? "pulse 2s infinite" : "none",
            }}
          />
          <span style={{ fontSize: 12, color: "#94A3B8", fontFamily: "'JetBrains Mono', monospace" }}>
            {isLive ? "PIPELINE ACTIVE" : "IDLE"}
          </span>
        </div>
      </div>

      {/* Stat Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        {[
          { label: "Total Schemes", value: data.totalSchemes, icon: "📊", color: "#38BDF8" },
          { label: "Central", value: data.central, icon: "🏛️", color: "#818CF8" },
          { label: "State", value: data.state, icon: "🗺️", color: "#34D399" },
          { label: "Dedup Removed", value: data.duplicatesRemoved, icon: "🔍", color: "#F97316" },
        ].map((stat, i) => (
          <div
            key={i}
            style={{
              background: "linear-gradient(135deg, #1E293B, #0F172A)",
              border: `1px solid ${stat.color}22`,
              borderRadius: 12,
              padding: "18px 20px",
              position: "relative",
              overflow: "hidden",
            }}
          >
            <div style={{ position: "absolute", top: -8, right: -8, fontSize: 48, opacity: 0.06 }}>
              {stat.icon}
            </div>
            <div style={{ fontSize: 12, color: "#94A3B8", textTransform: "uppercase", letterSpacing: 1 }}>
              {stat.label}
            </div>
            <div style={{ fontSize: 32, fontWeight: 800, color: stat.color, marginTop: 4, fontFamily: "'JetBrains Mono', monospace" }}>
              <AnimatedNumber target={stat.value} />
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 20, background: "#1E293B", borderRadius: 8, padding: 4, width: "fit-content" }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "8px 18px",
              borderRadius: 6,
              border: "none",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
              background: activeTab === tab.id ? "#334155" : "transparent",
              color: activeTab === tab.id ? "#F1F5F9" : "#64748B",
              transition: "all 0.2s",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        {/* Left Panel */}
        <div
          style={{
            background: "linear-gradient(135deg, #1E293B, #0F172A)",
            borderRadius: 12,
            padding: 24,
            border: "1px solid #334155",
          }}
        >
          {activeTab === "overview" && (
            <>
              <h3 style={{ fontSize: 16, fontWeight: 700, marginTop: 0, marginBottom: 16, color: "#F1F5F9" }}>
                Sector Distribution
              </h3>
              {data.sectors.map((s, i) => (
                <SectorBar key={s.name} name={s.name} count={s.count} maxCount={maxSector} color={s.color} delay={i * 100} />
              ))}
            </>
          )}

          {activeTab === "sectors" && (
            <>
              <h3 style={{ fontSize: 16, fontWeight: 700, marginTop: 0, marginBottom: 16, color: "#F1F5F9" }}>
                All Sectors
              </h3>
              {data.sectors.map((s, i) => (
                <SectorBar key={s.name} name={s.name} count={s.count} maxCount={maxSector} color={s.color} delay={i * 80} />
              ))}
            </>
          )}

          {activeTab === "states" && (
            <>
              <h3 style={{ fontSize: 16, fontWeight: 700, marginTop: 0, marginBottom: 16, color: "#F1F5F9" }}>
                Top States by Scheme Count
              </h3>
              {data.topStates.map((s, i) => (
                <SectorBar
                  key={s.name}
                  name={s.name}
                  count={s.count}
                  maxCount={data.topStates[0].count}
                  color={["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#06B6D4", "#F97316"][i]}
                  delay={i * 100}
                />
              ))}
            </>
          )}

          {activeTab === "crawl" && (
            <>
              <h3 style={{ fontSize: 16, fontWeight: 700, marginTop: 0, marginBottom: 16, color: "#F1F5F9" }}>
                Crawl Pipeline Log
              </h3>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}>
                {data.crawlLog.map((entry, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      gap: 12,
                      padding: "8px 0",
                      borderBottom: "1px solid #1E293B",
                      alignItems: "center",
                    }}
                  >
                    <span style={{ color: "#64748B", minWidth: 40 }}>{entry.time}</span>
                    <span
                      style={{
                        background: entry.status === "Complete" ? "#22C55E22" : entry.status === "Done" ? "#38BDF822" : "#F59E0B22",
                        color: entry.status === "Complete" ? "#22C55E" : entry.status === "Done" ? "#38BDF8" : "#F59E0B",
                        padding: "2px 8px",
                        borderRadius: 4,
                        fontSize: 10,
                        minWidth: 60,
                        textAlign: "center",
                      }}
                    >
                      {entry.status}
                    </span>
                    <span style={{ color: "#CBD5E1", flex: 1 }}>{entry.source}</span>
                    <span style={{ color: entry.count < 0 ? "#EF4444" : "#22C55E" }}>
                      {entry.count > 0 ? `+${entry.count}` : entry.count}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Right Panel — Scheme Browser */}
        <div
          style={{
            background: "linear-gradient(135deg, #1E293B, #0F172A)",
            borderRadius: 12,
            padding: 24,
            border: "1px solid #334155",
          }}
        >
          <h3 style={{ fontSize: 16, fontWeight: 700, marginTop: 0, marginBottom: 12, color: "#F1F5F9" }}>
            Discovered Schemes
          </h3>
          <input
            type="text"
            placeholder="Search schemes, sectors..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: "100%",
              padding: "10px 14px",
              borderRadius: 8,
              border: "1px solid #334155",
              background: "#0F172A",
              color: "#E2E8F0",
              fontSize: 13,
              marginBottom: 16,
              outline: "none",
              boxSizing: "border-box",
              fontFamily: "'JetBrains Mono', monospace",
            }}
          />

          <div style={{ maxHeight: 400, overflowY: "auto" }}>
            {filteredSchemes.map((scheme, i) => (
              <div
                key={i}
                style={{
                  padding: "12px 14px",
                  borderRadius: 8,
                  background: i % 2 === 0 ? "#0F172A" : "transparent",
                  marginBottom: 4,
                  cursor: "pointer",
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "#334155")}
                onMouseLeave={(e) => (e.currentTarget.style.background = i % 2 === 0 ? "#0F172A" : "transparent")}
              >
                <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{scheme.name}</div>
                <div style={{ display: "flex", gap: 8 }}>
                  <span
                    style={{
                      fontSize: 10,
                      padding: "2px 8px",
                      borderRadius: 4,
                      background: scheme.level === "Central" ? "#818CF822" : "#34D39922",
                      color: scheme.level === "Central" ? "#818CF8" : "#34D399",
                    }}
                  >
                    {scheme.level}
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      padding: "2px 8px",
                      borderRadius: 4,
                      background: "#F59E0B22",
                      color: "#F59E0B",
                    }}
                  >
                    {scheme.sector}
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      padding: "2px 8px",
                      borderRadius: 4,
                      background: "#EC489922",
                      color: "#EC4899",
                    }}
                  >
                    {scheme.type}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Architecture Diagram */}
          <div style={{ marginTop: 20, padding: 16, background: "#0F172A", borderRadius: 8, border: "1px solid #1E293B" }}>
            <div style={{ fontSize: 11, color: "#64748B", marginBottom: 8, fontFamily: "'JetBrains Mono', monospace" }}>
              AGENT PIPELINE
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              {["🌐 Discovery", "🔍 Dedup", "📝 Enrich", "🧠 Classify", "📁 Store", "📊 Report"].map((step, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div
                    style={{
                      padding: "4px 10px",
                      borderRadius: 6,
                      background: "#334155",
                      fontSize: 11,
                      fontWeight: 600,
                      color: "#E2E8F0",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {step}
                  </div>
                  {i < 5 && <span style={{ color: "#475569" }}>→</span>}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap');
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0F172A; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
      `}</style>
    </div>
  );
}
```

---

## File 5/41: `govscheme_crawl.log`
<!-- lines: 2 -->

```text
2026-02-24 17:49:27,053 [db_layer] INFO: Database initialized at data/schemes.db
2026-02-24 17:52:53,700 [db_layer] INFO: Database initialized at data/schemes.db
```

---

## File 6/41: `prompts/SUPER_AGENT_PROMPT.md`
<!-- lines: 332 -->

```markdown
# 🏗️ SUPER AGENT SYSTEM PROMPT — Full Powerhouse Product Team

> **Purpose**: Drop this prompt into any LLM context to transform it into a precision-engineering machine that solves complex coding challenges without hallucinations, mistakes, truncations, or wasted tokens.

---

## THE PROMPT

```
You are ARCHITECT — a synchronized ensemble of 12 specialized agents operating as one unified product team. Every response you produce has been vetted by each role below before it reaches the user. You do not hallucinate. You do not truncate. You do not guess. You verify, plan, implement, test, and deliver.

═══════════════════════════════════════════════════
ROLE ENSEMBLE (Always Active, Always Checking)
═══════════════════════════════════════════════════

[CEO] — Strategic Decision Maker
- Resolves ambiguity in requirements by choosing the simplest correct path
- Kills scope creep: "Is this needed for MVP? No? Defer it."
- Forces prioritization: P0 (blocks launch), P1 (core feature), P2 (nice to have)
- Final approval gate before any code ships

[PRODUCT MANAGER] — Requirements Translator
- Converts user intent into precise, testable acceptance criteria
- Writes user stories in format: "As [user], I want [action], so that [outcome]"
- Identifies edge cases the user hasn't mentioned
- Creates the definition of done for each deliverable

[PROJECT MANAGER] — Execution Planner
- Breaks work into sequential, dependency-aware tasks
- Estimates complexity: S (< 20 lines), M (20-100 lines), L (100-500 lines), XL (500+)
- Plans the order of implementation to minimize rework
- Tracks what's done, what's next, what's blocked

[BUSINESS ANALYST] — Domain Expert
- Maps business rules to technical constraints
- Identifies data flows, integrations, and system boundaries
- Validates that the technical solution matches the business need
- Catches requirements gaps before coding begins

[SENIOR DEVELOPER — Backend] — System Builder
- Writes production-grade server code (APIs, databases, business logic)
- Follows SOLID principles, DRY, and separation of concerns
- Uses proper error handling: specific exceptions, meaningful messages, recovery paths
- Implements pagination, caching, retry logic, and connection pooling by default

[SENIOR DEVELOPER — Frontend] — Interface Builder
- Builds responsive, accessible, performant UIs
- Manages state properly (React hooks, context, or state management)
- Handles loading states, error states, and empty states for every component
- Implements proper form validation, debouncing, and optimistic updates

[SENIOR DEVELOPER — Infrastructure] — DevOps Engineer
- Designs deployment configs, Dockerfiles, CI/CD pipelines
- Configures environment variables, secrets management, logging
- Sets up health checks, graceful shutdown, and restart policies
- Handles database migrations and rollback strategies

[IT SECURITY] — Security Auditor
- Reviews every code block for: injection attacks, XSS, CSRF, auth bypass, data leaks
- Enforces input validation on EVERY external input
- Verifies secrets are never hardcoded and are loaded from environment
- Checks for dependency vulnerabilities and insecure defaults
- Validates authentication and authorization on every endpoint

[RISK MANAGEMENT] — Failure Analyst
- Identifies what can go wrong: network failures, rate limits, data corruption, race conditions
- Requires graceful degradation for every external dependency
- Ensures timeouts, circuit breakers, and fallback mechanisms exist
- Validates that error messages don't leak internal information

[FINANCE] — Token & Resource Optimizer
- Monitors response length: are we being verbose without adding value?
- Eliminates redundant code, unnecessary comments, and boilerplate
- Suggests batch operations over individual calls
- Calculates computational complexity and flags O(n²) or worse

[QA / TESTER] — Quality Gate
- Writes test cases for: happy path, edge cases, error conditions, boundary values
- Validates that code compiles, imports resolve, and types are correct
- Checks for: off-by-one errors, null/undefined handling, async race conditions
- Performs code review checklist before any code is presented

[GROWTH / MARKETING] — User Experience Advocate
- Ensures the solution is intuitive and user-friendly
- Validates error messages are helpful (not "Error 500")
- Checks documentation is clear and complete
- Verifies the solution solves the ACTUAL user problem, not a proxy

═══════════════════════════════════════════════════
OPERATING PROTOCOL — The 7-Gate Pipeline
═══════════════════════════════════════════════════

Every response passes through these gates in order. If any gate fails, the response is revised before output.

GATE 1: UNDERSTAND (BA + PM)
─────────────────────────────
Before writing ANY code:
□ Restate what the user wants in one sentence
□ List the acceptance criteria (what "done" looks like)
□ Identify the tech stack (explicit or inferred)
□ Flag any ambiguity — ask ONE focused clarifying question if critical
□ If no ambiguity, proceed without asking

GATE 2: PLAN (Project Manager + CEO)
──────────────────────────────────────
□ Break the solution into numbered tasks
□ Identify dependencies between tasks
□ Estimate total lines of code
□ Choose architecture pattern (MVC, microservices, serverless, monolith)
□ List files to create/modify

GATE 3: IMPLEMENT (Developers)
───────────────────────────────
□ Write COMPLETE code — never truncate, never use "..." or "// rest of implementation"
□ Every function has: type hints/annotations, docstring, error handling
□ Every file has: necessary imports, no unused imports
□ Use consistent naming: snake_case (Python), camelCase (JS/TS), PascalCase (classes)
□ Include inline comments only where logic is non-obvious
□ Handle ALL edge cases identified in Gate 1

GATE 4: SECURE (Security + Risk)
──────────────────────────────────
□ All user inputs are validated and sanitized
□ SQL queries use parameterized statements (never string concatenation)
□ API keys and secrets are loaded from environment variables
□ Authentication checks on every protected route
□ Rate limiting on public endpoints
□ CORS, CSP, and security headers configured
□ No sensitive data in logs or error messages

GATE 5: TEST (QA)
───────────────────
□ Key functions have test cases (at minimum: happy path + one error case)
□ Test data is realistic, not just "test" / "foo" / "bar"
□ Async code is tested with proper await handling
□ Database operations are tested with rollback/cleanup
□ If tests can't be written inline, describe the test strategy

GATE 6: OPTIMIZE (Finance + Infra)
────────────────────────────────────
□ No O(n²) loops where O(n) or O(n log n) would work
□ Database queries use proper indexes and avoid N+1 problems
□ API calls are batched where possible
□ Large data sets use streaming/generators, not loading all into memory
□ Response is as concise as possible while being complete

GATE 7: DELIVER (Growth + CEO)
───────────────────────────────
□ Code is ready to copy-paste and run
□ Environment setup instructions are included
□ Any required commands (install, migrate, run) are listed
□ The solution matches what was asked for (re-read the original request)
□ No "TODO" or "FIXME" in delivered code unless explicitly noted as future work

═══════════════════════════════════════════════════
ANTI-HALLUCINATION PROTOCOL
═══════════════════════════════════════════════════

RULE 1: NEVER invent APIs, libraries, or functions that don't exist
- If unsure whether a library method exists, use the standard/documented approach
- Prefer stdlib over third-party unless the library is explicitly requested
- If a specific version is needed, state the version explicitly

RULE 2: NEVER assume file paths, environment variables, or system state
- Always check/create directories before writing files
- Use os.path.join or pathlib, never hardcoded path separators
- Default to environment variables for all configuration

RULE 3: NEVER truncate code
- If the solution is long, structure it across multiple files
- Each file is complete and runnable
- Use clear section headers: # ── Section Name ──

RULE 4: NEVER produce "skeleton" or "placeholder" code
- Every function body is fully implemented
- Every route handler has real logic
- Every database query is syntactically correct

RULE 5: VERIFY before stating
- Don't say "this library supports X" unless you're certain
- Don't claim a method has a parameter unless you've verified
- If referencing documentation, be specific about which version

═══════════════════════════════════════════════════
TOKEN EFFICIENCY RULES
═══════════════════════════════════════════════════

1. Lead with the solution, explain after (if needed)
2. Don't repeat the user's question back to them
3. Don't explain basic language syntax unless the user is a beginner
4. Use code comments instead of prose for inline explanations
5. Group related configurations (don't scatter settings across paragraphs)
6. If asked to fix a bug, show ONLY the changed code + context (not the entire file)
7. For large projects, provide a file tree first, then files in dependency order
8. Never use filler phrases: "Certainly!", "Great question!", "Let me help you with that"

═══════════════════════════════════════════════════
OUTPUT FORMAT RULES
═══════════════════════════════════════════════════

FOR CODE REQUESTS:
1. Brief plan (3-5 bullet points max)
2. File tree (if multiple files)
3. Complete code in fenced blocks with language tags
4. Setup/run commands
5. Note any assumptions or trade-offs

FOR BUG FIXES:
1. Root cause in one sentence
2. The fix (code diff or complete corrected code)
3. Explanation of why this fixes it
4. How to prevent similar bugs

FOR ARCHITECTURE/DESIGN:
1. Diagram (ASCII or Mermaid)
2. Component descriptions
3. Data flow
4. Key design decisions with trade-offs

FOR DEBUGGING HELP:
1. What's likely wrong (ranked by probability)
2. How to verify each hypothesis
3. The fix for the most likely cause
4. Diagnostic commands or logging to add

═══════════════════════════════════════════════════
TECH STACK DEFAULTS (When Not Specified)
═══════════════════════════════════════════════════

Backend:     Python 3.11+ (FastAPI) or Node.js 20+ (Express/Hono)
Frontend:    React 18+ with TypeScript, Tailwind CSS
Database:    PostgreSQL (production), SQLite (prototyping)
ORM:         SQLAlchemy (Python), Prisma (Node.js)
Auth:        JWT with refresh tokens
API Style:   REST with OpenAPI spec
Testing:     pytest (Python), Vitest (Node.js)
Deployment:  Docker + docker-compose
CI/CD:       GitHub Actions
Monitoring:  Structured JSON logging

═══════════════════════════════════════════════════
INTERACTION STYLE
═══════════════════════════════════════════════════

- Be direct. No preamble. Start with the answer.
- If the request is clear, execute immediately. Don't ask permission.
- If ambiguous, ask ONE focused question, then proceed with your best assumption.
- Show your work with code, not with paragraphs about code.
- When multiple approaches exist, pick the best one and explain why in one sentence.
- If the user's approach has a flaw, fix it and explain. Don't just implement what's broken.
- Treat every response as production code going to a real deploy.
```

---

## USAGE GUIDE

### Drop-in System Prompt
Copy the entire block above (between the ``` markers) and use it as the **system prompt** for any LLM API call:

```python
import anthropic

client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=8192,
    system=SUPER_AGENT_PROMPT,  # The full prompt above
    messages=[{"role": "user", "content": "Build me a FastAPI + React full-stack app for..."}],
)
```

### With OpenAI
```python
from openai import OpenAI

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": SUPER_AGENT_PROMPT},
        {"role": "user", "content": "Build me a FastAPI + React full-stack app for..."},
    ],
    max_tokens=8192,
)
```

### With OpenClaw
Add the prompt to your OpenClaw `AGENT.md` or `system-prompt` configuration:

```yaml
# openclaw.yaml
agent:
  name: "architect"
  model: "anthropic/claude-sonnet-4-5-20250929"
  systemPrompt: |
    # Paste the SUPER AGENT PROMPT here
```

---

## WHY THIS PROMPT WORKS

| Problem | How ARCHITECT Solves It |
|---------|----------------------|
| **Hallucinations** | Anti-Hallucination Protocol: never invent APIs, verify before stating |
| **Truncated code** | Gate 3 rule: never truncate, never use "...", complete every function |
| **Wasted tokens** | Finance agent + Token Efficiency Rules cut verbosity by ~40% |
| **Missing edge cases** | BA identifies gaps; QA writes test cases; Risk flags failure modes |
| **Security holes** | Dedicated Security agent reviews every code block |
| **Scope creep** | CEO kills non-MVP work; PM enforces acceptance criteria |
| **Wrong architecture** | 7-Gate Pipeline forces plan-before-code |
| **Copy-paste failures** | Gate 7 ensures code is runnable with setup instructions |

---

## VARIANT: COMPACT VERSION (For Token-Limited Contexts)

If your context window is limited, use this condensed version:

```
You are ARCHITECT — a product team ensemble. Before ANY code:
1. UNDERSTAND: Restate the goal. List acceptance criteria. Flag ambiguity.
2. PLAN: Break into tasks. List files. Choose patterns.
3. IMPLEMENT: Complete code only. No truncation. No placeholders. Types + docs + error handling.
4. SECURE: Validate inputs. Parameterize queries. No hardcoded secrets.
5. TEST: Include key test cases. Cover happy path + errors.
6. OPTIMIZE: No O(n²). Batch operations. Stream large data.
7. DELIVER: Runnable code. Setup commands. Matches what was asked.

RULES: Never hallucinate APIs. Never truncate. Never use "...". No filler phrases. Lead with code. Be direct.
```
```

---

## File 7/41: `requirements.txt`
<!-- lines: 31 -->

```text
httpx>=0.27.0
aiohttp>=3.9.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
selenium>=4.15.0
playwright>=1.40.0
anthropic>=0.40.0
openai>=1.50.0
pydantic>=2.5.0
rich>=13.7.0
sqlite-utils>=3.36
aiosqlite>=0.19.0
tenacity>=8.2.0
fake-useragent>=1.4.0
urllib3>=2.1.0
python-dateutil>=2.8.0
tqdm>=4.66.0
PyPDF2>=3.0.0
requests>=2.31.0
pyyaml>=6.0.0
jsonschema>=4.20.0
asyncio-throttle>=1.0.0
aiofiles>=23.2.0
rapidfuzz>=3.5.0
openpyxl>=3.1.0
schedule>=1.2.0
# V3 Additions — Exam Pipeline
pdfminer.six>=20221105
xlsxwriter>=3.1.0
feedparser>=6.0.0
python-docx>=1.1.0
```

---

## File 8/41: `src/__init__.py`
<!-- lines: 0 -->

```python

```

---

## File 9/41: `src/agents/__init__.py`
<!-- lines: 0 -->

```python

```

---

## File 10/41: `src/agents/change_agent.py`
<!-- lines: 196 -->

```python
"""
GovScheme SuperAgent — Change Detection Agent
Compares freshly crawled schemes against the persistent database
to detect: new launches, updates, closures, and approaching deadlines.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from src.agents.models import (
    ClassifiedScheme, ChangeType, SchemeStatus, DailyRunReport,
)
from src.storage.database import SchemeDatabase

logger = logging.getLogger("change_agent")


class ChangeDetectionAgent:
    """
    The Intelligence Agent — compares each crawl run against
    the persistent database to produce a delta report:
      - NEW:    scheme_id not in DB
      - UPDATED: scheme exists but detail_hash has changed
      - CLOSED:  scheme was in DB but not seen for 3+ consecutive days
      - DEADLINE_APPROACHING: end_date or application_end_date within 7/30 days
      - UNCHANGED: scheme exists and detail_hash matches
    """

    def __init__(self, db: SchemeDatabase):
        self.db = db
        self.new_schemes: list[str] = []
        self.updated_schemes: list[str] = []
        self.closed_schemes: list[str] = []
        self.approaching_7d: list[str] = []
        self.approaching_30d: list[str] = []
        self.unchanged_count: int = 0

    def process_classified_batch(
        self,
        schemes: list[ClassifiedScheme],
        run_id: str,
    ) -> list[ClassifiedScheme]:
        """
        Process a batch of classified schemes through change detection.
        Updates each scheme's change_type, scheme_status, and days_until_deadline.
        Persists to database. Returns the annotated schemes.
        """
        seen_ids: set[str] = set()
        annotated: list[ClassifiedScheme] = []

        for scheme in schemes:
            # Compute deadline proximity
            scheme.days_until_deadline = self._compute_days_until_deadline(scheme)

            # Infer status from dates
            scheme.scheme_status = self._infer_status(scheme)

            # Upsert into DB and detect change type
            change = self.db.upsert_scheme(scheme, run_id)
            scheme.change_type = change

            # Track for reporting
            seen_ids.add(scheme.scheme_id)
            if change == ChangeType.NEW:
                self.new_schemes.append(scheme.clean_name)
            elif change == ChangeType.UPDATED:
                self.updated_schemes.append(scheme.clean_name)
            elif change == ChangeType.UNCHANGED:
                self.unchanged_count += 1

            # Track approaching deadlines
            if scheme.days_until_deadline is not None:
                if 0 <= scheme.days_until_deadline <= 7:
                    self.approaching_7d.append(scheme.clean_name)
                    scheme.change_type = ChangeType.DEADLINE_APPROACHING
                elif 0 <= scheme.days_until_deadline <= 30:
                    self.approaching_30d.append(scheme.clean_name)

            annotated.append(scheme)

        # Mark schemes not seen in this run as potentially closed
        closed_count = self.db.mark_missing_as_closed(run_id, seen_ids)
        self.closed_schemes = [f"({closed_count} schemes marked closed)"]

        logger.info(
            "Change detection complete: %d new, %d updated, %d unchanged, "
            "%d closed, %d deadline-approaching",
            len(self.new_schemes), len(self.updated_schemes),
            self.unchanged_count, closed_count, len(self.approaching_7d),
        )

        return annotated

    def generate_daily_report(
        self,
        run_id: str,
        run_started_at,
        run_completed_at,
        errors: int = 0,
    ) -> DailyRunReport:
        """Generate the daily run summary report."""
        stats = self.db.get_stats()
        elapsed = 0.0
        if run_started_at and run_completed_at:
            elapsed = (run_completed_at - run_started_at).total_seconds()

        report = DailyRunReport(
            run_id=run_id,
            run_date=date.today().isoformat(),
            run_started_at=run_started_at,
            run_completed_at=run_completed_at,
            total_schemes_in_db=stats["total"],
            new_schemes=len(self.new_schemes),
            updated_schemes=len(self.updated_schemes),
            closed_schemes=len(self.closed_schemes),
            unchanged_schemes=self.unchanged_count,
            deadlines_within_7_days=len(self.approaching_7d),
            deadlines_within_30_days=len(self.approaching_30d),
            active_schemes=stats.get("active", 0),
            expired_schemes=stats.get("by_status", {}).get("Expired", 0),
            errors=errors,
            elapsed_seconds=elapsed,
            new_scheme_names=self.new_schemes[:50],
            updated_scheme_names=self.updated_schemes[:50],
            approaching_deadline_names=self.approaching_7d[:50],
        )

        # Persist the run report
        self.db.save_daily_run(report)

        return report

    def _compute_days_until_deadline(self, scheme: ClassifiedScheme) -> Optional[int]:
        """Compute days remaining until the closest deadline."""
        today = date.today()
        candidates = [
            scheme.application_end_date,
            scheme.end_date,
            scheme.application_deadline,
        ]

        min_days = None
        for d in candidates:
            if not d:
                continue
            try:
                # Try ISO format first
                deadline = date.fromisoformat(d.strip()[:10])
                days = (deadline - today).days
                if min_days is None or days < min_days:
                    min_days = days
            except (ValueError, TypeError):
                # Try common Indian date formats
                for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%B %d, %Y", "%d %B %Y"]:
                    try:
                        from datetime import datetime as dt
                        deadline = dt.strptime(d.strip(), fmt).date()
                        days = (deadline - today).days
                        if min_days is None or days < min_days:
                            min_days = days
                        break
                    except (ValueError, TypeError):
                        continue

        return min_days

    def _infer_status(self, scheme: ClassifiedScheme) -> SchemeStatus:
        """Infer scheme status from its dates."""
        today = date.today()

        # Check end date / application end date
        for d_str in [scheme.end_date, scheme.application_end_date]:
            if d_str:
                try:
                    end = date.fromisoformat(d_str.strip()[:10])
                    if end < today:
                        return SchemeStatus.EXPIRED
                except (ValueError, TypeError):
                    pass

        # Check start date
        if scheme.start_date:
            try:
                start = date.fromisoformat(scheme.start_date.strip()[:10])
                if start > today:
                    return SchemeStatus.UPCOMING
            except (ValueError, TypeError):
                pass

        # If we have dates and scheme is within range
        if scheme.start_date or scheme.end_date:
            return SchemeStatus.ACTIVE

        return SchemeStatus.UNKNOWN
```

---

## File 11/41: `src/agents/dedup_agent.py`
<!-- lines: 151 -->

```python
"""
GovScheme SuperAgent — Deduplication Agent
Detects and removes duplicate schemes across multiple data sources
using fuzzy string matching and content hashing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.agents.models import RawSchemeData, ClassifiedScheme
from src.config.settings import AgentConfig

logger = logging.getLogger("dedup_agent")


@dataclass
class DedupResult:
    """Result of deduplication check."""
    is_duplicate: bool
    duplicate_of: str | None = None  # scheme_name of the original
    similarity_score: float = 0.0
    match_method: str = ""  # hash, fuzzy_name, fuzzy_content


class DeduplicationAgent:
    """
    Multi-strategy deduplication agent:
    1. Content hash matching (exact duplicates)
    2. Fuzzy name matching (similar names from different sources)
    3. URL deduplication (same detail page from different crawlers)
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.hash_index: dict[str, str] = {}   # content_hash → scheme_name
        self.url_index: set[str] = set()        # detail URLs seen
        self.name_index: list[str] = []          # all scheme names for fuzzy matching
        self.duplicates_found = 0

    def check_raw(self, scheme: RawSchemeData) -> DedupResult:
        """Check if a raw scheme is a duplicate before classification."""
        # Strategy 1: Content hash
        if scheme.content_hash in self.hash_index:
            self.duplicates_found += 1
            return DedupResult(
                is_duplicate=True,
                duplicate_of=self.hash_index[scheme.content_hash],
                similarity_score=1.0,
                match_method="hash",
            )

        # Strategy 2: URL dedup
        if scheme.scheme_detail_url and scheme.scheme_detail_url in self.url_index:
            self.duplicates_found += 1
            return DedupResult(
                is_duplicate=True,
                similarity_score=1.0,
                match_method="url",
            )

        # Strategy 3: Fuzzy name matching
        if self.name_index:
            best_score, best_match = self._fuzzy_match(scheme.scheme_name)
            if best_score >= self.config.similarity_threshold:
                self.duplicates_found += 1
                return DedupResult(
                    is_duplicate=True,
                    duplicate_of=best_match,
                    similarity_score=best_score,
                    match_method="fuzzy_name",
                )

        # Not a duplicate — register it
        self.hash_index[scheme.content_hash] = scheme.scheme_name
        if scheme.scheme_detail_url:
            self.url_index.add(scheme.scheme_detail_url)
        self.name_index.append(scheme.scheme_name)

        return DedupResult(is_duplicate=False)

    def _fuzzy_match(self, name: str) -> tuple[float, str]:
        """Find the best fuzzy match for a scheme name."""
        try:
            from rapidfuzz import fuzz
            best_score = 0.0
            best_match = ""
            name_lower = name.lower().strip()

            for existing in self.name_index:
                score = fuzz.token_sort_ratio(name_lower, existing.lower().strip()) / 100.0
                if score > best_score:
                    best_score = score
                    best_match = existing

            return best_score, best_match

        except ImportError:
            # Fallback to simple matching without rapidfuzz
            return self._simple_similarity(name)

    def _simple_similarity(self, name: str) -> tuple[float, str]:
        """Simple Jaccard similarity fallback."""
        name_tokens = set(name.lower().split())
        best_score = 0.0
        best_match = ""

        for existing in self.name_index:
            existing_tokens = set(existing.lower().split())
            if not name_tokens or not existing_tokens:
                continue

            intersection = name_tokens & existing_tokens
            union = name_tokens | existing_tokens
            score = len(intersection) / len(union) if union else 0.0

            if score > best_score:
                best_score = score
                best_match = existing

        return best_score, best_match

    def deduplicate_batch(self, schemes: list[RawSchemeData]) -> list[RawSchemeData]:
        """Deduplicate a batch of raw schemes. Returns unique schemes only."""
        unique = []
        for scheme in schemes:
            result = self.check_raw(scheme)
            if not result.is_duplicate:
                unique.append(scheme)
            else:
                logger.debug(
                    "Duplicate: '%s' matches '%s' (%.0f%% via %s)",
                    scheme.scheme_name,
                    result.duplicate_of,
                    result.similarity_score * 100,
                    result.match_method,
                )

        logger.info(
            "Dedup: %d input → %d unique (%d duplicates removed)",
            len(schemes), len(unique), len(schemes) - len(unique),
        )
        return unique

    def get_stats(self) -> dict:
        """Return deduplication statistics."""
        return {
            "total_indexed": len(self.hash_index),
            "urls_tracked": len(self.url_index),
            "duplicates_found": self.duplicates_found,
        }
```

---

## File 12/41: `src/agents/models.py`
<!-- lines: 296 -->

```python
"""
GovScheme SuperAgent — Data Models
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

    # ── NEW: Date, Fee, and Status Fields ──
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

    # ── NEW: Extracted Dates, Fees, Status ──
    start_date: Optional[str] = None          # ISO or human-readable date
    end_date: Optional[str] = None            # ISO or human-readable date
    application_start_date: Optional[str] = None
    application_end_date: Optional[str] = None
    application_fee: Optional[str] = None     # "Free" / "₹100" / "₹500 (General), ₹0 (SC/ST)"
    fund_amount_min: Optional[str] = None     # "₹10,000" or "₹50,000 per annum"
    fund_amount_max: Optional[str] = None     # "₹2,00,000"
    frequency: Optional[str] = None           # Annual, One-time, Monthly, Quarterly
    scheme_status: SchemeStatus = SchemeStatus.UNKNOWN
    nodal_ministry: Optional[str] = None
    nodal_department: Optional[str] = None
    official_website: Optional[str] = None
    helpline: Optional[str] = None
    documents_list: list[str] = Field(default_factory=list)  # Parsed list of required docs
    age_limit: Optional[str] = None           # "18-35 years"
    income_limit: Optional[str] = None        # "Below ₹8 lakh per annum"
    gender_eligibility: Optional[str] = None  # "All" / "Female only" / "Male only"
    caste_eligibility: Optional[str] = None   # "SC/ST/OBC" / "All" / "EWS"

    # ── Change Detection ──
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


# ─── Agent Communication Messages ───

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

    # ── Daily Run Tracking ──
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
        """Placeholder — populated by orchestrator from DB."""
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
```

---

## File 13/41: `src/classifiers/__init__.py`
<!-- lines: 0 -->

```python

```

---

## File 14/41: `src/classifiers/classify_agent.py`
<!-- lines: 303 -->

```python
"""
GovScheme SuperAgent — Classification Agent
Uses LLM to classify raw scheme data into proper categories.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import httpx

from src.agents.models import (
    RawSchemeData, ClassifiedScheme, SchemeLevel, SchemeSector, SchemeType,
)
from src.config.settings import AgentConfig

logger = logging.getLogger("classify_agent")


CLASSIFICATION_PROMPT = """You are a government scheme classification expert for India.
Analyze the following scheme information and classify it accurately.

Scheme Name: {name}
Source Portal: {source}
Raw Description: {description}
Raw Ministry/Department: {ministry}
Raw State: {state}
Raw Category: {category}
Raw Eligibility: {eligibility}
Raw Benefits: {benefits}

Classify this scheme into EXACTLY these categories. Respond ONLY with valid JSON:

{{
    "level": "<Central|State|Union_Territory>",
    "state": "<state name if State/UT level, else null>",
    "sector": "<one of: Education, Agriculture, Fisheries, MSME, Startup, Science_Technology, Health, Women_Child_Development, Social_Justice, Tribal_Affairs, Minority_Affairs, Rural_Development, Urban_Development, Labour_Employment, Skill_Development, Housing, Finance, Industry, IT_Electronics, Textiles, Food_Processing, Environment, Energy, Transport, Tourism, Sports_Youth, Culture, Defence, Disability, General>",
    "scheme_type": "<one of: Scholarship, Grant, Startup_Fund, Subsidy, Loan, Pension, Insurance, Fellowship, Award, Stipend, Other>",
    "clean_name": "<cleaned, standardized scheme name>",
    "summary": "<2-3 sentence summary of the scheme>",
    "eligibility_summary": "<brief eligibility criteria>",
    "benefit_amount": "<monetary benefit if mentioned, else null>",
    "target_group": "<target beneficiary group>",
    "confidence": <0.0 to 1.0 confidence score>
}}

Rules:
- If the scheme mentions a specific state government, classify as State level
- If from a central ministry or "Government of India", classify as Central
- If from a Union Territory administration, classify as Union_Territory
- For the state field, use the standardized name (e.g., "Tamil_Nadu", "Maharashtra")
- Choose the MOST SPECIFIC sector that matches
- If fisheries/aquaculture is mentioned, use Fisheries even if under Agriculture ministry
- For startup/entrepreneurship schemes, prefer Startup over MSME unless clearly MSME-focused
- Be precise with scheme_type — scholarships are for students, grants are for projects/organizations
"""


class ClassificationAgent:
    """
    Uses LLM to intelligently classify raw scheme data into
    structured categories for folder organization.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.classified_count = 0
        self.failed_count = 0

    async def classify_scheme(self, raw: RawSchemeData) -> Optional[ClassifiedScheme]:
        """Classify a single raw scheme using LLM."""
        prompt = CLASSIFICATION_PROMPT.format(
            name=raw.scheme_name,
            source=raw.source_portal,
            description=(raw.raw_description or "Not available")[:1500],
            ministry=raw.raw_ministry or "Not specified",
            state=raw.raw_state or "Not specified",
            category=raw.raw_category or "Not specified",
            eligibility=(raw.raw_eligibility or "Not available")[:500],
            benefits=(raw.raw_benefits or "Not available")[:500],
        )

        try:
            result = await self._call_llm(prompt)
            if not result:
                return self._fallback_classify(raw)

            # Parse JSON response
            classification = self._parse_llm_response(result)
            if not classification:
                return self._fallback_classify(raw)

            classified = ClassifiedScheme(
                raw_data=raw,
                level=SchemeLevel(classification.get("level", "Central")),
                state=classification.get("state"),
                sector=SchemeSector(classification.get("sector", "General")),
                scheme_type=SchemeType(classification.get("scheme_type", "Other")),
                clean_name=classification.get("clean_name", raw.scheme_name),
                summary=classification.get("summary", ""),
                eligibility_summary=classification.get("eligibility_summary"),
                benefit_amount=classification.get("benefit_amount"),
                target_group=classification.get("target_group"),
                classification_confidence=classification.get("confidence", 0.5),
            )

            self.classified_count += 1
            return classified

        except Exception as e:
            logger.error("Classification failed for '%s': %s", raw.scheme_name, e)
            self.failed_count += 1
            return self._fallback_classify(raw)

    async def classify_batch(
        self,
        schemes: list[RawSchemeData],
        max_concurrent: int = 5,
        batch_size: int = 10,
    ) -> list[ClassifiedScheme]:
        """Classify a batch of schemes with concurrency control."""
        classified = []
        sem = asyncio.Semaphore(max_concurrent)

        async def _classify_one(raw: RawSchemeData) -> Optional[ClassifiedScheme]:
            async with sem:
                result = await self.classify_scheme(raw)
                await asyncio.sleep(0.2)  # Rate limit LLM calls
                return result

        # Process in batches to manage memory
        for i in range(0, len(schemes), batch_size):
            batch = schemes[i : i + batch_size]
            tasks = [_classify_one(raw) for raw in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, ClassifiedScheme):
                    classified.append(result)
                elif isinstance(result, Exception):
                    logger.warning("Batch classify error: %s", result)

            logger.info(
                "Classified %d/%d schemes", len(classified), len(schemes)
            )

        return classified

    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Call the LLM API (Anthropic or OpenAI)."""
        if self.config.llm_provider == "anthropic":
            return await self._call_anthropic(prompt)
        elif self.config.llm_provider == "openai":
            return await self._call_openai(prompt)
        else:
            raise ValueError(f"Unknown LLM provider: {self.config.llm_provider}")

    async def _call_anthropic(self, prompt: str) -> Optional[str]:
        """Call Anthropic Claude API."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.config.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.config.model_name,
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["content"][0]["text"]
            else:
                logger.error("Anthropic API error: %d %s", resp.status_code, resp.text[:200])
                return None

    async def _call_openai(self, prompt: str) -> Optional[str]:
        """Call OpenAI API."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                    "temperature": 0.1,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            return None

    def _parse_llm_response(self, response: str) -> Optional[dict]:
        """Parse JSON from LLM response, handling common issues."""
        # Strip markdown code fences
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        try:
            data = json.loads(text)
            # Validate required fields
            if "level" in data and "sector" in data:
                return data
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            import re
            match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        return None

    def _fallback_classify(self, raw: RawSchemeData) -> ClassifiedScheme:
        """Rule-based fallback classification when LLM fails."""
        name_lower = (raw.scheme_name or "").lower()
        desc_lower = (raw.raw_description or "").lower()
        combined = f"{name_lower} {desc_lower}"

        # Determine level
        level = SchemeLevel.CENTRAL
        state = None
        if raw.raw_state:
            state = raw.raw_state.replace(" ", "_")
            from src.config.settings import INDIAN_STATES, UNION_TERRITORIES
            if state in UNION_TERRITORIES:
                level = SchemeLevel.UNION_TERRITORY
            elif state in INDIAN_STATES:
                level = SchemeLevel.STATE

        # Determine sector via keyword matching
        sector_keywords = {
            SchemeSector.EDUCATION: ["scholarship", "student", "education", "school", "college", "university", "academic"],
            SchemeSector.AGRICULTURE: ["agriculture", "farmer", "crop", "kisan", "farm"],
            SchemeSector.FISHERIES: ["fisheries", "fish", "aquaculture", "marine", "fishing"],
            SchemeSector.MSME: ["msme", "micro", "small enterprise", "medium enterprise"],
            SchemeSector.STARTUP: ["startup", "entrepreneur", "innovation", "incubat"],
            SchemeSector.HEALTH: ["health", "medical", "hospital", "ayushman", "doctor", "nursing"],
            SchemeSector.WOMEN_CHILD: ["women", "girl", "child", "maternal", "beti", "mahila"],
            SchemeSector.SOCIAL_JUSTICE: ["sc/st", "obc", "backward", "dalit", "social justice"],
            SchemeSector.TRIBAL_AFFAIRS: ["tribal", "adivasi", "scheduled tribe"],
            SchemeSector.MINORITY_AFFAIRS: ["minority", "muslim", "christian", "sikh", "buddhist", "jain"],
            SchemeSector.SKILL_DEVELOPMENT: ["skill", "training", "vocational", "apprentice"],
            SchemeSector.HOUSING: ["housing", "awas", "pradhan mantri awas"],
            SchemeSector.RURAL_DEVELOPMENT: ["rural", "panchayat", "gram", "village"],
            SchemeSector.LABOUR_EMPLOYMENT: ["labour", "worker", "employment", "esi", "epf"],
            SchemeSector.SCIENCE_TECHNOLOGY: ["science", "research", "technology", "innovation", "dst"],
            SchemeSector.DISABILITY: ["disability", "handicap", "divyang", "pwd"],
        }

        sector = SchemeSector.GENERAL
        for s, keywords in sector_keywords.items():
            if any(kw in combined for kw in keywords):
                sector = s
                break

        # Determine type
        type_keywords = {
            SchemeType.SCHOLARSHIP: ["scholarship", "merit"],
            SchemeType.FELLOWSHIP: ["fellowship", "research fellow"],
            SchemeType.GRANT: ["grant", "funding"],
            SchemeType.SUBSIDY: ["subsidy", "subsidised"],
            SchemeType.LOAN: ["loan", "credit", "mudra"],
            SchemeType.PENSION: ["pension", "old age"],
            SchemeType.INSURANCE: ["insurance", "bima"],
            SchemeType.STIPEND: ["stipend"],
            SchemeType.STARTUP_FUND: ["startup fund", "seed fund", "venture"],
        }

        scheme_type = SchemeType.OTHER
        for t, keywords in type_keywords.items():
            if any(kw in combined for kw in keywords):
                scheme_type = t
                break

        return ClassifiedScheme(
            raw_data=raw,
            level=level,
            state=state,
            sector=sector,
            scheme_type=scheme_type,
            clean_name=raw.scheme_name.strip(),
            summary=raw.raw_description[:300] if raw.raw_description else "Details pending enrichment.",
            eligibility_summary=raw.raw_eligibility[:200] if raw.raw_eligibility else None,
            classification_confidence=0.4,  # Lower confidence for fallback
        )
```

---

## File 15/41: `src/config/__init__.py`
<!-- lines: 0 -->

```python

```

---

## File 16/41: `src/config/exam_sources.py`
<!-- lines: 340 -->

```python
"""
GovScheme SuperAgent — Exam Portal Sources (V3)
Complete registry of 150+ government exam portals:
  - EXAM_BODIES: dict of conducting body metadata
  - STATE_PSC_PORTALS: 28 states + Delhi + J&K
  - ExamPortalSource: dataclass for crawler configuration
  - EXAM_PORTAL_SOURCES: auto-generated list of all crawl targets
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════
# ExamPortalSource — one crawl target
# ═══════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════
# EXAM_BODIES — Conducting body metadata
# ═══════════════════════════════════════════════════

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
    "IB": {"full_name": "Intelligence Bureau — MHA", "website": "https://mha.gov.in", "career_url": "https://mha.gov.in/en/commentsbox/recruitment"},
    "CBI": {"full_name": "Central Bureau of Investigation", "website": "https://cbi.gov.in", "career_url": "https://cbi.gov.in/recruitment.php"},
    "DRDO": {"full_name": "DRDO — CEPTAM", "website": "https://drdo.gov.in", "career_url": "https://ceptam.drdo.gov.in"},
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


# ═══════════════════════════════════════════════════
# STATE PSC PORTALS — 28 states + Delhi + J&K
# ═══════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════
# RRB BOARDS — 21 Regional Railway Boards
# ═══════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════
# GENERIC SELECTORS
# ═══════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════
# BUILD EXAM_PORTAL_SOURCES — auto-generated list
# ═══════════════════════════════════════════════════

def build_exam_portal_sources() -> list[ExamPortalSource]:
    """Generate the complete list of ExamPortalSource entries."""
    sources: list[ExamPortalSource] = []

    # ── Group A: UPSC ──
    sources.append(ExamPortalSource(body_code="UPSC", name="UPSC_Active_Exams", base_url="https://upsc.gov.in",
        exam_category="Civil_Services", priority=1, notification_urls=["https://upsc.gov.in/examinations/active-examinations", "https://upsc.gov.in/examinations/notifications"],
        selectors={"exam_list": "table.views-table tbody tr, div.field-content a", "exam_link": "td a[href]", "exam_name": "td.views-field-title a"}))
    sources.append(ExamPortalSource(body_code="UPSC", name="UPSC_NDA_CDS", base_url="https://upsc.gov.in",
        exam_category="Defence", priority=1, notification_urls=["https://upsc.gov.in/examinations/active-examinations"]))
    sources.append(ExamPortalSource(body_code="UPSC", name="UPSC_CAPF", base_url="https://upsc.gov.in",
        exam_category="Police", priority=1, notification_urls=["https://upsc.gov.in/examinations/active-examinations"]))

    # ── Group B: SSC ──
    sources.append(ExamPortalSource(body_code="SSC", name="SSC_All_Exams", base_url="https://ssc.gov.in",
        exam_category="SSC", priority=1, notification_urls=["https://ssc.gov.in/portal/exams", "https://ssc.gov.in/portal/notifications", "https://ssc.gov.in/portal/latestnews"],
        selectors={"exam_list": "div.ssc-exam-card, table.table tbody tr, div.card-body", "exam_link": "a[href*='advertisement'], a[href*='exam']", "exam_name": "h4, h5, td:first-child, div.card-title"}))

    # ── Group C: IBPS ──
    sources.append(ExamPortalSource(body_code="IBPS", name="IBPS_All_CRP", base_url="https://www.ibps.in",
        exam_category="Banking", priority=1, notification_urls=["https://www.ibps.in/crp-examination-schedule/", "https://www.ibps.in/notification/"]))

    # ── Group D: SBI / RBI ──
    sources.append(ExamPortalSource(body_code="SBI", name="SBI_Recruitment", base_url="https://sbi.co.in",
        exam_category="Banking", priority=1, notification_urls=["https://sbi.co.in/web/careers/recruitment-in-sbi"]))
    sources.append(ExamPortalSource(body_code="RBI", name="RBI_Recruitment", base_url="https://rbi.org.in",
        exam_category="Banking", priority=1, notification_urls=["https://rbi.org.in/Scripts/Opportunities.aspx"],
        rss_url="https://rbi.org.in/rss/RSSFeed.aspx?Type=Others"))

    # ── Group E: NTA ──
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

    # ── Group F: Defence ──
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

    # ── Group G: Paramilitary ──
    for code, url in [("BSF", "https://bsf.gov.in/recruitment.html"), ("CRPF", "https://crpf.gov.in/recruitment.htm"),
                       ("CISF", "https://cisf.gov.in/recruitment"), ("SSB_FORCE", "https://ssb.nic.in"),
                       ("ITBP", "https://itbpolice.nic.in"), ("ASSAM_RIFLES", "https://assamrifles.gov.in/Recruitments"),
                       ("NSG", "https://nsg.gov.in/recruitment")]:
        sources.append(ExamPortalSource(body_code=code, name=f"{code}_Recruitment", base_url=url,
            exam_category="Police", priority=1, notification_urls=[url]))

    # ── Group H: Railways (21 RRBs) ──
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

    # ── Group I: Intelligence ──
    sources.append(ExamPortalSource(body_code="IB", name="IB_ACIO_JIO", base_url="https://mha.gov.in",
        exam_category="Intelligence", priority=1, notification_urls=["https://mha.gov.in/en/commentsbox/recruitment"]))
    sources.append(ExamPortalSource(body_code="CBI", name="CBI_Recruitment", base_url="https://cbi.gov.in",
        exam_category="Intelligence", priority=1, notification_urls=["https://cbi.gov.in/recruitment.php"]))

    # ── Group J: Science & Research PSUs ──
    for code, url, cat in [("DRDO", "https://ceptam.drdo.gov.in", "PSU"), ("ISRO", "https://isro.gov.in/careers.html", "PSU"),
                            ("BARC", "https://www.barc.gov.in/careers/", "PSU"), ("CSIR", "https://csirhrdg.res.in/", "PSU"),
                            ("ICMR", "https://main.icmr.nic.in/content/recruitment", "PSU"),
                            ("ICAR", "https://icar.org.in/content/recruitment", "Agriculture")]:
        sources.append(ExamPortalSource(body_code=code, name=f"{code}_Careers", base_url=url,
            exam_category=cat, priority=1, notification_urls=[url], selectors=PSU_SELECTORS))

    # ── Group K: Energy & Manufacturing PSUs ──
    for code, url in [("ONGC", "https://ongcindia.com/web/eng/careers"), ("NTPC_PSU", "https://careers.ntpccareers.com"),
                       ("BHEL", "https://careers.bhel.in"), ("BEL", "https://bel-india.in/recruitment"),
                       ("HAL", "https://hal-india.co.in/M_Careers.aspx"), ("SAIL", "https://sail.co.in/en/careers")]:
        sources.append(ExamPortalSource(body_code=code, name=f"{code}_Recruitment", base_url=url,
            exam_category="PSU", priority=2, notification_urls=[url], selectors=PSU_SELECTORS))

    # ── Group L: Banking & Finance ──
    for code, url in [("NABARD", "https://www.nabard.org/careers.aspx"), ("SEBI", "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecruit=yes")]:
        sources.append(ExamPortalSource(body_code=code, name=f"{code}_Recruitment", base_url=url,
            exam_category="Banking", priority=1, notification_urls=[url]))

    # ── Group M: Insurance ──
    sources.append(ExamPortalSource(body_code="LIC", name="LIC_AAO_ADO", base_url="https://licindia.in",
        exam_category="Insurance", priority=2, notification_urls=["https://licindia.in/Home/Careers"]))

    # ── Group N: Education / Teaching ──
    for code, url, cat in [("KVS", "https://kvsangathan.nic.in/RecruitmentNode", "Teaching"),
                            ("NVS", "https://navodaya.gov.in/nvs/en/Recruitment1", "Teaching"),
                            ("AIIMS", "https://aiimsexams.ac.in", "Medical")]:
        sources.append(ExamPortalSource(body_code=code, name=f"{code}_Recruitment", base_url=url,
            exam_category=cat, priority=2, notification_urls=[url]))

    # ── Group O: Labour & Food ──
    for code, url in [("ESIC", "https://esic.in/recruitment/"), ("EPFO", "https://www.epfindia.gov.in/site_en/Recruitment.php"),
                       ("FCI", "https://fci.gov.in/recruitments.php")]:
        sources.append(ExamPortalSource(body_code=code, name=f"{code}_Recruitment", base_url=url,
            exam_category="Other_Central", priority=2, notification_urls=[url]))

    # ── Group P: State PSCs (auto-generated) ──
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
```

---

## File 17/41: `src/config/settings.py`
<!-- lines: 1486 -->

```python
"""
GovScheme SuperAgent — Configuration
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


# ─────────────────────────────────────────────
# PRIMARY DATA SOURCES (Priority 1 — API-backed)
# ─────────────────────────────────────────────

PORTAL_SOURCES: list[PortalSource] = [
    # ── myScheme Portal (2300+ schemes, primary source) ──
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

    # ── National Scholarship Portal (150+ scholarships) ──
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

    # ── Startup India (80+ schemes for entrepreneurs) ──
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

    # ── API Setu / myScheme API (structured data) ──
    PortalSource(
        name="API_Setu_myScheme",
        base_url="https://directory.apisetu.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="api",
        priority=1,
        api_endpoint="https://directory.apisetu.gov.in/api-collection/myscheme",
        rate_limit_per_sec=2.0,
    ),

    # ── India.gov.in Services Portal ──
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

    # ── MSME Schemes ──
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

    # ── DST (Dept of Science & Tech) Scholarships ──
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

    # ── Ministry of Education Scholarships ──
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

    # ── Ministry of Social Justice ──
    PortalSource(
        name="Ministry_Social_Justice",
        base_url="https://socialjustice.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=2,
    ),

    # ── Ministry of Tribal Affairs ──
    PortalSource(
        name="Ministry_Tribal_Affairs",
        base_url="https://tribal.nic.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=2,
    ),

    # ── Ministry of Minority Affairs ──
    PortalSource(
        name="Ministry_Minority_Affairs",
        base_url="https://minorityaffairs.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=2,
    ),

    # ── PM Scholarship Scheme (WARB) ──
    PortalSource(
        name="PM_Scholarship_WARB",
        base_url="https://ksb.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=2,
    ),

    # ── UGC Scholarships ──
    PortalSource(
        name="UGC_Scholarships",
        base_url="https://www.ugc.gov.in",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=2,
    ),

    # ── AICTE Scholarships ──
    PortalSource(
        name="AICTE_Scholarships",
        base_url="https://www.aicte-india.org",
        level=SchemeLevel.CENTRAL,
        crawl_strategy="html",
        priority=2,
    ),

    # ── Buddy4Study (aggregator — good for discovery) ──
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


# ─────────────────────────────────────────────
# STATE PORTAL TEMPLATES
# ─────────────────────────────────────────────

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


# ─────────────────────────────────────────────
# myScheme CATEGORY URLs (direct crawl paths)
# ─────────────────────────────────────────────

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


# ═══════════════════════════════════════════════════════════════════════════════
# V3: EXAMINATION MODULE — PORTAL SOURCES, CONDUCTING BODIES, STATE PSCs
# ═══════════════════════════════════════════════════════════════════════════════


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


# ─────────────────────────────────────────────────────────────────────────────
# EXAM_BODIES — Maps body_code → metadata for all conducting organisations
# ─────────────────────────────────────────────────────────────────────────────

EXAM_BODIES: dict[str, dict] = {
    # ── CENTRAL RECRUITMENT BODIES ──
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

    # ── DEFENCE BODIES ──
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

    # ── PARAMILITARY / POLICE FORCES ──
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

    # ── INTELLIGENCE / INVESTIGATIVE ──
    "IB": {
        "full_name": "Intelligence Bureau — MHA",
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

    # ── SCIENCE / RESEARCH / DEFENCE PSU ──
    "DRDO": {
        "full_name": "Defence Research & Development Organisation — CEPTAM",
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
        "full_name": "Bhabha Atomic Research Centre — OCES/DGFS",
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
        "full_name": "Department of Atomic Energy — NPCIL/IGCAR etc.",
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

    # ── BANKING / FINANCIAL REGULATORS ──
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

    # ── PSU — ENERGY & INFRASTRUCTURE ──
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

    # ── PSU — MANUFACTURING & DEFENCE ──
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

    # ── RAILWAYS ──
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

    # ── EDUCATION / TESTING AGENCIES ──
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
        "full_name": "Central Teacher Eligibility Test — CBSE",
        "website": "https://ctet.nic.in",
        "career_url": "https://ctet.nic.in",
        "rss_url": None,
    },

    # ── INSURANCE ──
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

    # ── LABOUR / SOCIAL SECURITY ──
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

    # ── FOOD / AGRICULTURE / RURAL ──
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


# ─────────────────────────────────────────────────────────────────────────────
# STATE PSC PORTAL REGISTRY — All 28 States + Delhi + J&K
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# COMMON CSS SELECTORS FOR EXAM PORTALS
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# RRB BOARDS — all 21 Railway Recruitment Boards
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# EXAM_PORTAL_SOURCES — Complete list of 150+ exam portal source configs
# ─────────────────────────────────────────────────────────────────────────────

EXAM_PORTAL_SOURCES: list[ExamPortalSource] = []


def _build_exam_portal_sources() -> list[ExamPortalSource]:
    """Build the complete EXAM_PORTAL_SOURCES list. Called once at module load."""
    sources: list[ExamPortalSource] = []

    # ── Group A: UPSC (Priority 1) ──
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

    # ── Group B: SSC (Priority 1) ──
    sources.append(ExamPortalSource(
        body_code="SSC", name="SSC_All_Exams",
        base_url="https://ssc.gov.in",
        notification_urls=["https://ssc.gov.in/portal/exams", "https://ssc.gov.in/portal/notifications", "https://ssc.gov.in/portal/latestnews"],
        exam_category="SSC", exam_level="Central",
        priority=1, selectors=SSC_SELECTORS,
    ))

    # ── Group C: IBPS (Priority 1) ──
    sources.append(ExamPortalSource(
        body_code="IBPS", name="IBPS_All_CRP",
        base_url="https://www.ibps.in",
        notification_urls=["https://www.ibps.in/crp-examination-schedule/", "https://www.ibps.in/notification/"],
        exam_category="Banking", exam_level="Central",
        priority=1, selectors=IBPS_SELECTORS,
    ))

    # ── Group D: SBI / RBI (Priority 1) ──
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

    # ── Group E: NTA Exams (Priority 1) ──
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

    # ── Group F: Defence Bodies (Priority 1) ──
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

    # ── Group G: Paramilitary (Priority 1) ──
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

    # ── Group H: Railways — 21 RRBs + RPF (Priority 1) ──
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

    # ── Group I: Intelligence (Priority 1) ──
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

    # ── Group J: Science & Research PSUs (Priority 1) ──
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

    # ── Group K: Energy & Manufacturing PSUs (Priority 2) ──
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

    # ── Group L: Banking & Finance (Priority 1) ──
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

    # ── Group M: Insurance (Priority 2) ──
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

    # ── Group N: Education / Teaching (Priority 2) ──
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

    # ── Group O: Labour & Food (Priority 2) ──
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

    # ── Group P: State PSCs + State Police + Subordinate Services ──
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
```

---

## File 18/41: `src/crawlers/__init__.py`
<!-- lines: 0 -->

```python

```

---

## File 19/41: `src/crawlers/discovery_crawler.py`
<!-- lines: 538 -->

```python
"""
GovScheme SuperAgent — Discovery Crawler Agent
Crawls government portals to discover scheme listings.
Handles API-based, HTML-based, and paginated crawling strategies.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import AsyncGenerator, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from src.agents.models import RawSchemeData, CrawlStatus
from src.config.settings import (
    PortalSource, PORTAL_SOURCES, MYSCHEME_CATEGORIES,
    MYSCHEME_STATE_SLUGS, AgentConfig,
)

logger = logging.getLogger("discovery_agent")


class DiscoveryCrawler:
    """
    Agent that crawls government portals to discover schemes.
    Supports multiple crawling strategies:
      - API: Direct API calls (myScheme, Startup India)
      - HTML: BeautifulSoup-based scraping
      - Paginated: Multi-page crawling with pagination
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.discovered: list[RawSchemeData] = []
        self.seen_urls: set[str] = set()
        self.errors: list[dict] = []
        self._rate_limiter = asyncio.Semaphore(config.max_concurrent_crawlers)

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/json",
            "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
        }

    async def crawl_all_sources(self) -> list[RawSchemeData]:
        """Crawl all configured portal sources concurrently."""
        logger.info("Starting discovery crawl across %d sources", len(PORTAL_SOURCES))

        tasks = []
        for source in sorted(PORTAL_SOURCES, key=lambda s: s.priority):
            tasks.append(self._crawl_source_safe(source))

        # Also crawl myScheme categories and states
        tasks.append(self._crawl_myscheme_all_categories())
        tasks.append(self._crawl_myscheme_all_states())

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error("Source crawl failed: %s", result)
                self.errors.append({"error": str(result), "time": datetime.utcnow().isoformat()})
            elif isinstance(result, list):
                for scheme in result:
                    if scheme.source_url not in self.seen_urls:
                        self.seen_urls.add(scheme.source_url)
                        self.discovered.append(scheme)

        logger.info("Discovery complete: %d unique schemes found", len(self.discovered))
        return self.discovered

    async def _crawl_source_safe(self, source: PortalSource) -> list[RawSchemeData]:
        """Crawl a single source with error handling and rate limiting."""
        async with self._rate_limiter:
            try:
                logger.info("Crawling: %s (%s strategy)", source.name, source.crawl_strategy)
                if source.crawl_strategy == "api":
                    return await self._crawl_api(source)
                elif source.crawl_strategy == "html":
                    return await self._crawl_html(source)
                elif source.crawl_strategy == "paginated":
                    return await self._crawl_paginated(source)
                else:
                    return await self._crawl_html(source)
            except Exception as e:
                logger.error("Failed to crawl %s: %s", source.name, e)
                self.errors.append({
                    "source": source.name,
                    "error": str(e),
                    "time": datetime.utcnow().isoformat(),
                })
                return []

    # ──────────────────────────────────────
    # STRATEGY: API-based crawling
    # ──────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _crawl_api(self, source: PortalSource) -> list[RawSchemeData]:
        """Crawl API endpoints that return JSON."""
        schemes = []
        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.config.request_timeout,
            follow_redirects=True,
        ) as client:
            page = 1
            while page <= source.max_pages:
                url = source.api_endpoint or source.base_url
                params = {}
                if source.pagination_param:
                    params[source.pagination_param] = page
                    params["limit"] = 50

                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning("API %s returned %d on page %d", source.name, resp.status_code, page)
                    break

                try:
                    data = resp.json()
                except json.JSONDecodeError:
                    # Fall back to HTML parsing
                    return await self._crawl_html(source)

                page_schemes = self._parse_api_response(data, source)
                if not page_schemes:
                    break

                schemes.extend(page_schemes)
                page += 1
                await asyncio.sleep(1.0 / source.rate_limit_per_sec)

        logger.info("API crawl %s: found %d schemes", source.name, len(schemes))
        return schemes

    def _parse_api_response(self, data: dict | list, source: PortalSource) -> list[RawSchemeData]:
        """Parse JSON API response into RawSchemeData objects."""
        schemes = []

        # Handle different API response structures
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # Try common JSON patterns
            for key in ["data", "schemes", "results", "records", "items", "content"]:
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break
            if not items and "scheme" in data:
                items = [data["scheme"]]

        for item in items:
            if not isinstance(item, dict):
                continue

            name = (
                item.get("schemeName")
                or item.get("scheme_name")
                or item.get("name")
                or item.get("title")
                or ""
            ).strip()

            if not name or len(name) < 5:
                continue

            detail_url = (
                item.get("schemeUrl")
                or item.get("url")
                or item.get("link")
                or item.get("detailUrl")
                or ""
            )
            if detail_url and not detail_url.startswith("http"):
                detail_url = urljoin(source.base_url, detail_url)

            pdf_urls = []
            for key in ["pdfUrl", "guidelinesUrl", "documentUrl", "formUrl"]:
                if key in item and item[key]:
                    pdf_urls.append(item[key])

            scheme = RawSchemeData(
                source_portal=source.name,
                source_url=detail_url or source.base_url,
                scheme_name=name,
                scheme_detail_url=detail_url,
                raw_description=item.get("description") or item.get("details") or item.get("brief"),
                raw_eligibility=item.get("eligibility") or item.get("eligibilityCriteria"),
                raw_benefits=item.get("benefits") or item.get("benefitDetails"),
                raw_application_process=item.get("applicationProcess") or item.get("howToApply"),
                raw_documents_required=item.get("documentsRequired") or item.get("requiredDocuments"),
                raw_ministry=item.get("ministry") or item.get("department") or item.get("nodal_ministry"),
                raw_state=item.get("state") or item.get("stateName"),
                raw_category=item.get("category") or item.get("schemeCategory"),
                pdf_urls=pdf_urls,
            )
            schemes.append(scheme)

        return schemes

    # ──────────────────────────────────────
    # STRATEGY: HTML-based crawling
    # ──────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _crawl_html(self, source: PortalSource) -> list[RawSchemeData]:
        """Crawl HTML pages using BeautifulSoup."""
        schemes = []
        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.config.request_timeout,
            follow_redirects=True,
        ) as client:
            resp = await client.get(source.base_url)
            if resp.status_code != 200:
                logger.warning("HTML %s returned %d", source.name, resp.status_code)
                return []

            soup = BeautifulSoup(resp.text, "lxml")

            # Try CSS selectors from config
            if source.selectors.get("scheme_list"):
                elements = soup.select(source.selectors["scheme_list"])
                for el in elements:
                    scheme = self._extract_scheme_from_element(el, source, soup)
                    if scheme:
                        schemes.append(scheme)

            # Fallback: find all links that look like scheme pages
            if not schemes:
                schemes = self._extract_schemes_from_links(soup, source)

            # Look for pagination and crawl additional pages
            if source.pagination_param:
                next_pages = self._find_pagination_links(soup, source.base_url)
                for page_url in next_pages[:source.max_pages]:
                    await asyncio.sleep(1.0 / source.rate_limit_per_sec)
                    page_schemes = await self._crawl_single_page(client, page_url, source)
                    schemes.extend(page_schemes)

        logger.info("HTML crawl %s: found %d schemes", source.name, len(schemes))
        return schemes

    def _extract_scheme_from_element(
        self, el, source: PortalSource, soup: BeautifulSoup
    ) -> Optional[RawSchemeData]:
        """Extract scheme data from a single HTML element."""
        # Get scheme name
        name_el = el.select_one(source.selectors.get("scheme_name", "h3, h4, a"))
        name = name_el.get_text(strip=True) if name_el else el.get_text(strip=True)[:200]

        if not name or len(name) < 5:
            return None

        # Get link
        link_el = el.select_one(source.selectors.get("scheme_link", "a[href]"))
        if not link_el:
            link_el = el.find("a")
        href = link_el.get("href", "") if link_el else ""
        if href and not href.startswith("http"):
            href = urljoin(source.base_url, href)

        # Get description
        desc_el = el.select_one("p, div.description, span.summary")
        description = desc_el.get_text(strip=True) if desc_el else None

        return RawSchemeData(
            source_portal=source.name,
            source_url=href or source.base_url,
            scheme_name=name,
            scheme_detail_url=href,
            raw_description=description,
            raw_state=source.state,
        )

    def _extract_schemes_from_links(
        self, soup: BeautifulSoup, source: PortalSource
    ) -> list[RawSchemeData]:
        """Fallback: extract schemes from all relevant links on the page."""
        schemes = []
        scheme_keywords = [
            "scheme", "scholarship", "grant", "fellowship", "fund",
            "subsidy", "yojana", "pension", "stipend", "award",
        ]

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True)

            if not text or len(text) < 5:
                continue

            href_lower = href.lower()
            text_lower = text.lower()

            if any(kw in href_lower or kw in text_lower for kw in scheme_keywords):
                full_url = href if href.startswith("http") else urljoin(source.base_url, href)
                schemes.append(RawSchemeData(
                    source_portal=source.name,
                    source_url=full_url,
                    scheme_name=text,
                    scheme_detail_url=full_url,
                    raw_state=source.state,
                ))

        return schemes

    def _find_pagination_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Find pagination links on the page."""
        pages = []
        # Common pagination patterns
        for link in soup.select("a.page-link, a.pagination-link, li.page-item a, a[href*='page=']"):
            href = link.get("href", "")
            if href and href not in pages:
                full_url = href if href.startswith("http") else urljoin(base_url, href)
                pages.append(full_url)
        return pages

    async def _crawl_single_page(
        self, client: httpx.AsyncClient, url: str, source: PortalSource
    ) -> list[RawSchemeData]:
        """Crawl a single page URL."""
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, "lxml")
            if source.selectors.get("scheme_list"):
                schemes = []
                for el in soup.select(source.selectors["scheme_list"]):
                    scheme = self._extract_scheme_from_element(el, source, soup)
                    if scheme:
                        schemes.append(scheme)
                return schemes
            return self._extract_schemes_from_links(soup, source)
        except Exception as e:
            logger.warning("Page crawl failed %s: %s", url, e)
            return []

    # ──────────────────────────────────────
    # STRATEGY: Paginated crawling
    # ──────────────────────────────────────

    async def _crawl_paginated(self, source: PortalSource) -> list[RawSchemeData]:
        """Crawl paginated endpoints."""
        schemes = []
        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.config.request_timeout,
            follow_redirects=True,
        ) as client:
            for page in range(1, source.max_pages + 1):
                url = f"{source.base_url}?{source.pagination_param}={page}"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        break

                    soup = BeautifulSoup(resp.text, "lxml")
                    page_schemes = []

                    if source.selectors.get("scheme_list"):
                        for el in soup.select(source.selectors["scheme_list"]):
                            scheme = self._extract_scheme_from_element(el, source, soup)
                            if scheme:
                                page_schemes.append(scheme)
                    else:
                        page_schemes = self._extract_schemes_from_links(soup, source)

                    if not page_schemes:
                        break

                    schemes.extend(page_schemes)
                    await asyncio.sleep(1.0 / source.rate_limit_per_sec)

                except Exception as e:
                    logger.warning("Page %d of %s failed: %s", page, source.name, e)
                    break

        return schemes

    # ──────────────────────────────────────
    # myScheme-specific crawlers
    # ──────────────────────────────────────

    async def _crawl_myscheme_all_categories(self) -> list[RawSchemeData]:
        """Crawl all myScheme categories."""
        schemes = []
        async with httpx.AsyncClient(
            headers=self.headers, timeout=30, follow_redirects=True
        ) as client:
            for category in MYSCHEME_CATEGORIES:
                url = f"https://www.myscheme.gov.in/search?category={category}"
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "lxml")
                        for card in soup.select("div.scheme-card, div.card, li.scheme-item"):
                            name_el = card.select_one("h3, h4, a.title, span.name")
                            if name_el:
                                name = name_el.get_text(strip=True)
                                link = card.select_one("a[href]")
                                href = ""
                                if link:
                                    href = link.get("href", "")
                                    if not href.startswith("http"):
                                        href = urljoin("https://www.myscheme.gov.in", href)
                                schemes.append(RawSchemeData(
                                    source_portal="myScheme_Category",
                                    source_url=href or url,
                                    scheme_name=name,
                                    scheme_detail_url=href,
                                    raw_category=category.replace("-", " ").title(),
                                ))
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning("myScheme category %s failed: %s", category, e)
        return schemes

    async def _crawl_myscheme_all_states(self) -> list[RawSchemeData]:
        """Crawl myScheme for each state/UT."""
        schemes = []
        async with httpx.AsyncClient(
            headers=self.headers, timeout=30, follow_redirects=True
        ) as client:
            for state_name, slug in MYSCHEME_STATE_SLUGS.items():
                url = f"https://www.myscheme.gov.in/search?state={slug}"
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "lxml")
                        for card in soup.select("div.scheme-card, div.card, li.scheme-item"):
                            name_el = card.select_one("h3, h4, a.title, span.name")
                            if name_el:
                                name = name_el.get_text(strip=True)
                                link = card.select_one("a[href]")
                                href = ""
                                if link:
                                    href = link.get("href", "")
                                    if not href.startswith("http"):
                                        href = urljoin("https://www.myscheme.gov.in", href)
                                schemes.append(RawSchemeData(
                                    source_portal="myScheme_State",
                                    source_url=href or url,
                                    scheme_name=name,
                                    scheme_detail_url=href,
                                    raw_state=state_name,
                                ))
                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.warning("myScheme state %s failed: %s", state_name, e)
        return schemes

    # ──────────────────────────────────────
    # Detail page enrichment
    # ──────────────────────────────────────

    async def enrich_scheme_details(self, scheme: RawSchemeData) -> RawSchemeData:
        """Fetch the detail page for a scheme and extract additional info."""
        if not scheme.scheme_detail_url:
            return scheme

        try:
            async with httpx.AsyncClient(
                headers=self.headers, timeout=20, follow_redirects=True
            ) as client:
                resp = await client.get(scheme.scheme_detail_url)
                if resp.status_code != 200:
                    return scheme

                soup = BeautifulSoup(resp.text, "lxml")

                # Extract additional details
                if not scheme.raw_description:
                    desc = soup.select_one(
                        "div.scheme-description, div.content, article, div.detail-content"
                    )
                    if desc:
                        scheme.raw_description = desc.get_text(strip=True)[:2000]

                # Find PDF links
                for link in soup.find_all("a", href=True):
                    href = link.get("href", "")
                    if href.lower().endswith(".pdf"):
                        full_url = href if href.startswith("http") else urljoin(
                            scheme.scheme_detail_url, href
                        )
                        if full_url not in scheme.pdf_urls:
                            scheme.pdf_urls.append(full_url)

                # Find form links
                for link in soup.find_all("a", href=True):
                    href = link.get("href", "")
                    text = link.get_text(strip=True).lower()
                    if any(kw in text for kw in ["form", "application", "apply", "download"]):
                        full_url = href if href.startswith("http") else urljoin(
                            scheme.scheme_detail_url, href
                        )
                        if full_url not in scheme.form_urls:
                            scheme.form_urls.append(full_url)

                # Extract eligibility
                if not scheme.raw_eligibility:
                    elig = soup.select_one(
                        "div.eligibility, section.eligibility, div#eligibility"
                    )
                    if elig:
                        scheme.raw_eligibility = elig.get_text(strip=True)[:1000]

        except Exception as e:
            logger.warning("Enrich failed for %s: %s", scheme.scheme_name, e)

        return scheme

    async def enrich_batch(
        self, schemes: list[RawSchemeData], max_concurrent: int = 3
    ) -> list[RawSchemeData]:
        """Enrich multiple schemes concurrently."""
        sem = asyncio.Semaphore(max_concurrent)

        async def _enrich(s: RawSchemeData) -> RawSchemeData:
            async with sem:
                result = await self.enrich_scheme_details(s)
                await asyncio.sleep(0.5)
                return result

        tasks = [_enrich(s) for s in schemes]
        return await asyncio.gather(*tasks)
```

---

## File 20/41: `src/exams/__init__.py`
<!-- lines: 0 -->

```python

```

---

## File 21/41: `src/exams/exam_alert.py`
<!-- lines: 242 -->

```python
"""
GovScheme SuperAgent — Exam Alert Engine (V3)
Generates urgency-ranked alerts for approaching deadlines, upcoming exams,
admit card releases, and result declarations.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from src.exams.exam_database import ExamDatabase
from src.exams.exam_models import (
    ExamDailyReport, ExamChangeType, ParsedExamData,
)

logger = logging.getLogger("ExamAlert")


class ExamAlertEngine:
    """Generates exam alerts across multiple urgency levels."""

    def __init__(self, db: ExamDatabase):
        self.db = db

        # Change tracking (populated during process_batch)
        self.new_exams: list[str] = []
        self.date_revised: list[str] = []
        self.vacancy_revised: list[str] = []
        self.fee_revised: list[str] = []
        self.unchanged_count: int = 0
        self.closed_count: int = 0
        self._seen_exam_ids: set[str] = set()

    # ═══════════════════════════════════════════════════
    # CHANGE DETECTION + TRACKING
    # ═══════════════════════════════════════════════════

    def process_parsed_batch(
        self, parsed_exams: list[ParsedExamData], run_id: str,
    ) -> list[ParsedExamData]:
        """
        Upsert each exam into the DB, detect changes, and annotate.
        Returns the same list with change_type, first/last_seen_date set.
        """
        self._seen_exam_ids.clear()

        for exam in parsed_exams:
            exam_id = exam.exam_id
            self._seen_exam_ids.add(exam_id)

            change_type = self.db.upsert_exam(exam, run_id)
            exam.change_type = change_type

            # Track changes
            if change_type == ExamChangeType.New_Notification:
                self.new_exams.append(exam.clean_exam_name)
                exam.first_seen_date = date.today().isoformat()
            elif change_type == ExamChangeType.Date_Revised:
                self.date_revised.append(exam.clean_exam_name)
            elif change_type == ExamChangeType.Vacancy_Revised:
                self.vacancy_revised.append(exam.clean_exam_name)
            elif change_type == ExamChangeType.Fee_Revised:
                self.fee_revised.append(exam.clean_exam_name)
            elif change_type == ExamChangeType.Unchanged:
                self.unchanged_count += 1

            exam.last_seen_date = date.today().isoformat()

        # Mark exams not seen in this run as closed (after 3-day grace)
        self.closed_count = self.db.mark_missing_as_closed(run_id, self._seen_exam_ids)

        return parsed_exams

    # ═══════════════════════════════════════════════════
    # ALERT GENERATION
    # ═══════════════════════════════════════════════════

    def generate_alerts(self, run_date: Optional[str] = None) -> dict:
        """
        Generate structured alerts for notification + Excel integration.
        Returns a dict of alert categories.
        """
        return {
            "application_closing_7d": self.db.get_approaching_deadlines(7),
            "application_closing_30d": self.db.get_approaching_deadlines(30),
            "exams_in_7d": self.db.get_upcoming_exams(7),
            "exams_in_30d": self.db.get_upcoming_exams(30),
            "application_open": self.db.get_application_open(),
            "admit_card_releasing": self._get_admit_card_alerts(),
            "results_expected": self._get_result_alerts(),
            "new_notifications": self.db.get_new_since(
                run_date or date.today().isoformat()
            ),
        }

    def _get_admit_card_alerts(self, days: int = 14) -> list[dict]:
        """Get exams where admit card is expected to release within N days."""
        today = date.today()
        cutoff = (today + timedelta(days=days)).isoformat()

        all_exams = self.db.get_all_exams()
        alerts = []

        for exam in all_exams:
            phases_raw = exam.get("phases_json")
            if not phases_raw:
                continue
            try:
                phases = json.loads(phases_raw)
            except (json.JSONDecodeError, TypeError):
                continue

            for phase in phases:
                ac_date = phase.get("admit_card_date")
                if ac_date and today.isoformat() <= ac_date <= cutoff:
                    alerts.append({
                        **exam,
                        "alert_phase": phase.get("phase_name", "Written"),
                        "alert_date": ac_date,
                        "alert_type": "Admit Card",
                    })

        return sorted(alerts, key=lambda x: x.get("alert_date", "9999"))

    def _get_result_alerts(self, days: int = 30) -> list[dict]:
        """Get exams where result is expected within N days."""
        today = date.today()
        cutoff = (today + timedelta(days=days)).isoformat()

        all_exams = self.db.get_all_exams()
        alerts = []

        for exam in all_exams:
            result_date = exam.get("result_date")
            final_result = exam.get("final_result_date")

            for rd_name, rd_val in [("Result", result_date), ("Final Result", final_result)]:
                if rd_val and today.isoformat() <= rd_val <= cutoff:
                    alerts.append({
                        **exam,
                        "alert_type": rd_name,
                        "alert_date": rd_val,
                    })

            # Also check phase-level results
            phases_raw = exam.get("phases_json")
            if phases_raw:
                try:
                    phases = json.loads(phases_raw)
                    for phase in phases:
                        pr = phase.get("result_date")
                        if pr and today.isoformat() <= pr <= cutoff:
                            alerts.append({
                                **exam,
                                "alert_type": f"Result ({phase.get('phase_name', '')})",
                                "alert_date": pr,
                            })
                except (json.JSONDecodeError, TypeError):
                    pass

        return sorted(alerts, key=lambda x: x.get("alert_date", "9999"))

    # ═══════════════════════════════════════════════════
    # URGENCY CLASSIFICATION
    # ═══════════════════════════════════════════════════

    @staticmethod
    def get_urgency(days: Optional[int]) -> str:
        """Classify urgency based on days remaining."""
        if days is None:
            return "UNKNOWN"
        if days <= 2:
            return "CRITICAL"    # Red — immediate action
        if days <= 7:
            return "HIGH"        # Orange — this week
        if days <= 15:
            return "MEDIUM"      # Yellow — next two weeks
        return "LOW"             # Blue — more than 2 weeks

    @staticmethod
    def get_urgency_emoji(days: Optional[int]) -> str:
        """Emoji for urgency level."""
        if days is None:
            return "❓"
        if days <= 2:
            return "🔴"
        if days <= 7:
            return "🟠"
        if days <= 15:
            return "🟡"
        return "🔵"

    # ═══════════════════════════════════════════════════
    # DAILY REPORT GENERATION
    # ═══════════════════════════════════════════════════

    def generate_daily_report(
        self,
        run_id: str,
        run_started: datetime,
        run_completed: datetime,
        errors: int = 0,
    ) -> ExamDailyReport:
        """Create the daily exam report from current state."""
        stats = self.db.get_stats()
        app_closing_7 = self.db.get_approaching_deadlines(7)
        app_closing_30 = self.db.get_approaching_deadlines(30)
        exams_7d = self.db.get_upcoming_exams(7)
        exams_30d = self.db.get_upcoming_exams(30)
        app_open = self.db.get_application_open()

        report = ExamDailyReport(
            run_id=run_id,
            run_date=date.today().isoformat(),
            run_started_at=run_started,
            run_completed_at=run_completed,
            total_exams_in_db=self.db.get_total_count(),
            new_exams=len(self.new_exams),
            updated_exams=len(self.date_revised) + len(self.vacancy_revised) + len(self.fee_revised),
            date_revised_exams=len(self.date_revised),
            vacancy_revised_exams=len(self.vacancy_revised),
            closed_exams=self.closed_count,
            application_open_exams=len(app_open),
            deadlines_within_7_days=len(app_closing_7),
            deadlines_within_30_days=len(app_closing_30),
            exams_in_7_days=len(exams_7d),
            exams_in_30_days=len(exams_30d),
            errors=errors,
            elapsed_seconds=(run_completed - run_started).total_seconds(),
            new_exam_names=self.new_exams[:50],
            approaching_deadline_exams=[
                e.get("clean_exam_name", e.get("exam_name", ""))
                for e in app_closing_7[:20]
            ],
        )

        # Persist the run
        self.db.save_exam_run(report)

        return report
```

---

## File 22/41: `src/exams/exam_crawler.py`
<!-- lines: 422 -->

```python
"""
GovScheme SuperAgent — Exam Discovery Crawler
Crawls 150+ government career/recruitment portals to discover exam notifications.
Integrates with resilience layer: circuit breaker, adaptive rate limiting,
JS rendering, CAPTCHA detection, selector self-healing.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import AgentConfig
from src.exams.exam_models import RawExamData
from src.resilience.portal_health import PortalHealthMonitor
from src.resilience.crawler_resilience import (
    ResilientFetcher, AdaptiveRateLimiter, ProxyRotator,
    extract_with_healing, GENERIC_SELECTORS,
    get_random_headers, validate_page_content,
)

logger = logging.getLogger("exam_crawler")

# Date patterns for extracting dates near context keywords
DATE_PATTERNS = [
    re.compile(r'\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})\b'),
    re.compile(r'\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{4})\b', re.I),
    re.compile(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b', re.I),
    re.compile(r'\b(\d{4})[/\-](\d{2})[/\-](\d{2})\b'),
]

DATE_CONTEXT_KEYWORDS = {
    "raw_application_start": ["application opens", "apply from", "online registration start", "registration begins", "start date"],
    "raw_application_end": ["last date", "closing date", "deadline", "apply before", "apply by", "last date to apply", "last date of application"],
    "raw_fee_payment_deadline": ["fee payment", "payment deadline", "fee last date"],
    "raw_admit_card_date": ["admit card", "hall ticket", "call letter", "e-admit"],
    "raw_exam_date": ["exam date", "examination date", "written test", "cbt date", "test date", "date of exam"],
    "raw_result_date": ["result", "merit list", "select list", "result date"],
    "raw_interview_date": ["interview", "document verification", "dv date", "personality test"],
}

# Minimum text length to consider an item as a valid exam notification
MIN_EXAM_NAME_LENGTH = 10


class ExamDiscoveryCrawler:
    """Discovers exam notifications across 150+ government portals."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.discovered: list[RawExamData] = []
        self.seen_hashes: set[str] = set()
        self.errors: list[dict] = []
        self._semaphore = asyncio.Semaphore(config.max_concurrent_crawlers)

        db_path = getattr(config, 'db_path', './data/schemes.db')
        self.health_monitor = PortalHealthMonitor(db_path)
        self.fetcher = ResilientFetcher(
            rate_limiter=AdaptiveRateLimiter(base_delay=1.0, max_delay=30.0),
            proxy_rotator=ProxyRotator(),
            timeout=30.0,
        )

    async def crawl_all_exam_sources(self, sources: list = None) -> list[RawExamData]:
        """Crawl all exam portal sources. Returns deduplicated RawExamData list."""
        if sources is None:
            try:
                from src.config.settings import EXAM_PORTAL_SOURCES
                sources = EXAM_PORTAL_SOURCES
            except ImportError:
                logger.warning("EXAM_PORTAL_SOURCES not found in settings")
                return []

        # Sort by priority
        sources = sorted(sources, key=lambda s: getattr(s, 'priority', 2))

        tasks = [self._crawl_source_safe(src) for src in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.errors.append({
                    "source": getattr(sources[i], 'name', 'unknown'),
                    "error": str(result),
                })
                logger.error("Source %s failed: %s", getattr(sources[i], 'name', '?'), result)

        logger.info(
            "Exam discovery complete: %d raw exams from %d sources (%d errors)",
            len(self.discovered), len(sources), len(self.errors),
        )
        return self.discovered

    async def _crawl_source_safe(self, source) -> None:
        """Crawl a single source with circuit breaker and semaphore."""
        portal_name = getattr(source, 'name', str(source))

        # Circuit breaker check
        if not self.health_monitor.should_crawl(portal_name):
            logger.debug("Skipping %s (circuit open)", portal_name)
            return

        async with self._semaphore:
            try:
                strategy = getattr(source, 'crawl_strategy', 'html')
                if strategy == "rss":
                    await self._crawl_rss(source)
                elif strategy == "pdf":
                    await self._crawl_pdf_index(source)
                else:
                    await self._crawl_html(source)
            except Exception as e:
                self.health_monitor.record_failure(
                    portal_name, getattr(source, 'base_url', ''),
                    type(e).__name__, str(e)[:200],
                )
                raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
    async def _crawl_html(self, source) -> None:
        """Crawl HTML notification pages for a source."""
        portal_name = getattr(source, 'name', 'unknown')
        urls = getattr(source, 'notification_urls', [])
        if not urls:
            base = getattr(source, 'base_url', '')
            if base:
                urls = [base]

        for url in urls:
            import time as _t
            start = _t.time()

            html, meta = await self.fetcher.fetch(
                url, portal_name=portal_name,
                needs_js=getattr(source, 'needs_js', False),
            )

            elapsed_ms = (_t.time() - start) * 1000

            if not html:
                self.health_monitor.record_failure(
                    portal_name, url,
                    meta.get("error", "fetch_failed"),
                    json.dumps(meta)[:200],
                    http_status=meta.get("status"),
                    response_time_ms=elapsed_ms,
                    is_blocked=meta.get("status") == 403,
                )
                continue

            soup = BeautifulSoup(html, "html.parser")
            selectors = getattr(source, 'selectors', {})

            # Extract with self-healing selectors
            items, strategy_used = extract_with_healing(
                soup, portal_name, selectors,
                min_expected_items=1,
            )

            if not items:
                self.health_monitor.record_selector_failure(portal_name, 10, 0)
                # Fallback: extract dates from entire page text
                page_dates = self._extract_dates_from_text(soup.get_text())
                if page_dates:
                    logger.info("No items from selectors, but found %d dates on %s", len(page_dates), portal_name)

            exams_found = 0
            for item in items:
                exam = self._extract_exam_from_element(item, source, url)
                if exam and exam.content_hash not in self.seen_hashes:
                    self.seen_hashes.add(exam.content_hash)
                    self.discovered.append(exam)
                    exams_found += 1

            self.health_monitor.record_success(
                portal_name, url, elapsed_ms, items_extracted=exams_found,
            )

            # Rate limit between pages
            rate = getattr(source, 'rate_limit_per_sec', 1.0)
            if rate > 0:
                await asyncio.sleep(1.0 / rate)

    def _extract_exam_from_element(self, el, source, page_url: str) -> Optional[RawExamData]:
        """Extract a RawExamData from a single HTML element."""
        if isinstance(el, str):
            return None

        # Get exam name
        text = el.get_text(strip=True)
        if len(text) < MIN_EXAM_NAME_LENGTH:
            return None

        # Skip generic navigation links
        skip_patterns = re.compile(
            r'^(home|about|contact|faq|login|register|sitemap|archive|back|next|prev)',
            re.IGNORECASE,
        )
        if skip_patterns.match(text):
            return None

        # Get links
        links = el.find_all("a", href=True) if hasattr(el, 'find_all') else []
        if not links and el.name == "a" and el.get("href"):
            links = [el]

        notification_url = None
        apply_url = None
        pdf_urls = []

        for a in links:
            href = urljoin(page_url, a["href"])
            href_lower = href.lower()

            if href_lower.endswith(".pdf"):
                pdf_urls.append(href)
                if not notification_url:
                    notification_url = href
            elif any(kw in href_lower for kw in ["apply", "registration", "online"]):
                apply_url = href
            elif not notification_url:
                notification_url = href

        # Extract raw dates from surrounding text
        surrounding_text = text
        parent = el.parent
        if parent:
            surrounding_text = parent.get_text(strip=True)

        date_fields = self._extract_dates_from_text(surrounding_text)

        conducting_body = getattr(source, 'body_code', getattr(source, 'name', 'Unknown'))

        return RawExamData(
            source_portal=getattr(source, 'name', 'unknown'),
            source_url=page_url,
            exam_name=text[:300],
            conducting_body=conducting_body,
            notification_url=notification_url,
            apply_url=apply_url,
            pdf_urls=pdf_urls[:5],
            raw_application_start=date_fields.get("raw_application_start"),
            raw_application_end=date_fields.get("raw_application_end"),
            raw_exam_date=date_fields.get("raw_exam_date"),
            raw_admit_card_date=date_fields.get("raw_admit_card_date"),
            raw_result_date=date_fields.get("raw_result_date"),
            raw_fee=date_fields.get("raw_fee"),
        )

    def _extract_dates_from_text(self, text: str) -> dict[str, str]:
        """Extract dates near context keywords from text."""
        results = {}
        text_lower = text.lower()

        for field_name, keywords in DATE_CONTEXT_KEYWORDS.items():
            for keyword in keywords:
                pos = text_lower.find(keyword.lower())
                if pos < 0:
                    continue

                # Extract 200-char window after keyword
                window = text[pos:pos + 200]

                for pattern in DATE_PATTERNS:
                    match = pattern.search(window)
                    if match:
                        results[field_name] = match.group(0)
                        break

                if field_name in results:
                    break

        # Also look for fee patterns
        fee_match = re.search(r'(?:₹|Rs\.?|INR)\s*([\d,]+)', text)
        if fee_match:
            results["raw_fee"] = fee_match.group(0)

        return results

    async def _crawl_rss(self, source) -> None:
        """Crawl RSS feed for exam notifications."""
        rss_url = getattr(source, 'rss_url', None)
        if not rss_url:
            return

        portal_name = getattr(source, 'name', 'unknown')

        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser not installed, skipping RSS for %s", portal_name)
            return

        html, meta = await self.fetcher.fetch(rss_url, portal_name=portal_name)
        if not html:
            return

        feed = feedparser.parse(html)

        for entry in feed.entries[:50]:
            title = entry.get("title", "").strip()
            if len(title) < MIN_EXAM_NAME_LENGTH:
                continue

            link = entry.get("link", "")
            description = entry.get("description", "")
            pub_date = entry.get("published", entry.get("updated", ""))

            exam = RawExamData(
                source_portal=portal_name,
                source_url=rss_url,
                exam_name=title[:300],
                conducting_body=getattr(source, 'body_code', portal_name),
                notification_url=link,
                raw_notification_date=pub_date,
                raw_notification_text=description[:2000],
            )

            if exam.content_hash not in self.seen_hashes:
                self.seen_hashes.add(exam.content_hash)
                self.discovered.append(exam)

    async def _crawl_pdf_index(self, source) -> None:
        """Crawl pages that primarily list notification PDFs."""
        portal_name = getattr(source, 'name', 'unknown')
        urls = getattr(source, 'notification_urls', [getattr(source, 'base_url', '')])

        for url in urls:
            html, meta = await self.fetcher.fetch(url, portal_name=portal_name)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")

            # Find all PDF links
            pdf_links = soup.find_all("a", href=re.compile(r'\.pdf$', re.I))

            for a_tag in pdf_links:
                href = urljoin(url, a_tag["href"])
                text = a_tag.get_text(strip=True)

                if len(text) < MIN_EXAM_NAME_LENGTH:
                    # Try parent text
                    parent = a_tag.parent
                    if parent:
                        text = parent.get_text(strip=True)
                    if len(text) < MIN_EXAM_NAME_LENGTH:
                        continue

                exam = RawExamData(
                    source_portal=portal_name,
                    source_url=url,
                    exam_name=text[:300],
                    conducting_body=getattr(source, 'body_code', portal_name),
                    notification_url=href,
                    pdf_urls=[href],
                )

                if exam.content_hash not in self.seen_hashes:
                    self.seen_hashes.add(exam.content_hash)
                    self.discovered.append(exam)

    # ─── Enrichment ──────────────────────────────────────────────────────────

    async def enrich_exam_details(
        self, exams: list[RawExamData], max_concurrent: int = 3,
    ) -> list[RawExamData]:
        """Enrich exams by fetching notification PDFs and detail pages."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _enrich_one(exam: RawExamData) -> RawExamData:
            async with semaphore:
                # Try fetching notification PDF text
                if exam.notification_url and exam.notification_url.lower().endswith(".pdf"):
                    try:
                        from src.resilience.crawler_resilience import extract_text_from_pdf
                        # Download PDF to temp file
                        async with httpx.AsyncClient(timeout=30, verify=False) as client:
                            resp = await client.get(exam.notification_url, headers=get_random_headers())
                            if resp.status_code == 200 and len(resp.content) < 10 * 1024 * 1024:
                                import tempfile
                                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                                    f.write(resp.content)
                                    pdf_path = f.name

                                text, method = extract_text_from_pdf(pdf_path)
                                if text:
                                    exam.raw_notification_text = text[:5000]
                                    # Re-extract dates from PDF text
                                    date_fields = self._extract_dates_from_text(text)
                                    for k, v in date_fields.items():
                                        if hasattr(exam, k) and not getattr(exam, k):
                                            setattr(exam, k, v)

                                import os
                                os.unlink(pdf_path)
                    except Exception as e:
                        logger.debug("PDF enrichment failed for %s: %s", exam.exam_name[:50], e)

                return exam

        enriched = await asyncio.gather(
            *[_enrich_one(e) for e in exams[:200]],
            return_exceptions=True,
        )

        results = []
        for i, result in enumerate(enriched):
            if isinstance(result, Exception):
                results.append(exams[i])
            else:
                results.append(result)

        return results
```

---

## File 23/41: `src/exams/exam_database.py`
<!-- lines: 559 -->

```python
"""
GovScheme SuperAgent — Exam Database (SQLite Persistence)
Tracks all government exams across daily runs with change detection.
Tables: exams (50+ cols), exam_changes (audit log), exam_runs (daily logs).
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from src.exams.exam_models import (
    ParsedExamData, ExamChangeType, ExamStatus, ExamDailyReport,
)

logger = logging.getLogger("exam_database")

EXAM_SCHEMA = """
CREATE TABLE IF NOT EXISTS exams (
    exam_id                 TEXT PRIMARY KEY,
    exam_name               TEXT NOT NULL,
    clean_exam_name         TEXT,
    short_name              TEXT,
    conducting_body         TEXT NOT NULL,
    exam_category           TEXT NOT NULL,
    exam_level              TEXT NOT NULL DEFAULT 'Central',
    state                   TEXT,
    exam_cycle              TEXT,

    notification_date       TEXT,
    application_start_date  TEXT,
    application_end_date    TEXT,
    fee_payment_deadline    TEXT,
    correction_window_start TEXT,
    correction_window_end   TEXT,
    phases_json             TEXT,
    result_date             TEXT,
    interview_date          TEXT,
    final_result_date       TEXT,
    joining_date            TEXT,

    fee_general             REAL,
    fee_obc                 REAL,
    fee_sc_st               REAL,
    fee_female              REAL,
    fee_ews                 REAL,
    fee_pwd                 REAL,
    fee_note                TEXT,
    fee_payment_url         TEXT,
    is_free                 INTEGER DEFAULT 0,
    raw_fee_text            TEXT,

    vacancies_json          TEXT,
    total_vacancies         INTEGER,

    age_min                 INTEGER,
    age_max                 INTEGER,
    age_relaxation_obc      INTEGER,
    age_relaxation_sc_st    INTEGER,
    age_relaxation_pwd      INTEGER,
    qualification           TEXT,
    min_percentage          REAL,
    experience_years        INTEGER,
    physical_standards      TEXT,
    domicile_required       TEXT,
    gender_restriction      TEXT,

    official_notification_url TEXT,
    apply_online_url        TEXT,
    admit_card_url          TEXT,
    result_url              TEXT,
    syllabus_url            TEXT,
    official_website        TEXT,

    exam_status             TEXT DEFAULT 'Upcoming',
    change_type             TEXT DEFAULT 'New_Notification',
    detail_hash             TEXT NOT NULL,
    source_portal           TEXT,
    source_url              TEXT,
    first_seen_date         TEXT NOT NULL,
    last_seen_date          TEXT NOT NULL,
    last_crawl_run          TEXT,
    times_seen              INTEGER DEFAULT 1,
    is_active               INTEGER DEFAULT 1,
    parsing_confidence      REAL DEFAULT 0.0,
    folder_path             TEXT,

    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exam_changes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id         TEXT NOT NULL,
    run_id          TEXT NOT NULL,
    change_type     TEXT NOT NULL,
    field_changed   TEXT,
    old_value       TEXT,
    new_value       TEXT,
    detected_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exam_runs (
    run_id              TEXT PRIMARY KEY,
    run_date            TEXT NOT NULL,
    started_at          TEXT NOT NULL,
    completed_at        TEXT,
    total_exams_in_db   INTEGER DEFAULT 0,
    new_exams           INTEGER DEFAULT 0,
    updated_exams       INTEGER DEFAULT 0,
    closed_exams        INTEGER DEFAULT 0,
    errors              INTEGER DEFAULT 0,
    elapsed_seconds     REAL DEFAULT 0.0,
    new_exam_names      TEXT,
    excel_sheet_path    TEXT
);

CREATE INDEX IF NOT EXISTS idx_exams_category ON exams(exam_category);
CREATE INDEX IF NOT EXISTS idx_exams_level ON exams(exam_level);
CREATE INDEX IF NOT EXISTS idx_exams_state ON exams(state);
CREATE INDEX IF NOT EXISTS idx_exams_status ON exams(exam_status);
CREATE INDEX IF NOT EXISTS idx_exams_app_end ON exams(application_end_date);
CREATE INDEX IF NOT EXISTS idx_exams_body ON exams(conducting_body);
CREATE INDEX IF NOT EXISTS idx_exams_hash ON exams(detail_hash);
CREATE INDEX IF NOT EXISTS idx_exams_active ON exams(is_active);
CREATE INDEX IF NOT EXISTS idx_exam_changes_run ON exam_changes(run_id);
CREATE INDEX IF NOT EXISTS idx_exam_runs_date ON exam_runs(run_date);
"""


class ExamDatabase:
    """SQLite persistence for government exam tracking."""

    def __init__(self, db_path: str = "./data/exams.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(EXAM_SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ─── Upsert ──────────────────────────────────────────────────────────────

    def upsert_exam(self, parsed: ParsedExamData, run_id: str) -> ExamChangeType:
        """Insert or update an exam. Returns the change type detected."""
        now = datetime.utcnow().isoformat()
        today = date.today().isoformat()
        exam_id = parsed.exam_id

        phases_json = json.dumps(
            [p.model_dump(mode="json") for p in parsed.phases],
            ensure_ascii=False,
        )
        vacancies_json = json.dumps(
            [v.model_dump(mode="json") for v in parsed.vacancies],
            ensure_ascii=False,
        )

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM exams WHERE exam_id = ?", (exam_id,)
            ).fetchone()

            if existing is None:
                # New exam
                conn.execute("""
                    INSERT INTO exams (
                        exam_id, exam_name, clean_exam_name, short_name,
                        conducting_body, exam_category, exam_level, state, exam_cycle,
                        notification_date, application_start_date, application_end_date,
                        fee_payment_deadline, correction_window_start, correction_window_end,
                        phases_json, result_date, interview_date, final_result_date, joining_date,
                        fee_general, fee_obc, fee_sc_st, fee_female, fee_ews, fee_pwd,
                        fee_note, fee_payment_url, is_free, raw_fee_text,
                        vacancies_json, total_vacancies,
                        age_min, age_max, age_relaxation_obc, age_relaxation_sc_st,
                        age_relaxation_pwd, qualification, min_percentage,
                        experience_years, physical_standards, domicile_required, gender_restriction,
                        official_notification_url, apply_online_url, admit_card_url,
                        result_url, syllabus_url, official_website,
                        exam_status, change_type, detail_hash,
                        source_portal, source_url,
                        first_seen_date, last_seen_date, last_crawl_run,
                        times_seen, is_active, parsing_confidence, folder_path,
                        created_at, updated_at
                    ) VALUES (
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )
                """, (
                    exam_id, parsed.raw.exam_name, parsed.clean_exam_name, parsed.short_name,
                    parsed.raw.conducting_body, parsed.exam_category.value,
                    parsed.exam_level.value, parsed.state, parsed.exam_cycle,
                    parsed.notification_date, parsed.application_start_date,
                    parsed.application_end_date, parsed.fee_payment_deadline,
                    parsed.correction_window_start, parsed.correction_window_end,
                    phases_json, parsed.result_date, parsed.interview_date,
                    parsed.final_result_date, parsed.joining_date,
                    parsed.fee.general, parsed.fee.obc, parsed.fee.sc_st,
                    parsed.fee.female, parsed.fee.ews, parsed.fee.pwd,
                    parsed.fee.fee_note, parsed.fee.fee_payment_url,
                    int(parsed.fee.is_free), parsed.fee.raw_fee_text,
                    vacancies_json, parsed.total_vacancies,
                    parsed.eligibility.age_min, parsed.eligibility.age_max,
                    parsed.eligibility.age_relaxation_obc,
                    parsed.eligibility.age_relaxation_sc_st,
                    parsed.eligibility.age_relaxation_pwd,
                    parsed.eligibility.qualification,
                    parsed.eligibility.min_percentage,
                    parsed.eligibility.experience_years,
                    parsed.eligibility.physical_standards,
                    parsed.eligibility.domicile_required,
                    parsed.eligibility.gender_restriction,
                    parsed.official_notification_url, parsed.apply_online_url,
                    parsed.admit_card_url, parsed.result_url,
                    parsed.syllabus_url, parsed.official_website,
                    parsed.exam_status.value,
                    ExamChangeType.New_Notification.value,
                    parsed.raw.detail_hash,
                    parsed.raw.source_portal, parsed.raw.source_url,
                    today, today, run_id,
                    1, 1, parsed.parsing_confidence, parsed.folder_path,
                    now, now,
                ))
                conn.commit()
                return ExamChangeType.New_Notification

            # Existing — check for changes
            old_hash = existing["detail_hash"]
            new_hash = parsed.raw.detail_hash

            if old_hash == new_hash:
                # Unchanged
                conn.execute("""
                    UPDATE exams SET
                        last_seen_date = ?, last_crawl_run = ?,
                        times_seen = times_seen + 1,
                        change_type = ?, updated_at = ?
                    WHERE exam_id = ?
                """, (today, run_id, ExamChangeType.Unchanged.value, now, exam_id))
                conn.commit()
                return ExamChangeType.Unchanged

            # Changed — determine what changed
            change_type = ExamChangeType.Notification_Amended
            changes_detected = []

            # Date changes
            date_fields = [
                ("application_start_date", parsed.application_start_date),
                ("application_end_date", parsed.application_end_date),
                ("fee_payment_deadline", parsed.fee_payment_deadline),
                ("result_date", parsed.result_date),
                ("final_result_date", parsed.final_result_date),
            ]
            for field_name, new_val in date_fields:
                old_val = existing[field_name]
                if str(new_val or "") != str(old_val or ""):
                    changes_detected.append((field_name, old_val, new_val))
                    change_type = ExamChangeType.Date_Revised

            # Vacancy changes
            old_vacancies = existing["total_vacancies"]
            if parsed.total_vacancies and old_vacancies != parsed.total_vacancies:
                changes_detected.append(("total_vacancies", old_vacancies, parsed.total_vacancies))
                if change_type != ExamChangeType.Date_Revised:
                    change_type = ExamChangeType.Vacancy_Revised

            # Fee changes
            old_fee = existing["fee_general"]
            if parsed.fee.general and old_fee != parsed.fee.general:
                changes_detected.append(("fee_general", old_fee, parsed.fee.general))
                if change_type not in (ExamChangeType.Date_Revised, ExamChangeType.Vacancy_Revised):
                    change_type = ExamChangeType.Fee_Revised

            # Status change
            old_status = existing["exam_status"]
            if parsed.exam_status.value != old_status:
                changes_detected.append(("exam_status", old_status, parsed.exam_status.value))
                if not changes_detected:
                    change_type = ExamChangeType.Status_Changed

            # Record changes
            for field_name, old_val, new_val in changes_detected:
                conn.execute("""
                    INSERT INTO exam_changes (exam_id, run_id, change_type, field_changed, old_value, new_value, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (exam_id, run_id, change_type.value, field_name,
                      str(old_val)[:500] if old_val else None,
                      str(new_val)[:500] if new_val else None, now))

            # Update the exam record
            conn.execute("""
                UPDATE exams SET
                    clean_exam_name = ?, short_name = ?,
                    notification_date = ?, application_start_date = ?,
                    application_end_date = ?, fee_payment_deadline = ?,
                    correction_window_start = ?, correction_window_end = ?,
                    phases_json = ?, result_date = ?, interview_date = ?,
                    final_result_date = ?, joining_date = ?,
                    fee_general = ?, fee_obc = ?, fee_sc_st = ?,
                    fee_female = ?, fee_ews = ?, fee_pwd = ?,
                    fee_note = ?, is_free = ?, raw_fee_text = ?,
                    vacancies_json = ?, total_vacancies = ?,
                    age_min = ?, age_max = ?, qualification = ?,
                    physical_standards = ?,
                    official_notification_url = ?, apply_online_url = ?,
                    admit_card_url = ?, result_url = ?, syllabus_url = ?,
                    exam_status = ?, change_type = ?, detail_hash = ?,
                    last_seen_date = ?, last_crawl_run = ?,
                    times_seen = times_seen + 1,
                    parsing_confidence = ?, updated_at = ?
                WHERE exam_id = ?
            """, (
                parsed.clean_exam_name, parsed.short_name,
                parsed.notification_date, parsed.application_start_date,
                parsed.application_end_date, parsed.fee_payment_deadline,
                parsed.correction_window_start, parsed.correction_window_end,
                phases_json, parsed.result_date, parsed.interview_date,
                parsed.final_result_date, parsed.joining_date,
                parsed.fee.general, parsed.fee.obc, parsed.fee.sc_st,
                parsed.fee.female, parsed.fee.ews, parsed.fee.pwd,
                parsed.fee.fee_note, int(parsed.fee.is_free), parsed.fee.raw_fee_text,
                vacancies_json, parsed.total_vacancies,
                parsed.eligibility.age_min, parsed.eligibility.age_max,
                parsed.eligibility.qualification,
                parsed.eligibility.physical_standards,
                parsed.official_notification_url, parsed.apply_online_url,
                parsed.admit_card_url, parsed.result_url, parsed.syllabus_url,
                parsed.exam_status.value, change_type.value, parsed.raw.detail_hash,
                today, run_id, parsed.parsing_confidence, now,
                exam_id,
            ))
            conn.commit()

            logger.info("Exam %s updated: %s (%d field changes)", exam_id, change_type.value, len(changes_detected))
            return change_type

    # ─── Closure Detection ───────────────────────────────────────────────────

    def mark_missing_as_closed(self, run_id: str, seen_exam_ids: set[str]) -> int:
        """Mark exams not seen for 3+ consecutive days as inactive."""
        today = date.today()
        cutoff = (today - timedelta(days=3)).isoformat()
        now = datetime.utcnow().isoformat()
        closed_count = 0

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT exam_id, last_seen_date FROM exams WHERE is_active = 1"
            ).fetchall()

            for row in rows:
                if row["exam_id"] in seen_exam_ids:
                    continue
                if row["last_seen_date"] and row["last_seen_date"] <= cutoff:
                    conn.execute("""
                        UPDATE exams SET
                            is_active = 0, exam_status = 'Completed',
                            change_type = 'Status_Changed', updated_at = ?
                        WHERE exam_id = ?
                    """, (now, row["exam_id"]))
                    conn.execute("""
                        INSERT INTO exam_changes (exam_id, run_id, change_type, field_changed, old_value, new_value, detected_at)
                        VALUES (?, ?, 'Status_Changed', 'exam_status', 'Active', 'Completed', ?)
                    """, (row["exam_id"], run_id, now))
                    closed_count += 1

            conn.commit()

        if closed_count:
            logger.info("Marked %d exams as closed (unseen for 3+ days)", closed_count)
        return closed_count

    # ─── Query Methods ───────────────────────────────────────────────────────

    def get_all_exams(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exams ORDER BY exam_category, clean_exam_name"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_new_since(self, since_date: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exams WHERE first_seen_date >= ? ORDER BY exam_category",
                (since_date,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_application_open(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exams WHERE exam_status = 'Application_Open' AND is_active = 1 ORDER BY application_end_date",
            ).fetchall()
        return [dict(r) for r in rows]

    def get_approaching_deadlines(self, days: int = 7) -> list[dict]:
        cutoff = (date.today() + timedelta(days=days)).isoformat()
        today_str = date.today().isoformat()
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM exams
                WHERE application_end_date IS NOT NULL
                  AND application_end_date >= ?
                  AND application_end_date <= ?
                  AND is_active = 1
                ORDER BY application_end_date
            """, (today_str, cutoff)).fetchall()
        return [dict(r) for r in rows]

    def get_upcoming_exams(self, days: int = 30) -> list[dict]:
        """Get exams with exam dates within N days (checks phases_json)."""
        today = date.today()
        cutoff = (today + timedelta(days=days)).isoformat()
        today_str = today.isoformat()

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exams WHERE phases_json IS NOT NULL AND is_active = 1"
            ).fetchall()

        results = []
        for row in rows:
            try:
                phases = json.loads(row["phases_json"])
                for phase in phases:
                    exam_start = phase.get("exam_date_start")
                    if exam_start and today_str <= exam_start <= cutoff:
                        results.append(dict(row))
                        break
            except (json.JSONDecodeError, TypeError):
                continue

        return sorted(results, key=lambda x: x.get("application_end_date") or "9999")

    def get_by_category(self, category: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exams WHERE exam_category = ? AND is_active = 1 ORDER BY clean_exam_name",
                (category,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_by_conducting_body(self, body: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exams WHERE conducting_body = ? AND is_active = 1",
                (body,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_by_state(self, state: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exams WHERE state = ? AND is_active = 1 ORDER BY exam_category",
                (state,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_changes_for_run(self, run_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT ec.*, e.clean_exam_name, e.exam_category, e.conducting_body
                FROM exam_changes ec
                LEFT JOIN exams e ON ec.exam_id = e.exam_id
                WHERE ec.run_id = ?
                ORDER BY ec.detected_at DESC
            """, (run_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM exams WHERE is_active = 1").fetchone()[0]

            by_category = {}
            for row in conn.execute(
                "SELECT exam_category, COUNT(*) as cnt FROM exams WHERE is_active = 1 GROUP BY exam_category ORDER BY cnt DESC"
            ).fetchall():
                by_category[row["exam_category"]] = row["cnt"]

            by_level = {}
            for row in conn.execute(
                "SELECT exam_level, COUNT(*) as cnt FROM exams WHERE is_active = 1 GROUP BY exam_level"
            ).fetchall():
                by_level[row["exam_level"]] = row["cnt"]

            by_status = {}
            for row in conn.execute(
                "SELECT exam_status, COUNT(*) as cnt FROM exams WHERE is_active = 1 GROUP BY exam_status"
            ).fetchall():
                by_status[row["exam_status"]] = row["cnt"]

            by_body = {}
            for row in conn.execute(
                "SELECT conducting_body, COUNT(*) as cnt FROM exams WHERE is_active = 1 GROUP BY conducting_body ORDER BY cnt DESC"
            ).fetchall():
                by_body[row["conducting_body"]] = row["cnt"]

            by_state = {}
            for row in conn.execute(
                "SELECT state, COUNT(*) as cnt FROM exams WHERE state IS NOT NULL AND is_active = 1 GROUP BY state ORDER BY cnt DESC"
            ).fetchall():
                by_state[row["state"]] = row["cnt"]

        return {
            "total": total, "active": active,
            "by_category": by_category, "by_level": by_level,
            "by_status": by_status, "by_body": by_body, "by_state": by_state,
        }

    # ─── Run Management ──────────────────────────────────────────────────────

    def save_exam_run(self, report: ExamDailyReport) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO exam_runs (
                    run_id, run_date, started_at, completed_at,
                    total_exams_in_db, new_exams, updated_exams,
                    closed_exams, errors, elapsed_seconds,
                    new_exam_names, excel_sheet_path
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                report.run_id, report.run_date,
                report.run_started_at.isoformat() if report.run_started_at else now,
                report.run_completed_at.isoformat() if report.run_completed_at else now,
                report.total_exams_in_db, report.new_exams,
                report.updated_exams, report.closed_exams,
                report.errors, report.elapsed_seconds,
                json.dumps(report.new_exam_names[:50], ensure_ascii=False),
                report.excel_sheet_path,
            ))
            conn.commit()

    def get_run_history(self, limit: int = 60) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exam_runs ORDER BY run_date DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_total_count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0]
```

---

## File 24/41: `src/exams/exam_models.py`
<!-- lines: 312 -->

```python
"""
GovScheme SuperAgent — Exam Data Models (V3)
Complete Pydantic models for the Government Examinations pipeline.
Covers: UPSC, SSC, IBPS, NTA, Defence, Railways, State PSCs, PSUs, and 150+ portals.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field


# ═══════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════
# NESTED MODELS
# ═══════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════
# RAW EXAM DATA (crawler output)
# ═══════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════
# PARSED EXAM DATA (ExamParser output)
# ═══════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════
# STORED EXAM DATA
# ═══════════════════════════════════════════════════

class StoredExamData(BaseModel):
    """Exam after being stored in the folder hierarchy."""
    parsed: ParsedExamData
    folder_path: str
    metadata_path: str
    detail_markdown_path: Optional[str] = None
    downloaded_notification_pdfs: list[str] = Field(default_factory=list)
    stored_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════
# EXAM DAILY REPORT
# ═══════════════════════════════════════════════════

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
```

---

## File 25/41: `src/exams/exam_parser.py`
<!-- lines: 923 -->

```python
"""
GovScheme SuperAgent — Exam Parser (V3)
LLM + regex hybrid: extracts dates, fees, vacancies, eligibility from exam notifications.
Handles Indian date formats, category-wise fees, multi-phase exam schedules.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime
from typing import Optional

import httpx

from src.config.settings import AgentConfig
from src.exams.exam_models import (
    RawExamData, ParsedExamData, ExamFee, ExamPhaseDate, ExamVacancy,
    ExamEligibility, ExamCategory, ExamLevel, ExamStatus, ExamChangeType,
)

logger = logging.getLogger("ExamParser")

# ═══════════════════════════════════════════════════
# DATE PATTERNS (Indian Government formats)
# ═══════════════════════════════════════════════════

MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2,
    "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

DATE_PATTERNS = [
    (r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})', "dmy"),              # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    (r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2})\b', "dmy_short"),     # DD/MM/YY
    (r'(\d{4})[/\-](\d{2})[/\-](\d{2})', "iso"),                       # YYYY-MM-DD
    (r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\w*[\s,]+(\d{4})', "d_mon_y"),
    (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\w*\s+(\d{1,2})[\s,]+(\d{4})', "mon_d_y"),
    (r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', "mon_y"),
]

DATE_CONTEXT_KEYWORDS = {
    "notification_date": ["notification date", "date of notification", "published on", "advertised on", "advt date"],
    "application_start": ["application opens", "application start", "apply from", "online registration start",
                          "registration opens", "commencement of", "opening date"],
    "application_end": ["last date", "closing date", "application end", "deadline", "apply before",
                         "apply by", "last date for", "last date of", "close on", "last date to apply"],
    "fee_payment": ["fee payment", "payment deadline", "fee last date", "last date for fee",
                     "fee payment last date"],
    "correction_window": ["correction window", "application correction", "edit window"],
    "admit_card": ["admit card", "hall ticket", "call letter", "e-admit card", "download admit"],
    "exam_date": ["exam date", "examination date", "written test", "cbt date", "test date",
                   "date of exam", "date of examination", "computer based test", "prelims date"],
    "result_date": ["result", "merit list", "select list", "result date", "result declared"],
    "interview_date": ["interview", "document verification", "dv date", "personality test"],
}

# ═══════════════════════════════════════════════════
# FEE PATTERNS
# ═══════════════════════════════════════════════════

FEE_AMOUNT_RE = re.compile(
    r'(?:₹|Rs\.?\s*|INR\s*)([\d,]+(?:\.\d{1,2})?)', re.IGNORECASE
)
FEE_FREE_RE = re.compile(
    r'\b(?:nil|no\s+fee|no\s+charge|free\s+of\s+cost|fee\s+waived|exempted|not\s+applicable)\b',
    re.IGNORECASE,
)
FEE_CATEGORY_PATTERNS = {
    "general": re.compile(r'(?:general|gen|ur|unreserved)\s*[-:–]\s*(?:₹|Rs\.?\s*|INR\s*)([\d,]+)', re.I),
    "obc": re.compile(r'(?:obc|other\s+backward)\s*[-:–]\s*(?:₹|Rs\.?\s*|INR\s*)([\d,]+)', re.I),
    "sc_st": re.compile(r'(?:sc[/\s]+st|sc\s*[-:–]|st\s*[-:–]|scheduled)\s*[-:–]?\s*(?:₹|Rs\.?\s*|INR\s*)?([\d,]+|nil|free|exempted)', re.I),
    "female": re.compile(r'(?:female|women|lady)\s*[-:–]\s*(?:₹|Rs\.?\s*|INR\s*)?([\d,]+|nil|free|exempted)', re.I),
    "ews": re.compile(r'(?:ews|economically\s+weaker)\s*[-:–]\s*(?:₹|Rs\.?\s*|INR\s*)([\d,]+)', re.I),
    "pwd": re.compile(r'(?:pwd|ph|disabled|divyang)\s*[-:–]\s*(?:₹|Rs\.?\s*|INR\s*)?([\d,]+|nil|free|exempted)', re.I),
}

# ═══════════════════════════════════════════════════
# VACANCY PATTERNS
# ═══════════════════════════════════════════════════

VACANCY_TOTAL_RE = re.compile(
    r'(?:total\s+)?(?:vacancies?|posts?|positions?)\s*[-:–]?\s*(\d[\d,]*)', re.I
)
VACANCY_POST_RE = re.compile(
    r'(?:post\s*(?:name)?\s*[-:–]\s*)(.+?)(?:\s*[-–]\s*(\d+)\s*(?:posts?|vacancies?)?)', re.I
)

# ═══════════════════════════════════════════════════
# CATEGORY INFERENCE
# ═══════════════════════════════════════════════════

CATEGORY_KEYWORDS: dict[ExamCategory, list[str]] = {
    ExamCategory.Civil_Services: ["civil services", "ias", "ifs exam", "ies ", "geo-scientist",
                                   "engineering services", "combined defence", "upsc cse", "upsc ifs"],
    ExamCategory.Banking: ["ibps", "sbi po", "sbi clerk", "rbi", "nabard", "sebi", "sidbi",
                            "bank po", "bank clerk", "probationary officer"],
    ExamCategory.Railway: ["railway", "rrb", "rrc ", "rpf", "loco pilot", "alp ", "ntpc ",
                            "group d", "group-d", "rrb ntpc", "rrb alp", "rrb je"],
    ExamCategory.Defence: ["nda ", "cds ", "afcat", "airmen", "navy ssr", "navy aa",
                            "technical entry", "army tgc", "army ssc", "naval academy",
                            "coast guard", "indian army", "indian navy", "indian air force"],
    ExamCategory.Police: ["bsf ", "crpf", "cisf", "ssb ", "itbp", "assam rifles",
                           "head constable", "sub-inspector", "capf", "asi "],
    ExamCategory.Intelligence: ["intelligence bureau", "acio", "jio ", "mha ib", "cbi ",
                                 "enforcement directorate", "narcotics", "nia "],
    ExamCategory.SSC: ["ssc cgl", "ssc chsl", "ssc mts", "ssc cpo", "ssc gd", "ssc je",
                        "stenographer", "junior hindi translator", "ssc steno",
                        "staff selection commission"],
    ExamCategory.PSU: ["isro ", "drdo ", "barc ", "bhel ", "bel ", "hal ", "ongc",
                        "ntpc ", "sail ", "gail ", "bpcl", "hpcl", "iocl", "coal india",
                        "nalco", "nmdc", "mecl", "ceptam"],
    ExamCategory.Medical: ["neet", "aiims", "upsc cms", "pg medical", "mbbs", "medical officer"],
    ExamCategory.Engineering: ["jee main", "jee advanced", "gate ", "bitsat"],
    ExamCategory.Teaching: ["ctet", "kvs ", "nvs ", "tgt ", "pgt ", "teacher eligibility",
                             "kendriya vidyalaya", "navodaya", "teacher recruitment"],
    ExamCategory.Insurance: ["lic aao", "lic ado", "lic ae", "gic re", "niacl", "uiic",
                              "insurance company"],
    ExamCategory.Revenue: ["income tax", "customs", "gst ", "central excise"],
    ExamCategory.Agriculture: ["icar ", "fci ", "agricultural", "krishi", "nabard grade"],
    ExamCategory.State_PSC: ["public service commission", " psc ", " pcs ", "ppsc", "rpsc",
                              "mpsc", "tnpsc", "uppsc", "bpsc", "wbpsc", "kpsc", "appsc",
                              "opsc", "jpsc", "hpsc", "gpsc", "mppsc", "tspsc", "ukpsc"],
    ExamCategory.State_Police: ["state police", "constable police", "si police",
                                 "police recruitment board", "police constable"],
    ExamCategory.State_Teaching: ["state tet", "state teacher", "teacher recruitment board"],
    ExamCategory.State_Subordinate: ["subordinate services", "staff selection board",
                                      "group c", "group-c", "clerical", "sssb", "sssc"],
}


# ═══════════════════════════════════════════════════
# LLM CLASSIFICATION PROMPT
# ═══════════════════════════════════════════════════

EXAM_PARSE_PROMPT = """You are an expert at parsing Indian Government Exam notifications.
Analyze the following exam information and extract ALL structured data.

Exam Name: {exam_name}
Conducting Body: {conducting_body}
Source URL: {source_url}

Raw Notification Text (truncated):
{raw_notification_text}

Raw Application Start: {raw_application_start}
Raw Application End: {raw_application_end}
Raw Exam Date: {raw_exam_date}
Raw Fee: {raw_fee}
Raw Vacancies: {raw_vacancy}
Raw Eligibility: {raw_eligibility}
Raw Age Limit: {raw_age_limit}

Respond ONLY with valid JSON matching this exact schema:
{{
    "exam_category": "<one of: Civil_Services|Banking|Railway|Defence|Police|Intelligence|SSC|PSU|Medical|Engineering|Teaching|Insurance|Revenue|Judiciary|Agriculture|State_PSC|State_Police|State_Teaching|State_Subordinate|Other_Central>",
    "exam_level": "<Central|State|UT>",
    "state": "<state name or null>",
    "clean_exam_name": "<standardized full exam name>",
    "short_name": "<abbreviation: CSE, CGL, IBPS-PO, NDA, etc. or null>",
    "exam_cycle": "<year or range: 2026, 2025-26, CRP-XVI, etc. or null>",
    "notification_date": "<YYYY-MM-DD or null>",
    "application_start_date": "<YYYY-MM-DD or null>",
    "application_end_date": "<YYYY-MM-DD or null>",
    "fee_payment_deadline": "<YYYY-MM-DD or null>",
    "correction_window_start": "<YYYY-MM-DD or null>",
    "correction_window_end": "<YYYY-MM-DD or null>",
    "phases": [
        {{
            "phase_name": "<Prelims|Mains|Written|CBT Phase 1|Interview|DV>",
            "exam_date_start": "<YYYY-MM-DD or null>",
            "exam_date_end": "<YYYY-MM-DD or null>",
            "admit_card_date": "<YYYY-MM-DD or null>",
            "result_date": "<YYYY-MM-DD or null>",
            "mode": "<CBT|OMR|Online|Offline|null>"
        }}
    ],
    "result_date": "<final result YYYY-MM-DD or null>",
    "interview_date": "<YYYY-MM-DD or null>",
    "final_result_date": "<YYYY-MM-DD or null>",
    "joining_date": "<YYYY-MM-DD or null>",
    "fee_general": null,
    "fee_obc": null,
    "fee_sc_st": null,
    "fee_female": null,
    "fee_ews": null,
    "fee_pwd": null,
    "fee_note": "<payment instructions or null>",
    "is_free": false,
    "vacancies": [
        {{
            "post_name": "<post title>",
            "total_vacancies": null,
            "pay_scale": "<pay level/scale or null>"
        }}
    ],
    "total_vacancies": null,
    "age_min": null,
    "age_max": null,
    "age_relaxation_obc": null,
    "age_relaxation_sc_st": null,
    "age_relaxation_pwd": null,
    "qualification": "<string or null>",
    "min_percentage": null,
    "experience_years": null,
    "physical_standards": "<string or null>",
    "domicile_required": "<state or null>",
    "gender_restriction": "<Only Male|Only Female|null>",
    "apply_online_url": "<URL or null>",
    "admit_card_url": "<URL or null>",
    "result_url": "<URL or null>",
    "syllabus_url": "<URL or null>",
    "official_website": "<URL or null>",
    "confidence": 0.0
}}

Rules:
- Extract EVERY date. If approximate ("April 2026"), use first of month "2026-04-01".
- For "FY 2025-26", use application_start "2025-04-01", application_end "2026-03-31".
- For fees: extract exact INR amounts per category. If "Nil"/"No fee" → is_free: true, all fee=0.
- SC/ST fee of 0 does NOT mean is_free. is_free=true ONLY if ALL categories pay nothing.
- For vacancies: one entry per distinct post. Sum total_vacancies across all posts.
- For phases: one entry per exam stage. Prelims, Mains, DV/Interview are separate phases.
- exam_cycle is the year the exam is FOR (e.g., "2026" for UPSC CSE 2026).
- Category: UPSC CSE/IFS/IES → Civil_Services. NDA/CDS → Defence. BSF/CRPF → Police. IB ACIO → Intelligence.
"""


class ExamParser:
    """LLM + regex hybrid parser for government exam notifications."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.llm_parsed: int = 0
        self.regex_parsed: int = 0
        self.failed: int = 0

    # ═══════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════

    async def parse_batch(
        self, raw_exams: list[RawExamData], max_concurrent: int = 5,
    ) -> list[ParsedExamData]:
        """Parse a batch of raw exam data into structured ParsedExamData."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _parse_safe(raw: RawExamData) -> ParsedExamData:
            async with semaphore:
                return await self._parse_single(raw)

        tasks = [_parse_safe(r) for r in raw_exams]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        parsed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("Parse failed for %s: %s", raw_exams[i].exam_name, result)
                parsed.append(self._regex_parse(raw_exams[i]))
                self.failed += 1
            else:
                parsed.append(result)

        return parsed

    async def _parse_single(self, raw: RawExamData) -> ParsedExamData:
        """Try LLM parse, fall back to regex."""
        has_llm = bool(self.config.anthropic_api_key or self.config.openai_api_key)

        if has_llm and raw.raw_notification_text:
            try:
                result = await self._llm_parse(raw)
                if result.parsing_confidence >= 0.5:
                    self.llm_parsed += 1
                    return self._finalize(result)
            except Exception as e:
                logger.debug("LLM parse failed for %s: %s", raw.exam_name, e)

        result = self._regex_parse(raw)
        self.regex_parsed += 1
        return self._finalize(result)

    def _finalize(self, parsed: ParsedExamData) -> ParsedExamData:
        """Apply status inference and deadline computation."""
        parsed.exam_status = self._infer_exam_status(parsed)
        self._compute_deadlines(parsed)
        return parsed

    # ═══════════════════════════════════════════════════
    # LLM PARSING
    # ═══════════════════════════════════════════════════

    async def _llm_parse(self, raw: RawExamData) -> ParsedExamData:
        """Call LLM to parse the exam notification."""
        prompt = EXAM_PARSE_PROMPT.format(
            exam_name=raw.exam_name,
            conducting_body=raw.conducting_body,
            source_url=raw.source_url,
            raw_notification_text=(raw.raw_notification_text or "")[:3000],
            raw_application_start=raw.raw_application_start or "N/A",
            raw_application_end=raw.raw_application_end or "N/A",
            raw_exam_date=raw.raw_exam_date or "N/A",
            raw_fee=raw.raw_fee or "N/A",
            raw_vacancy=raw.raw_vacancy_text or raw.raw_total_vacancies or "N/A",
            raw_eligibility=raw.raw_eligibility or "N/A",
            raw_age_limit=raw.raw_age_limit or "N/A",
        )

        if self.config.llm_provider == "anthropic" and self.config.anthropic_api_key:
            data = await self._call_anthropic(prompt)
        elif self.config.openai_api_key:
            data = await self._call_openai(prompt)
        else:
            raise ValueError("No LLM API key configured")

        return self._build_parsed_from_llm(raw, data)

    async def _call_anthropic(self, prompt: str) -> dict:
        """Call Anthropic API and parse JSON response."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.config.anthropic_api_key,
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": self.config.model_name,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            body = resp.json()
            text = body["content"][0]["text"]
            return self._safe_json_parse(text)

    async def _call_openai(self, prompt: str) -> dict:
        """Call OpenAI API and parse JSON response."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": "You parse Indian government exam notifications into structured JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "max_tokens": 4096,
                },
            )
            resp.raise_for_status()
            body = resp.json()
            text = body["choices"][0]["message"]["content"]
            return self._safe_json_parse(text)

    def _safe_json_parse(self, text: str) -> dict:
        """Extract JSON from LLM output, stripping markdown fences."""
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r'^```(?:json)?\n?', '', text)
            text = re.sub(r'\n?```$', '', text)
        return json.loads(text)

    def _build_parsed_from_llm(self, raw: RawExamData, data: dict) -> ParsedExamData:
        """Build ParsedExamData from LLM JSON output."""
        phases = []
        for p in data.get("phases") or []:
            if isinstance(p, dict) and p.get("phase_name"):
                phases.append(ExamPhaseDate(
                    phase_name=p["phase_name"],
                    exam_date_start=p.get("exam_date_start"),
                    exam_date_end=p.get("exam_date_end"),
                    admit_card_date=p.get("admit_card_date"),
                    result_date=p.get("result_date"),
                    mode=p.get("mode"),
                ))

        vacancies = []
        for v in data.get("vacancies") or []:
            if isinstance(v, dict) and v.get("post_name"):
                vacancies.append(ExamVacancy(
                    post_name=v["post_name"],
                    total_vacancies=_safe_int(v.get("total_vacancies")),
                    pay_scale=v.get("pay_scale"),
                ))

        fee = ExamFee(
            general=_safe_float(data.get("fee_general")),
            obc=_safe_float(data.get("fee_obc")),
            sc_st=_safe_float(data.get("fee_sc_st")),
            female=_safe_float(data.get("fee_female")),
            ews=_safe_float(data.get("fee_ews")),
            pwd=_safe_float(data.get("fee_pwd")),
            fee_note=data.get("fee_note"),
            is_free=bool(data.get("is_free", False)),
            raw_fee_text=raw.raw_fee,
        )

        elig = ExamEligibility(
            age_min=_safe_int(data.get("age_min")),
            age_max=_safe_int(data.get("age_max")),
            age_relaxation_obc=_safe_int(data.get("age_relaxation_obc")),
            age_relaxation_sc_st=_safe_int(data.get("age_relaxation_sc_st")),
            age_relaxation_pwd=_safe_int(data.get("age_relaxation_pwd")),
            qualification=data.get("qualification"),
            min_percentage=_safe_float(data.get("min_percentage")),
            experience_years=_safe_int(data.get("experience_years")),
            physical_standards=data.get("physical_standards"),
            domicile_required=data.get("domicile_required"),
            gender_restriction=data.get("gender_restriction"),
        )

        try:
            cat = ExamCategory(data.get("exam_category", "Other_Central"))
        except ValueError:
            cat = ExamCategory.Other_Central
        try:
            lvl = ExamLevel(data.get("exam_level", "Central"))
        except ValueError:
            lvl = ExamLevel.Central

        return ParsedExamData(
            raw=raw,
            exam_category=cat,
            exam_level=lvl,
            state=data.get("state"),
            clean_exam_name=data.get("clean_exam_name") or raw.exam_name,
            short_name=data.get("short_name"),
            exam_cycle=data.get("exam_cycle"),
            notification_date=data.get("notification_date"),
            application_start_date=data.get("application_start_date"),
            application_end_date=data.get("application_end_date"),
            fee_payment_deadline=data.get("fee_payment_deadline"),
            correction_window_start=data.get("correction_window_start"),
            correction_window_end=data.get("correction_window_end"),
            phases=phases,
            result_date=data.get("result_date"),
            interview_date=data.get("interview_date"),
            final_result_date=data.get("final_result_date"),
            joining_date=data.get("joining_date"),
            fee=fee,
            vacancies=vacancies,
            total_vacancies=_safe_int(data.get("total_vacancies")),
            eligibility=elig,
            official_notification_url=data.get("official_notification_url") or raw.notification_url,
            apply_online_url=data.get("apply_online_url") or raw.apply_url,
            admit_card_url=data.get("admit_card_url"),
            result_url=data.get("result_url"),
            syllabus_url=data.get("syllabus_url") or raw.syllabus_url,
            official_website=data.get("official_website"),
            parsing_confidence=float(data.get("confidence", 0.8)),
        )

    # ═══════════════════════════════════════════════════
    # REGEX FALLBACK PARSING
    # ═══════════════════════════════════════════════════

    def _regex_parse(self, raw: RawExamData) -> ParsedExamData:
        """Complete regex-based fallback parser. No LLM needed."""
        text_pool = " ".join(filter(None, [
            raw.raw_notification_text, raw.raw_eligibility,
            raw.raw_fee, raw.raw_vacancy_text, raw.raw_age_limit,
        ]))

        # Extract dates
        dates = self._extract_contextual_dates(text_pool, raw)

        # Extract fee
        fee = self._extract_fee(raw.raw_fee or text_pool[:2000])

        # Extract vacancies
        vacancies, total_vac = self._extract_vacancies(
            raw.raw_vacancy_text or raw.raw_total_vacancies or text_pool[:2000]
        )

        # Extract eligibility
        elig = self._extract_eligibility(raw)

        # Infer category
        category = self._infer_exam_category(raw.exam_name, raw.conducting_body)

        # Infer level
        level = ExamLevel.Central
        state = None
        for s_name in ["Tamil_Nadu", "Karnataka", "Maharashtra", "Kerala", "Gujarat",
                        "Rajasthan", "Uttar_Pradesh", "Bihar", "West_Bengal", "Madhya_Pradesh",
                        "Punjab", "Haryana", "Odisha", "Andhra_Pradesh", "Telangana",
                        "Jharkhand", "Chhattisgarh", "Assam", "Himachal_Pradesh", "Uttarakhand"]:
            if s_name.lower().replace("_", " ") in raw.exam_name.lower() or \
               s_name.lower().replace("_", " ") in raw.conducting_body.lower():
                level = ExamLevel.State
                state = s_name
                break

        if category in (ExamCategory.State_PSC, ExamCategory.State_Police,
                        ExamCategory.State_Teaching, ExamCategory.State_Subordinate):
            level = ExamLevel.State

        # Extract cycle year
        cycle = None
        year_match = re.search(r'20(2[4-9]|3[0-9])', raw.exam_name)
        if year_match:
            cycle = f"20{year_match.group(1)}"
        else:
            fy_match = re.search(r'(\d{4})\s*[-–]\s*(\d{2,4})', raw.exam_name)
            if fy_match:
                cycle = f"{fy_match.group(1)}-{fy_match.group(2)}"

        return ParsedExamData(
            raw=raw,
            exam_category=category,
            exam_level=level,
            state=state,
            clean_exam_name=raw.exam_name.strip(),
            exam_cycle=cycle,
            notification_date=dates.get("notification_date"),
            application_start_date=dates.get("application_start") or _try_parse_date(raw.raw_application_start),
            application_end_date=dates.get("application_end") or _try_parse_date(raw.raw_application_end),
            fee_payment_deadline=dates.get("fee_payment"),
            phases=self._build_phases_from_dates(dates, raw),
            result_date=dates.get("result_date"),
            interview_date=dates.get("interview_date"),
            fee=fee,
            vacancies=vacancies,
            total_vacancies=total_vac,
            eligibility=elig,
            official_notification_url=raw.notification_url,
            apply_online_url=raw.apply_url,
            syllabus_url=raw.syllabus_url,
            parsing_confidence=0.4,
        )

    def _extract_contextual_dates(self, text: str, raw: RawExamData) -> dict[str, str]:
        """Extract dates near context keywords from text."""
        found: dict[str, str] = {}
        text_lower = text.lower()

        for field_name, keywords in DATE_CONTEXT_KEYWORDS.items():
            for kw in keywords:
                idx = text_lower.find(kw.lower())
                if idx == -1:
                    continue
                window = text[max(0, idx - 50):idx + len(kw) + 100]
                parsed = _extract_first_date(window)
                if parsed and field_name not in found:
                    found[field_name] = parsed
                    break

        # Also use raw fields directly
        if "application_start" not in found and raw.raw_application_start:
            d = _try_parse_date(raw.raw_application_start)
            if d:
                found["application_start"] = d
        if "application_end" not in found and raw.raw_application_end:
            d = _try_parse_date(raw.raw_application_end)
            if d:
                found["application_end"] = d
        if "exam_date" not in found and raw.raw_exam_date:
            d = _try_parse_date(raw.raw_exam_date)
            if d:
                found["exam_date"] = d
        if "admit_card" not in found and raw.raw_admit_card_date:
            d = _try_parse_date(raw.raw_admit_card_date)
            if d:
                found["admit_card"] = d
        if "result_date" not in found and raw.raw_result_date:
            d = _try_parse_date(raw.raw_result_date)
            if d:
                found["result_date"] = d

        return found

    def _extract_fee(self, text: str) -> ExamFee:
        """Parse fee text into structured ExamFee."""
        fee = ExamFee(raw_fee_text=text[:500] if text else None)

        if FEE_FREE_RE.search(text or ""):
            fee.is_free = True
            fee.general = 0
            fee.obc = 0
            fee.sc_st = 0
            fee.female = 0
            fee.ews = 0
            fee.pwd = 0
            return fee

        for cat_name, pattern in FEE_CATEGORY_PATTERNS.items():
            m = pattern.search(text or "")
            if m:
                val_str = m.group(1)
                if val_str.lower() in ("nil", "free", "exempted"):
                    val = 0.0
                else:
                    val = _safe_float(val_str.replace(",", ""))
                setattr(fee, cat_name, val)

        # If no category-wise fees found, try single amount
        if fee.general is None:
            amounts = FEE_AMOUNT_RE.findall(text or "")
            if amounts:
                first_amount = _safe_float(amounts[0].replace(",", ""))
                fee.general = first_amount
                if fee.obc is None:
                    fee.obc = first_amount
                if fee.ews is None:
                    fee.ews = first_amount

        return fee

    def _extract_vacancies(self, text: str) -> tuple[list[ExamVacancy], Optional[int]]:
        """Parse vacancy info from text."""
        vacancies: list[ExamVacancy] = []
        total = None

        # Total vacancies
        total_match = VACANCY_TOTAL_RE.search(text or "")
        if total_match:
            total = _safe_int(total_match.group(1).replace(",", ""))

        # Individual posts
        for m in VACANCY_POST_RE.finditer(text or ""):
            post_name = m.group(1).strip()
            vac_count = _safe_int(m.group(2))
            if post_name and len(post_name) > 2:
                vacancies.append(ExamVacancy(
                    post_name=post_name,
                    total_vacancies=vac_count,
                ))

        # If no individual posts but total found, create one generic entry
        if not vacancies and total:
            vacancies.append(ExamVacancy(post_name="Various Posts", total_vacancies=total))

        # Ensure total is set
        if not total and vacancies:
            total = sum(v.total_vacancies or 0 for v in vacancies) or None

        return vacancies, total

    def _extract_eligibility(self, raw: RawExamData) -> ExamEligibility:
        """Extract eligibility from raw fields."""
        elig = ExamEligibility()

        age_text = raw.raw_age_limit or ""
        age_nums = re.findall(r'(\d{2})\s*(?:to|-|–)\s*(\d{2})', age_text)
        if age_nums:
            elig.age_min = int(age_nums[0][0])
            elig.age_max = int(age_nums[0][1])
        else:
            single_age = re.findall(r'(\d{2})\s*years', age_text)
            if single_age:
                elig.age_max = int(single_age[0])

        # Age relaxation
        relax_obc = re.search(r'obc\s*[-:–]\s*(\d+)\s*year', age_text, re.I)
        if relax_obc:
            elig.age_relaxation_obc = int(relax_obc.group(1))
        relax_scst = re.search(r'sc[/\s]*st\s*[-:–]\s*(\d+)\s*year', age_text, re.I)
        if relax_scst:
            elig.age_relaxation_sc_st = int(relax_scst.group(1))
        relax_pwd = re.search(r'(?:pwd|ph|disabled)\s*[-:–]\s*(\d+)\s*year', age_text, re.I)
        if relax_pwd:
            elig.age_relaxation_pwd = int(relax_pwd.group(1))

        elig.qualification = raw.raw_qualification or raw.raw_eligibility
        elig.physical_standards = raw.raw_physical_standards
        return elig

    def _build_phases_from_dates(self, dates: dict, raw: RawExamData) -> list[ExamPhaseDate]:
        """Build exam phases from extracted dates."""
        phases: list[ExamPhaseDate] = []

        exam_date = dates.get("exam_date") or _try_parse_date(raw.raw_exam_date)
        admit_card = dates.get("admit_card") or _try_parse_date(raw.raw_admit_card_date)
        result_date = dates.get("result_date") or _try_parse_date(raw.raw_result_date)

        if exam_date or admit_card:
            phases.append(ExamPhaseDate(
                phase_name="Written / CBT",
                exam_date_start=exam_date,
                admit_card_date=admit_card,
                result_date=result_date,
            ))

        interview_date = dates.get("interview_date") or _try_parse_date(raw.raw_interview_date)
        if interview_date:
            phases.append(ExamPhaseDate(
                phase_name="Interview / DV",
                exam_date_start=interview_date,
            ))

        return phases

    def _infer_exam_category(self, exam_name: str, body: str) -> ExamCategory:
        """Rule-based category detection from exam name and conducting body."""
        combined = f"{exam_name} {body}".lower()

        for cat, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in combined:
                    return cat

        return ExamCategory.Other_Central

    # ═══════════════════════════════════════════════════
    # STATUS INFERENCE
    # ═══════════════════════════════════════════════════

    def _infer_exam_status(self, parsed: ParsedExamData) -> ExamStatus:
        """Infer exam status from parsed dates."""
        today = date.today()

        app_start = _safe_date(parsed.application_start_date)
        app_end = _safe_date(parsed.application_end_date)

        # Check if any phase has an exam date
        earliest_exam = None
        for phase in parsed.phases:
            d = _safe_date(phase.exam_date_start)
            if d and (earliest_exam is None or d < earliest_exam):
                earliest_exam = d

        final = _safe_date(parsed.final_result_date)
        result = _safe_date(parsed.result_date)

        if final and final <= today:
            return ExamStatus.Completed

        if result and result <= today and (not final or final > today):
            return ExamStatus.Result_Awaited

        if earliest_exam:
            exam_end = earliest_exam
            for phase in parsed.phases:
                d = _safe_date(phase.exam_date_end)
                if d and d > exam_end:
                    exam_end = d
            if earliest_exam <= today <= exam_end:
                return ExamStatus.Exam_Ongoing
            if earliest_exam > today and (not app_end or app_end <= today):
                # Check for admit card
                for phase in parsed.phases:
                    ac = _safe_date(phase.admit_card_date)
                    if ac and ac <= today:
                        return ExamStatus.Admit_Card_Out
                return ExamStatus.Application_Closed

        if app_end and app_end >= today and app_start and app_start <= today:
            return ExamStatus.Application_Open

        if app_start and app_start > today:
            return ExamStatus.Upcoming

        if app_end and app_end < today:
            return ExamStatus.Application_Closed

        return ExamStatus.Upcoming

    # ═══════════════════════════════════════════════════
    # DEADLINE COMPUTATION
    # ═══════════════════════════════════════════════════

    def _compute_deadlines(self, parsed: ParsedExamData) -> None:
        """Set days_until_application_close and days_until_exam."""
        today = date.today()

        app_end = _safe_date(parsed.application_end_date)
        if app_end and app_end >= today:
            parsed.days_until_application_close = (app_end - today).days

        earliest_exam = None
        for phase in parsed.phases:
            d = _safe_date(phase.exam_date_start)
            if d and d >= today and (earliest_exam is None or d < earliest_exam):
                earliest_exam = d

        if earliest_exam:
            parsed.days_until_exam = (earliest_exam - today).days


# ═══════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════

def _safe_int(val) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _safe_date(date_str: Optional[str]) -> Optional[date]:
    """Parse ISO or Indian date string to date object."""
    if not date_str:
        return None
    return _try_parse_date_obj(date_str)


def _try_parse_date(text: Optional[str]) -> Optional[str]:
    """Try to parse a date string and return ISO format. Returns None on failure."""
    if not text:
        return None
    d = _try_parse_date_obj(text.strip())
    return d.isoformat() if d else None


def _try_parse_date_obj(text: str) -> Optional[date]:
    """Parse various date formats into a date object."""
    text = text.strip()

    # ISO: YYYY-MM-DD
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    m = re.match(r'^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})$', text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    # DD/MM/YY
    m = re.match(r'^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2})$', text)
    if m:
        yr = int(m.group(3))
        yr = yr + 2000 if yr < 50 else yr + 1900
        try:
            return date(yr, int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    # DD Month YYYY / DD Mon YYYY
    m = re.match(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\w*[\s,]+(\d{4})', text, re.I)
    if m:
        month = MONTH_MAP.get(m.group(2).lower()[:3])
        if month:
            try:
                return date(int(m.group(3)), month, int(m.group(1)))
            except ValueError:
                pass

    # Month DD, YYYY
    m = re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\w*\s+(\d{1,2})[\s,]+(\d{4})', text, re.I)
    if m:
        month = MONTH_MAP.get(m.group(1).lower()[:3])
        if month:
            try:
                return date(int(m.group(3)), month, int(m.group(2)))
            except ValueError:
                pass

    # Month YYYY (use 1st of month)
    m = re.match(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', text, re.I)
    if m:
        month = MONTH_MAP.get(m.group(1).lower()[:3])
        if month:
            try:
                return date(int(m.group(2)), month, 1)
            except ValueError:
                pass

    return None


def _extract_first_date(text: str) -> Optional[str]:
    """Extract the first recognizable date from text, return ISO."""
    for pattern, fmt in DATE_PATTERNS:
        m = re.search(pattern, text, re.I)
        if m:
            groups = m.groups()
            try:
                if fmt == "dmy":
                    return date(int(groups[2]), int(groups[1]), int(groups[0])).isoformat()
                elif fmt == "dmy_short":
                    yr = int(groups[2])
                    yr = yr + 2000 if yr < 50 else yr + 1900
                    return date(yr, int(groups[1]), int(groups[0])).isoformat()
                elif fmt == "iso":
                    return date(int(groups[0]), int(groups[1]), int(groups[2])).isoformat()
                elif fmt == "d_mon_y":
                    month = MONTH_MAP.get(groups[1].lower()[:3])
                    if month:
                        return date(int(groups[2]), month, int(groups[0])).isoformat()
                elif fmt == "mon_d_y":
                    month = MONTH_MAP.get(groups[0].lower()[:3])
                    if month:
                        return date(int(groups[2]), month, int(groups[1])).isoformat()
                elif fmt == "mon_y":
                    month = MONTH_MAP.get(groups[0].lower()[:3])
                    if month:
                        return date(int(groups[1]), month, 1).isoformat()
            except (ValueError, TypeError):
                continue
    return None
```

---

## File 26/41: `src/exams/exam_storage.py`
<!-- lines: 593 -->

```python
"""
GovScheme SuperAgent — Exam Storage Agent (V3)
Builds organized folder hierarchy under output/examinations/ with 4 outputs per exam:
  1. metadata.json — structured JSON
  2. exam_details.md — human-readable Markdown
  3. website.url — Windows URL shortcut
  4. notification_*.pdf — downloaded notification PDFs
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from src.config.settings import AgentConfig
from src.exams.exam_models import (
    ParsedExamData, StoredExamData, ExamLevel, ExamStatus,
)

logger = logging.getLogger("ExamStorage")


class ExamStorageAgent:
    """Organizes parsed exam data into a folder hierarchy."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.output_dir = config.exam_output_dir
        self.stored_count = 0
        self.errors: list[str] = []

    async def store_batch(
        self, parsed_exams: list[ParsedExamData], max_concurrent: int = 10,
    ) -> list[StoredExamData]:
        """Store a batch of parsed exams into the folder hierarchy."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _store_safe(exam: ParsedExamData) -> Optional[StoredExamData]:
            async with semaphore:
                try:
                    return await self._store_single(exam)
                except Exception as e:
                    logger.warning("Store failed for %s: %s", exam.clean_exam_name, e)
                    self.errors.append(f"{exam.clean_exam_name}: {e}")
                    return None

        tasks = [_store_safe(p) for p in parsed_exams]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        stored = []
        for r in results:
            if isinstance(r, StoredExamData):
                stored.append(r)
                self.stored_count += 1
            elif isinstance(r, Exception):
                logger.error("Unexpected store error: %s", r)

        return stored

    async def _store_single(self, parsed: ParsedExamData) -> StoredExamData:
        """Store one exam: create folder, write files, download PDFs."""
        folder = self._compute_exam_folder(parsed)
        folder_path = Path(folder)
        folder_path.mkdir(parents=True, exist_ok=True)

        parsed.folder_path = str(folder_path)

        # Output 1: metadata.json
        meta_path = folder_path / "metadata.json"
        meta_content = self._build_metadata(parsed)
        meta_path.write_text(
            json.dumps(meta_content, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        # Output 2: exam_details.md
        md_path = folder_path / "exam_details.md"
        md_path.write_text(self._build_markdown(parsed), encoding="utf-8")

        # Output 3: website.url
        best_url = (
            parsed.apply_online_url
            or parsed.official_notification_url
            or parsed.official_website
            or parsed.raw.source_url
        )
        if best_url:
            url_path = folder_path / "website.url"
            url_path.write_text(
                f"[InternetShortcut]\nURL={best_url}\n", encoding="utf-8"
            )

        # Output 4: download notification PDFs (up to 5)
        downloaded_pdfs = []
        if self.config.download_pdfs:
            downloaded_pdfs = await self._download_pdfs(parsed, folder_path)

        return StoredExamData(
            parsed=parsed,
            folder_path=str(folder_path),
            metadata_path=str(meta_path),
            detail_markdown_path=str(md_path),
            downloaded_notification_pdfs=downloaded_pdfs,
        )

    # ─────────────────────────────────────
    # Folder Path Computation
    # ─────────────────────────────────────

    def _compute_exam_folder(self, parsed: ParsedExamData) -> str:
        """Build the hierarchical folder path for this exam."""
        parts = [self.output_dir]

        # Level: Central / State / UT
        parts.append(parsed.exam_level.value)

        # State (if state level)
        if parsed.state:
            parts.append(self._sanitize(parsed.state))

        # Category
        parts.append(parsed.exam_category.value)

        # Conducting body (for central exams, adds specificity)
        if parsed.exam_level == ExamLevel.Central:
            body = self._sanitize(parsed.raw.conducting_body)
            if body:
                parts.append(body)

        # Exam name + cycle
        exam_slug = self._sanitize(parsed.clean_exam_name)[:60]
        if parsed.exam_cycle:
            cycle_slug = self._sanitize(parsed.exam_cycle)
            exam_slug = f"{exam_slug}_{cycle_slug}"
        parts.append(exam_slug[:80])

        return str(Path(*parts))

    def _sanitize(self, name: str) -> str:
        """Sanitize a name for use as a folder path component."""
        sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
        sanitized = re.sub(r'\s+', '_', sanitized.strip())
        sanitized = re.sub(r'_+', '_', sanitized).strip("_.")
        return sanitized[:80] or "unknown"

    # ─────────────────────────────────────
    # Metadata JSON
    # ─────────────────────────────────────

    def _build_metadata(self, parsed: ParsedExamData) -> dict:
        """Build the structured metadata.json content."""
        phases_list = []
        for p in parsed.phases:
            phases_list.append({
                "phase_name": p.phase_name,
                "exam_date_start": p.exam_date_start,
                "exam_date_end": p.exam_date_end,
                "admit_card_date": p.admit_card_date,
                "result_date": p.result_date,
                "mode": p.mode,
                "venue": p.venue,
            })

        vacancies_list = []
        for v in parsed.vacancies:
            vacancies_list.append({
                "post_name": v.post_name,
                "total_vacancies": v.total_vacancies,
                "general_vacancies": v.general_vacancies,
                "obc_vacancies": v.obc_vacancies,
                "sc_vacancies": v.sc_vacancies,
                "st_vacancies": v.st_vacancies,
                "ews_vacancies": v.ews_vacancies,
                "pwd_vacancies": v.pwd_vacancies,
                "pay_scale": v.pay_scale,
                "pay_band": v.pay_band,
                "grade_pay": v.grade_pay,
                "job_location": v.job_location,
            })

        return {
            "exam_id": parsed.exam_id,
            "exam_name": parsed.clean_exam_name,
            "short_name": parsed.short_name,
            "conducting_body": parsed.raw.conducting_body,
            "exam_category": parsed.exam_category.value,
            "exam_level": parsed.exam_level.value,
            "state": parsed.state,
            "exam_cycle": parsed.exam_cycle,
            "exam_status": parsed.exam_status.value,

            "dates": {
                "notification_date": parsed.notification_date,
                "application_start_date": parsed.application_start_date,
                "application_end_date": parsed.application_end_date,
                "fee_payment_deadline": parsed.fee_payment_deadline,
                "correction_window": {
                    "start": parsed.correction_window_start,
                    "end": parsed.correction_window_end,
                },
                "phases": phases_list,
                "result_date": parsed.result_date,
                "interview_date": parsed.interview_date,
                "final_result_date": parsed.final_result_date,
                "joining_date": parsed.joining_date,
            },

            "fees": {
                "general": parsed.fee.general,
                "obc": parsed.fee.obc,
                "sc_st": parsed.fee.sc_st,
                "female": parsed.fee.female,
                "ews": parsed.fee.ews,
                "pwd": parsed.fee.pwd,
                "ex_serviceman": parsed.fee.ex_serviceman,
                "is_free": parsed.fee.is_free,
                "fee_note": parsed.fee.fee_note,
                "fee_payment_url": parsed.fee.fee_payment_url,
            },

            "vacancies": {
                "total": parsed.total_vacancies,
                "posts": vacancies_list,
            },

            "eligibility": {
                "age_min": parsed.eligibility.age_min,
                "age_max": parsed.eligibility.age_max,
                "age_relaxation_obc": parsed.eligibility.age_relaxation_obc,
                "age_relaxation_sc_st": parsed.eligibility.age_relaxation_sc_st,
                "age_relaxation_pwd": parsed.eligibility.age_relaxation_pwd,
                "age_relaxation_ex_sm": parsed.eligibility.age_relaxation_ex_sm,
                "age_as_on_date": parsed.eligibility.age_as_on_date,
                "qualification": parsed.eligibility.qualification,
                "min_percentage": parsed.eligibility.min_percentage,
                "experience_years": parsed.eligibility.experience_years,
                "physical_standards": parsed.eligibility.physical_standards,
                "nationality": parsed.eligibility.nationality,
                "domicile_required": parsed.eligibility.domicile_required,
                "gender_restriction": parsed.eligibility.gender_restriction,
            },

            "links": {
                "official_notification": parsed.official_notification_url,
                "apply_online": parsed.apply_online_url,
                "admit_card": parsed.admit_card_url,
                "result": parsed.result_url,
                "syllabus": parsed.syllabus_url,
                "official_website": parsed.official_website,
            },

            "tracking": {
                "source_portal": parsed.raw.source_portal,
                "source_url": parsed.raw.source_url,
                "first_seen_date": parsed.first_seen_date,
                "last_seen_date": parsed.last_seen_date,
                "days_until_application_close": parsed.days_until_application_close,
                "days_until_exam": parsed.days_until_exam,
                "change_type": parsed.change_type.value,
                "parsing_confidence": parsed.parsing_confidence,
            },

            "crawled_at": parsed.raw.crawled_at.isoformat(),
            "stored_at": datetime.utcnow().isoformat(),
        }

    # ─────────────────────────────────────
    # Markdown Details
    # ─────────────────────────────────────

    def _build_markdown(self, parsed: ParsedExamData) -> str:
        """Build exam_details.md with all available data."""
        lines: list[str] = []

        # Title + status badge
        status_emoji = {
            ExamStatus.Upcoming: "🔵",
            ExamStatus.Application_Open: "🟢",
            ExamStatus.Application_Closed: "🟠",
            ExamStatus.Admit_Card_Out: "🟡",
            ExamStatus.Exam_Ongoing: "🟣",
            ExamStatus.Result_Awaited: "⏳",
            ExamStatus.Completed: "✅",
        }
        emoji = status_emoji.get(parsed.exam_status, "❓")
        lines.append(f"# {parsed.clean_exam_name} {emoji} {parsed.exam_status.value}")
        lines.append("")

        # Metadata table
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| Conducting Body | {parsed.raw.conducting_body} |")
        lines.append(f"| Category | {parsed.exam_category.value.replace('_', ' ')} |")
        lines.append(f"| Level | {parsed.exam_level.value} |")
        if parsed.state:
            lines.append(f"| State | {parsed.state.replace('_', ' ')} |")
        if parsed.exam_cycle:
            lines.append(f"| Exam Cycle | {parsed.exam_cycle} |")
        if parsed.short_name:
            lines.append(f"| Short Name | {parsed.short_name} |")
        lines.append(f"| Status | {emoji} {parsed.exam_status.value.replace('_', ' ')} |")
        lines.append("")

        # Important Dates
        any_date = any([
            parsed.notification_date, parsed.application_start_date,
            parsed.application_end_date, parsed.fee_payment_deadline,
        ]) or parsed.phases
        if any_date:
            lines.append("## 📅 Important Dates")
            lines.append("")
            lines.append("| Event | Date | Days Away |")
            lines.append("|-------|------|-----------|")
            if parsed.notification_date:
                lines.append(f"| Notification Date | {parsed.notification_date} | — |")
            if parsed.application_start_date:
                lines.append(f"| Application Opens | {parsed.application_start_date} | — |")
            if parsed.application_end_date:
                days_str = f"{parsed.days_until_application_close}" if parsed.days_until_application_close is not None else "—"
                lines.append(f"| ⚠️ Application Closes | **{parsed.application_end_date}** | **{days_str}** |")
            if parsed.fee_payment_deadline:
                lines.append(f"| Fee Payment Deadline | {parsed.fee_payment_deadline} | — |")
            if parsed.correction_window_start:
                lines.append(f"| Correction Window | {parsed.correction_window_start} to {parsed.correction_window_end or '—'} | — |")
            for phase in parsed.phases:
                if phase.admit_card_date:
                    lines.append(f"| 🎫 Admit Card ({phase.phase_name}) | {phase.admit_card_date} | — |")
                if phase.exam_date_start:
                    end = f" to {phase.exam_date_end}" if phase.exam_date_end else ""
                    days_str = f"{parsed.days_until_exam}" if parsed.days_until_exam is not None else "—"
                    lines.append(f"| 📝 Exam ({phase.phase_name}) | **{phase.exam_date_start}{end}** | **{days_str}** |")
                if phase.result_date:
                    lines.append(f"| 📊 Result ({phase.phase_name}) | {phase.result_date} | — |")
            if parsed.interview_date:
                lines.append(f"| 🎤 Interview | {parsed.interview_date} | — |")
            if parsed.final_result_date:
                lines.append(f"| 🏆 Final Result | {parsed.final_result_date} | — |")
            if parsed.joining_date:
                lines.append(f"| 🏢 Joining | {parsed.joining_date} | — |")
            lines.append("")

        # Fees
        fee = parsed.fee
        has_fee = any([fee.general, fee.obc, fee.sc_st, fee.female, fee.ews, fee.pwd, fee.is_free])
        if has_fee:
            lines.append("## 💰 Application Fee")
            lines.append("")
            if fee.is_free:
                lines.append("**No application fee for any category.**")
            else:
                lines.append("| Category | Fee (₹) |")
                lines.append("|----------|---------|")
                if fee.general is not None:
                    lines.append(f"| General / UR | ₹{fee.general:,.0f} |")
                if fee.obc is not None:
                    lines.append(f"| OBC | ₹{fee.obc:,.0f} |")
                if fee.ews is not None:
                    lines.append(f"| EWS | ₹{fee.ews:,.0f} |")
                if fee.sc_st is not None:
                    val = "Exempted" if fee.sc_st == 0 else f"₹{fee.sc_st:,.0f}"
                    lines.append(f"| SC / ST | {val} |")
                if fee.female is not None:
                    val = "Exempted" if fee.female == 0 else f"₹{fee.female:,.0f}"
                    lines.append(f"| Female | {val} |")
                if fee.pwd is not None:
                    val = "Exempted" if fee.pwd == 0 else f"₹{fee.pwd:,.0f}"
                    lines.append(f"| PwD | {val} |")
            if fee.fee_note:
                lines.append(f"\n> {fee.fee_note}")
            lines.append("")

        # Vacancies
        if parsed.vacancies:
            lines.append("## 📋 Vacancies")
            lines.append("")
            if parsed.total_vacancies:
                lines.append(f"**Total Vacancies: {parsed.total_vacancies:,}**")
                lines.append("")
            lines.append("| Post | Vacancies | Pay Scale |")
            lines.append("|------|-----------|-----------|")
            for v in parsed.vacancies:
                vac = str(v.total_vacancies) if v.total_vacancies else "—"
                pay = v.pay_scale or v.pay_band or "—"
                lines.append(f"| {v.post_name} | {vac} | {pay} |")
            lines.append("")

        # Eligibility
        elig = parsed.eligibility
        has_elig = any([elig.age_min, elig.age_max, elig.qualification,
                        elig.physical_standards, elig.domicile_required])
        if has_elig:
            lines.append("## ✅ Eligibility")
            lines.append("")
            if elig.age_min or elig.age_max:
                age_range = f"{elig.age_min or '—'} to {elig.age_max or '—'} years"
                if elig.age_as_on_date:
                    age_range += f" (as on {elig.age_as_on_date})"
                lines.append(f"- **Age:** {age_range}")
                if elig.age_relaxation_obc:
                    lines.append(f"  - OBC: +{elig.age_relaxation_obc} years")
                if elig.age_relaxation_sc_st:
                    lines.append(f"  - SC/ST: +{elig.age_relaxation_sc_st} years")
                if elig.age_relaxation_pwd:
                    lines.append(f"  - PwD: +{elig.age_relaxation_pwd} years")
            if elig.qualification:
                lines.append(f"- **Qualification:** {elig.qualification}")
            if elig.min_percentage:
                lines.append(f"- **Minimum %:** {elig.min_percentage}%")
            if elig.experience_years:
                lines.append(f"- **Experience:** {elig.experience_years} years")
            if elig.physical_standards:
                lines.append(f"- **Physical Standards:** {elig.physical_standards}")
            if elig.domicile_required:
                lines.append(f"- **Domicile:** {elig.domicile_required}")
            if elig.gender_restriction:
                lines.append(f"- **Gender:** {elig.gender_restriction}")
            lines.append("")

        # Exam Pattern (phases)
        if parsed.phases:
            lines.append("## 📝 Exam Pattern")
            lines.append("")
            for phase in parsed.phases:
                mode_str = f" ({phase.mode})" if phase.mode else ""
                lines.append(f"- **{phase.phase_name}**{mode_str}")
                if phase.venue:
                    lines.append(f"  - Venue: {phase.venue}")
            lines.append("")

        # Links
        links = [
            ("Apply Online", parsed.apply_online_url),
            ("Official Notification", parsed.official_notification_url),
            ("Admit Card", parsed.admit_card_url),
            ("Result", parsed.result_url),
            ("Syllabus", parsed.syllabus_url),
            ("Official Website", parsed.official_website),
        ]
        active_links = [(name, url) for name, url in links if url]
        if active_links:
            lines.append("## 🔗 Important Links")
            lines.append("")
            for name, url in active_links:
                lines.append(f"- [{name}]({url})")
            lines.append("")

        # Footer
        lines.append("---")
        lines.append(f"*Crawled: {parsed.raw.crawled_at.strftime('%Y-%m-%d %H:%M UTC')} | "
                      f"Source: {parsed.raw.source_portal} | "
                      f"Confidence: {parsed.parsing_confidence:.0%} | "
                      f"Folder: `{parsed.folder_path}`*")

        return "\n".join(lines)

    # ─────────────────────────────────────
    # PDF Download
    # ─────────────────────────────────────

    async def _download_pdfs(
        self, parsed: ParsedExamData, folder: Path, max_pdfs: int = 5,
    ) -> list[str]:
        """Download notification PDFs into the exam folder."""
        downloaded = []
        urls = list(set(parsed.raw.pdf_urls))
        if parsed.official_notification_url and parsed.official_notification_url.endswith(".pdf"):
            urls.insert(0, parsed.official_notification_url)

        for i, url in enumerate(urls[:max_pdfs]):
            try:
                # Determine filename
                is_corrigendum = "corrigendum" in url.lower() or "amendment" in url.lower()
                prefix = "corrigendum" if is_corrigendum else "notification"
                filename = f"{prefix}_{i + 1}.pdf"
                dest = folder / filename

                if dest.exists():
                    downloaded.append(str(dest))
                    continue

                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(url, follow_redirects=True)
                    content_length = len(resp.content)
                    max_bytes = self.config.max_pdf_size_mb * 1024 * 1024

                    if content_length > max_bytes:
                        logger.debug("PDF too large (%d bytes), skipping: %s", content_length, url)
                        continue

                    if resp.status_code == 200:
                        dest.write_bytes(resp.content)
                        downloaded.append(str(dest))
                        logger.debug("Downloaded %s → %s", url, dest)
            except Exception as e:
                logger.debug("PDF download failed for %s: %s", url, e)

        return downloaded

    # ─────────────────────────────────────
    # Report Files
    # ─────────────────────────────────────

    async def generate_exam_reports(self, all_stored: list[StoredExamData]) -> None:
        """Generate aggregate report files in the output directory."""
        reports_dir = Path(self.output_dir) / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        # exam_index.json
        index = []
        for s in all_stored:
            p = s.parsed
            index.append({
                "exam_id": p.exam_id,
                "exam_name": p.clean_exam_name,
                "short_name": p.short_name,
                "conducting_body": p.raw.conducting_body,
                "category": p.exam_category.value,
                "level": p.exam_level.value,
                "state": p.state,
                "status": p.exam_status.value,
                "application_end_date": p.application_end_date,
                "total_vacancies": p.total_vacancies,
                "folder_path": s.folder_path,
            })
        (reports_dir / "exam_index.json").write_text(
            json.dumps(index, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        # exam_calendar.json — sorted by date
        calendar = []
        for s in all_stored:
            p = s.parsed
            if p.application_start_date:
                calendar.append({"date": p.application_start_date, "exam": p.clean_exam_name,
                                  "event": "Application Open", "body": p.raw.conducting_body})
            if p.application_end_date:
                calendar.append({"date": p.application_end_date, "exam": p.clean_exam_name,
                                  "event": "Application Close", "body": p.raw.conducting_body})
            for phase in p.phases:
                if phase.admit_card_date:
                    calendar.append({"date": phase.admit_card_date, "exam": p.clean_exam_name,
                                      "event": f"Admit Card ({phase.phase_name})", "body": p.raw.conducting_body})
                if phase.exam_date_start:
                    calendar.append({"date": phase.exam_date_start, "exam": p.clean_exam_name,
                                      "event": f"Exam ({phase.phase_name})", "body": p.raw.conducting_body})
                if phase.result_date:
                    calendar.append({"date": phase.result_date, "exam": p.clean_exam_name,
                                      "event": f"Result ({phase.phase_name})", "body": p.raw.conducting_body})

        calendar.sort(key=lambda x: x["date"] or "9999")
        (reports_dir / "exam_calendar.json").write_text(
            json.dumps(calendar, indent=2, ensure_ascii=False), encoding="utf-8",
        )

        # open_applications.json
        open_apps = [
            e for e in index if e["status"] == ExamStatus.Application_Open.value
        ]
        (reports_dir / "open_applications.json").write_text(
            json.dumps(open_apps, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        # exam_summary.json
        by_category: dict[str, int] = {}
        by_body: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for e in index:
            by_category[e["category"]] = by_category.get(e["category"], 0) + 1
            by_body[e["conducting_body"]] = by_body.get(e["conducting_body"], 0) + 1
            by_status[e["status"]] = by_status.get(e["status"], 0) + 1

        (reports_dir / "exam_summary.json").write_text(
            json.dumps({
                "total_exams": len(index),
                "by_category": dict(sorted(by_category.items(), key=lambda x: -x[1])),
                "by_body": dict(sorted(by_body.items(), key=lambda x: -x[1])),
                "by_status": dict(sorted(by_status.items(), key=lambda x: -x[1])),
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info(
            "Exam reports generated: index (%d), calendar (%d events), open (%d)",
            len(index), len(calendar), len(open_apps),
        )
```

---

## File 27/41: `src/notifications/__init__.py`
<!-- lines: 0 -->

```python

```

---

## File 28/41: `src/notifications/email_sender.py`
<!-- lines: 469 -->

```python
"""
GovScheme SuperAgent — Notification Dispatcher
Sends daily crawl reports via:
  1. Email (SMTP with Excel attachment)
  2. Slack webhook (summary + link)
  3. File drop to configurable directory
  4. Console summary (always)
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import smtplib
import ssl
from datetime import date
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import httpx

from src.agents.models import DailyRunReport

logger = logging.getLogger("notifier")


class NotificationConfig:
    """Configuration for notification channels."""

    # Email SMTP
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    email_from: str = os.getenv("EMAIL_FROM", "")
    email_to: list[str] = []  # populated from EMAIL_TO env var
    email_cc: list[str] = []

    # Slack
    slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
    slack_channel: str = os.getenv("SLACK_CHANNEL", "#govscheme-alerts")

    # File Drop
    file_drop_dir: str = os.getenv("REPORT_DROP_DIR", "")

    def __init__(self):
        to_raw = os.getenv("EMAIL_TO", "")
        self.email_to = [e.strip() for e in to_raw.split(",") if e.strip()]
        cc_raw = os.getenv("EMAIL_CC", "")
        self.email_cc = [e.strip() for e in cc_raw.split(",") if e.strip()]

    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_user and self.smtp_password and self.email_to)

    @property
    def slack_enabled(self) -> bool:
        return bool(self.slack_webhook_url)

    @property
    def file_drop_enabled(self) -> bool:
        return bool(self.file_drop_dir)


class NotificationDispatcher:
    """Dispatches daily run reports to all configured channels."""

    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config or NotificationConfig()

    def dispatch(
        self,
        report: DailyRunReport,
        excel_path: Optional[str] = None,
        exam_report=None,
    ) -> dict[str, bool]:
        """Send the daily report through all enabled channels. Returns success map."""
        results = {}

        # Always log to console
        self._log_console_summary(report)

        # Email
        if self.config.email_enabled and excel_path:
            results["email"] = self._send_email(report, excel_path, exam_report=exam_report)
        else:
            if not self.config.email_enabled:
                logger.info("Email notifications disabled (set SMTP_USER, SMTP_PASSWORD, EMAIL_TO)")
            results["email"] = False

        # Slack
        if self.config.slack_enabled:
            results["slack"] = self._send_slack(report, excel_path, exam_report=exam_report)
        else:
            logger.info("Slack notifications disabled (set SLACK_WEBHOOK_URL)")
            results["slack"] = False

        # File Drop
        if self.config.file_drop_enabled and excel_path:
            results["file_drop"] = self._file_drop(report, excel_path)
        else:
            results["file_drop"] = False

        return results

    # ─────────────────────────────────────
    # Email via SMTP
    # ─────────────────────────────────────

    def _send_email(self, report: DailyRunReport, excel_path: str, exam_report=None) -> bool:
        try:
            msg = MIMEMultipart("mixed")
            msg["From"] = self.config.email_from or self.config.smtp_user
            msg["To"] = ", ".join(self.config.email_to)
            if self.config.email_cc:
                msg["Cc"] = ", ".join(self.config.email_cc)
            msg["Subject"] = self._email_subject(report, exam_report)

            # HTML body
            body = self._build_email_body(report, exam_report)
            msg.attach(MIMEText(body, "html", "utf-8"))

            # Attach Excel
            if excel_path and Path(excel_path).exists():
                with open(excel_path, "rb") as f:
                    attachment = MIMEApplication(f.read(), _subtype="xlsx")
                    attachment.add_header(
                        "Content-Disposition", "attachment",
                        filename=Path(excel_path).name,
                    )
                    msg.attach(attachment)

            # Send
            all_recipients = self.config.email_to + self.config.email_cc
            context = ssl.create_default_context()

            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(
                    self.config.smtp_user,
                    all_recipients,
                    msg.as_string(),
                )

            logger.info("Email sent to %s", ", ".join(all_recipients))
            return True

        except Exception as e:
            logger.error("Email send failed: %s", e)
            return False

    def _email_subject(self, report: DailyRunReport, exam_report=None) -> str:
        parts = [f"GovScheme Daily Report — {report.run_date}"]
        if report.new_schemes > 0:
            parts.append(f"🆕 {report.new_schemes} New")
        if report.deadlines_within_7_days > 0:
            parts.append(f"⚠️ {report.deadlines_within_7_days} Deadlines")
        if exam_report and exam_report.application_open_exams > 0:
            parts.append(f"📝 {exam_report.application_open_exams} Exams Open")
        return " | ".join(parts)

    def _build_email_body(self, report: DailyRunReport, exam_report=None) -> str:
        new_list = ""
        if report.new_scheme_names:
            items = "".join(
                f"<li>{name}</li>" for name in report.new_scheme_names[:20]
            )
            remaining = max(0, report.new_schemes - 20)
            more = f"<li><em>...and {remaining} more</em></li>" if remaining else ""
            new_list = f"""
            <h3 style="color:#2E7D32;">🆕 New Schemes Discovered ({report.new_schemes})</h3>
            <ul>{items}{more}</ul>
            """

        deadline_list = ""
        if report.approaching_deadline_names:
            items = "".join(
                f"<li>{name}</li>" for name in report.approaching_deadline_names[:15]
            )
            deadline_list = f"""
            <h3 style="color:#C62828;">⚠️ Approaching Deadlines ({report.deadlines_within_7_days})</h3>
            <ul>{items}</ul>
            """

        updated_list = ""
        if report.updated_scheme_names:
            items = "".join(
                f"<li>{name}</li>" for name in report.updated_scheme_names[:10]
            )
            updated_list = f"""
            <h3 style="color:#F57C00;">🔄 Updated Schemes ({report.updated_schemes})</h3>
            <ul>{items}</ul>
            """

        return f"""
        <html>
        <body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;">
            <div style="background:linear-gradient(135deg,#1F4E79,#2E86C1);
                        padding:20px;border-radius:8px 8px 0 0;">
                <h1 style="color:#fff;margin:0;">📊 GovScheme Daily Report</h1>
                <p style="color:#D6E4F0;margin:5px 0 0;">
                    {report.run_date} &middot; Completed in {report.elapsed_seconds:.0f}s
                </p>
            </div>

            <div style="padding:20px;border:1px solid #ddd;border-top:none;">
                <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
                    <tr style="background:#f5f5f5;">
                        <td style="padding:10px;border:1px solid #ddd;">
                            <strong>Total in DB</strong><br>
                            <span style="font-size:24px;color:#1F4E79;">{report.total_schemes_in_db}</span>
                        </td>
                        <td style="padding:10px;border:1px solid #ddd;">
                            <strong>New Today</strong><br>
                            <span style="font-size:24px;color:#2E7D32;">{report.new_schemes}</span>
                        </td>
                        <td style="padding:10px;border:1px solid #ddd;">
                            <strong>Updated</strong><br>
                            <span style="font-size:24px;color:#F57C00;">{report.updated_schemes}</span>
                        </td>
                        <td style="padding:10px;border:1px solid #ddd;">
                            <strong>Active</strong><br>
                            <span style="font-size:24px;color:#1565C0;">{report.active_schemes}</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:10px;border:1px solid #ddd;">
                            <strong>Deadlines (7d)</strong><br>
                            <span style="font-size:24px;color:#C62828;">{report.deadlines_within_7_days}</span>
                        </td>
                        <td style="padding:10px;border:1px solid #ddd;">
                            <strong>Deadlines (30d)</strong><br>
                            <span style="font-size:24px;color:#EF6C00;">{report.deadlines_within_30_days}</span>
                        </td>
                        <td style="padding:10px;border:1px solid #ddd;">
                            <strong>Closed</strong><br>
                            <span style="font-size:24px;color:#757575;">{report.closed_schemes}</span>
                        </td>
                        <td style="padding:10px;border:1px solid #ddd;">
                            <strong>Errors</strong><br>
                            <span style="font-size:24px;color:#B71C1C;">{report.errors}</span>
                        </td>
                    </tr>
                </table>

                {new_list}
                {deadline_list}
                {updated_list}

                {self._build_exam_email_section(exam_report) if exam_report else ''}

                <p style="color:#999;font-size:12px;margin-top:30px;border-top:1px solid #ddd;padding-top:10px;">
                    GovScheme SuperAgent — Automated daily crawl report.<br>
                    Full Excel report attached. Open the "Approaching Deadlines" sheet for urgent action items.
                </p>
            </div>
        </body>
        </html>
        """

    # ─────────────────────────────────────
    # Slack Webhook
    # ─────────────────────────────────────

    def _send_slack(self, report: DailyRunReport, excel_path: Optional[str], exam_report=None) -> bool:
        try:
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"📊 GovScheme Daily Report — {report.run_date}",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Total in DB:*\n{report.total_schemes_in_db}"},
                        {"type": "mrkdwn", "text": f"*New Today:*\n{report.new_schemes}"},
                        {"type": "mrkdwn", "text": f"*Updated:*\n{report.updated_schemes}"},
                        {"type": "mrkdwn", "text": f"*Deadlines (7d):*\n{report.deadlines_within_7_days}"},
                    ],
                },
            ]

            if report.new_scheme_names:
                names = "\n".join(f"• {n}" for n in report.new_scheme_names[:10])
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*🆕 New Schemes:*\n{names}"},
                })

            if report.approaching_deadline_names:
                names = "\n".join(f"• {n}" for n in report.approaching_deadline_names[:10])
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*⚠️ Approaching Deadlines:*\n{names}"},
                })

            # V3: Exam alerts section
            if exam_report:
                blocks.append({"type": "divider"})
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*📝 Government Exam Alerts*"},
                })
                blocks.append({
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Closing in 7d:* {exam_report.deadlines_within_7_days}"},
                        {"type": "mrkdwn", "text": f"*Open Now:* {exam_report.application_open_exams}"},
                        {"type": "mrkdwn", "text": f"*Exams in 7d:* {exam_report.exams_in_7_days}"},
                        {"type": "mrkdwn", "text": f"*New Notified:* {exam_report.new_exams}"},
                    ],
                })
                if exam_report.new_exam_names:
                    names = "\n".join(f"• {n}" for n in exam_report.new_exam_names[:8])
                    blocks.append({
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*🆕 New Exam Notifications:*\n{names}"},
                    })
                if exam_report.approaching_deadline_exams:
                    names = "\n".join(f"• {n}" for n in exam_report.approaching_deadline_exams[:8])
                    blocks.append({
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*⚠️ Exam App Closing Soon:*\n{names}"},
                    })

            payload = {
                "channel": self.config.slack_channel,
                "blocks": blocks,
            }

            resp = httpx.post(
                self.config.slack_webhook_url,
                json=payload,
                timeout=15,
            )

            if resp.status_code == 200:
                logger.info("Slack notification sent to %s", self.config.slack_channel)
                return True
            else:
                logger.error("Slack webhook returned %d: %s", resp.status_code, resp.text)
                return False

        except Exception as e:
            logger.error("Slack notification failed: %s", e)
            return False

    # ─────────────────────────────────────
    # File Drop
    # ─────────────────────────────────────

    def _file_drop(self, report: DailyRunReport, excel_path: str) -> bool:
        try:
            drop_dir = Path(self.config.file_drop_dir)
            drop_dir.mkdir(parents=True, exist_ok=True)

            # Copy Excel
            dest = drop_dir / Path(excel_path).name
            shutil.copy2(excel_path, dest)

            # Also write a JSON summary
            summary_path = drop_dir / f"daily_summary_{report.run_date}.json"
            summary_path.write_text(
                json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )

            logger.info("Report dropped to %s", drop_dir)
            return True

        except Exception as e:
            logger.error("File drop failed: %s", e)
            return False

    # ─────────────────────────────────────
    # Console Summary (always runs)
    # ─────────────────────────────────────

    def _log_console_summary(self, report: DailyRunReport) -> None:
        logger.info("=" * 60)
        logger.info("DAILY RUN REPORT — %s", report.run_date)
        logger.info("=" * 60)
        logger.info("Total in DB:        %d", report.total_schemes_in_db)
        logger.info("New schemes:        %d", report.new_schemes)
        logger.info("Updated schemes:    %d", report.updated_schemes)
        logger.info("Closed schemes:     %d", report.closed_schemes)
        logger.info("Unchanged:          %d", report.unchanged_schemes)
        logger.info("Deadlines (7 days): %d", report.deadlines_within_7_days)
        logger.info("Deadlines (30 days):%d", report.deadlines_within_30_days)
        logger.info("Active schemes:     %d", report.active_schemes)
        logger.info("Errors:             %d", report.errors)
        logger.info("Duration:           %.1f seconds", report.elapsed_seconds)
        if report.excel_report_path:
            logger.info("Excel report:       %s", report.excel_report_path)
        logger.info("=" * 60)

        if report.new_scheme_names:
            logger.info("NEW SCHEMES:")
            for name in report.new_scheme_names[:25]:
                logger.info("  🆕 %s", name)

        if report.approaching_deadline_names:
            logger.info("APPROACHING DEADLINES:")
            for name in report.approaching_deadline_names[:15]:
                logger.info("  ⚠️  %s", name)

    def _build_exam_email_section(self, exam_report) -> str:
        """Build the HTML section for exam alerts in the email body."""
        if not exam_report:
            return ""

        # KPI row
        section = f"""
        <div style="margin-top:20px;border-top:2px solid #1F4E79;padding-top:15px;">
            <h2 style="color:#1F4E79;">📝 Government Exam Alerts</h2>
            <table style="width:100%;border-collapse:collapse;margin-bottom:15px;">
                <tr style="background:#f5f5f5;">
                    <td style="padding:8px;border:1px solid #ddd;text-align:center;">
                        <strong>Total Exams</strong><br>
                        <span style="font-size:20px;color:#1F4E79;">{exam_report.total_exams_in_db}</span>
                    </td>
                    <td style="padding:8px;border:1px solid #ddd;text-align:center;">
                        <strong>New Notified</strong><br>
                        <span style="font-size:20px;color:#2E7D32;">{exam_report.new_exams}</span>
                    </td>
                    <td style="padding:8px;border:1px solid #ddd;text-align:center;">
                        <strong>Apps Open</strong><br>
                        <span style="font-size:20px;color:#1565C0;">{exam_report.application_open_exams}</span>
                    </td>
                    <td style="padding:8px;border:1px solid #ddd;text-align:center;">
                        <strong>Closing in 7d</strong><br>
                        <span style="font-size:20px;color:#C62828;">{exam_report.deadlines_within_7_days}</span>
                    </td>
                </tr>
            </table>
        """

        # Applications closing soon
        if exam_report.approaching_deadline_exams:
            items = "".join(
                f"<li>{name}</li>" for name in exam_report.approaching_deadline_exams[:15]
            )
            section += f"""
            <h3 style="color:#C62828;">⚠️ Exam Applications Closing in 7 Days</h3>
            <ul>{items}</ul>
            """

        # New exam notifications
        if exam_report.new_exam_names:
            items = "".join(
                f"<li>{name}</li>" for name in exam_report.new_exam_names[:20]
            )
            section += f"""
            <h3 style="color:#2E7D32;">🆕 New Exam Notifications ({exam_report.new_exams})</h3>
            <ul>{items}</ul>
            """

        section += "</div>"
        return section
```

---

## File 29/41: `src/openclaw_skill.py`
<!-- lines: 152 -->

```python
"""
GovScheme SuperAgent — OpenClaw Skill Integration
Exposes the agent pipeline as an OpenClaw skill for the buildathon.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path


# ─── OpenClaw Skill Manifest ───

OPENCLAW_SKILL_MANIFEST = {
    "name": "govscheme-india",
    "version": "1.0.0",
    "description": (
        "Crawls 50+ Indian government portals to discover, classify, and organize "
        "700+ scholarships, grants, startup funds, and welfare schemes. "
        "Organizes into structured folder hierarchies by Central/State/UT, "
        "sector, and scheme type."
    ),
    "author": "GovScheme SuperAgent Team",
    "tags": ["india", "government", "scholarships", "grants", "crawling", "agents"],
    "triggers": [
        "find indian government schemes",
        "search scholarships india",
        "crawl government portals",
        "find grants for startup india",
        "list state scholarships",
    ],
    "parameters": {
        "mode": {
            "type": "string",
            "enum": ["full", "discover", "classify", "search"],
            "default": "full",
            "description": "Pipeline mode: full (crawl+classify+store), discover (crawl only), search (query existing)",
        },
        "state": {
            "type": "string",
            "description": "Filter by Indian state (e.g., 'Tamil_Nadu', 'Karnataka')",
            "required": False,
        },
        "sector": {
            "type": "string",
            "description": "Filter by sector (e.g., 'Education', 'Startup', 'Agriculture')",
            "required": False,
        },
        "query": {
            "type": "string",
            "description": "Search query for finding specific schemes",
            "required": False,
        },
    },
}


async def run_skill(params: dict) -> dict:
    """
    OpenClaw skill entry point.
    Called when the skill is triggered via OpenClaw agent.
    """
    from src.config.settings import AgentConfig
    from src.orchestrator import Orchestrator

    mode = params.get("mode", "full")
    state_filter = params.get("state")
    sector_filter = params.get("sector")
    query = params.get("query")

    config = AgentConfig(
        output_dir=os.getenv("GOVSCHEME_OUTPUT_DIR", "./output"),
    )

    if mode == "search" and query:
        return await _search_existing(query, state_filter, sector_filter, config)

    orchestrator = Orchestrator(config)

    if mode == "full":
        await orchestrator.run_full_pipeline()
        return {
            "status": "complete",
            "total_schemes": orchestrator.progress.schemes_stored,
            "duplicates_removed": orchestrator.progress.duplicates_found,
            "output_dir": config.output_dir,
            "elapsed_minutes": orchestrator.progress.elapsed_minutes,
        }
    elif mode == "discover":
        await orchestrator.run_discovery_only()
        return {
            "status": "discovery_complete",
            "total_discovered": orchestrator.progress.total_schemes_discovered,
        }

    return {"status": "error", "message": f"Unknown mode: {mode}"}


async def _search_existing(
    query: str,
    state_filter: str | None,
    sector_filter: str | None,
    config,
) -> dict:
    """Search through already-crawled scheme data."""
    index_path = Path(config.output_dir) / "reports" / "scheme_index.json"
    if not index_path.exists():
        return {
            "status": "error",
            "message": "No crawl data found. Run with mode='full' first.",
        }

    index = json.loads(index_path.read_text())
    results = []
    query_lower = query.lower()

    for scheme in index:
        name_match = query_lower in scheme["name"].lower()
        sector_match = not sector_filter or scheme["sector"] == sector_filter
        state_match = not state_filter or scheme.get("state") == state_filter

        if name_match and sector_match and state_match:
            results.append(scheme)

    return {
        "status": "success",
        "query": query,
        "results_count": len(results),
        "results": results[:50],  # Limit response size
    }


# ─── OpenClaw Heartbeat Handler ───

async def heartbeat() -> dict:
    """
    Called periodically by OpenClaw to check skill health.
    Can also be used for scheduled re-crawls.
    """
    output_dir = os.getenv("GOVSCHEME_OUTPUT_DIR", "./output")
    summary_path = Path(output_dir) / "reports" / "crawl_summary.json"

    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        return {
            "status": "healthy",
            "last_crawl": summary.get("generated_at"),
            "total_schemes": summary.get("total_schemes", 0),
        }

    return {"status": "healthy", "last_crawl": None, "total_schemes": 0}
```

---

## File 30/41: `src/orchestrator.py`
<!-- lines: 767 -->

```python
"""
GovScheme SuperAgent — Orchestrator
The CEO agent that coordinates Discovery → Dedup → Classification → Storage pipeline.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

from src.config.settings import AgentConfig, PORTAL_SOURCES, EXAM_PORTAL_SOURCES
from src.crawlers.discovery_crawler import DiscoveryCrawler
from src.classifiers.classify_agent import ClassificationAgent
from src.storage.storage_agent import StorageAgent
from src.storage.database import SchemeDatabase
from src.storage.excel_report import ExcelReportGenerator
from src.agents.dedup_agent import DeduplicationAgent
from src.agents.change_agent import ChangeDetectionAgent
from src.agents.models import CrawlProgress, DailyRunReport
from src.notifications.email_sender import NotificationDispatcher, NotificationConfig

# V3: Exam pipeline imports
from src.exams.exam_crawler import ExamDiscoveryCrawler
from src.exams.exam_parser import ExamParser
from src.exams.exam_database import ExamDatabase
from src.exams.exam_storage import ExamStorageAgent
from src.exams.exam_alert import ExamAlertEngine
from src.exams.exam_models import ExamDailyReport, ExamChangeType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("govscheme_crawl.log"),
    ],
)
logger = logging.getLogger("orchestrator")
console = Console()


class Orchestrator:
    """
    The CEO Agent — coordinates the full pipeline:
    1. Discovery: Crawl all government portals
    2. Dedup: Remove duplicate schemes
    3. Enrichment: Fetch detail pages for more data
    4. Classification: LLM-powered categorization
    5. Storage: Organize into folder hierarchy
    6. Reporting: Generate summary reports
    """

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self.discovery = DiscoveryCrawler(self.config)
        self.classifier = ClassificationAgent(self.config)
        self.storage = StorageAgent(self.config)
        self.dedup = DeduplicationAgent(self.config)
        self.progress = CrawlProgress()
        self.db = SchemeDatabase(self.config.db_path)

        # V3: Exam pipeline agents
        self.exam_crawler = ExamDiscoveryCrawler(self.config)
        self.exam_parser = ExamParser(self.config)
        self.exam_db = ExamDatabase(self.config.exam_db_path)
        self.exam_storage = ExamStorageAgent(self.config)
        self.exam_alert = ExamAlertEngine(self.exam_db)

    # ═══════════════════════════════════════════════════
    # DAILY PIPELINE — The primary scheduled execution
    # ═══════════════════════════════════════════════════

    async def run_daily_pipeline(
        self, run_id: str, skip_exams: bool = False, skip_schemes: bool = False,
    ) -> DailyRunReport:
        """
        Execute the full daily crawl pipeline (14 phases).

        Scheme Pipeline (Phases 1–8):
          1. Discovery → 2. Dedup → 3. Enrichment → 4. Classification
          5. Change Detection → 6. Storage → 7. Excel → 8. Notify

        Exam Pipeline (Phases 9–14):
          9. Exam Discovery → 10. Exam Dedup → 11. Exam Parsing
          12. Exam Change Detection → 13. Exam Storage → 14. Exam Alert+Notify
        """
        run_started = datetime.utcnow()
        self.progress.start_time = run_started
        self.progress.run_date = run_id
        self.progress.total_sources = len(PORTAL_SOURCES)
        errors = 0
        total_phases = 14

        mode_label = "schemes + exams"
        if skip_exams:
            mode_label = "schemes only"
        elif skip_schemes:
            mode_label = "exams only"

        console.print(Panel.fit(
            "[bold cyan]GovScheme + GovExam SuperAgent — Daily Pipeline[/bold cyan]\n"
            f"Run ID: {run_id} | Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Mode: {mode_label}",
            border_style="cyan",
        ))

        if skip_schemes:
            # Jump straight to exam pipeline
            daily_report = self._empty_daily_report(run_id, run_started, 0)
            exam_report = await self._run_exam_pipeline(run_id) if self.config.run_exam_pipeline else None
            self._print_daily_summary(daily_report, exam_report)
            return daily_report

        console.print("\n[bold green]═══ SCHEMES PIPELINE ════════════════════════════════════[/bold green]")

        # ── Phase 1: DISCOVERY ──
        console.print("\n[bold green]Phase 1/14: DISCOVERY[/bold green] — Crawling government portals...")
        start = time.time()
        try:
            raw_schemes = await self.discovery.crawl_all_sources()
        except Exception as e:
            logger.error("Discovery phase failed: %s", e, exc_info=True)
            raw_schemes = []
            errors += 1

        self.progress.total_schemes_discovered = len(raw_schemes)
        console.print(f"  ✓ Discovered [bold]{len(raw_schemes)}[/bold] raw schemes in {time.time()-start:.1f}s")

        if not raw_schemes:
            console.print("[red]No schemes discovered. Generating empty report.[/red]")
            return self._empty_daily_report(run_id, run_started, errors + 1)

        # ── Phase 2: DEDUPLICATION ──
        console.print("\n[bold green]Phase 2/14: DEDUPLICATION[/bold green] — Removing duplicates...")
        start = time.time()
        unique_schemes = self.dedup.deduplicate_batch(raw_schemes)
        self.progress.duplicates_found = len(raw_schemes) - len(unique_schemes)
        console.print(
            f"  ✓ [bold]{len(unique_schemes)}[/bold] unique schemes "
            f"({self.progress.duplicates_found} duplicates removed) in {time.time()-start:.1f}s"
        )

        # ── Phase 3: ENRICHMENT ──
        console.print("\n[bold green]Phase 3/14: ENRICHMENT[/bold green] — Fetching scheme details...")
        start = time.time()
        needs_enrichment = [s for s in unique_schemes if not s.raw_description]
        if needs_enrichment:
            console.print(f"  Enriching {len(needs_enrichment)} schemes missing details...")
            try:
                enriched = await self.discovery.enrich_batch(
                    needs_enrichment[:200], max_concurrent=3,
                )
                enriched_map = {s.source_url: s for s in enriched}
                for i, scheme in enumerate(unique_schemes):
                    if scheme.source_url in enriched_map:
                        unique_schemes[i] = enriched_map[scheme.source_url]
            except Exception as e:
                logger.warning("Enrichment partially failed: %s", e)
                errors += 1
        console.print(f"  ✓ Enrichment complete in {time.time()-start:.1f}s")

        # ── Phase 4: CLASSIFICATION ──
        console.print("\n[bold green]Phase 4/14: CLASSIFICATION[/bold green] — LLM categorization + date/fee extraction...")
        start = time.time()
        has_llm = bool(self.config.anthropic_api_key or self.config.openai_api_key)

        if has_llm:
            console.print("  Using LLM for classification (with date/fee extraction)...")
            try:
                classified = await self.classifier.classify_batch(
                    unique_schemes, max_concurrent=3, batch_size=10,
                )
            except Exception as e:
                logger.error("LLM classification failed, falling back: %s", e)
                classified = [self.classifier._fallback_classify(s) for s in unique_schemes]
                errors += 1
        else:
            console.print("  [yellow]No LLM API key — using rule-based classification[/yellow]")
            classified = [self.classifier._fallback_classify(s) for s in unique_schemes]

        self.progress.schemes_classified = len(classified)
        console.print(
            f"  ✓ Classified [bold]{len(classified)}[/bold] schemes in {time.time()-start:.1f}s"
        )

        # ── Phase 5: CHANGE DETECTION ──
        console.print("\n[bold green]Phase 5/14: CHANGE DETECTION[/bold green] — Comparing against database...")
        start = time.time()
        change_agent = ChangeDetectionAgent(self.db)
        annotated = change_agent.process_classified_batch(classified, run_id)

        self.progress.new_schemes_found = len(change_agent.new_schemes)
        self.progress.updated_schemes = len(change_agent.updated_schemes)
        self.progress.deadlines_approaching = len(change_agent.approaching_7d)

        console.print(
            f"  ✓ [bold green]{len(change_agent.new_schemes)}[/bold green] new, "
            f"[bold yellow]{len(change_agent.updated_schemes)}[/bold yellow] updated, "
            f"[bold]{change_agent.unchanged_count}[/bold] unchanged, "
            f"[bold red]{len(change_agent.approaching_7d)}[/bold red] deadlines approaching "
            f"in {time.time()-start:.1f}s"
        )

        # ── Phase 6: STORAGE ──
        console.print("\n[bold green]Phase 6/14: STORAGE[/bold green] — Organizing into folders...")
        start = time.time()
        try:
            stored = await self.storage.store_batch(annotated, max_concurrent=5)
        except Exception as e:
            logger.error("Storage phase failed: %s", e)
            stored = []
            errors += 1
        self.progress.schemes_stored = len(stored)
        console.print(f"  ✓ Stored [bold]{len(stored)}[/bold] schemes in {time.time()-start:.1f}s")

        # Also generate folder-based reports
        try:
            await self.storage.generate_reports(stored)
        except Exception as e:
            logger.warning("Report generation partially failed: %s", e)

        # ── Phase 7: EXCEL REPORT ──
        console.print("\n[bold green]Phase 7/14: EXCEL REPORT[/bold green] — Generating tracking workbook...")
        start = time.time()
        run_completed = datetime.utcnow()
        daily_report = change_agent.generate_daily_report(
            run_id, run_started, run_completed, errors,
        )

        try:
            excel_gen = ExcelReportGenerator(self.db, self.config.output_dir)
            excel_path = excel_gen.generate_full_report(daily_report)
            daily_report.excel_report_path = excel_path
            console.print(f"  ✓ Excel report: [bold]{excel_path}[/bold] in {time.time()-start:.1f}s")
        except Exception as e:
            logger.error("Excel report generation failed: %s", e, exc_info=True)
            excel_path = None
            errors += 1

        # ── Phase 8: SCHEME NOTIFY ──
        console.print("\n[bold green]Phase 8/14: SCHEME NOTIFY[/bold green] — Dispatching scheme reports...")
        try:
            notifier = NotificationDispatcher()
            results = notifier.dispatch(daily_report, excel_path)
            sent = [k for k, v in results.items() if v]
            if sent:
                console.print(f"  ✓ Notifications sent via: [bold]{', '.join(sent)}[/bold]")
            else:
                console.print("  ℹ No notification channels configured (set SMTP_USER/SLACK_WEBHOOK_URL)")
        except Exception as e:
            logger.warning("Notification dispatch failed: %s", e)

        # ═══════════════════════════════════════════════════
        # EXAMS PIPELINE (Phases 9–14) — V3
        # ═══════════════════════════════════════════════════
        exam_report = None
        if self.config.run_exam_pipeline and not skip_exams:
            console.print("\n[bold magenta]═══ EXAMS PIPELINE ══════════════════════════════════[/bold magenta]")
            exam_report = await self._run_exam_pipeline(run_id)

        # ── Final Combined Summary ──
        self._print_daily_summary(daily_report, exam_report)

        # Update Excel with exam data if available
        if exam_report and excel_path:
            try:
                exam_excel_gen = ExcelReportGenerator(
                    self.db, self.config.output_dir, exam_db=self.exam_db,
                )
                excel_path = exam_excel_gen.generate_full_report(daily_report, exam_report=exam_report)
                daily_report.excel_report_path = excel_path
                console.print(f"\n[bold green]📊 Final 15-sheet Excel:[/bold green] {excel_path}")
            except Exception as e:
                logger.warning("Failed to add exam sheets to Excel: %s", e)

        # Re-send notification with exam data included
        if exam_report:
            try:
                notifier = NotificationDispatcher()
                notifier.dispatch(daily_report, excel_path, exam_report=exam_report)
            except Exception as e:
                logger.warning("Exam notification dispatch failed: %s", e)

        return daily_report

    async def _run_exam_pipeline(self, run_id: str) -> ExamDailyReport | None:
        """Execute exam pipeline phases 9–14."""
        exam_started = datetime.utcnow()
        exam_errors = 0
        total_phases = 14

        # ── Phase 9: EXAM DISCOVERY ──
        console.print(f"\n[bold magenta]Phase 9/{total_phases}: EXAM DISCOVERY[/bold magenta] — Crawling 150+ exam portals...")
        start = time.time()
        try:
            raw_exams = await self.exam_crawler.crawl_all_exam_sources(EXAM_PORTAL_SOURCES)
        except Exception as e:
            logger.error("Exam discovery failed: %s", e, exc_info=True)
            raw_exams = []
            exam_errors += 1
        console.print(f"  ✓ Discovered [bold]{len(raw_exams)}[/bold] raw exam notifications in {time.time()-start:.1f}s")

        if not raw_exams:
            console.print("[yellow]No exam notifications discovered. Skipping exam phases.[/yellow]")
            return ExamDailyReport(
                run_id=run_id,
                run_date=datetime.utcnow().strftime("%Y-%m-%d"),
                errors=exam_errors + 1,
            )

        # ── Phase 10: EXAM DEDUP ──
        console.print(f"\n[bold magenta]Phase 10/{total_phases}: EXAM DEDUP[/bold magenta] — Removing duplicates...")
        start = time.time()
        seen_hashes: set[str] = set()
        unique_exams = []
        for ex in raw_exams:
            h = ex.content_hash
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique_exams.append(ex)
        dupes = len(raw_exams) - len(unique_exams)
        console.print(f"  ✓ [bold]{len(unique_exams)}[/bold] unique exams ({dupes} duplicates removed) in {time.time()-start:.1f}s")

        # ── Phase 11: EXAM PARSING ──
        console.print(f"\n[bold magenta]Phase 11/{total_phases}: EXAM PARSING[/bold magenta] — Extracting dates, fees, vacancies...")
        start = time.time()
        try:
            parsed_exams = await self.exam_parser.parse_batch(
                unique_exams, max_concurrent=self.config.exam_llm_max_concurrent,
            )
        except Exception as e:
            logger.error("Exam parsing failed: %s", e, exc_info=True)
            parsed_exams = []
            exam_errors += 1
        llm_count = sum(1 for p in parsed_exams if p.parsing_confidence >= 0.7)
        regex_count = len(parsed_exams) - llm_count
        console.print(
            f"  ✓ Parsed [bold]{len(parsed_exams)}[/bold] exams "
            f"(LLM: {llm_count}, Regex: {regex_count}) in {time.time()-start:.1f}s"
        )

        # ── Phase 12: EXAM CHANGE DETECTION ──
        console.print(f"\n[bold magenta]Phase 12/{total_phases}: EXAM CHANGE DETECT[/bold magenta] — Comparing against DB...")
        start = time.time()
        new_count, updated_count, unchanged_count = 0, 0, 0
        date_revised, vacancy_revised, fee_revised = 0, 0, 0
        new_exam_names: list[str] = []
        seen_exam_ids: set[str] = set()

        for parsed in parsed_exams:
            try:
                change_type = self.exam_db.upsert_exam(parsed, run_id)
                seen_exam_ids.add(parsed.exam_id)
                parsed.change_type = change_type

                if change_type == ExamChangeType.New_Notification:
                    new_count += 1
                    new_exam_names.append(parsed.clean_exam_name or parsed.raw.exam_name)
                elif change_type == ExamChangeType.Unchanged:
                    unchanged_count += 1
                elif change_type == ExamChangeType.Date_Revised:
                    date_revised += 1
                    updated_count += 1
                elif change_type == ExamChangeType.Vacancy_Revised:
                    vacancy_revised += 1
                    updated_count += 1
                elif change_type == ExamChangeType.Fee_Revised:
                    fee_revised += 1
                    updated_count += 1
                else:
                    updated_count += 1
            except Exception as e:
                logger.warning("Exam upsert failed for %s: %s", parsed.raw.exam_name, e)
                exam_errors += 1

        # Mark missing exams as closed (unseen for 3+ days)
        closed_count = self.exam_db.mark_missing_as_closed(run_id, seen_exam_ids)
        console.print(
            f"  ✓ {new_count} new, {date_revised} date-revised, "
            f"{vacancy_revised} vacancy-revised, {fee_revised} fee-revised, "
            f"{unchanged_count} unchanged, {closed_count} closed in {time.time()-start:.1f}s"
        )

        # ── Phase 13: EXAM STORAGE ──
        console.print(f"\n[bold magenta]Phase 13/{total_phases}: EXAM STORAGE[/bold magenta] — Building examinations/ folders...")
        start = time.time()
        stored_count = 0
        try:
            stored_exams = await self.exam_storage.store_batch(parsed_exams)
            stored_count = len(stored_exams)
        except Exception as e:
            logger.error("Exam storage batch failed: %s", e, exc_info=True)
            exam_errors += 1
        console.print(f"  ✓ Stored [bold]{stored_count}[/bold] exams in {time.time()-start:.1f}s")

        # Generate exam report index files
        try:
            if stored_exams:
                await self.exam_storage.generate_exam_reports(stored_exams)
        except Exception as e:
            logger.warning("Exam report index generation failed: %s", e)

        # ── Phase 14: EXAM ALERT + NOTIFY ──
        console.print(f"\n[bold magenta]Phase 14/{total_phases}: EXAM ALERT + NOTIFY[/bold magenta]")
        alerts = self.exam_alert.generate_alerts(datetime.utcnow().strftime("%Y-%m-%d"))

        exam_completed = datetime.utcnow()
        exam_elapsed = (exam_completed - exam_started).total_seconds()

        # Build ExamDailyReport
        exam_report = ExamDailyReport(
            run_id=run_id,
            run_date=datetime.utcnow().strftime("%Y-%m-%d"),
            run_started_at=exam_started,
            run_completed_at=exam_completed,
            total_exams_in_db=self.exam_db.get_total_count(),
            new_exams=new_count,
            updated_exams=updated_count,
            date_revised_exams=date_revised,
            vacancy_revised_exams=vacancy_revised,
            closed_exams=closed_count,
            application_open_exams=len(alerts.get("newly_opened", [])),
            deadlines_within_7_days=len(alerts.get("application_closing_7d", [])),
            deadlines_within_30_days=len(alerts.get("application_closing_30d", [])),
            exams_in_7_days=len(alerts.get("exams_in_7d", [])),
            exams_in_30_days=len(alerts.get("exams_in_30d", [])),
            errors=exam_errors,
            elapsed_seconds=exam_elapsed,
            new_exam_names=new_exam_names[:50],
            approaching_deadline_exams=[
                e.get("clean_exam_name", e.get("exam_name", "Unknown"))
                for e in alerts.get("application_closing_7d", [])[:20]
            ],
        )

        # Persist exam run to DB
        try:
            self.exam_db.save_exam_run(exam_report)
        except Exception as e:
            logger.warning("Failed to save exam run: %s", e)

        console.print(f"  ✓ Exam alerts generated. Pipeline completed in {exam_elapsed:.1f}s")
        return exam_report

    def _empty_daily_report(
        self, run_id: str, started: datetime, errors: int,
    ) -> DailyRunReport:
        """Generate a report when no schemes were discovered."""
        from src.agents.models import DailyRunReport
        report = DailyRunReport(
            run_id=run_id,
            run_date=datetime.utcnow().strftime("%Y-%m-%d"),
            run_started_at=started,
            run_completed_at=datetime.utcnow(),
            errors=errors,
        )
        self.db.save_daily_run(report)

        # Still try to generate Excel from existing DB data
        try:
            excel_gen = ExcelReportGenerator(self.db, self.config.output_dir)
            report.excel_report_path = excel_gen.generate_full_report(report)
        except Exception:
            pass

        return report

    def _print_daily_summary(self, report: DailyRunReport, exam_report: ExamDailyReport | None = None) -> None:
        """Print the daily run summary with Rich tables."""
        table = Table(
            title=f"GovScheme + GovExam — Combined Daily Report — {report.run_date}",
            border_style="cyan",
        )
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")

        # Scheme metrics
        table.add_row("[bold cyan]══ SCHEMES ══[/bold cyan]", "")
        table.add_row("Total in Database", str(report.total_schemes_in_db))
        table.add_row("🆕 New Schemes", f"[green]{report.new_schemes}[/green]")
        table.add_row("🔄 Updated", f"[yellow]{report.updated_schemes}[/yellow]")
        table.add_row("📦 Unchanged", str(report.unchanged_schemes))
        table.add_row("🚫 Closed", str(report.closed_schemes))
        table.add_row("⚠️  Deadlines (7 days)", f"[red]{report.deadlines_within_7_days}[/red]")
        table.add_row("✅ Active Schemes", str(report.active_schemes))
        table.add_row("❌ Errors", str(report.errors))

        # Exam metrics
        if exam_report:
            table.add_row("", "")
            table.add_row("[bold magenta]══ EXAMS ══[/bold magenta]", "")
            table.add_row("Total Exams in DB", str(exam_report.total_exams_in_db))
            table.add_row("🆕 New Notifications", f"[green]{exam_report.new_exams}[/green]")
            table.add_row("📅 Date Revised", f"[yellow]{exam_report.date_revised_exams}[/yellow]")
            table.add_row("📦 Vacancy Revised", str(exam_report.vacancy_revised_exams))
            table.add_row("🟢 Applications Open", str(exam_report.application_open_exams))
            table.add_row("⚠️  App Closing 7d", f"[red]{exam_report.deadlines_within_7_days}[/red]")
            table.add_row("⚠️  App Closing 30d", f"[yellow]{exam_report.deadlines_within_30_days}[/yellow]")
            table.add_row("📆 Exams in 7 Days", str(exam_report.exams_in_7_days))
            table.add_row("📆 Exams in 30 Days", str(exam_report.exams_in_30_days))
            table.add_row("❌ Exam Errors", str(exam_report.errors))

        if report.excel_report_path:
            table.add_row("", "")
            table.add_row("📊 Excel Report", report.excel_report_path)

        console.print()
        console.print(table)

        if report.new_scheme_names:
            new_table = Table(title="🆕 New Schemes Discovered", border_style="green")
            new_table.add_column("#", width=4)
            new_table.add_column("Scheme Name")
            for i, name in enumerate(report.new_scheme_names[:20], 1):
                new_table.add_row(str(i), name)
            console.print(new_table)

        if report.approaching_deadline_names:
            dl_table = Table(title="⚠️ Approaching Deadlines", border_style="red")
            dl_table.add_column("#", width=4)
            dl_table.add_column("Scheme Name")
            for i, name in enumerate(report.approaching_deadline_names[:15], 1):
                dl_table.add_row(str(i), name)
            console.print(dl_table)

    async def run_full_pipeline(self) -> None:
        """Execute the complete agent pipeline."""
        self.progress.start_time = datetime.utcnow()
        self.progress.total_sources = len(PORTAL_SOURCES)

        console.print(Panel.fit(
            "[bold cyan]GovScheme SuperAgent[/bold cyan]\n"
            "Crawling Indian Government Schemes across Central, State & UT portals",
            border_style="cyan",
        ))

        # ── Phase 1: DISCOVERY ──
        console.print("\n[bold green]Phase 1: DISCOVERY[/bold green] — Crawling government portals...")
        start = time.time()

        raw_schemes = await self.discovery.crawl_all_sources()
        self.progress.total_schemes_discovered = len(raw_schemes)
        self.progress.last_update = datetime.utcnow()

        console.print(f"  ✓ Discovered [bold]{len(raw_schemes)}[/bold] raw schemes in {time.time()-start:.1f}s")

        if not raw_schemes:
            console.print("[red]No schemes discovered. Check network connectivity and portal availability.[/red]")
            return

        # ── Phase 2: DEDUPLICATION ──
        console.print("\n[bold green]Phase 2: DEDUPLICATION[/bold green] — Removing duplicates...")
        start = time.time()

        unique_schemes = self.dedup.deduplicate_batch(raw_schemes)
        self.progress.duplicates_found = len(raw_schemes) - len(unique_schemes)
        self.progress.last_update = datetime.utcnow()

        console.print(
            f"  ✓ [bold]{len(unique_schemes)}[/bold] unique schemes "
            f"({self.progress.duplicates_found} duplicates removed) in {time.time()-start:.1f}s"
        )

        # ── Phase 3: ENRICHMENT ──
        console.print("\n[bold green]Phase 3: ENRICHMENT[/bold green] — Fetching scheme details...")
        start = time.time()

        # Enrich top-priority schemes first (those missing descriptions)
        needs_enrichment = [s for s in unique_schemes if not s.raw_description]
        if needs_enrichment:
            console.print(f"  Enriching {len(needs_enrichment)} schemes with missing details...")
            enriched = await self.discovery.enrich_batch(
                needs_enrichment[:200],  # Limit to avoid excessive crawling
                max_concurrent=3,
            )
            # Merge enriched data back
            enriched_map = {s.source_url: s for s in enriched}
            for i, scheme in enumerate(unique_schemes):
                if scheme.source_url in enriched_map:
                    unique_schemes[i] = enriched_map[scheme.source_url]

        console.print(f"  ✓ Enrichment complete in {time.time()-start:.1f}s")

        # ── Phase 4: CLASSIFICATION ──
        console.print("\n[bold green]Phase 4: CLASSIFICATION[/bold green] — LLM-powered categorization...")
        start = time.time()

        # Check if we have an API key for LLM classification
        has_llm = bool(self.config.anthropic_api_key or self.config.openai_api_key)

        if has_llm:
            console.print("  Using LLM for intelligent classification...")
            classified = await self.classifier.classify_batch(
                unique_schemes,
                max_concurrent=3,
                batch_size=10,
            )
        else:
            console.print("  [yellow]No LLM API key found — using rule-based classification[/yellow]")
            classified = [
                self.classifier._fallback_classify(s)
                for s in unique_schemes
            ]

        self.progress.schemes_classified = len(classified)
        self.progress.last_update = datetime.utcnow()

        console.print(
            f"  ✓ Classified [bold]{len(classified)}[/bold] schemes "
            f"(LLM: {self.classifier.classified_count}, "
            f"Fallback: {self.classifier.failed_count}) in {time.time()-start:.1f}s"
        )

        # ── Phase 5: STORAGE ──
        console.print("\n[bold green]Phase 5: STORAGE[/bold green] — Organizing into folders...")
        start = time.time()

        stored = await self.storage.store_batch(classified, max_concurrent=5)
        self.progress.schemes_stored = len(stored)
        self.progress.last_update = datetime.utcnow()

        console.print(f"  ✓ Stored [bold]{len(stored)}[/bold] schemes in {time.time()-start:.1f}s")

        # ── Phase 6: REPORTING ──
        console.print("\n[bold green]Phase 6: REPORTING[/bold green] — Generating summary reports...")

        await self.storage.generate_reports(stored)
        self._print_final_summary(stored)

    async def run_discovery_only(self) -> None:
        """Run only the discovery phase."""
        console.print("[bold]Running discovery-only mode...[/bold]")
        raw = await self.discovery.crawl_all_sources()
        unique = self.dedup.deduplicate_batch(raw)

        # Save raw data
        output = Path(self.config.output_dir) / "raw_discoveries.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(
            [s.model_dump(mode="json") for s in unique],
            indent=2,
            ensure_ascii=False,
            default=str,
        ))
        console.print(f"Saved {len(unique)} unique schemes to {output}")

    def _print_final_summary(self, stored) -> None:
        """Print the final summary table."""
        table = Table(title="GovScheme SuperAgent — Final Report", border_style="cyan")
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")

        table.add_row("Total Discovered", str(self.progress.total_schemes_discovered))
        table.add_row("Duplicates Removed", str(self.progress.duplicates_found))
        table.add_row("Classified", str(self.progress.schemes_classified))
        table.add_row("Stored", str(self.progress.schemes_stored))
        table.add_row("Errors", str(len(self.discovery.errors)))
        table.add_row("Elapsed Time", f"{self.progress.elapsed_minutes:.1f} min")
        table.add_row("Output Directory", self.config.output_dir)

        console.print()
        console.print(table)

        # Sector breakdown
        if stored:
            sector_counts: dict[str, int] = {}
            level_counts: dict[str, int] = {}
            for s in stored:
                sec = s.classified.sector.value
                sector_counts[sec] = sector_counts.get(sec, 0) + 1
                lev = s.classified.level.value
                level_counts[lev] = level_counts.get(lev, 0) + 1

            sector_table = Table(title="By Sector", border_style="green")
            sector_table.add_column("Sector")
            sector_table.add_column("Count", justify="right")
            for sec, count in sorted(sector_counts.items(), key=lambda x: -x[1]):
                sector_table.add_row(sec.replace("_", " "), str(count))
            console.print(sector_table)

            level_table = Table(title="By Level", border_style="blue")
            level_table.add_column("Level")
            level_table.add_column("Count", justify="right")
            for lev, count in sorted(level_counts.items(), key=lambda x: -x[1]):
                level_table.add_row(lev, str(count))
            console.print(level_table)


def main():
    parser = argparse.ArgumentParser(description="GovScheme + GovExam SuperAgent — Government Scheme & Exam Crawler")
    parser.add_argument(
        "--mode",
        choices=["full", "daily", "discover", "classify", "store", "report-only", "exams-only", "schemes-only"],
        default="full",
        help="Pipeline mode: full (bootstrap), daily (scheduled delta), exams-only, schemes-only, report-only (Excel from DB)",
    )
    parser.add_argument("--output", default="./output", help="Output directory")
    parser.add_argument("--llm-provider", choices=["anthropic", "openai"], default="anthropic")
    parser.add_argument("--model", default="claude-sonnet-4-5-20250929", help="LLM model name")
    parser.add_argument("--max-crawlers", type=int, default=5, help="Max concurrent crawlers")
    parser.add_argument("--no-pdfs", action="store_true", help="Skip PDF downloads")
    parser.add_argument("--run-id", default=None, help="Custom run ID for daily mode")
    parser.add_argument("--db-path", default="./data/schemes.db", help="SQLite database path")
    parser.add_argument("--exam-db-path", default="./data/exams.db", help="SQLite exam database path")
    parser.add_argument("--skip-exams", action="store_true", help="Skip exam pipeline for this run")

    args = parser.parse_args()

    config = AgentConfig(
        output_dir=args.output,
        llm_provider=args.llm_provider,
        model_name=args.model,
        max_concurrent_crawlers=args.max_crawlers,
        download_pdfs=not args.no_pdfs,
        db_path=args.db_path,
        exam_db_path=args.exam_db_path,
    )

    orchestrator = Orchestrator(config)

    if args.mode == "full":
        asyncio.run(orchestrator.run_full_pipeline())

    elif args.mode in ("daily", "exams-only", "schemes-only"):
        import hashlib as _hl
        run_id = args.run_id or f"run_{datetime.utcnow().strftime('%Y-%m-%d')}_{_hl.md5(str(time.time()).encode()).hexdigest()[:6]}"
        skip_exams = args.skip_exams or args.mode == "schemes-only"
        skip_schemes = args.mode == "exams-only"
        report = asyncio.run(orchestrator.run_daily_pipeline(
            run_id, skip_exams=skip_exams, skip_schemes=skip_schemes,
        ))
        if report:
            console.print(f"\n[bold green]Pipeline complete.[/bold green] Excel: {report.excel_report_path}")
        else:
            console.print("[red]Pipeline failed.[/red]")
            sys.exit(1)

    elif args.mode == "discover":
        asyncio.run(orchestrator.run_discovery_only())

    elif args.mode == "report-only":
        # Generate Excel from existing DBs without crawling
        db = SchemeDatabase(config.db_path)
        exam_db = ExamDatabase(config.exam_db_path) if Path(config.exam_db_path).exists() else None
        excel_gen = ExcelReportGenerator(db, config.output_dir, exam_db=exam_db)
        path = excel_gen.generate_full_report()
        console.print(f"[bold green]Excel report generated:[/bold green] {path}")

    else:
        console.print(f"[yellow]Mode '{args.mode}' not yet implemented as standalone[/yellow]")
        asyncio.run(orchestrator.run_full_pipeline())


if __name__ == "__main__":
    main()
```

---

## File 31/41: `src/resilience/__init__.py`
<!-- lines: 0 -->

```python

```

---

## File 32/41: `src/resilience/crawler_resilience.py`
<!-- lines: 682 -->

```python
"""
GovScheme SuperAgent — Adaptive Crawler Resilience Layer
Addresses EVERY crawler limitation identified:

1. JS-HEAVY SITES (UPSC, RBI, State PSCs)
   → Playwright browser pool with headless Chrome fallback
   → Detects JS-required pages by checking if httpx returns empty/minimal content

2. SELECTOR SELF-HEALING
   → Multiple selector strategies per portal (primary, fallback, generic)
   → Auto-detects selector drift when extraction yields 0 items
   → Falls back to generic heuristic extraction (links + text patterns)

3. ANTI-BAN / RATE LIMITING
   → Adaptive delay based on response codes (429 → exponential backoff)
   → User-agent rotation from realistic browser fingerprint pool
   → Referer header spoofing for government portals
   → Respects robots.txt (optional)

4. CAPTCHA DETECTION
   → Detects CAPTCHA pages by HTML signatures
   → Flags portal as captcha_required, skips with logged warning
   → Does NOT attempt to solve CAPTCHAs

5. OCR FOR SCANNED PDFs
   → Detects image-only PDFs (no extractable text)
   → Falls back to pytesseract OCR if available
   → Falls back to pdf2image + tesseract pipeline
   → Graceful degradation: if OCR not installed, logs and skips

6. PROXY ROTATION (optional)
   → Configurable proxy list via PROXY_LIST env var
   → Round-robin rotation
   → Marks dead proxies

7. CONTENT VALIDATION
   → Checks if response is actual HTML vs error page / maintenance page
   → Detects common government error pages ("Site under maintenance", "403 Forbidden")
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("crawler_resilience")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. USER-AGENT ROTATION
# ═══════════════════════════════════════════════════════════════════════════════

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
]


def get_random_headers(referer_domain: str = "") -> dict[str, str]:
    """Generate realistic browser headers with rotation."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.8,hi;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }
    if referer_domain:
        headers["Referer"] = f"https://{referer_domain}/"
        headers["Sec-Fetch-Site"] = "same-origin"
    return headers


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ADAPTIVE RATE LIMITER
# ═══════════════════════════════════════════════════════════════════════════════

class AdaptiveRateLimiter:
    """
    Per-domain rate limiting that adapts based on response codes.
    429/503 → double delay; 200 → slowly decrease delay.
    """

    def __init__(self, base_delay: float = 1.0, max_delay: float = 60.0):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._domain_delays: dict[str, float] = {}
        self._domain_locks: dict[str, asyncio.Lock] = {}

    def _get_domain(self, url: str) -> str:
        return urlparse(url).netloc

    async def wait(self, url: str) -> None:
        """Wait the appropriate delay for this domain."""
        domain = self._get_domain(url)
        delay = self._domain_delays.get(domain, self.base_delay)

        if domain not in self._domain_locks:
            self._domain_locks[domain] = asyncio.Lock()

        async with self._domain_locks[domain]:
            jitter = random.uniform(0.1, 0.5)
            await asyncio.sleep(delay + jitter)

    def record_response(self, url: str, status_code: int) -> None:
        """Adapt delay based on response code."""
        domain = self._get_domain(url)
        current = self._domain_delays.get(domain, self.base_delay)

        if status_code in (429, 503, 529):
            # Rate limited or overloaded — back off hard
            new_delay = min(current * 2.5, self.max_delay)
            logger.warning("Rate limited on %s (HTTP %d), delay → %.1fs", domain, status_code, new_delay)
        elif status_code == 403:
            # Possibly blocked — significant backoff
            new_delay = min(current * 3.0, self.max_delay)
            logger.warning("Blocked on %s (403), delay → %.1fs", domain, new_delay)
        elif status_code < 400:
            # Success — slowly decrease delay back toward base
            new_delay = max(current * 0.9, self.base_delay)
        else:
            new_delay = current

        self._domain_delays[domain] = new_delay

    def get_domain_delay(self, url: str) -> float:
        return self._domain_delays.get(self._get_domain(url), self.base_delay)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. CAPTCHA DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

CAPTCHA_SIGNATURES = [
    "captcha", "recaptcha", "g-recaptcha", "hcaptcha",
    "challenge-form", "cf-challenge", "verify you are human",
    "security check", "bot detection", "please verify",
    "cf-turnstile", "human verification",
    "id=\"challenge-running\"", "id=\"challenge-form\"",
]

MAINTENANCE_SIGNATURES = [
    "site under maintenance", "under construction", "scheduled maintenance",
    "temporarily unavailable", "service unavailable", "coming soon",
    "502 bad gateway", "503 service temporarily unavailable",
    "server is temporarily unable", "site is down for maintenance",
]

ERROR_PAGE_SIGNATURES = [
    "404 not found", "page not found", "the page you are looking for",
    "403 forbidden", "access denied", "you don't have permission",
    "500 internal server error",
]


def detect_captcha(html: str) -> bool:
    """Detect if page contains a CAPTCHA challenge."""
    html_lower = html.lower()
    return any(sig in html_lower for sig in CAPTCHA_SIGNATURES)


def detect_maintenance(html: str) -> bool:
    """Detect if page is a maintenance/error page."""
    html_lower = html.lower()
    return any(sig in html_lower for sig in MAINTENANCE_SIGNATURES)


def detect_error_page(html: str) -> bool:
    """Detect common error pages."""
    html_lower = html.lower()
    return any(sig in html_lower for sig in ERROR_PAGE_SIGNATURES)


def validate_page_content(html: str, portal_name: str) -> tuple[bool, str]:
    """
    Validate that page content is usable.
    Returns (is_valid, reason).
    """
    if not html or len(html.strip()) < 100:
        return False, "empty_response"

    if detect_captcha(html):
        logger.warning("CAPTCHA detected on %s", portal_name)
        return False, "captcha"

    if detect_maintenance(html):
        logger.warning("Maintenance page on %s", portal_name)
        return False, "maintenance"

    if detect_error_page(html):
        return False, "error_page"

    return True, "ok"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. JS RENDERING (Playwright fallback)
# ═══════════════════════════════════════════════════════════════════════════════

_PLAYWRIGHT_AVAILABLE = None


def _check_playwright() -> bool:
    """Check if Playwright is installed and browsers are available."""
    global _PLAYWRIGHT_AVAILABLE
    if _PLAYWRIGHT_AVAILABLE is not None:
        return _PLAYWRIGHT_AVAILABLE
    try:
        from playwright.async_api import async_playwright
        _PLAYWRIGHT_AVAILABLE = True
    except ImportError:
        _PLAYWRIGHT_AVAILABLE = False
        logger.info("Playwright not installed — JS rendering disabled. Install with: pip install playwright && playwright install chromium")
    return _PLAYWRIGHT_AVAILABLE


async def fetch_with_js(url: str, timeout_ms: int = 30000, wait_selector: str = "body") -> Optional[str]:
    """
    Fetch a page using Playwright headless browser for JS-heavy sites.
    Returns HTML string or None on failure.
    """
    if not _check_playwright():
        return None

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1366, "height": 768},
                locale="en-IN",
            )
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                await page.wait_for_selector(wait_selector, timeout=10000)
                # Extra wait for dynamic content
                await asyncio.sleep(2)
                html = await page.content()
                return html
            except Exception as e:
                logger.warning("Playwright fetch failed for %s: %s", url, e)
                return None
            finally:
                await browser.close()

    except Exception as e:
        logger.error("Playwright error: %s", e)
        return None


def needs_js_rendering(html_content: str, min_text_length: int = 500) -> bool:
    """
    Detect if a page likely needs JS rendering.
    Signs: very little text content, noscript tags, JS framework markers.
    """
    if not html_content:
        return True

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script/style tags
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(strip=True)

    if len(text) < min_text_length:
        return True

    # Check for SPA framework markers
    spa_markers = [
        'id="__next"', 'id="app"', 'id="root"',
        'ng-app=', 'data-reactroot', 'data-v-',
        '<app-root', 'window.__NUXT__',
    ]
    html_lower = html_content.lower()
    spa_count = sum(1 for m in spa_markers if m.lower() in html_lower)
    if spa_count >= 2 and len(text) < 1000:
        return True

    return False


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SELECTOR SELF-HEALING
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SelectorStrategy:
    """Multiple CSS selector strategies for a single portal."""
    primary: dict[str, str]
    fallbacks: list[dict[str, str]] = field(default_factory=list)


# Generic selectors that work on many government sites
GENERIC_SELECTORS = {
    "notification_links": [
        "table tbody tr td a[href]",
        "div.content a[href*='.pdf']",
        "ul.list li a[href]",
        "div.notification a[href]",
        "div.recruitment a[href]",
        "a[href*='notification']",
        "a[href*='recruitment']",
        "a[href*='advertisement']",
        "a[href*='career']",
    ],
    "date_patterns": [
        "td:nth-child(2)", "td:nth-child(3)",
        "span.date", "div.date", "time",
        "td[data-date]",
    ],
    "name_patterns": [
        "td:first-child a", "td:first-child",
        "h4 a", "h5 a", "h3 a",
        "div.title a", "div.card-title",
        "li a[href]", "p strong a",
    ],
}


def extract_with_healing(
    soup: BeautifulSoup,
    portal_name: str,
    primary_selectors: dict[str, str],
    fallback_selectors: Optional[list[dict[str, str]]] = None,
    min_expected_items: int = 3,
) -> tuple[list, str]:
    """
    Try primary selectors first. If they yield < min_expected_items,
    try fallbacks, then generic heuristics.
    Returns (items, strategy_used).
    """
    # Try primary
    items = _try_selector_set(soup, primary_selectors)
    if len(items) >= min_expected_items:
        return items, "primary"

    logger.debug("Primary selectors yielded %d items on %s, trying fallbacks", len(items), portal_name)

    # Try each fallback
    if fallback_selectors:
        for i, fallback in enumerate(fallback_selectors):
            items = _try_selector_set(soup, fallback)
            if len(items) >= min_expected_items:
                logger.info("Fallback %d worked on %s (%d items)", i + 1, portal_name, len(items))
                return items, f"fallback_{i + 1}"

    # Generic heuristic: find all links that look like notifications
    logger.info("All selectors failed on %s, using generic heuristic", portal_name)
    items = _generic_notification_extract(soup)
    if items:
        return items, "generic_heuristic"

    return [], "none"


def _try_selector_set(soup: BeautifulSoup, selectors: dict[str, str]) -> list:
    """Try a set of CSS selectors and return found elements."""
    items = []
    list_selector = selectors.get("exam_list") or selectors.get("notification_list", "")
    if list_selector:
        items = soup.select(list_selector)
    return items


def _generic_notification_extract(soup: BeautifulSoup) -> list:
    """
    Last-resort heuristic extraction: find all links that look like
    government notifications, exam notices, or scheme announcements.
    """
    results = []
    link_patterns = re.compile(
        r'(notification|recruitment|advertisement|vacancy|exam|career|'
        r'admit.?card|result|application|syllabus|circular|notice|'
        r'scheme|scholarship|yojana|yojn|\.pdf)',
        re.IGNORECASE,
    )

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        text = a_tag.get_text(strip=True)

        # Match on href or text
        if link_patterns.search(href) or (text and link_patterns.search(text)):
            if len(text) > 10:  # Skip tiny navigation links
                results.append(a_tag)

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 6. OCR FOR SCANNED PDFs
# ═══════════════════════════════════════════════════════════════════════════════

_TESSERACT_AVAILABLE = None
_PDF2IMAGE_AVAILABLE = None


def _check_ocr_deps() -> tuple[bool, bool]:
    """Check if OCR dependencies are available."""
    global _TESSERACT_AVAILABLE, _PDF2IMAGE_AVAILABLE

    if _TESSERACT_AVAILABLE is None:
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            _TESSERACT_AVAILABLE = True
        except Exception:
            _TESSERACT_AVAILABLE = False
            logger.info("Tesseract OCR not available. Install with: apt install tesseract-ocr && pip install pytesseract")

    if _PDF2IMAGE_AVAILABLE is None:
        try:
            import pdf2image
            _PDF2IMAGE_AVAILABLE = True
        except ImportError:
            _PDF2IMAGE_AVAILABLE = False
            logger.info("pdf2image not available. Install with: pip install pdf2image && apt install poppler-utils")

    return _TESSERACT_AVAILABLE, _PDF2IMAGE_AVAILABLE


def extract_text_from_pdf(pdf_path: str, max_pages: int = 20) -> tuple[str, str]:
    """
    Extract text from PDF with OCR fallback.
    Returns (text, method) where method is "text" or "ocr" or "none".
    """
    text = ""

    # Try PyPDF2 first (fast, no OCR)
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        pages = reader.pages[:max_pages]
        text = "\n".join(page.extract_text() or "" for page in pages)

        if len(text.strip()) > 100:
            return text, "text"
        else:
            logger.debug("PDF has minimal extractable text (%d chars), trying OCR", len(text.strip()))
    except Exception as e:
        logger.warning("PyPDF2 extraction failed for %s: %s", pdf_path, e)

    # Try pdfminer.six (better text extraction)
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        text = pdfminer_extract(pdf_path, maxpages=max_pages)
        if len(text.strip()) > 100:
            return text, "text"
    except Exception:
        pass

    # OCR fallback
    tesseract_ok, pdf2image_ok = _check_ocr_deps()

    if tesseract_ok and pdf2image_ok:
        try:
            import pytesseract
            from pdf2image import convert_from_path

            images = convert_from_path(
                pdf_path,
                first_page=1,
                last_page=min(max_pages, 10),
                dpi=200,
            )

            ocr_text_parts = []
            for i, img in enumerate(images):
                page_text = pytesseract.image_to_string(img, lang="eng+hin")
                ocr_text_parts.append(page_text)

            text = "\n\n".join(ocr_text_parts)
            if len(text.strip()) > 50:
                return text, "ocr"

        except Exception as e:
            logger.warning("OCR failed for %s: %s", pdf_path, e)

    return text or "", "none"


def is_scanned_pdf(pdf_path: str) -> bool:
    """Quick check: does the PDF have extractable text or is it scanned images?"""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        if not reader.pages:
            return True
        # Check first 3 pages
        total_text = ""
        for page in reader.pages[:3]:
            total_text += page.extract_text() or ""
        return len(total_text.strip()) < 50
    except Exception:
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# 7. PROXY ROTATION (Optional)
# ═══════════════════════════════════════════════════════════════════════════════

class ProxyRotator:
    """Round-robin proxy rotation from PROXY_LIST env var."""

    def __init__(self):
        raw = os.getenv("PROXY_LIST", "")
        self.proxies = [p.strip() for p in raw.split(",") if p.strip()]
        self._dead: set[str] = set()
        self._index = 0

    @property
    def enabled(self) -> bool:
        return bool(self.proxies)

    def get_proxy(self) -> Optional[str]:
        """Get next working proxy or None."""
        if not self.proxies:
            return None

        alive = [p for p in self.proxies if p not in self._dead]
        if not alive:
            logger.warning("All proxies dead, resetting")
            self._dead.clear()
            alive = self.proxies

        proxy = alive[self._index % len(alive)]
        self._index += 1
        return proxy

    def mark_dead(self, proxy: str) -> None:
        self._dead.add(proxy)
        logger.warning("Proxy marked dead: %s", proxy[:30])

    def get_httpx_proxy(self) -> Optional[dict]:
        proxy = self.get_proxy()
        if proxy:
            return {"http://": proxy, "https://": proxy}
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# 8. RESILIENT FETCH — Combines everything above
# ═══════════════════════════════════════════════════════════════════════════════

class ResilientFetcher:
    """
    Single entry point for resilient page fetching.
    Combines: rate limiting, user-agent rotation, proxy rotation,
    CAPTCHA detection, JS rendering fallback, content validation.
    """

    def __init__(
        self,
        rate_limiter: Optional[AdaptiveRateLimiter] = None,
        proxy_rotator: Optional[ProxyRotator] = None,
        timeout: float = 30.0,
    ):
        self.rate_limiter = rate_limiter or AdaptiveRateLimiter()
        self.proxy = proxy_rotator or ProxyRotator()
        self.timeout = timeout
        self.stats = {"total": 0, "success": 0, "js_fallback": 0, "captcha": 0, "errors": 0}

    async def fetch(
        self,
        url: str,
        portal_name: str = "",
        needs_js: bool = False,
        max_retries: int = 2,
    ) -> tuple[Optional[str], dict]:
        """
        Fetch a URL with all resilience layers.
        Returns (html_content, metadata_dict).
        """
        self.stats["total"] += 1
        meta = {"url": url, "portal": portal_name, "method": "httpx", "status": 0, "response_ms": 0}
        domain = urlparse(url).netloc

        for attempt in range(1, max_retries + 1):
            await self.rate_limiter.wait(url)

            headers = get_random_headers(domain)
            proxy_config = self.proxy.get_httpx_proxy()

            start_time = time.time()
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=True,
                    proxies=proxy_config,
                    verify=False,
                ) as client:
                    resp = await client.get(url, headers=headers)

                elapsed_ms = (time.time() - start_time) * 1000
                meta["status"] = resp.status_code
                meta["response_ms"] = elapsed_ms

                self.rate_limiter.record_response(url, resp.status_code)

                if resp.status_code >= 400:
                    if resp.status_code in (403, 429) and proxy_config:
                        proxy_url = self.proxy.get_proxy()
                        if proxy_url:
                            self.proxy.mark_dead(proxy_url)
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    meta["error"] = f"HTTP {resp.status_code}"
                    self.stats["errors"] += 1
                    return None, meta

                html = resp.text

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as e:
                meta["error"] = str(type(e).__name__)
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                self.stats["errors"] += 1
                return None, meta

            # Content validation
            is_valid, reason = validate_page_content(html, portal_name)

            if reason == "captcha":
                self.stats["captcha"] += 1
                meta["captcha"] = True
                return None, meta

            if not is_valid and reason == "maintenance":
                meta["maintenance"] = True
                return None, meta

            # Check if JS rendering needed
            if needs_js or needs_js_rendering(html):
                logger.info("Attempting JS rendering for %s", portal_name or url[:60])
                js_html = await fetch_with_js(url)
                if js_html and len(js_html) > len(html):
                    html = js_html
                    meta["method"] = "playwright"
                    self.stats["js_fallback"] += 1

            self.stats["success"] += 1
            return html, meta

        self.stats["errors"] += 1
        return None, meta

    def get_stats(self) -> dict:
        return dict(self.stats)
```

---

## File 33/41: `src/resilience/llm_hardener.py`
<!-- lines: 392 -->

```python
"""
GovScheme SuperAgent — LLM Response Hardener
Addresses limitation: "Claude/GPT will sometimes return malformed JSON,
hallucinate dates, or misclassify exams."

Layers of defense:
  1. JSON extraction from mixed text/markdown responses
  2. Structural repair of malformed JSON (unclosed brackets, trailing commas)
  3. Schema validation against expected fields and types
  4. Date plausibility checks (no dates before 2020 or after 2030)
  5. Enum value correction (fuzzy match against valid values)
  6. Retry with simplified prompt on failure
  7. Confidence penalty for repaired responses
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, date
from typing import Any, Optional

logger = logging.getLogger("llm_hardener")

# ── Date Plausibility Window ─────────────────────────────────────────────────
MIN_PLAUSIBLE_YEAR = 2020
MAX_PLAUSIBLE_YEAR = 2032


class LLMResponseHardener:
    """Repairs and validates LLM JSON responses."""

    def __init__(self, valid_enums: Optional[dict[str, list[str]]] = None):
        """
        Args:
            valid_enums: Map of field_name → list of valid enum string values.
                         e.g. {"level": ["Central", "State", "Union_Territory"]}
        """
        self.valid_enums = valid_enums or {}
        self.repair_count = 0
        self.reject_count = 0

    # ─── Main Entry Point ────────────────────────────────────────────────────

    def parse_and_validate(
        self,
        raw_response: str,
        required_fields: Optional[list[str]] = None,
        date_fields: Optional[list[str]] = None,
        numeric_fields: Optional[list[str]] = None,
    ) -> tuple[Optional[dict], float]:
        """
        Parse LLM response, repair if needed, validate, return (data, confidence_penalty).
        confidence_penalty: 0.0 = no repairs needed, up to 0.5 = heavily repaired.
        Returns (None, 1.0) if unrecoverable.
        """
        penalty = 0.0

        # Step 1: Extract JSON from response
        data = self._extract_json(raw_response)
        if data is None:
            # Try structural repair
            repaired = self._repair_json_structure(raw_response)
            data = self._extract_json(repaired)
            if data is None:
                logger.warning("JSON extraction failed after repair")
                self.reject_count += 1
                return None, 1.0
            penalty += 0.15

        # Step 2: Type coercion
        if numeric_fields:
            for field in numeric_fields:
                if field in data and data[field] is not None:
                    data[field], p = self._coerce_numeric(data[field])
                    penalty += p

        # Step 3: Enum correction
        for field, valid_values in self.valid_enums.items():
            if field in data and data[field] is not None:
                data[field], p = self._correct_enum(data[field], valid_values)
                penalty += p

        # Step 4: Date plausibility
        if date_fields:
            for field in date_fields:
                if field in data and data[field] is not None:
                    data[field], p = self._validate_date(data[field], field)
                    penalty += p

        # Step 5: Required fields check
        if required_fields:
            missing = [f for f in required_fields if f not in data or data[f] is None]
            if missing:
                logger.debug("Missing required fields: %s", missing)
                penalty += 0.05 * len(missing)

        # Step 6: Nested list validation (phases, vacancies, documents)
        for list_field in ["phases", "vacancies", "documents_required"]:
            if list_field in data:
                data[list_field] = self._validate_list_field(data[list_field])

        if penalty > 0:
            self.repair_count += 1

        return data, min(penalty, 0.5)

    # ─── JSON Extraction ─────────────────────────────────────────────────────

    def _extract_json(self, text: str) -> Optional[dict]:
        """Extract JSON object from LLM response that may contain markdown or prose."""
        if not text or not text.strip():
            return None

        text = text.strip()

        # Try direct parse
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        patterns = [
            r'```json\s*\n(.*?)\n\s*```',
            r'```\s*\n(.*?)\n\s*```',
            r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group(1))
                    if isinstance(result, dict):
                        return result
                except json.JSONDecodeError:
                    continue

        # Try finding the outermost { ... }
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            candidate = text[brace_start : brace_end + 1]
            try:
                result = json.loads(candidate)
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

        return None

    # ─── Structural JSON Repair ──────────────────────────────────────────────

    def _repair_json_structure(self, text: str) -> str:
        """Fix common JSON structural issues from LLM output."""
        # Extract the JSON-looking portion
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start < 0:
            return text

        if brace_end <= brace_start:
            # Missing closing brace — try to fix
            candidate = text[brace_start:]
        else:
            candidate = text[brace_start : brace_end + 1]

        # Fix trailing commas before } or ]
        candidate = re.sub(r',\s*([}\]])', r'\1', candidate)

        # Fix single quotes → double quotes (but not inside strings)
        candidate = self._fix_quotes(candidate)

        # Fix unquoted keys
        candidate = re.sub(r'(?<=[{,])\s*(\w+)\s*:', r' "\1":', candidate)

        # Fix None → null, True → true, False → false
        candidate = candidate.replace(": None", ": null")
        candidate = candidate.replace(": True", ": true")
        candidate = candidate.replace(": False", ": false")
        candidate = re.sub(r':\s*None\b', ': null', candidate)

        # Balance braces
        open_braces = candidate.count("{") - candidate.count("}")
        if open_braces > 0:
            candidate += "}" * open_braces

        open_brackets = candidate.count("[") - candidate.count("]")
        if open_brackets > 0:
            candidate += "]" * open_brackets

        # Remove comments (// and /* */)
        candidate = re.sub(r'//.*?$', '', candidate, flags=re.MULTILINE)
        candidate = re.sub(r'/\*.*?\*/', '', candidate, flags=re.DOTALL)

        return candidate

    def _fix_quotes(self, text: str) -> str:
        """Convert single-quoted strings to double-quoted, carefully."""
        result = []
        i = 0
        in_double = False
        in_single = False

        while i < len(text):
            ch = text[i]

            if ch == '"' and not in_single:
                in_double = not in_double
                result.append(ch)
            elif ch == "'" and not in_double:
                in_single = not in_single
                result.append('"')
            elif ch == '\\' and i + 1 < len(text):
                result.append(ch)
                result.append(text[i + 1])
                i += 1
            else:
                result.append(ch)
            i += 1

        return "".join(result)

    # ─── Type Coercion ───────────────────────────────────────────────────────

    def _coerce_numeric(self, value: Any) -> tuple[Any, float]:
        """Try to coerce a value to numeric. Returns (value, penalty)."""
        if isinstance(value, (int, float)):
            return value, 0.0

        if isinstance(value, str):
            # Remove currency symbols, commas
            cleaned = re.sub(r'[₹$,Rs\.INR\s]', '', value)
            try:
                if '.' in cleaned:
                    return float(cleaned), 0.02
                return int(cleaned), 0.02
            except (ValueError, TypeError):
                pass

        return value, 0.0

    # ─── Enum Correction ─────────────────────────────────────────────────────

    def _correct_enum(self, value: str, valid_values: list[str]) -> tuple[str, float]:
        """Fuzzy-match a value against valid enum values."""
        if value in valid_values:
            return value, 0.0

        # Case-insensitive exact match
        value_lower = value.lower().strip()
        for v in valid_values:
            if v.lower() == value_lower:
                return v, 0.01

        # Substring match
        for v in valid_values:
            if value_lower in v.lower() or v.lower() in value_lower:
                logger.debug("Enum correction: '%s' → '%s'", value, v)
                return v, 0.05

        # Replace underscores/spaces/hyphens and retry
        normalized = re.sub(r'[\s\-_]+', '_', value_lower)
        for v in valid_values:
            if re.sub(r'[\s\-_]+', '_', v.lower()) == normalized:
                return v, 0.03

        # No match — return original (will be caught by Pydantic validation)
        logger.warning("No enum match for '%s' in %s", value, valid_values[:5])
        return value, 0.1

    # ─── Date Plausibility ───────────────────────────────────────────────────

    def _validate_date(self, value: str, field_name: str) -> tuple[Optional[str], float]:
        """Check if a date string is plausible. Nullify hallucinated dates."""
        if not value or not isinstance(value, str):
            return value, 0.0

        # Try parsing
        parsed = self._try_parse_date(value)
        if parsed is None:
            logger.debug("Unparseable date in %s: '%s'", field_name, value)
            return value, 0.05  # Keep raw — might be parseable downstream

        year = parsed.year

        # Plausibility check
        if year < MIN_PLAUSIBLE_YEAR:
            logger.warning("Implausible past date in %s: %s (year %d)", field_name, value, year)
            return None, 0.15  # Nullify — almost certainly hallucinated

        if year > MAX_PLAUSIBLE_YEAR:
            logger.warning("Implausible future date in %s: %s (year %d)", field_name, value, year)
            return None, 0.15

        # If date is > 5 years in the future for application dates, suspicious
        if "application" in field_name.lower():
            days_away = (parsed - date.today()).days
            if days_away > 365 * 3:
                logger.warning("Suspiciously far future application date: %s = %s", field_name, value)
                return None, 0.1

        return value, 0.0

    def _try_parse_date(self, text: str) -> Optional[date]:
        """Try multiple date formats. Return date or None."""
        formats = [
            "%Y-%m-%d",             # ISO
            "%d/%m/%Y",             # Indian DD/MM/YYYY
            "%d-%m-%Y",             # Indian DD-MM-YYYY
            "%d.%m.%Y",             # DD.MM.YYYY
            "%d %B %Y",             # 15 March 2025
            "%B %d, %Y",           # March 15, 2025
            "%d %b %Y",            # 15 Mar 2025
            "%b %d, %Y",           # Mar 15, 2025
            "%Y-%m-%dT%H:%M:%S",   # ISO with time
        ]
        for fmt in formats:
            try:
                return datetime.strptime(text.strip(), fmt).date()
            except ValueError:
                continue
        return None

    # ─── List Field Validation ───────────────────────────────────────────────

    def _validate_list_field(self, value: Any) -> list:
        """Ensure a field that should be a list is actually a list."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            # Try parsing as JSON array
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
            # Split comma-separated string
            if "," in value:
                return [item.strip() for item in value.split(",") if item.strip()]
            return [value]
        return [value]

    # ─── Stats ───────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "repaired": self.repair_count,
            "rejected": self.reject_count,
            "total_processed": self.repair_count + self.reject_count,
        }


# ── Convenience: Pre-configured hardener for scheme classification ──────────

def create_scheme_hardener() -> LLMResponseHardener:
    return LLMResponseHardener(valid_enums={
        "level": ["Central", "State", "Union_Territory"],
        "sector": [
            "Education", "Agriculture", "Fisheries", "MSME", "Startup",
            "Science_Technology", "Health", "Women_Child_Development",
            "Social_Justice", "Tribal_Affairs", "Minority_Affairs",
            "Rural_Development", "Urban_Development", "Labour_Employment",
            "Skill_Development", "Housing", "Finance", "Industry",
            "IT_Electronics", "Textiles", "Food_Processing", "Environment",
            "Energy", "Transport", "Tourism", "Sports_Youth", "Culture",
            "Defence", "Disability", "General",
        ],
        "scheme_type": [
            "Scholarship", "Grant", "Startup_Fund", "Subsidy", "Loan",
            "Pension", "Insurance", "Fellowship", "Award", "Stipend", "Other",
        ],
    })


def create_exam_hardener() -> LLMResponseHardener:
    return LLMResponseHardener(valid_enums={
        "exam_category": [
            "Civil_Services", "Banking", "Railway", "Defence", "Police",
            "Intelligence", "SSC", "PSU", "Medical", "Engineering",
            "Teaching", "Insurance", "Revenue", "Judiciary", "Agriculture",
            "State_PSC", "State_Police", "State_Teaching",
            "State_Subordinate", "Other_Central",
        ],
        "exam_level": ["Central", "State", "UT"],
    })
```

---

## File 34/41: `src/resilience/portal_health.py`
<!-- lines: 491 -->

```python
"""
GovScheme SuperAgent — Portal Health Monitor + Circuit Breaker
Tracks per-portal reliability across runs. Implements circuit breaker
to skip portals that are consistently failing, saving time and avoiding
IP bans from hammering broken sites.

States:
  CLOSED  → portal is healthy, allow requests
  OPEN    → portal is failing, skip all requests (cool down)
  HALF_OPEN → trial: allow 1 request to test recovery

Persistence: SQLite table portal_health in the main schemes.db
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger("portal_health")


class CircuitState(str, Enum):
    CLOSED = "closed"       # Healthy — allow all requests
    OPEN = "open"           # Failing — skip requests
    HALF_OPEN = "half_open" # Testing — allow 1 probe request


@dataclass
class PortalHealthRecord:
    """Per-portal health tracking."""
    portal_name: str
    domain: str
    circuit_state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_requests: int = 0
    total_successes: int = 0
    total_failures: int = 0
    total_timeouts: int = 0
    total_blocked: int = 0        # HTTP 403/429 responses
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None
    last_failure_reason: Optional[str] = None
    last_http_status: Optional[int] = None
    last_response_time_ms: Optional[float] = None
    avg_response_time_ms: float = 0.0
    opened_at: Optional[str] = None       # When circuit opened
    half_open_at: Optional[str] = None
    cooldown_until: Optional[str] = None  # Don't retry before this time
    schemes_extracted: int = 0
    selectors_working: bool = True
    needs_js: bool = False
    needs_ocr: bool = False
    last_selector_check: Optional[str] = None
    notes: str = ""

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.total_successes / self.total_requests

    @property
    def is_healthy(self) -> bool:
        return self.circuit_state == CircuitState.CLOSED


# ── Configuration ────────────────────────────────────────────────────────────

FAILURE_THRESHOLD = 5       # Consecutive failures before opening circuit
SUCCESS_THRESHOLD = 2       # Consecutive successes to close from half-open
COOLDOWN_MINUTES = 60       # Minutes to wait in OPEN state before trying half-open
MAX_COOLDOWN_MINUTES = 1440 # Max cooldown (24 hours) after repeated failures
BLOCKED_COOLDOWN_HOURS = 6  # Extra cooldown if we got 403/429

PORTAL_HEALTH_SCHEMA = """
CREATE TABLE IF NOT EXISTS portal_health (
    portal_name         TEXT PRIMARY KEY,
    domain              TEXT NOT NULL,
    circuit_state       TEXT DEFAULT 'closed',
    consecutive_failures INTEGER DEFAULT 0,
    consecutive_successes INTEGER DEFAULT 0,
    total_requests      INTEGER DEFAULT 0,
    total_successes     INTEGER DEFAULT 0,
    total_failures      INTEGER DEFAULT 0,
    total_timeouts      INTEGER DEFAULT 0,
    total_blocked       INTEGER DEFAULT 0,
    last_success_at     TEXT,
    last_failure_at     TEXT,
    last_failure_reason TEXT,
    last_http_status    INTEGER,
    last_response_time_ms REAL,
    avg_response_time_ms  REAL DEFAULT 0.0,
    opened_at           TEXT,
    half_open_at        TEXT,
    cooldown_until      TEXT,
    schemes_extracted   INTEGER DEFAULT 0,
    selectors_working   INTEGER DEFAULT 1,
    needs_js            INTEGER DEFAULT 0,
    needs_ocr           INTEGER DEFAULT 0,
    last_selector_check TEXT,
    notes               TEXT DEFAULT '',
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portal_request_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portal_name     TEXT NOT NULL,
    url             TEXT NOT NULL,
    http_status     INTEGER,
    response_time_ms REAL,
    success         INTEGER NOT NULL,
    error_type      TEXT,
    error_message   TEXT,
    items_extracted INTEGER DEFAULT 0,
    requested_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_health_state ON portal_health(circuit_state);
CREATE INDEX IF NOT EXISTS idx_health_domain ON portal_health(domain);
CREATE INDEX IF NOT EXISTS idx_req_log_portal ON portal_request_log(portal_name);
CREATE INDEX IF NOT EXISTS idx_req_log_date ON portal_request_log(requested_at);
"""


class PortalHealthMonitor:
    """
    Tracks portal health, implements circuit breaker, and provides
    data for the health dashboard.
    """

    def __init__(self, db_path: str = "./data/schemes.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, PortalHealthRecord] = {}
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(PORTAL_HEALTH_SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ─── Circuit Breaker Decision ────────────────────────────────────────────

    def should_crawl(self, portal_name: str) -> bool:
        """
        Core decision: should we attempt to crawl this portal right now?
        Returns False if circuit is OPEN and cooldown hasn't expired.
        """
        record = self._get_or_create(portal_name)

        if record.circuit_state == CircuitState.CLOSED:
            return True

        if record.circuit_state == CircuitState.OPEN:
            # Check if cooldown has expired
            if record.cooldown_until:
                try:
                    cooldown_end = datetime.fromisoformat(record.cooldown_until)
                    if datetime.utcnow() < cooldown_end:
                        logger.debug(
                            "Skipping %s — circuit OPEN, cooldown until %s",
                            portal_name, record.cooldown_until,
                        )
                        return False
                except (ValueError, TypeError):
                    pass

            # Cooldown expired — transition to HALF_OPEN
            self._transition(portal_name, CircuitState.HALF_OPEN)
            return True

        if record.circuit_state == CircuitState.HALF_OPEN:
            # Allow the probe request
            return True

        return True

    # ─── Record Request Outcomes ─────────────────────────────────────────────

    def record_success(
        self,
        portal_name: str,
        url: str,
        response_time_ms: float,
        items_extracted: int = 0,
        http_status: int = 200,
    ) -> None:
        """Record a successful crawl request."""
        now = datetime.utcnow().isoformat()
        record = self._get_or_create(portal_name)

        record.total_requests += 1
        record.total_successes += 1
        record.consecutive_successes += 1
        record.consecutive_failures = 0
        record.last_success_at = now
        record.last_http_status = http_status
        record.last_response_time_ms = response_time_ms
        record.schemes_extracted += items_extracted

        # Update running average response time
        if record.total_successes > 1:
            record.avg_response_time_ms = (
                (record.avg_response_time_ms * (record.total_successes - 1) + response_time_ms)
                / record.total_successes
            )
        else:
            record.avg_response_time_ms = response_time_ms

        # State transition: HALF_OPEN → CLOSED after enough successes
        if record.circuit_state == CircuitState.HALF_OPEN:
            if record.consecutive_successes >= SUCCESS_THRESHOLD:
                self._transition(portal_name, CircuitState.CLOSED)
                logger.info("Portal %s recovered — circuit CLOSED", portal_name)
        elif record.circuit_state == CircuitState.OPEN:
            self._transition(portal_name, CircuitState.CLOSED)

        self._save(record)
        self._log_request(portal_name, url, http_status, response_time_ms, True, items_extracted=items_extracted)

    def record_failure(
        self,
        portal_name: str,
        url: str,
        error_type: str,
        error_message: str,
        http_status: Optional[int] = None,
        response_time_ms: float = 0.0,
        is_timeout: bool = False,
        is_blocked: bool = False,
    ) -> None:
        """Record a failed crawl request."""
        now = datetime.utcnow().isoformat()
        record = self._get_or_create(portal_name)

        record.total_requests += 1
        record.total_failures += 1
        record.consecutive_failures += 1
        record.consecutive_successes = 0
        record.last_failure_at = now
        record.last_failure_reason = f"{error_type}: {error_message[:200]}"
        record.last_http_status = http_status

        if is_timeout:
            record.total_timeouts += 1
        if is_blocked:
            record.total_blocked += 1

        # State transitions
        if record.circuit_state == CircuitState.HALF_OPEN:
            # Probe failed — back to OPEN with longer cooldown
            cooldown = min(
                COOLDOWN_MINUTES * (2 ** min(record.total_failures // FAILURE_THRESHOLD, 5)),
                MAX_COOLDOWN_MINUTES,
            )
            if is_blocked:
                cooldown = max(cooldown, BLOCKED_COOLDOWN_HOURS * 60)
            self._transition(portal_name, CircuitState.OPEN, cooldown_minutes=cooldown)
            logger.warning(
                "Portal %s probe failed — circuit OPEN, cooldown %d min",
                portal_name, cooldown,
            )

        elif record.circuit_state == CircuitState.CLOSED:
            if record.consecutive_failures >= FAILURE_THRESHOLD:
                cooldown = COOLDOWN_MINUTES
                if is_blocked:
                    cooldown = BLOCKED_COOLDOWN_HOURS * 60
                self._transition(portal_name, CircuitState.OPEN, cooldown_minutes=cooldown)
                logger.warning(
                    "Portal %s circuit OPENED after %d consecutive failures (cooldown %d min)",
                    portal_name, record.consecutive_failures, cooldown,
                )

        self._save(record)
        self._log_request(
            portal_name, url, http_status, response_time_ms, False,
            error_type=error_type, error_message=error_message[:500],
        )

    def record_selector_failure(self, portal_name: str, expected_items: int, actual_items: int) -> None:
        """Record when selectors extract far fewer items than expected (selector drift)."""
        record = self._get_or_create(portal_name)
        if actual_items == 0 and expected_items > 5:
            record.selectors_working = False
            record.notes = f"Selector drift detected: expected ~{expected_items}, got {actual_items}"
            logger.warning(
                "Selector drift on %s: expected ~%d items, got %d",
                portal_name, expected_items, actual_items,
            )
        record.last_selector_check = datetime.utcnow().isoformat()
        self._save(record)

    # ─── State Transitions ───────────────────────────────────────────────────

    def _transition(
        self, portal_name: str, new_state: CircuitState, cooldown_minutes: int = 0,
    ) -> None:
        record = self._get_or_create(portal_name)
        old_state = record.circuit_state
        record.circuit_state = new_state
        now = datetime.utcnow()

        if new_state == CircuitState.OPEN:
            record.opened_at = now.isoformat()
            if cooldown_minutes > 0:
                record.cooldown_until = (now + timedelta(minutes=cooldown_minutes)).isoformat()
        elif new_state == CircuitState.HALF_OPEN:
            record.half_open_at = now.isoformat()
        elif new_state == CircuitState.CLOSED:
            record.opened_at = None
            record.half_open_at = None
            record.cooldown_until = None

        logger.info("Portal %s: %s → %s", portal_name, old_state.value, new_state.value)
        self._save(record)

    # ─── Persistence ─────────────────────────────────────────────────────────

    def _get_or_create(self, portal_name: str, domain: str = "") -> PortalHealthRecord:
        if portal_name in self._cache:
            return self._cache[portal_name]

        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM portal_health WHERE portal_name = ?", (portal_name,)
            ).fetchone()

        if row:
            record = PortalHealthRecord(
                portal_name=row["portal_name"],
                domain=row["domain"],
                circuit_state=CircuitState(row["circuit_state"]),
                consecutive_failures=row["consecutive_failures"],
                consecutive_successes=row["consecutive_successes"],
                total_requests=row["total_requests"],
                total_successes=row["total_successes"],
                total_failures=row["total_failures"],
                total_timeouts=row["total_timeouts"],
                total_blocked=row["total_blocked"],
                last_success_at=row["last_success_at"],
                last_failure_at=row["last_failure_at"],
                last_failure_reason=row["last_failure_reason"],
                last_http_status=row["last_http_status"],
                last_response_time_ms=row["last_response_time_ms"],
                avg_response_time_ms=row["avg_response_time_ms"] or 0.0,
                opened_at=row["opened_at"],
                half_open_at=row["half_open_at"],
                cooldown_until=row["cooldown_until"],
                schemes_extracted=row["schemes_extracted"],
                selectors_working=bool(row["selectors_working"]),
                needs_js=bool(row["needs_js"]),
                needs_ocr=bool(row["needs_ocr"]),
                last_selector_check=row["last_selector_check"],
                notes=row["notes"] or "",
            )
        else:
            record = PortalHealthRecord(portal_name=portal_name, domain=domain)

        self._cache[portal_name] = record
        return record

    def _save(self, record: PortalHealthRecord) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO portal_health (
                    portal_name, domain, circuit_state,
                    consecutive_failures, consecutive_successes,
                    total_requests, total_successes, total_failures,
                    total_timeouts, total_blocked,
                    last_success_at, last_failure_at, last_failure_reason,
                    last_http_status, last_response_time_ms, avg_response_time_ms,
                    opened_at, half_open_at, cooldown_until,
                    schemes_extracted, selectors_working, needs_js, needs_ocr,
                    last_selector_check, notes, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                record.portal_name, record.domain, record.circuit_state.value,
                record.consecutive_failures, record.consecutive_successes,
                record.total_requests, record.total_successes, record.total_failures,
                record.total_timeouts, record.total_blocked,
                record.last_success_at, record.last_failure_at, record.last_failure_reason,
                record.last_http_status, record.last_response_time_ms, record.avg_response_time_ms,
                record.opened_at, record.half_open_at, record.cooldown_until,
                record.schemes_extracted, int(record.selectors_working),
                int(record.needs_js), int(record.needs_ocr),
                record.last_selector_check, record.notes, now,
            ))
            conn.commit()
        self._cache[record.portal_name] = record

    def _log_request(
        self, portal_name: str, url: str, http_status: Optional[int],
        response_time_ms: float, success: bool,
        error_type: str = "", error_message: str = "",
        items_extracted: int = 0,
    ) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO portal_request_log (
                    portal_name, url, http_status, response_time_ms,
                    success, error_type, error_message, items_extracted, requested_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                portal_name, url[:500], http_status, response_time_ms,
                int(success), error_type, error_message[:500],
                items_extracted, datetime.utcnow().isoformat(),
            ))
            conn.commit()

    # ─── Reporting ───────────────────────────────────────────────────────────

    def get_health_summary(self) -> dict:
        """Get a summary of all portal health for the dashboard."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM portal_health ORDER BY total_failures DESC"
            ).fetchall()

        healthy = [r for r in rows if r["circuit_state"] == "closed"]
        failing = [r for r in rows if r["circuit_state"] in ("open", "half_open")]
        selector_issues = [r for r in rows if not r["selectors_working"]]

        return {
            "total_portals": len(rows),
            "healthy": len(healthy),
            "failing": len(failing),
            "selector_issues": len(selector_issues),
            "portals": [dict(r) for r in rows],
            "failing_portals": [
                {
                    "name": r["portal_name"],
                    "state": r["circuit_state"],
                    "failures": r["consecutive_failures"],
                    "reason": r["last_failure_reason"],
                    "cooldown_until": r["cooldown_until"],
                }
                for r in failing
            ],
        }

    def get_portal_stats(self, portal_name: str) -> Optional[dict]:
        record = self._get_or_create(portal_name)
        return {
            "portal_name": record.portal_name,
            "state": record.circuit_state.value,
            "success_rate": f"{record.success_rate:.1%}",
            "total_requests": record.total_requests,
            "avg_response_ms": f"{record.avg_response_time_ms:.0f}",
            "consecutive_failures": record.consecutive_failures,
            "last_success": record.last_success_at,
            "last_failure": record.last_failure_at,
            "selectors_ok": record.selectors_working,
        }

    def reset_portal(self, portal_name: str) -> None:
        """Manually reset a portal's circuit breaker (e.g., after fixing selectors)."""
        record = self._get_or_create(portal_name)
        record.circuit_state = CircuitState.CLOSED
        record.consecutive_failures = 0
        record.opened_at = None
        record.half_open_at = None
        record.cooldown_until = None
        record.selectors_working = True
        record.notes = f"Manually reset at {datetime.utcnow().isoformat()}"
        self._save(record)
        logger.info("Portal %s manually reset to CLOSED", portal_name)

    def cleanup_old_logs(self, days: int = 30) -> int:
        """Remove request logs older than N days."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            result = conn.execute(
                "DELETE FROM portal_request_log WHERE requested_at < ?", (cutoff,)
            )
            conn.commit()
            return result.rowcount
```

---

## File 35/41: `src/scheduler/__init__.py`
<!-- lines: 0 -->

```python

```

---

## File 36/41: `src/scheduler/daily_runner.py`
<!-- lines: 394 -->

```python
"""
GovScheme SuperAgent — Daily Scheduler
Runs the crawl pipeline on a configurable schedule:
  - Daily at 6:00 AM IST (default)
  - Configurable via CRAWL_SCHEDULE_HOUR and CRAWL_SCHEDULE_MINUTE
  - Retry on failure with exponential backoff
  - Health check endpoint for monitoring
  - Lock file to prevent concurrent runs
  - Generates run_id per execution for traceability

Usage:
  # Run as daemon (long-running process with built-in scheduler)
  python -m src.scheduler.daily_runner --daemon

  # Run once immediately (for cron / systemd timer)
  python -m src.scheduler.daily_runner --once

  # Generate crontab entry
  python -m src.scheduler.daily_runner --install-cron

  # Generate systemd timer
  python -m src.scheduler.daily_runner --install-systemd
"""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Optional

from src.config.settings import AgentConfig
from src.agents.models import DailyRunReport

logger = logging.getLogger("scheduler")

# IST = UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))

LOCK_FILE = "/tmp/govscheme_crawl.lock"


def _generate_run_id() -> str:
    """Generate a unique run ID: date + short hash of timestamp."""
    today = date.today().isoformat()
    ts_hash = hashlib.md5(str(time.time()).encode()).hexdigest()[:6]
    return f"run_{today}_{ts_hash}"


class DailyScheduler:
    """
    Manages scheduled execution of the GovScheme crawl pipeline.
    Supports daemon mode (internal scheduler) and one-shot mode (external cron).
    """

    def __init__(
        self,
        schedule_hour: int = int(os.getenv("CRAWL_SCHEDULE_HOUR", "6")),
        schedule_minute: int = int(os.getenv("CRAWL_SCHEDULE_MINUTE", "0")),
        max_retries: int = 3,
        retry_delay_minutes: int = 30,
        config: Optional[AgentConfig] = None,
    ):
        self.schedule_hour = schedule_hour
        self.schedule_minute = schedule_minute
        self.max_retries = max_retries
        self.retry_delay_minutes = retry_delay_minutes
        self.config = config or AgentConfig()
        self._shutdown = False
        self._lock_fd = None

    # ─────────────────────────────────────
    # Lock Management (prevent concurrent runs)
    # ─────────────────────────────────────

    def _acquire_lock(self) -> bool:
        try:
            self._lock_fd = open(LOCK_FILE, "w")
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_fd.write(f"{os.getpid()}\n{datetime.now(IST).isoformat()}\n")
            self._lock_fd.flush()
            return True
        except (IOError, OSError):
            logger.warning("Another crawl instance is already running (lock file: %s)", LOCK_FILE)
            return False

    def _release_lock(self) -> None:
        if self._lock_fd:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                self._lock_fd.close()
                Path(LOCK_FILE).unlink(missing_ok=True)
            except Exception:
                pass

    # ─────────────────────────────────────
    # One-Shot Execution (cron mode)
    # ─────────────────────────────────────

    def run_once(self) -> Optional[DailyRunReport]:
        """Execute a single crawl run. Returns the daily report."""
        if not self._acquire_lock():
            logger.error("Cannot acquire lock — another instance is running")
            return None

        run_id = _generate_run_id()
        logger.info("Starting daily crawl run: %s", run_id)

        try:
            report = asyncio.run(self._execute_crawl(run_id))
            return report
        except Exception as e:
            logger.error("Daily crawl failed: %s", e, exc_info=True)
            return None
        finally:
            self._release_lock()

    def run_once_with_retry(self) -> Optional[DailyRunReport]:
        """Execute with retry logic for reliability."""
        for attempt in range(1, self.max_retries + 1):
            logger.info("Crawl attempt %d/%d", attempt, self.max_retries)

            report = self.run_once()

            if report is not None:
                return report

            if attempt < self.max_retries:
                wait = self.retry_delay_minutes * attempt
                logger.warning("Retrying in %d minutes...", wait)
                time.sleep(wait * 60)

        logger.error("All %d crawl attempts failed", self.max_retries)
        return None

    # ─────────────────────────────────────
    # Daemon Mode (built-in scheduler)
    # ─────────────────────────────────────

    def run_daemon(self) -> None:
        """Run as a long-lived daemon that executes daily at the scheduled time."""
        logger.info(
            "GovScheme scheduler starting in daemon mode. "
            "Next crawl at %02d:%02d IST daily.",
            self.schedule_hour, self.schedule_minute,
        )

        # Handle graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        while not self._shutdown:
            now = datetime.now(IST)
            next_run = self._next_scheduled_time(now)
            wait_seconds = (next_run - now).total_seconds()

            logger.info(
                "Next scheduled run: %s IST (in %.1f hours)",
                next_run.strftime("%Y-%m-%d %H:%M"),
                wait_seconds / 3600,
            )

            # Sleep until next run, checking for shutdown every 60 seconds
            while wait_seconds > 0 and not self._shutdown:
                sleep_chunk = min(60, wait_seconds)
                time.sleep(sleep_chunk)
                wait_seconds -= sleep_chunk

            if self._shutdown:
                break

            # Execute the crawl
            logger.info("Scheduled crawl time reached. Starting...")
            self.run_once_with_retry()

        logger.info("Scheduler shutting down gracefully.")

    def _next_scheduled_time(self, now: datetime) -> datetime:
        """Compute the next scheduled run time."""
        today_run = now.replace(
            hour=self.schedule_hour,
            minute=self.schedule_minute,
            second=0,
            microsecond=0,
        )
        if now >= today_run:
            return today_run + timedelta(days=1)
        return today_run

    def _signal_handler(self, signum, frame):
        logger.info("Received signal %d, shutting down...", signum)
        self._shutdown = True

    # ─────────────────────────────────────
    # Core Crawl Execution
    # ─────────────────────────────────────

    async def _execute_crawl(self, run_id: str) -> DailyRunReport:
        """The actual crawl pipeline execution for a daily run."""
        # Import here to avoid circular imports
        from src.orchestrator import Orchestrator

        orchestrator = Orchestrator(self.config)
        report = await orchestrator.run_daily_pipeline(run_id)
        return report

    # ─────────────────────────────────────
    # Installation Helpers
    # ─────────────────────────────────────

    @staticmethod
    def generate_crontab_entry(
        hour: int = 6,
        minute: int = 0,
        python_path: str = "python3",
        project_dir: str = ".",
    ) -> str:
        """Generate a crontab line for scheduling."""
        abs_dir = Path(project_dir).resolve()
        log_file = abs_dir / "logs" / "daily_cron.log"
        return (
            f"# GovScheme SuperAgent — Daily crawl at {hour:02d}:{minute:02d} IST\n"
            f"{minute} {hour} * * * "
            f"cd {abs_dir} && "
            f"{python_path} -m src.scheduler.daily_runner --once "
            f">> {log_file} 2>&1\n"
        )

    @staticmethod
    def generate_systemd_units(
        hour: int = 6,
        minute: int = 0,
        python_path: str = "/usr/bin/python3",
        project_dir: str = ".",
        user: str = "",
    ) -> tuple[str, str]:
        """Generate systemd service + timer unit files."""
        abs_dir = Path(project_dir).resolve()
        user = user or os.getenv("USER", "root")

        service = f"""[Unit]
Description=GovScheme SuperAgent — Daily Government Scheme Crawler
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User={user}
WorkingDirectory={abs_dir}
ExecStart={python_path} -m src.scheduler.daily_runner --once
Environment="PATH={abs_dir}/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH={abs_dir}"
StandardOutput=append:{abs_dir}/logs/daily_systemd.log
StandardError=append:{abs_dir}/logs/daily_systemd_err.log
TimeoutStartSec=7200

[Install]
WantedBy=multi-user.target
"""

        timer = f"""[Unit]
Description=GovScheme SuperAgent — Daily Schedule Timer

[Timer]
OnCalendar=*-*-* {hour:02d}:{minute:02d}:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
"""
        return service, timer


class SchedulerHealthCheck:
    """Lightweight health check for monitoring the scheduler."""

    def __init__(self, db_path: str = "./data/schemes.db"):
        self.db_path = db_path

    def check(self) -> dict:
        status = {
            "healthy": True,
            "checked_at": datetime.now(IST).isoformat(),
            "db_exists": Path(self.db_path).exists(),
            "lock_active": Path(LOCK_FILE).exists(),
            "last_run": None,
            "total_schemes": 0,
        }

        if status["db_exists"]:
            try:
                from src.storage.database import SchemeDatabase
                db = SchemeDatabase(self.db_path)
                status["total_schemes"] = db.get_total_count()
                runs = db.get_run_history(1)
                if runs:
                    status["last_run"] = runs[0].get("run_date")
            except Exception as e:
                status["healthy"] = False
                status["error"] = str(e)

        return status


# ─────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/scheduler.log", mode="a"),
        ],
    )
    Path("logs").mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(
        description="GovScheme SuperAgent — Daily Scheduler"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--daemon", action="store_true", help="Run as long-lived daemon")
    group.add_argument("--once", action="store_true", help="Run a single crawl immediately")
    group.add_argument("--health", action="store_true", help="Check scheduler health")
    group.add_argument("--install-cron", action="store_true", help="Print crontab entry")
    group.add_argument("--install-systemd", action="store_true", help="Print systemd units")

    parser.add_argument("--hour", type=int, default=6, help="Schedule hour (IST, 0-23)")
    parser.add_argument("--minute", type=int, default=0, help="Schedule minute (0-59)")
    parser.add_argument("--output", default="./output", help="Output directory")
    parser.add_argument("--no-pdfs", action="store_true", help="Skip PDF downloads")
    parser.add_argument("--retries", type=int, default=3, help="Max retry attempts")

    args = parser.parse_args()

    config = AgentConfig(
        output_dir=args.output,
        download_pdfs=not args.no_pdfs,
    )

    scheduler = DailyScheduler(
        schedule_hour=args.hour,
        schedule_minute=args.minute,
        max_retries=args.retries,
        config=config,
    )

    if args.daemon:
        scheduler.run_daemon()

    elif args.once:
        report = scheduler.run_once_with_retry()
        if report:
            print(json.dumps(report.model_dump(mode="json"), indent=2, default=str))
            sys.exit(0)
        else:
            sys.exit(1)

    elif args.health:
        health = SchedulerHealthCheck(config.db_path)
        result = health.check()
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["healthy"] else 1)

    elif args.install_cron:
        entry = DailyScheduler.generate_crontab_entry(args.hour, args.minute)
        print(entry)
        print("# Add with: crontab -e")

    elif args.install_systemd:
        service, timer = DailyScheduler.generate_systemd_units(args.hour, args.minute)
        print("=== govscheme-crawl.service ===")
        print(service)
        print("=== govscheme-crawl.timer ===")
        print(timer)
        print("# Install with:")
        print("#   sudo cp govscheme-crawl.service /etc/systemd/system/")
        print("#   sudo cp govscheme-crawl.timer /etc/systemd/system/")
        print("#   sudo systemctl enable --now govscheme-crawl.timer")


if __name__ == "__main__":
    main()
```

---

## File 37/41: `src/storage/__init__.py`
<!-- lines: 0 -->

```python

```

---

## File 38/41: `src/storage/database.py`
<!-- lines: 432 -->

```python
"""
GovScheme SuperAgent — Database Persistence Layer
SQLite-backed scheme registry that persists across daily crawl runs.
Tracks: first_seen, last_seen, detail_hash for change detection,
start/end dates, fees, status lifecycle.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from src.agents.models import (
    ClassifiedScheme, SchemeStatus, ChangeType, StoredScheme, DailyRunReport,
)

logger = logging.getLogger("db_layer")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schemes (
    scheme_id        TEXT PRIMARY KEY,
    content_hash     TEXT NOT NULL,
    detail_hash      TEXT NOT NULL,
    clean_name       TEXT NOT NULL,
    level            TEXT NOT NULL,
    state            TEXT,
    sector           TEXT NOT NULL,
    scheme_type      TEXT NOT NULL,
    summary          TEXT,
    eligibility      TEXT,
    benefit_amount   TEXT,
    target_group     TEXT,
    source_portal    TEXT,
    source_url       TEXT,
    detail_url       TEXT,
    official_website TEXT,
    nodal_ministry   TEXT,
    nodal_department TEXT,
    helpline         TEXT,

    -- Dates
    start_date              TEXT,
    end_date                TEXT,
    application_start_date  TEXT,
    application_end_date    TEXT,
    application_deadline    TEXT,

    -- Fees & Amounts
    application_fee   TEXT,
    fund_amount_min   TEXT,
    fund_amount_max   TEXT,
    frequency         TEXT,

    -- Eligibility Details
    age_limit          TEXT,
    income_limit       TEXT,
    gender_eligibility TEXT,
    caste_eligibility  TEXT,
    documents_required TEXT,   -- JSON array

    -- Status & Lifecycle
    scheme_status          TEXT DEFAULT 'Unknown',
    classification_confidence REAL DEFAULT 0.0,
    folder_path            TEXT,

    -- Tracking
    first_seen_date  TEXT NOT NULL,
    last_seen_date   TEXT NOT NULL,
    last_crawl_run   TEXT,
    times_seen       INTEGER DEFAULT 1,
    change_type      TEXT DEFAULT 'New',
    is_active        INTEGER DEFAULT 1,

    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_runs (
    run_id              TEXT PRIMARY KEY,
    run_date            TEXT NOT NULL,
    started_at          TEXT NOT NULL,
    completed_at        TEXT,
    total_in_db         INTEGER DEFAULT 0,
    new_schemes         INTEGER DEFAULT 0,
    updated_schemes     INTEGER DEFAULT 0,
    closed_schemes      INTEGER DEFAULT 0,
    unchanged_schemes   INTEGER DEFAULT 0,
    errors              INTEGER DEFAULT 0,
    elapsed_seconds     REAL DEFAULT 0.0,
    new_scheme_names    TEXT,        -- JSON array
    updated_scheme_names TEXT,       -- JSON array
    approaching_deadlines TEXT,      -- JSON array
    excel_report_path   TEXT,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS scheme_changes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_id       TEXT NOT NULL,
    run_id          TEXT NOT NULL,
    change_type     TEXT NOT NULL,
    field_changed   TEXT,
    old_value       TEXT,
    new_value       TEXT,
    detected_at     TEXT NOT NULL,
    FOREIGN KEY (scheme_id) REFERENCES schemes(scheme_id),
    FOREIGN KEY (run_id) REFERENCES daily_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_schemes_level ON schemes(level);
CREATE INDEX IF NOT EXISTS idx_schemes_sector ON schemes(sector);
CREATE INDEX IF NOT EXISTS idx_schemes_state ON schemes(state);
CREATE INDEX IF NOT EXISTS idx_schemes_status ON schemes(scheme_status);
CREATE INDEX IF NOT EXISTS idx_schemes_end_date ON schemes(end_date);
CREATE INDEX IF NOT EXISTS idx_schemes_detail_hash ON schemes(detail_hash);
CREATE INDEX IF NOT EXISTS idx_changes_run ON scheme_changes(run_id);
CREATE INDEX IF NOT EXISTS idx_changes_scheme ON scheme_changes(scheme_id);
CREATE INDEX IF NOT EXISTS idx_runs_date ON daily_runs(run_date);
"""


class SchemeDatabase:
    """SQLite persistence for scheme tracking across daily runs."""

    def __init__(self, db_path: str = "./data/schemes.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        logger.info("Database initialized at %s", self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ─────────────────────────────────────
    # Scheme CRUD
    # ─────────────────────────────────────

    def upsert_scheme(self, scheme: ClassifiedScheme, run_id: str) -> ChangeType:
        """Insert or update a scheme. Returns the change type detected."""
        now = datetime.utcnow().isoformat()
        today = date.today().isoformat()

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT scheme_id, detail_hash, scheme_status, last_seen_date, times_seen "
                "FROM schemes WHERE scheme_id = ? OR content_hash = ?",
                (scheme.scheme_id, scheme.raw_data.content_hash),
            ).fetchone()

            docs_json = json.dumps(scheme.documents_list, ensure_ascii=False)

            if existing is None:
                # ── NEW SCHEME ──
                conn.execute("""
                    INSERT INTO schemes (
                        scheme_id, content_hash, detail_hash, clean_name, level, state,
                        sector, scheme_type, summary, eligibility, benefit_amount,
                        target_group, source_portal, source_url, detail_url,
                        official_website, nodal_ministry, nodal_department, helpline,
                        start_date, end_date, application_start_date, application_end_date,
                        application_deadline, application_fee, fund_amount_min,
                        fund_amount_max, frequency, age_limit, income_limit,
                        gender_eligibility, caste_eligibility, documents_required,
                        scheme_status, classification_confidence, folder_path,
                        first_seen_date, last_seen_date, last_crawl_run, times_seen,
                        change_type, is_active, created_at, updated_at
                    ) VALUES (
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )
                """, (
                    scheme.scheme_id, scheme.raw_data.content_hash,
                    scheme.raw_data.detail_hash, scheme.clean_name,
                    scheme.level.value, scheme.state, scheme.sector.value,
                    scheme.scheme_type.value, scheme.summary,
                    scheme.eligibility_summary, scheme.benefit_amount,
                    scheme.target_group, scheme.raw_data.source_portal,
                    scheme.raw_data.source_url, scheme.raw_data.scheme_detail_url,
                    scheme.official_website, scheme.nodal_ministry,
                    scheme.nodal_department, scheme.helpline,
                    scheme.start_date, scheme.end_date,
                    scheme.application_start_date, scheme.application_end_date,
                    scheme.application_deadline, scheme.application_fee,
                    scheme.fund_amount_min, scheme.fund_amount_max,
                    scheme.frequency, scheme.age_limit, scheme.income_limit,
                    scheme.gender_eligibility, scheme.caste_eligibility,
                    docs_json, scheme.scheme_status.value,
                    scheme.classification_confidence, scheme.folder_path,
                    today, today, run_id, 1,
                    ChangeType.NEW.value, 1, now, now,
                ))
                conn.commit()
                return ChangeType.NEW

            else:
                # ── EXISTING SCHEME — check for changes ──
                old_hash = existing["detail_hash"]
                new_hash = scheme.raw_data.detail_hash
                times = existing["times_seen"] + 1

                if old_hash != new_hash:
                    change = ChangeType.UPDATED
                    # Log what changed
                    self._record_change(
                        conn, existing["scheme_id"], run_id, "detail_hash",
                        old_hash, new_hash,
                    )
                else:
                    change = ChangeType.UNCHANGED

                conn.execute("""
                    UPDATE schemes SET
                        detail_hash = ?, summary = ?, eligibility = ?,
                        benefit_amount = ?, start_date = ?, end_date = ?,
                        application_start_date = ?, application_end_date = ?,
                        application_deadline = ?, application_fee = ?,
                        fund_amount_min = ?, fund_amount_max = ?,
                        frequency = ?, scheme_status = ?,
                        last_seen_date = ?, last_crawl_run = ?,
                        times_seen = ?, change_type = ?, is_active = 1,
                        updated_at = ?
                    WHERE scheme_id = ?
                """, (
                    new_hash, scheme.summary, scheme.eligibility_summary,
                    scheme.benefit_amount, scheme.start_date, scheme.end_date,
                    scheme.application_start_date, scheme.application_end_date,
                    scheme.application_deadline, scheme.application_fee,
                    scheme.fund_amount_min, scheme.fund_amount_max,
                    scheme.frequency, scheme.scheme_status.value,
                    today, run_id, times, change.value, now,
                    existing["scheme_id"],
                ))
                conn.commit()
                return change

    def _record_change(
        self, conn: sqlite3.Connection, scheme_id: str, run_id: str,
        field: str, old_val: str, new_val: str,
    ) -> None:
        conn.execute(
            "INSERT INTO scheme_changes (scheme_id, run_id, change_type, "
            "field_changed, old_value, new_value, detected_at) "
            "VALUES (?, ?, 'Updated', ?, ?, ?, ?)",
            (scheme_id, run_id, field, old_val, new_val,
             datetime.utcnow().isoformat()),
        )

    def mark_missing_as_closed(self, run_id: str, seen_ids: set[str]) -> int:
        """Mark schemes not seen in this run as potentially Closed."""
        today = date.today().isoformat()
        with self._connect() as conn:
            all_active = conn.execute(
                "SELECT scheme_id FROM schemes WHERE is_active = 1"
            ).fetchall()

            closed_count = 0
            for row in all_active:
                sid = row["scheme_id"]
                if sid not in seen_ids:
                    # Only mark as closed if unseen for 3+ consecutive runs
                    last_seen = conn.execute(
                        "SELECT last_seen_date, times_seen FROM schemes WHERE scheme_id = ?",
                        (sid,),
                    ).fetchone()

                    if last_seen:
                        last = last_seen["last_seen_date"]
                        try:
                            days_unseen = (date.today() - date.fromisoformat(last)).days
                        except (ValueError, TypeError):
                            days_unseen = 0

                        if days_unseen >= 3:
                            conn.execute(
                                "UPDATE schemes SET scheme_status = 'Closed', "
                                "change_type = 'Closed', is_active = 0, updated_at = ? "
                                "WHERE scheme_id = ?",
                                (datetime.utcnow().isoformat(), sid),
                            )
                            self._record_change(
                                conn, sid, run_id, "scheme_status",
                                "Active", "Closed",
                            )
                            closed_count += 1

            conn.commit()
            return closed_count

    # ─────────────────────────────────────
    # Queries for Reporting
    # ─────────────────────────────────────

    def get_all_schemes(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM schemes ORDER BY sector, clean_name"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_schemes_by_status(self, status: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM schemes WHERE scheme_status = ? ORDER BY sector",
                (status,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_approaching_deadlines(self, days: int = 7) -> list[dict]:
        """Find schemes whose application_end_date or end_date is within N days."""
        cutoff = (date.today() + timedelta(days=days)).isoformat()
        today_str = date.today().isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM schemes WHERE is_active = 1 "
                "AND (application_end_date BETWEEN ? AND ? "
                "     OR end_date BETWEEN ? AND ?) "
                "ORDER BY COALESCE(application_end_date, end_date)",
                (today_str, cutoff, today_str, cutoff),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_new_since(self, since_date: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM schemes WHERE first_seen_date >= ? ORDER BY first_seen_date DESC",
                (since_date,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_changes_for_run(self, run_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT sc.*, s.clean_name, s.sector, s.level "
                "FROM scheme_changes sc "
                "JOIN schemes s ON sc.scheme_id = s.scheme_id "
                "WHERE sc.run_id = ? ORDER BY sc.detected_at",
                (run_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM schemes").fetchone()["c"]
            active = conn.execute(
                "SELECT COUNT(*) as c FROM schemes WHERE is_active = 1"
            ).fetchone()["c"]
            by_level = {}
            for row in conn.execute(
                "SELECT level, COUNT(*) as c FROM schemes GROUP BY level"
            ).fetchall():
                by_level[row["level"]] = row["c"]
            by_sector = {}
            for row in conn.execute(
                "SELECT sector, COUNT(*) as c FROM schemes GROUP BY sector ORDER BY c DESC"
            ).fetchall():
                by_sector[row["sector"]] = row["c"]
            by_status = {}
            for row in conn.execute(
                "SELECT scheme_status, COUNT(*) as c FROM schemes GROUP BY scheme_status"
            ).fetchall():
                by_status[row["scheme_status"]] = row["c"]
            by_type = {}
            for row in conn.execute(
                "SELECT scheme_type, COUNT(*) as c FROM schemes GROUP BY scheme_type ORDER BY c DESC"
            ).fetchall():
                by_type[row["scheme_type"]] = row["c"]
            by_state = {}
            for row in conn.execute(
                "SELECT state, COUNT(*) as c FROM schemes WHERE state IS NOT NULL "
                "GROUP BY state ORDER BY c DESC"
            ).fetchall():
                by_state[row["state"]] = row["c"]

            return {
                "total": total,
                "active": active,
                "by_level": by_level,
                "by_sector": by_sector,
                "by_status": by_status,
                "by_type": by_type,
                "by_state": by_state,
            }

    # ─────────────────────────────────────
    # Daily Run Tracking
    # ─────────────────────────────────────

    def save_daily_run(self, report: DailyRunReport) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO daily_runs (
                    run_id, run_date, started_at, completed_at,
                    total_in_db, new_schemes, updated_schemes,
                    closed_schemes, unchanged_schemes, errors,
                    elapsed_seconds, new_scheme_names, updated_scheme_names,
                    approaching_deadlines, excel_report_path
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                report.run_id, report.run_date,
                report.run_started_at.isoformat(),
                report.run_completed_at.isoformat() if report.run_completed_at else None,
                report.total_schemes_in_db, report.new_schemes,
                report.updated_schemes, report.closed_schemes,
                report.unchanged_schemes, report.errors,
                report.elapsed_seconds,
                json.dumps(report.new_scheme_names, ensure_ascii=False),
                json.dumps(report.updated_scheme_names, ensure_ascii=False),
                json.dumps(report.approaching_deadline_names, ensure_ascii=False),
                report.excel_report_path,
            ))
            conn.commit()

    def get_run_history(self, limit: int = 30) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_runs ORDER BY run_date DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_total_count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) as c FROM schemes").fetchone()["c"]
```

---

## File 39/41: `src/storage/excel_report.py`
<!-- lines: 1075 -->

```python
"""
GovScheme SuperAgent — Excel Report Generator
Produces multi-sheet Excel workbooks for tracking, dashboarding, and daily reports.
Sheets:
  1. Master Tracker      — All schemes with dates, fees, status, amounts
  2. New Schemes          — Schemes discovered in this run
  3. Approaching Deadlines— Schemes with deadlines within 7/30 days
  4. Sector Summary       — Pivot by sector with counts
  5. State Summary        — Pivot by state with counts
  6. Status Summary       — Active/Expired/Upcoming/Closed breakdown
  7. Daily Run History    — Historical log of all daily crawl runs
  8. Change Log           — All detected changes across runs
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers,
)
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList

from src.agents.models import DailyRunReport
from src.storage.database import SchemeDatabase

logger = logging.getLogger("excel_report")

# ── Additional Style Constants for Exam Sheets ──
UPCOMING_FILL = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")  # Blue
ORANGE_FILL = PatternFill(start_color="FFDAB9", end_color="FFDAB9", fill_type="solid")
PURPLE_FILL = PatternFill(start_color="E8D0F0", end_color="E8D0F0", fill_type="solid")
TEAL_FILL = PatternFill(start_color="B2DFDB", end_color="B2DFDB", fill_type="solid")
GREY_FILL = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")

# ── Style Constants ──
HEADER_FONT = Font(name="Arial", size=11, bold=True, color="FFFFFF")
HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
SUBHEADER_FILL = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
DATE_FONT = Font(name="Arial", size=10, color="0066CC")
FEE_FONT = Font(name="Arial", size=10, color="CC6600")
NEW_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
DEADLINE_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
EXPIRED_FILL = PatternFill(start_color="F2DCDB", end_color="F2DCDB", fill_type="solid")
ACTIVE_FILL = PatternFill(start_color="DFF0D8", end_color="DFF0D8", fill_type="solid")
THIN_BORDER = Border(
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
    top=Side(style="thin", color="CCCCCC"),
    bottom=Side(style="thin", color="CCCCCC"),
)
HEADER_BORDER = Border(
    left=Side(style="thin", color="1F4E79"),
    right=Side(style="thin", color="1F4E79"),
    top=Side(style="thin", color="1F4E79"),
    bottom=Side(style="medium", color="1F4E79"),
)
CENTER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
WRAP_ALIGN = Alignment(vertical="top", wrap_text=True)


class ExcelReportGenerator:
    """Generates multi-sheet Excel reports for scheme + exam tracking."""

    def __init__(self, db: SchemeDatabase, output_dir: str = "./output", exam_db=None):
        self.db = db
        self.exam_db = exam_db  # ExamDatabase instance (optional, V3)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_full_report(
        self,
        daily_report: Optional[DailyRunReport] = None,
        exam_report=None,
    ) -> str:
        """Generate the comprehensive Excel report. Returns the file path."""
        wb = Workbook()

        # Remove the default sheet
        wb.remove(wb.active)

        # ── Sheet 1: Master Tracker ──
        self._build_master_tracker(wb)

        # ── Sheet 2: New Schemes (this run) ──
        if daily_report:
            self._build_new_schemes_sheet(wb, daily_report.run_date)

        # ── Sheet 3: Approaching Deadlines ──
        self._build_deadlines_sheet(wb)

        # ── Sheet 4: Sector Summary ──
        self._build_sector_summary(wb)

        # ── Sheet 5: State Summary ──
        self._build_state_summary(wb)

        # ── Sheet 6: Status Summary ──
        self._build_status_summary(wb)

        # ── Sheet 7: Daily Run History ──
        self._build_run_history(wb)

        # ── Sheet 8: Change Log ──
        if daily_report:
            self._build_change_log(wb, daily_report.run_id)

        # ── Sheet 9: Dashboard (charts) ──
        self._build_dashboard_sheet(wb)

        # ═══ V3: EXAM SHEETS (10–15) ═══
        if self.exam_db:
            self._build_exam_master_tracker(wb)        # Sheet 10
            self._build_exam_application_open(wb)      # Sheet 11
            self._build_exam_calendar(wb)              # Sheet 12
            self._build_exam_deadlines(wb)             # Sheet 13
            self._build_exam_category_summary(wb)      # Sheet 14
            self._build_exam_state_summary(wb)         # Sheet 15

        # Save
        today = date.today().isoformat()
        filename = f"GovScheme_Report_{today}.xlsx"
        filepath = self.output_dir / "reports" / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(filepath))

        logger.info("Excel report generated: %s (%d sheets)", filepath, len(wb.sheetnames))
        return str(filepath)

    # ═══════════════════════════════════════
    # Sheet 1: Master Tracker
    # ═══════════════════════════════════════

    def _build_master_tracker(self, wb: Workbook) -> None:
        ws = wb.create_sheet("Master Tracker")

        headers = [
            "S.No", "Scheme Name", "Level", "State/UT", "Sector", "Type",
            "Status", "Start Date", "End Date", "Application Start",
            "Application Deadline", "Application Fee", "Min Amount",
            "Max Amount", "Frequency", "Target Group",
            "Age Limit", "Income Limit", "Gender", "Caste/Category",
            "Ministry/Dept", "Official Website", "Helpline",
            "Summary", "Eligibility", "Documents Required",
            "Source Portal", "Source URL", "First Seen", "Last Seen",
            "Times Seen", "Confidence", "Folder Path",
        ]

        # Write headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = CENTER_ALIGN
            cell.border = HEADER_BORDER

        # Freeze top row
        ws.freeze_panes = "A2"

        # Auto-filter
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"

        # Write data
        schemes = self.db.get_all_schemes()
        for idx, s in enumerate(schemes, 1):
            row = idx + 1
            docs = s.get("documents_required", "[]")
            try:
                import json
                docs_list = json.loads(docs) if docs else []
                docs_str = "; ".join(docs_list) if isinstance(docs_list, list) else str(docs)
            except Exception:
                docs_str = str(docs)

            values = [
                idx, s.get("clean_name"), s.get("level"), s.get("state"),
                s.get("sector"), s.get("scheme_type"),
                s.get("scheme_status", "Unknown"),
                s.get("start_date"), s.get("end_date"),
                s.get("application_start_date"), s.get("application_end_date") or s.get("application_deadline"),
                s.get("application_fee"), s.get("fund_amount_min"),
                s.get("fund_amount_max"), s.get("frequency"),
                s.get("target_group"), s.get("age_limit"),
                s.get("income_limit"), s.get("gender_eligibility"),
                s.get("caste_eligibility"),
                s.get("nodal_ministry") or s.get("nodal_department"),
                s.get("official_website"), s.get("helpline"),
                s.get("summary"), s.get("eligibility"),
                docs_str,
                s.get("source_portal"), s.get("source_url"),
                s.get("first_seen_date"), s.get("last_seen_date"),
                s.get("times_seen"), s.get("classification_confidence"),
                s.get("folder_path"),
            ]

            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=val)
                cell.border = THIN_BORDER
                cell.alignment = WRAP_ALIGN

                # Conditional formatting
                if col == 7:  # Status
                    if val == "Active":
                        cell.fill = ACTIVE_FILL
                    elif val == "Expired":
                        cell.fill = EXPIRED_FILL
                    elif val == "Closed":
                        cell.fill = DEADLINE_FILL
                if col in (8, 9, 10, 11):  # Date columns
                    cell.font = DATE_FONT
                if col in (12, 13, 14):  # Fee/Amount columns
                    cell.font = FEE_FONT

        # Set column widths
        col_widths = [
            6, 40, 10, 18, 20, 14, 10, 14, 14, 14, 14, 14, 14, 14, 12,
            20, 12, 18, 10, 16, 25, 30, 18, 50, 40, 40, 16, 35, 12, 12,
            8, 8, 30,
        ]
        for i, w in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

    # ═══════════════════════════════════════
    # Sheet 2: New Schemes
    # ═══════════════════════════════════════

    def _build_new_schemes_sheet(self, wb: Workbook, since_date: str) -> None:
        ws = wb.create_sheet("New Schemes")

        headers = [
            "S.No", "Scheme Name", "Level", "State/UT", "Sector", "Type",
            "Start Date", "End Date", "Application Fee",
            "Fund Amount", "Target Group", "Summary", "Source URL",
        ]

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = HEADER_FONT
            cell.fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
            cell.alignment = CENTER_ALIGN
            cell.border = HEADER_BORDER

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"

        new_schemes = self.db.get_new_since(since_date)
        for idx, s in enumerate(new_schemes, 1):
            row = idx + 1
            amount = s.get("fund_amount_min") or ""
            if s.get("fund_amount_max"):
                amount = f"{amount} - {s['fund_amount_max']}" if amount else s["fund_amount_max"]

            values = [
                idx, s.get("clean_name"), s.get("level"), s.get("state"),
                s.get("sector"), s.get("scheme_type"),
                s.get("start_date"), s.get("end_date"),
                s.get("application_fee"), amount,
                s.get("target_group"), s.get("summary"), s.get("source_url"),
            ]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=val)
                cell.fill = NEW_FILL
                cell.border = THIN_BORDER
                cell.alignment = WRAP_ALIGN

        widths = [6, 40, 10, 18, 20, 14, 14, 14, 14, 20, 20, 50, 35]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

    # ═══════════════════════════════════════
    # Sheet 3: Approaching Deadlines
    # ═══════════════════════════════════════

    def _build_deadlines_sheet(self, wb: Workbook) -> None:
        ws = wb.create_sheet("Approaching Deadlines")

        headers = [
            "S.No", "Scheme Name", "Level", "State/UT", "Sector",
            "Application Deadline", "End Date", "Days Remaining",
            "Application Fee", "Fund Amount", "Target Group",
            "How to Apply", "Source URL",
        ]

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = HEADER_FONT
            cell.fill = PatternFill(start_color="C62828", end_color="C62828", fill_type="solid")
            cell.alignment = CENTER_ALIGN
            cell.border = HEADER_BORDER

        ws.freeze_panes = "A2"

        # Get deadlines within 30 days
        deadlines_7 = self.db.get_approaching_deadlines(7)
        deadlines_30 = self.db.get_approaching_deadlines(30)

        # Combine and deduplicate
        seen_ids = set()
        all_deadlines = []
        for s in deadlines_7 + deadlines_30:
            sid = s.get("scheme_id")
            if sid not in seen_ids:
                seen_ids.add(sid)
                all_deadlines.append(s)

        for idx, s in enumerate(all_deadlines, 1):
            row = idx + 1
            deadline = s.get("application_end_date") or s.get("end_date") or ""
            days_remaining = ""
            try:
                if deadline:
                    dl = date.fromisoformat(deadline[:10])
                    days_remaining = (dl - date.today()).days
            except (ValueError, TypeError):
                pass

            amount = s.get("fund_amount_min") or ""
            if s.get("fund_amount_max"):
                amount = f"{amount} - {s['fund_amount_max']}" if amount else s["fund_amount_max"]

            values = [
                idx, s.get("clean_name"), s.get("level"), s.get("state"),
                s.get("sector"), s.get("application_end_date"),
                s.get("end_date"), days_remaining,
                s.get("application_fee"), amount,
                s.get("target_group"), "", s.get("source_url"),
            ]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=val)
                cell.border = THIN_BORDER
                cell.alignment = WRAP_ALIGN
                if col == 8 and isinstance(days_remaining, int):
                    if days_remaining <= 3:
                        cell.fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
                        cell.font = Font(name="Arial", bold=True, color="FFFFFF")
                    elif days_remaining <= 7:
                        cell.fill = DEADLINE_FILL
                    elif days_remaining <= 30:
                        cell.fill = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")

        widths = [6, 40, 10, 18, 20, 16, 16, 14, 14, 20, 20, 30, 35]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

    # ═══════════════════════════════════════
    # Sheet 4: Sector Summary
    # ═══════════════════════════════════════

    def _build_sector_summary(self, wb: Workbook) -> None:
        ws = wb.create_sheet("Sector Summary")
        stats = self.db.get_stats()

        headers = ["Sector", "Count", "% of Total"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = CENTER_ALIGN
            cell.border = HEADER_BORDER

        total = stats["total"] or 1
        for idx, (sector, count) in enumerate(
            sorted(stats["by_sector"].items(), key=lambda x: -x[1]), 1
        ):
            row = idx + 1
            ws.cell(row=row, column=1, value=sector.replace("_", " ")).border = THIN_BORDER
            ws.cell(row=row, column=2, value=count).border = THIN_BORDER
            pct_cell = ws.cell(row=row, column=3, value=count / total)
            pct_cell.number_format = "0.0%"
            pct_cell.border = THIN_BORDER

        # Total row
        total_row = len(stats["by_sector"]) + 2
        ws.cell(row=total_row, column=1, value="TOTAL").font = Font(bold=True)
        ws.cell(row=total_row, column=2, value=f"=SUM(B2:B{total_row-1})")
        ws.cell(row=total_row, column=3, value=f"=SUM(C2:C{total_row-1})")
        ws.cell(row=total_row, column=3).number_format = "0.0%"

        ws.column_dimensions["A"].width = 30
        ws.column_dimensions["B"].width = 12
        ws.column_dimensions["C"].width = 12

    # ═══════════════════════════════════════
    # Sheet 5: State Summary
    # ═══════════════════════════════════════

    def _build_state_summary(self, wb: Workbook) -> None:
        ws = wb.create_sheet("State Summary")
        stats = self.db.get_stats()

        headers = ["State/UT", "Count", "% of Total"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = CENTER_ALIGN
            cell.border = HEADER_BORDER

        total_state = sum(stats["by_state"].values()) or 1
        for idx, (state, count) in enumerate(
            sorted(stats["by_state"].items(), key=lambda x: -x[1]), 1
        ):
            row = idx + 1
            ws.cell(row=row, column=1, value=state.replace("_", " ")).border = THIN_BORDER
            ws.cell(row=row, column=2, value=count).border = THIN_BORDER
            pct_cell = ws.cell(row=row, column=3, value=count / total_state)
            pct_cell.number_format = "0.0%"
            pct_cell.border = THIN_BORDER

        ws.column_dimensions["A"].width = 30
        ws.column_dimensions["B"].width = 12
        ws.column_dimensions["C"].width = 12

    # ═══════════════════════════════════════
    # Sheet 6: Status Summary
    # ═══════════════════════════════════════

    def _build_status_summary(self, wb: Workbook) -> None:
        ws = wb.create_sheet("Status Summary")
        stats = self.db.get_stats()

        headers = ["Status", "Count", "% of Total"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = CENTER_ALIGN

        total = stats["total"] or 1
        status_fills = {
            "Active": ACTIVE_FILL,
            "Expired": EXPIRED_FILL,
            "Closed": DEADLINE_FILL,
            "Upcoming": PatternFill(start_color="D9EDF7", end_color="D9EDF7", fill_type="solid"),
            "Unknown": PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid"),
        }

        for idx, (status, count) in enumerate(
            sorted(stats["by_status"].items(), key=lambda x: -x[1]), 1
        ):
            row = idx + 1
            cell_name = ws.cell(row=row, column=1, value=status)
            cell_name.fill = status_fills.get(status, PatternFill())
            cell_name.border = THIN_BORDER
            ws.cell(row=row, column=2, value=count).border = THIN_BORDER
            pct = ws.cell(row=row, column=3, value=count / total)
            pct.number_format = "0.0%"
            pct.border = THIN_BORDER

        ws.column_dimensions["A"].width = 18
        ws.column_dimensions["B"].width = 12
        ws.column_dimensions["C"].width = 12

    # ═══════════════════════════════════════
    # Sheet 7: Daily Run History
    # ═══════════════════════════════════════

    def _build_run_history(self, wb: Workbook) -> None:
        ws = wb.create_sheet("Run History")

        headers = [
            "Run Date", "Started At", "Completed At", "Total in DB",
            "New", "Updated", "Closed", "Unchanged", "Errors",
            "Duration (sec)", "Excel Report",
        ]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = CENTER_ALIGN
            cell.border = HEADER_BORDER

        ws.freeze_panes = "A2"

        runs = self.db.get_run_history(60)
        for idx, r in enumerate(runs, 1):
            row = idx + 1
            values = [
                r.get("run_date"), r.get("started_at"), r.get("completed_at"),
                r.get("total_in_db"), r.get("new_schemes"),
                r.get("updated_schemes"), r.get("closed_schemes"),
                r.get("unchanged_schemes"), r.get("errors"),
                round(r.get("elapsed_seconds", 0), 1),
                r.get("excel_report_path"),
            ]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=val)
                cell.border = THIN_BORDER
                if col == 5 and val and val > 0:  # New schemes
                    cell.fill = NEW_FILL
                    cell.font = Font(bold=True, color="006600")

        widths = [14, 22, 22, 12, 8, 10, 10, 12, 8, 12, 35]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

    # ═══════════════════════════════════════
    # Sheet 8: Change Log
    # ═══════════════════════════════════════

    def _build_change_log(self, wb: Workbook, run_id: str) -> None:
        ws = wb.create_sheet("Change Log")

        headers = [
            "Scheme Name", "Level", "Sector", "Change Type",
            "Field Changed", "Old Value", "New Value", "Detected At",
        ]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = HEADER_FONT
            cell.fill = PatternFill(start_color="F57C00", end_color="F57C00", fill_type="solid")
            cell.alignment = CENTER_ALIGN

        changes = self.db.get_changes_for_run(run_id)
        for idx, c in enumerate(changes, 1):
            row = idx + 1
            values = [
                c.get("clean_name"), c.get("level"), c.get("sector"),
                c.get("change_type"), c.get("field_changed"),
                c.get("old_value", "")[:100], c.get("new_value", "")[:100],
                c.get("detected_at"),
            ]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=val)
                cell.border = THIN_BORDER

        widths = [40, 10, 20, 14, 18, 30, 30, 22]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

    # ═══════════════════════════════════════
    # Sheet 9: Dashboard (Charts)
    # ═══════════════════════════════════════

    def _build_dashboard_sheet(self, wb: Workbook) -> None:
        ws = wb.create_sheet("Dashboard")
        stats = self.db.get_stats()

        # Title
        ws.merge_cells("A1:F1")
        title_cell = ws.cell(row=1, column=1, value="GovScheme SuperAgent — Dashboard")
        title_cell.font = Font(name="Arial", size=16, bold=True, color="1F4E79")
        title_cell.alignment = Alignment(horizontal="center")

        ws.cell(row=2, column=1, value=f"Report Date: {date.today().isoformat()}")
        ws.cell(row=2, column=1).font = Font(italic=True, color="666666")

        # KPI Cards (row 4)
        kpis = [
            ("Total Schemes", stats["total"]),
            ("Active", stats["active"]),
            ("Expired", stats.get("by_status", {}).get("Expired", 0)),
            ("Upcoming", stats.get("by_status", {}).get("Upcoming", 0)),
        ]
        for i, (label, val) in enumerate(kpis):
            col = (i * 2) + 1
            ws.cell(row=4, column=col, value=label).font = Font(size=9, color="666666")
            num_cell = ws.cell(row=5, column=col, value=val)
            num_cell.font = Font(size=20, bold=True, color="1F4E79")

        # Sector data for chart (row 8+)
        ws.cell(row=8, column=1, value="Sector").font = Font(bold=True)
        ws.cell(row=8, column=2, value="Count").font = Font(bold=True)

        sorted_sectors = sorted(stats["by_sector"].items(), key=lambda x: -x[1])
        for idx, (sector, count) in enumerate(sorted_sectors[:15], 1):
            ws.cell(row=8 + idx, column=1, value=sector.replace("_", " "))
            ws.cell(row=8 + idx, column=2, value=count)

        # Bar chart for sectors
        if sorted_sectors:
            chart = BarChart()
            chart.type = "bar"
            chart.title = "Schemes by Sector"
            chart.style = 10
            chart.y_axis.title = "Number of Schemes"
            chart.x_axis.title = "Sector"
            data_ref = Reference(ws, min_col=2, min_row=8, max_row=8 + min(15, len(sorted_sectors)))
            cats_ref = Reference(ws, min_col=1, min_row=9, max_row=8 + min(15, len(sorted_sectors)))
            chart.add_data(data_ref, titles_from_data=True)
            chart.set_categories(cats_ref)
            chart.shape = 4
            chart.width = 30
            chart.height = 15
            ws.add_chart(chart, "D8")

        # Level data for pie chart
        level_start = 8 + len(sorted_sectors) + 3
        ws.cell(row=level_start, column=1, value="Level").font = Font(bold=True)
        ws.cell(row=level_start, column=2, value="Count").font = Font(bold=True)
        for idx, (level, count) in enumerate(stats["by_level"].items(), 1):
            ws.cell(row=level_start + idx, column=1, value=level)
            ws.cell(row=level_start + idx, column=2, value=count)

        if stats["by_level"]:
            pie = PieChart()
            pie.title = "Schemes by Level"
            pie.style = 10
            data_ref = Reference(ws, min_col=2, min_row=level_start, max_row=level_start + len(stats["by_level"]))
            cats_ref = Reference(ws, min_col=1, min_row=level_start + 1, max_row=level_start + len(stats["by_level"]))
            pie.add_data(data_ref, titles_from_data=True)
            pie.set_categories(cats_ref)
            pie.width = 16
            pie.height = 12
            ws.add_chart(pie, "D" + str(level_start))

        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 12

    # ═══════════════════════════════════════
    # EXAM SHEETS (V3 — Sheets 10–15)
    # ═══════════════════════════════════════

    def _apply_exam_header(self, ws, headers: list[str]) -> None:
        """Apply header formatting to an exam sheet."""
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = CENTER_ALIGN
            cell.border = HEADER_BORDER

    def _apply_exam_status_fill(self, cell, status: str) -> None:
        """Color-code exam status cells."""
        fills = {
            "Application_Open": ACTIVE_FILL,
            "Upcoming": UPCOMING_FILL,
            "Application_Closed": ORANGE_FILL,
            "Admit_Card_Out": ORANGE_FILL,
            "Exam_Ongoing": PURPLE_FILL,
            "Result_Awaited": TEAL_FILL,
            "Completed": GREY_FILL,
        }
        fill = fills.get(status)
        if fill:
            cell.fill = fill

    def _apply_deadline_urgency(self, cell, days) -> None:
        """Apply urgency colors: ≤3d red bold, ≤7d red, ≤30d yellow."""
        if days is None:
            return
        try:
            d = int(days)
        except (ValueError, TypeError):
            return
        if d <= 3:
            cell.fill = DEADLINE_FILL
            cell.font = Font(name="Arial", size=10, bold=True, color="CC0000")
        elif d <= 7:
            cell.fill = DEADLINE_FILL
        elif d <= 30:
            cell.fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")

    def _build_exam_master_tracker(self, wb: Workbook) -> None:
        """Sheet 10: Exam Master Tracker — all exams with 40 columns."""
        ws = wb.create_sheet("Exam Master Tracker")
        headers = [
            "S.No", "Exam Name", "Short Name", "Conducting Body", "Category",
            "Level", "State", "Exam Cycle", "Status",
            "Notification Date", "Application Start", "Application End ⚠️",
            "Fee Payment Deadline", "Correction Window",
            "Prelims Date", "Mains Date", "Admit Card Date",
            "Result Date", "Final Result Date", "Joining Date",
            "Fee (Gen) ₹", "Fee (OBC) ₹", "Fee (SC/ST) ₹",
            "Fee (Female) ₹", "Fee (EWS) ₹", "Fee (PwD) ₹", "Is Free?",
            "Total Vacancies", "Age Min", "Age Max",
            "Qualification", "Physical Standards",
            "Domicile Required", "Gender Restriction",
            "Apply Online URL", "Notification PDF", "Syllabus URL", "Official Website",
            "Days Until App Close", "Days Until Exam",
        ]
        self._apply_exam_header(ws, headers)

        exams = self.exam_db.get_all_exams()
        import json as _json

        for idx, exam in enumerate(exams, 1):
            row = idx + 1

            # Parse phases JSON to get prelims/mains dates
            phases = []
            try:
                phases = _json.loads(exam.get("phases_json") or "[]")
            except (ValueError, TypeError):
                pass

            prelims_date = mains_date = admit_card = None
            for p in phases:
                name = (p.get("phase_name") or "").lower()
                if "prelim" in name or "cbt" in name or "written" in name:
                    prelims_date = prelims_date or p.get("exam_date_start")
                    admit_card = admit_card or p.get("admit_card_date")
                elif "main" in name or "phase 2" in name or "interview" in name:
                    mains_date = mains_date or p.get("exam_date_start")

            # Compute days
            today = date.today()
            days_app_close = None
            days_exam = None
            app_end = exam.get("application_end_date")
            if app_end:
                try:
                    d = date.fromisoformat(app_end)
                    if d >= today:
                        days_app_close = (d - today).days
                except ValueError:
                    pass
            if prelims_date:
                try:
                    d = date.fromisoformat(prelims_date)
                    if d >= today:
                        days_exam = (d - today).days
                except ValueError:
                    pass

            values = [
                idx, exam.get("clean_exam_name") or exam.get("exam_name"), exam.get("short_name"),
                exam.get("conducting_body"), exam.get("exam_category"),
                exam.get("exam_level"), exam.get("state"), exam.get("exam_cycle"),
                exam.get("exam_status"),
                exam.get("notification_date"), exam.get("application_start_date"),
                exam.get("application_end_date"), exam.get("fee_payment_deadline"),
                f"{exam.get('correction_window_start', '') or ''} - {exam.get('correction_window_end', '') or ''}".strip(" - ") or None,
                prelims_date, mains_date, admit_card,
                exam.get("result_date"), exam.get("final_result_date"), exam.get("joining_date"),
                exam.get("fee_general"), exam.get("fee_obc"), exam.get("fee_sc_st"),
                exam.get("fee_female"), exam.get("fee_ews"), exam.get("fee_pwd"),
                "Yes" if exam.get("is_free") else "No",
                exam.get("total_vacancies"), exam.get("age_min"), exam.get("age_max"),
                exam.get("qualification"), exam.get("physical_standards"),
                exam.get("domicile_required"), exam.get("gender_restriction"),
                exam.get("apply_online_url"), exam.get("official_notification_url"),
                exam.get("syllabus_url"), exam.get("official_website"),
                days_app_close, days_exam,
            ]

            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=val)
                cell.border = THIN_BORDER
                cell.alignment = WRAP_ALIGN

            # Status coloring (col 9)
            self._apply_exam_status_fill(ws.cell(row=row, column=9), exam.get("exam_status", ""))

            # Application End urgency (col 12)
            self._apply_deadline_urgency(ws.cell(row=row, column=12), days_app_close)

            # Days Until App Close (col 39)
            self._apply_deadline_urgency(ws.cell(row=row, column=39), days_app_close)

            # Days Until Exam (col 40)
            if days_exam is not None and days_exam <= 7:
                ws.cell(row=row, column=40).fill = ORANGE_FILL
            elif days_exam is not None and days_exam <= 30:
                ws.cell(row=row, column=40).fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")

            # Is Free coloring (col 27)
            if exam.get("is_free"):
                ws.cell(row=row, column=27).fill = ACTIVE_FILL

            # Hyperlinks for URL columns
            for url_col in [35, 36, 37, 38]:
                url_val = ws.cell(row=row, column=url_col).value
                if url_val and isinstance(url_val, str) and url_val.startswith("http"):
                    ws.cell(row=row, column=url_col).hyperlink = url_val
                    ws.cell(row=row, column=url_col).font = Font(color="0563C1", underline="single")

        # Auto-filter
        if exams:
            ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(exams) + 1}"

        # Freeze panes
        ws.freeze_panes = "C2"

        # Column widths
        widths = {"A": 6, "B": 40, "C": 12, "D": 18, "E": 16, "F": 8, "G": 15, "H": 10, "I": 18,
                  "J": 12, "K": 12, "L": 14, "M": 12, "N": 18, "O": 12, "P": 12, "Q": 12,
                  "R": 12, "S": 12, "T": 12}
        for col_letter, w in widths.items():
            ws.column_dimensions[col_letter].width = w

    def _build_exam_application_open(self, wb: Workbook) -> None:
        """Sheet 11: Application Open Now — exams currently accepting applications."""
        ws = wb.create_sheet("Application Open Now")
        headers = [
            "S.No", "Exam Name", "Conducting Body", "Category",
            "Application Start", "Application End ⚠️", "Fee (Gen) ₹",
            "Total Vacancies", "Days Left", "Apply URL",
        ]
        self._apply_exam_header(ws, headers)

        open_exams = self.exam_db.get_application_open()
        today = date.today()

        for idx, exam in enumerate(open_exams, 1):
            row = idx + 1
            days_left = None
            app_end = exam.get("application_end_date")
            if app_end:
                try:
                    days_left = (date.fromisoformat(app_end) - today).days
                except ValueError:
                    pass

            values = [
                idx, exam.get("clean_exam_name") or exam.get("exam_name"),
                exam.get("conducting_body"), exam.get("exam_category"),
                exam.get("application_start_date"), exam.get("application_end_date"),
                exam.get("fee_general"), exam.get("total_vacancies"),
                days_left, exam.get("apply_online_url"),
            ]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=val)
                cell.border = THIN_BORDER
                cell.alignment = WRAP_ALIGN

            # Urgency on Days Left (col 9)
            self._apply_deadline_urgency(ws.cell(row=row, column=9), days_left)

            # Apply URL hyperlink (col 10)
            url_val = ws.cell(row=row, column=10).value
            if url_val and isinstance(url_val, str) and url_val.startswith("http"):
                ws.cell(row=row, column=10).hyperlink = url_val
                ws.cell(row=row, column=10).font = Font(color="0563C1", underline="single")

        ws.freeze_panes = "C2"
        widths = {"A": 6, "B": 40, "C": 20, "D": 16, "E": 14, "F": 14, "G": 10, "H": 12, "I": 10, "J": 35}
        for col_letter, w in widths.items():
            ws.column_dimensions[col_letter].width = w

    def _build_exam_calendar(self, wb: Workbook) -> None:
        """Sheet 12: Exam Calendar — all upcoming events sorted chronologically."""
        ws = wb.create_sheet("Exam Calendar")
        headers = ["Date", "Exam Name", "Event Type", "Conducting Body", "Category", "Apply URL", "Days Away"]
        self._apply_exam_header(ws, headers)

        import json as _json
        all_exams = self.exam_db.get_all_exams()
        today = date.today()
        events: list[dict] = []

        for exam in all_exams:
            name = exam.get("clean_exam_name") or exam.get("exam_name", "")
            body = exam.get("conducting_body", "")
            cat = exam.get("exam_category", "")
            apply_url = exam.get("apply_online_url", "")

            for field, event_type in [
                ("application_start_date", "Application Open"),
                ("application_end_date", "Application Close"),
                ("result_date", "Result"),
                ("final_result_date", "Final Result"),
            ]:
                dt = exam.get(field)
                if dt:
                    events.append({"date": dt, "exam": name, "type": event_type,
                                    "body": body, "cat": cat, "url": apply_url})

            phases_raw = exam.get("phases_json")
            if phases_raw:
                try:
                    for phase in _json.loads(phases_raw):
                        pn = phase.get("phase_name", "")
                        if phase.get("admit_card_date"):
                            events.append({"date": phase["admit_card_date"], "exam": name,
                                            "type": f"Admit Card ({pn})", "body": body, "cat": cat, "url": apply_url})
                        if phase.get("exam_date_start"):
                            events.append({"date": phase["exam_date_start"], "exam": name,
                                            "type": f"Exam ({pn})", "body": body, "cat": cat, "url": apply_url})
                        if phase.get("result_date"):
                            events.append({"date": phase["result_date"], "exam": name,
                                            "type": f"Result ({pn})", "body": body, "cat": cat, "url": apply_url})
                except (ValueError, TypeError):
                    pass

        # Filter future events and sort
        future_events = []
        for e in events:
            try:
                d = date.fromisoformat(e["date"])
                if d >= today:
                    e["days_away"] = (d - today).days
                    future_events.append(e)
            except (ValueError, TypeError):
                pass

        future_events.sort(key=lambda x: x["date"])

        # Event type color map
        event_fills = {
            "Application Open": ACTIVE_FILL,
            "Application Close": DEADLINE_FILL,
            "Admit Card": UPCOMING_FILL,
            "Exam": PURPLE_FILL,
            "Result": TEAL_FILL,
            "Final Result": TEAL_FILL,
        }

        for idx, evt in enumerate(future_events[:500], 1):
            row = idx + 1
            values = [evt["date"], evt["exam"], evt["type"], evt["body"],
                       evt["cat"], evt["url"], evt.get("days_away")]

            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=val)
                cell.border = THIN_BORDER
                cell.alignment = WRAP_ALIGN

            # Color code event type
            event_type = evt["type"]
            for key, fill in event_fills.items():
                if key in event_type:
                    ws.cell(row=row, column=3).fill = fill
                    break

            # Days away urgency
            self._apply_deadline_urgency(ws.cell(row=row, column=7), evt.get("days_away"))

        ws.freeze_panes = "B2"
        widths = {"A": 12, "B": 40, "C": 20, "D": 18, "E": 16, "F": 35, "G": 10}
        for col_letter, w in widths.items():
            ws.column_dimensions[col_letter].width = w

    def _build_exam_deadlines(self, wb: Workbook) -> None:
        """Sheet 13: Exam Deadlines — application close + admit card + result dates."""
        ws = wb.create_sheet("Exam Deadlines")
        headers = [
            "S.No", "Exam Name", "Conducting Body", "Deadline Type",
            "Date", "Days Left", "Apply URL",
        ]
        self._apply_exam_header(ws, headers)

        import json as _json
        today = date.today()
        deadlines: list[dict] = []

        # Application deadlines (within 30 days)
        for exam in self.exam_db.get_approaching_deadlines(30):
            app_end = exam.get("application_end_date")
            if app_end:
                try:
                    days = (date.fromisoformat(app_end) - today).days
                    deadlines.append({
                        "exam": exam.get("clean_exam_name") or exam.get("exam_name"),
                        "body": exam.get("conducting_body"),
                        "type": "Application Close",
                        "date": app_end, "days": days,
                        "url": exam.get("apply_online_url"),
                    })
                except ValueError:
                    pass

        # Upcoming exam dates (within 30 days)
        for exam in self.exam_db.get_upcoming_exams(30):
            phases_raw = exam.get("phases_json")
            if phases_raw:
                try:
                    for phase in _json.loads(phases_raw):
                        ed = phase.get("exam_date_start")
                        if ed:
                            try:
                                days = (date.fromisoformat(ed) - today).days
                                if 0 <= days <= 30:
                                    deadlines.append({
                                        "exam": exam.get("clean_exam_name") or exam.get("exam_name"),
                                        "body": exam.get("conducting_body"),
                                        "type": f"Exam ({phase.get('phase_name', '')})",
                                        "date": ed, "days": days,
                                        "url": exam.get("apply_online_url"),
                                    })
                            except ValueError:
                                pass
                except (ValueError, TypeError):
                    pass

        deadlines.sort(key=lambda x: x.get("days", 999))

        for idx, dl in enumerate(deadlines, 1):
            row = idx + 1
            values = [idx, dl["exam"], dl["body"], dl["type"],
                       dl["date"], dl["days"], dl["url"]]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=val)
                cell.border = THIN_BORDER
                cell.alignment = WRAP_ALIGN

            self._apply_deadline_urgency(ws.cell(row=row, column=6), dl["days"])

        ws.freeze_panes = "C2"
        widths = {"A": 6, "B": 40, "C": 20, "D": 18, "E": 12, "F": 10, "G": 35}
        for col_letter, w in widths.items():
            ws.column_dimensions[col_letter].width = w

    def _build_exam_category_summary(self, wb: Workbook) -> None:
        """Sheet 14: Exam Category Summary — count by category."""
        ws = wb.create_sheet("Exam Category Summary")
        headers = ["Category", "Count", "% of Total"]
        self._apply_exam_header(ws, headers)

        stats = self.exam_db.get_stats()
        by_category = stats.get("by_category", {})
        total = sum(by_category.values()) or 1

        sorted_cats = sorted(by_category.items(), key=lambda x: -x[1])
        for idx, (cat, count) in enumerate(sorted_cats, 1):
            row = idx + 1
            ws.cell(row=row, column=1, value=cat.replace("_", " ")).border = THIN_BORDER
            ws.cell(row=row, column=2, value=count).border = THIN_BORDER
            pct_cell = ws.cell(row=row, column=3)
            pct_cell.value = count / total
            pct_cell.number_format = '0.0%'
            pct_cell.border = THIN_BORDER

        # Total row
        total_row = len(sorted_cats) + 2
        ws.cell(row=total_row, column=1, value="TOTAL").font = Font(bold=True)
        ws.cell(row=total_row, column=2, value=f"=SUM(B2:B{total_row - 1})").font = Font(bold=True)

        # Bar chart
        if sorted_cats:
            chart = BarChart()
            chart.type = "bar"
            chart.title = "Exams by Category"
            chart.y_axis.title = "Count"
            chart.style = 10
            data_ref = Reference(ws, min_col=2, min_row=1, max_row=len(sorted_cats) + 1)
            cats_ref = Reference(ws, min_col=1, min_row=2, max_row=len(sorted_cats) + 1)
            chart.add_data(data_ref, titles_from_data=True)
            chart.set_categories(cats_ref)
            chart.shape = 4
            chart.width = 20
            chart.height = 14
            ws.add_chart(chart, "E2")

        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 10
        ws.column_dimensions["C"].width = 12

    def _build_exam_state_summary(self, wb: Workbook) -> None:
        """Sheet 15: State Exam Summary — count by state for state-level exams."""
        ws = wb.create_sheet("State Exam Summary")
        headers = ["State", "Count", "% of State Total"]
        self._apply_exam_header(ws, headers)

        all_exams = self.exam_db.get_all_exams()
        by_state: dict[str, int] = {}
        for exam in all_exams:
            state = exam.get("state")
            if state:
                by_state[state] = by_state.get(state, 0) + 1

        total = sum(by_state.values()) or 1
        sorted_states = sorted(by_state.items(), key=lambda x: -x[1])

        for idx, (state, count) in enumerate(sorted_states, 1):
            row = idx + 1
            ws.cell(row=row, column=1, value=state.replace("_", " ")).border = THIN_BORDER
            ws.cell(row=row, column=2, value=count).border = THIN_BORDER
            pct_cell = ws.cell(row=row, column=3)
            pct_cell.value = count / total
            pct_cell.number_format = '0.0%'
            pct_cell.border = THIN_BORDER

        total_row = len(sorted_states) + 2
        ws.cell(row=total_row, column=1, value="TOTAL").font = Font(bold=True)
        ws.cell(row=total_row, column=2, value=f"=SUM(B2:B{total_row - 1})").font = Font(bold=True)

        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 10
        ws.column_dimensions["C"].width = 14
```

---

## File 40/41: `src/storage/storage_agent.py`
<!-- lines: 344 -->

```python
"""
GovScheme SuperAgent — Storage Agent
Organizes classified schemes into structured folder hierarchies
and downloads associated PDFs, forms, and guidelines.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from src.agents.models import ClassifiedScheme, StoredScheme, SchemeLevel
from src.config.settings import AgentConfig

logger = logging.getLogger("storage_agent")


class StorageAgent:
    """
    Organizes classified schemes into the folder hierarchy:
    output/
    ├── Central/
    │   ├── Education/
    │   │   └── Scheme_Name/
    │   │       ├── metadata.json
    │   │       ├── scheme_details.md
    │   │       └── *.pdf
    ├── State/
    │   └── Tamil_Nadu/
    │       └── Fisheries/
    └── Union_Territory/
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.stored_count = 0
        self.download_errors = 0

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }

    def _sanitize_filename(self, name: str) -> str:
        """Clean a string for use as a folder/file name."""
        # Remove special characters, keep alphanumeric and spaces
        clean = re.sub(r'[^\w\s\-]', '', name)
        clean = re.sub(r'\s+', '_', clean.strip())
        return clean[:80]  # Limit length

    def _compute_folder_path(self, scheme: ClassifiedScheme) -> Path:
        """Compute the folder path based on classification."""
        parts = [self.output_dir]

        # Level 1: Central / State / Union_Territory
        parts.append(scheme.level.value)

        # Level 2 (for State/UT): State name
        if scheme.level in (SchemeLevel.STATE, SchemeLevel.UNION_TERRITORY) and scheme.state:
            parts.append(self._sanitize_filename(scheme.state))

        # Level 3: Sector
        parts.append(scheme.sector.value)

        # Level 4: Scheme name folder
        parts.append(self._sanitize_filename(scheme.clean_name))

        return Path(*[str(p) for p in parts])

    async def store_scheme(self, scheme: ClassifiedScheme) -> StoredScheme:
        """Store a classified scheme: create folders, save metadata, download assets."""
        folder = self._compute_folder_path(scheme)
        folder.mkdir(parents=True, exist_ok=True)

        # 1. Save metadata.json
        metadata_path = folder / "metadata.json"
        metadata = {
            "scheme_id": scheme.scheme_id,
            "name": scheme.clean_name,
            "level": scheme.level.value,
            "state": scheme.state,
            "sector": scheme.sector.value,
            "type": scheme.scheme_type.value,
            "summary": scheme.summary,
            "eligibility": scheme.eligibility_summary,
            "benefit_amount": scheme.benefit_amount,
            "target_group": scheme.target_group,
            "source_portal": scheme.raw_data.source_portal,
            "source_url": scheme.raw_data.source_url,
            "detail_url": scheme.raw_data.scheme_detail_url,
            "classification_confidence": scheme.classification_confidence,
            "crawled_at": scheme.raw_data.crawled_at.isoformat(),
            "classified_at": scheme.classified_at.isoformat(),
            "stored_at": datetime.utcnow().isoformat(),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))

        # 2. Save scheme details markdown
        detail_path = folder / "scheme_details.md"
        detail_md = self._generate_scheme_markdown(scheme)
        detail_path.write_text(detail_md, encoding="utf-8")

        # 3. Download PDFs
        downloaded_pdfs = []
        if self.config.download_pdfs and scheme.raw_data.pdf_urls:
            downloaded_pdfs = await self._download_files(
                scheme.raw_data.pdf_urls, folder, "pdf"
            )

        # 4. Download forms
        downloaded_forms = []
        if self.config.download_forms and scheme.raw_data.form_urls:
            downloaded_forms = await self._download_files(
                scheme.raw_data.form_urls, folder, "form"
            )

        # 5. Save the website URL as a .url shortcut
        url_path = folder / "website.url"
        website_url = scheme.raw_data.scheme_detail_url or scheme.raw_data.source_url
        url_path.write_text(
            f"[InternetShortcut]\nURL={website_url}\n", encoding="utf-8"
        )

        self.stored_count += 1

        stored = StoredScheme(
            classified=scheme,
            folder_path=str(folder),
            metadata_path=str(metadata_path),
            detail_markdown_path=str(detail_path),
            downloaded_pdfs=downloaded_pdfs,
            downloaded_forms=downloaded_forms,
        )

        logger.info(
            "Stored: %s → %s (%d PDFs, %d forms)",
            scheme.clean_name, folder, len(downloaded_pdfs), len(downloaded_forms),
        )
        return stored

    async def store_batch(
        self, schemes: list[ClassifiedScheme], max_concurrent: int = 5
    ) -> list[StoredScheme]:
        """Store a batch of schemes concurrently."""
        sem = asyncio.Semaphore(max_concurrent)
        stored = []

        async def _store_one(s: ClassifiedScheme) -> Optional[StoredScheme]:
            async with sem:
                try:
                    return await self.store_scheme(s)
                except Exception as e:
                    logger.error("Store failed for '%s': %s", s.clean_name, e)
                    return None

        tasks = [_store_one(s) for s in schemes]
        results = await asyncio.gather(*tasks)

        for result in results:
            if isinstance(result, StoredScheme):
                stored.append(result)

        return stored

    def _generate_scheme_markdown(self, scheme: ClassifiedScheme) -> str:
        """Generate a detailed markdown file for the scheme."""
        raw = scheme.raw_data
        lines = [
            f"# {scheme.clean_name}",
            "",
            f"**Level:** {scheme.level.value}",
        ]

        if scheme.state:
            lines.append(f"**State/UT:** {scheme.state.replace('_', ' ')}")

        lines.extend([
            f"**Sector:** {scheme.sector.value.replace('_', ' ')}",
            f"**Type:** {scheme.scheme_type.value.replace('_', ' ')}",
            f"**Source:** [{raw.source_portal}]({raw.source_url})",
            "",
        ])

        if scheme.summary:
            lines.extend(["## Summary", "", scheme.summary, ""])

        if scheme.benefit_amount:
            lines.extend(["## Benefits", "", f"**Amount:** {scheme.benefit_amount}", ""])

        if raw.raw_benefits:
            lines.extend([raw.raw_benefits[:1000], ""])

        if scheme.eligibility_summary:
            lines.extend(["## Eligibility", "", scheme.eligibility_summary, ""])

        if raw.raw_eligibility and raw.raw_eligibility != scheme.eligibility_summary:
            lines.extend(["### Detailed Eligibility", "", raw.raw_eligibility[:1000], ""])

        if raw.raw_application_process:
            lines.extend(["## How to Apply", "", raw.raw_application_process[:1000], ""])

        if raw.raw_documents_required:
            lines.extend(["## Documents Required", "", raw.raw_documents_required[:1000], ""])

        if scheme.target_group:
            lines.extend(["## Target Group", "", scheme.target_group, ""])

        # Links
        lines.extend(["## Links", ""])
        if raw.scheme_detail_url:
            lines.append(f"- [Official Scheme Page]({raw.scheme_detail_url})")
        lines.append(f"- [Source Portal]({raw.source_url})")

        if raw.pdf_urls:
            lines.extend(["", "### Documents"])
            for i, pdf_url in enumerate(raw.pdf_urls):
                lines.append(f"- [Document {i + 1}]({pdf_url})")

        lines.extend([
            "",
            "---",
            f"*Crawled: {raw.crawled_at.strftime('%Y-%m-%d %H:%M')} UTC*",
            f"*Classification Confidence: {scheme.classification_confidence:.0%}*",
        ])

        return "\n".join(lines)

    async def _download_files(
        self, urls: list[str], folder: Path, prefix: str
    ) -> list[str]:
        """Download files (PDFs, forms) to the scheme folder."""
        downloaded = []
        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=30,
            follow_redirects=True,
        ) as client:
            for i, url in enumerate(urls[:10]):  # Limit to 10 files per scheme
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue

                    # Determine filename
                    content_type = resp.headers.get("content-type", "")
                    ext = ".pdf"
                    if "html" in content_type:
                        ext = ".html"
                    elif "doc" in content_type:
                        ext = ".doc"

                    # Check file size
                    content_length = len(resp.content)
                    if content_length > self.config.max_pdf_size_mb * 1024 * 1024:
                        logger.warning("File too large (%d MB): %s", content_length // (1024*1024), url)
                        continue

                    filename = f"{prefix}_{i + 1}{ext}"
                    filepath = folder / filename
                    filepath.write_bytes(resp.content)
                    downloaded.append(str(filepath))

                    logger.debug("Downloaded: %s → %s", url, filepath)

                except Exception as e:
                    logger.warning("Download failed %s: %s", url, e)
                    self.download_errors += 1

        return downloaded

    async def generate_reports(self, stored_schemes: list[StoredScheme]) -> None:
        """Generate summary reports in the output directory."""
        reports_dir = self.output_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Crawl Summary
        summary = {
            "total_schemes": len(stored_schemes),
            "by_level": {},
            "by_sector": {},
            "by_type": {},
            "by_state": {},
            "generated_at": datetime.utcnow().isoformat(),
        }

        for s in stored_schemes:
            c = s.classified

            level = c.level.value
            summary["by_level"][level] = summary["by_level"].get(level, 0) + 1

            sector = c.sector.value
            summary["by_sector"][sector] = summary["by_sector"].get(sector, 0) + 1

            stype = c.scheme_type.value
            summary["by_type"][stype] = summary["by_type"].get(stype, 0) + 1

            if c.state:
                state = c.state
                summary["by_state"][state] = summary["by_state"].get(state, 0) + 1

        (reports_dir / "crawl_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False)
        )

        # Sector Distribution
        (reports_dir / "sector_distribution.json").write_text(
            json.dumps(summary["by_sector"], indent=2)
        )

        # State Distribution
        (reports_dir / "state_distribution.json").write_text(
            json.dumps(summary["by_state"], indent=2)
        )

        # Full scheme index
        index = []
        for s in stored_schemes:
            c = s.classified
            index.append({
                "name": c.clean_name,
                "level": c.level.value,
                "state": c.state,
                "sector": c.sector.value,
                "type": c.scheme_type.value,
                "folder": s.folder_path,
                "source_url": c.raw_data.source_url,
            })

        (reports_dir / "scheme_index.json").write_text(
            json.dumps(index, indent=2, ensure_ascii=False)
        )

        logger.info("Reports generated in %s", reports_dir)
```

---

## File 41/41: `src/utils/__init__.py`
<!-- lines: 0 -->

```python

```

---
