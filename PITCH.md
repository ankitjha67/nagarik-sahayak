# ðŸ† Hackathon Pitch: GovScheme SuperAgent
## The Problem
India has **2,300+** government schemes across Central, State, and UT governments â€” spread across **50+ portals** with no unified way to discover, compare, or access them. Citizens miss out on schemes they're eligible for simply because the information is fragmented.
## Our Solution
**GovScheme SuperAgent** â€” a multi-agent system built on OpenClaw that:
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
User Request â†’ Orchestrator (CEO Agent)
                    â†“
    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
    â†“               â†“               â†“
Discovery     Discovery        Discovery
(myScheme)    (NSP)           (State Portals)
    â†“               â†“               â†“
    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                    â†“
            Deduplication Agent
            (Hash + Fuzzy + URL)
                    â†“
            Enrichment Agent
            (Detail page fetch)
                    â†“
            Classification Agent
            (LLM / Rule-based)
                    â†“
            Storage Agent
            (Folders + PDFs + Metadata)
                    â†“
            Report Generator
            (Summary + Index + Stats)
```
## The Super Agent Prompt
We also built a **12-role product team prompt** that transforms any LLM into a precision engineering machine:
- CEO, PM, Project Manager, BA, 3 Developers, Security, Risk, Finance, QA, Growth
- 7-Gate Pipeline: Understand â†’ Plan â†’ Implement â†’ Secure â†’ Test â†’ Optimize â†’ Deliver
- Anti-Hallucination Protocol with 5 strict rules
- Token Efficiency Rules that cut verbosity by ~40%
## Demo Flow (8 Minutes)
1. **[1 min]** Show the problem: search for a scholarship across 5 different government sites
2. **[2 min]** Run the agent pipeline â€” show the Rich terminal output with progress
3. **[2 min]** Walk through the organized folder structure â€” open a scheme folder
4. **[1 min]** Show the React dashboard with real-time stats
5. **[1 min]** Demo the OpenClaw skill integration
6. **[1 min]** Show the Super Agent Prompt and how it eliminates LLM errors
## Team Members & Roles Simulated
Every agent in our system maps to a real product team role:
- **Orchestrator** â†’ CEO (strategic coordination)
- **Discovery Crawler** â†’ Development Team (5 concurrent workers)
- **Classification Agent** â†’ Business Analyst (domain understanding)
- **Storage Agent** â†’ Project Manager (organization & delivery)
- **Dedup Agent** â†’ QA/Testing (quality assurance)
- **Report Generator** â†’ Growth/Marketing (data presentation)
- **Super Prompt** â†’ The entire team's collective intelligence, codified
## Impact
If deployed as a public service, this system could help:
- **Students** find scholarships they didn't know existed
- **Entrepreneurs** discover startup funding across all states
- **NGOs** identify welfare schemes for their beneficiaries
- **Government** identify gaps and overlaps in scheme coverage
