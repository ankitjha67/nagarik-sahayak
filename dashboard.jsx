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
            ðŸ‡®ðŸ‡³ GovScheme SuperAgent
          </h1>
          <p style={{ color: "#64748B", margin: "4px 0 0", fontSize: 14 }}>
            OpenClaw Buildathon â€” Multi-Agent Government Scheme Discovery
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
          { label: "Total Schemes", value: data.totalSchemes, icon: "ðŸ“Š", color: "#38BDF8" },
          { label: "Central", value: data.central, icon: "ðŸ›ï¸", color: "#818CF8" },
          { label: "State", value: data.state, icon: "ðŸ—ºï¸", color: "#34D399" },
          { label: "Dedup Removed", value: data.duplicatesRemoved, icon: "ðŸ”", color: "#F97316" },
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
        {/* Right Panel â€” Scheme Browser */}
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
              {["ðŸŒ Discovery", "ðŸ” Dedup", "ðŸ“ Enrich", "ðŸ§  Classify", "ðŸ“ Store", "ðŸ“Š Report"].map((step, i) => (
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
                  {i < 5 && <span style={{ color: "#475569" }}>â†’</span>}
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
