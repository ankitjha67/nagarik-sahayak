import { useState, useEffect, useCallback } from "react";
import { AppHeader } from "../components/AppHeader";
import { BottomNav } from "../components/BottomNav";
import { Sidebar } from "../components/Sidebar";
import {
  getDiscoveryStatus, triggerDiscoveryCrawl, getDiscoveryPortals,
  getPortalHealth, getDiscoveryStats, downloadSchemesExcel,
  getNotificationConfig,
} from "../lib/api";
import { Badge } from "../components/ui/badge";
import {
  Activity, AlertCircle, CheckCircle2, ChevronRight, Clock,
  Download, Globe, Loader2, Play, RefreshCw, Search, Server,
  Shield, XCircle, Zap, BarChart3,
} from "lucide-react";

const CIRCUIT_STYLES = {
  closed: { bg: "bg-green-50", text: "text-green-700", icon: CheckCircle2, label: "Healthy" },
  open: { bg: "bg-red-50", text: "text-red-700", icon: XCircle, label: "Down" },
  half_open: { bg: "bg-yellow-50", text: "text-yellow-700", icon: AlertCircle, label: "Testing" },
};

export default function DiscoveryPage({ language = "hi" }) {
  const [tab, setTab] = useState("overview"); // overview | portals | health
  const [crawlStatus, setCrawlStatus] = useState(null);
  const [portals, setPortals] = useState([]);
  const [health, setHealth] = useState([]);
  const [stats, setStats] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [crawling, setCrawling] = useState(false);

  const isHindi = language === "hi";

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [statusRes, statsRes] = await Promise.all([
        getDiscoveryStatus().catch(() => ({ data: {} })),
        getDiscoveryStats().catch(() => ({ data: {} })),
      ]);
      setCrawlStatus(statusRes.data);
      setStats(statsRes.data);
      setCrawling(statusRes.data?.status === "running");
    } catch (e) {}
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    if (tab === "portals" && portals.length === 0) {
      getDiscoveryPortals().then(r => setPortals(r.data.portals || [])).catch(() => {});
    }
    if (tab === "health") {
      getPortalHealth().then(r => setHealth(r.data.portals || [])).catch(() => {});
    }
  }, [tab]);

  // Auto-refresh while crawling
  useEffect(() => {
    if (!crawling) return;
    const interval = setInterval(async () => {
      try {
        const res = await getDiscoveryStatus();
        setCrawlStatus(res.data);
        if (res.data.status !== "running") {
          setCrawling(false);
          loadData();
        }
      } catch (e) {}
    }, 3000);
    return () => clearInterval(interval);
  }, [crawling, loadData]);

  const handleStartCrawl = async () => {
    try {
      await triggerDiscoveryCrawl();
      setCrawling(true);
      setCrawlStatus(prev => ({ ...prev, status: "running" }));
    } catch (e) {
      if (e.response?.status === 409) {
        setCrawling(true);
      }
    }
  };

  const handleDownloadExcel = async () => {
    try {
      const res = await downloadSchemesExcel();
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `GovScheme_Report_${new Date().toISOString().slice(0,10)}.xlsx`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) {}
  };

  return (
    <div data-testid="discovery-page" className="min-h-screen bg-gray-50 pb-20">
      <AppHeader
        title={isHindi ? "खोज डैशबोर्ड" : "Discovery Dashboard"}
        onMenuClick={() => setSidebarOpen(true)}
      />
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="max-w-md mx-auto px-4 pt-4">
        {/* Tab Bar */}
        <div className="flex gap-1 bg-white rounded-xl p-1 border border-gray-100 mb-4">
          {[
            { key: "overview", label: isHindi ? "सारांश" : "Overview", icon: BarChart3 },
            { key: "portals", label: isHindi ? "पोर्टल" : "Portals", icon: Globe },
            { key: "health", label: isHindi ? "स्वास्थ्य" : "Health", icon: Activity },
          ].map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                tab === key
                  ? "bg-[#000080] text-white shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>

        {/* Overview Tab */}
        {tab === "overview" && (
          <div className="space-y-4 animate-fade-in-up">
            {/* Crawl Status Card */}
            <div className="bg-white rounded-xl p-5 border border-gray-100">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-[#000080] font-['Mukta']">
                  {isHindi ? "क्रॉल स्थिति" : "Crawl Status"}
                </h3>
                {crawlStatus?.status === "running" ? (
                  <Badge className="bg-orange-100 text-orange-700 text-[10px] animate-pulse">
                    <Loader2 size={10} className="mr-1 animate-spin" />
                    {isHindi ? "चल रहा है" : "Running"}
                  </Badge>
                ) : crawlStatus?.status === "completed" ? (
                  <Badge className="bg-green-100 text-green-700 text-[10px]">
                    <CheckCircle2 size={10} className="mr-1" />
                    {isHindi ? "पूरा हुआ" : "Completed"}
                  </Badge>
                ) : (
                  <Badge className="bg-gray-100 text-gray-600 text-[10px]">
                    {isHindi ? "निष्क्रिय" : "Idle"}
                  </Badge>
                )}
              </div>

              {crawlStatus?.status === "running" && (
                <div className="mb-3 space-y-1">
                  {crawlStatus.current_portal && (
                    <p className="text-xs text-gray-600">
                      <Globe size={11} className="inline mr-1" />
                      {crawlStatus.current_portal}
                    </p>
                  )}
                  <p className="text-xs text-gray-500">
                    {isHindi ? "योजनाएं मिलीं:" : "Schemes found:"} {crawlStatus.schemes_found} |
                    {" "}{isHindi ? "पोर्टल:" : "Portals:"} {crawlStatus.portals_crawled}
                  </p>
                </div>
              )}

              {crawlStatus?.status === "completed" && (
                <div className="grid grid-cols-3 gap-2 mb-3">
                  <div className="bg-[#FFF0E0] rounded-lg p-2 text-center">
                    <p className="text-lg font-bold text-[#FF9933]">{crawlStatus.schemes_found}</p>
                    <p className="text-[9px] text-gray-600">{isHindi ? "मिलीं" : "Found"}</p>
                  </div>
                  <div className="bg-[#E6F4EA] rounded-lg p-2 text-center">
                    <p className="text-lg font-bold text-[#138808]">{crawlStatus.schemes_new}</p>
                    <p className="text-[9px] text-gray-600">{isHindi ? "नई" : "New"}</p>
                  </div>
                  <div className="bg-[#E8EAF6] rounded-lg p-2 text-center">
                    <p className="text-lg font-bold text-[#000080]">{crawlStatus.schemes_updated}</p>
                    <p className="text-[9px] text-gray-600">{isHindi ? "अपडेट" : "Updated"}</p>
                  </div>
                </div>
              )}

              <div className="flex gap-2">
                <button
                  onClick={handleStartCrawl}
                  disabled={crawling}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2.5 bg-[#FF9933] text-white rounded-xl text-xs font-semibold disabled:opacity-50 hover:bg-[#E68A2E] transition-colors"
                >
                  {crawling ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                  {crawling ? (isHindi ? "चल रहा है..." : "Crawling...") : (isHindi ? "क्रॉल शुरू करें" : "Start Crawl")}
                </button>
                <button
                  onClick={handleDownloadExcel}
                  className="flex items-center justify-center gap-1.5 px-4 py-2.5 bg-[#000080] text-white rounded-xl text-xs font-semibold hover:bg-[#000060] transition-colors"
                >
                  <Download size={14} />
                  Excel
                </button>
              </div>
            </div>

            {/* Stats Cards */}
            {stats && !stats.error && (
              <>
                <div className="bg-white rounded-xl p-5 border border-gray-100">
                  <h3 className="text-sm font-bold text-[#000080] font-['Mukta'] mb-3">
                    {isHindi ? "योजना डेटाबेस" : "Scheme Database"}
                  </h3>
                  <div className="text-center mb-3">
                    <p className="text-3xl font-bold text-[#FF9933]">{stats.total_schemes}</p>
                    <p className="text-xs text-gray-500 font-['Mukta']">{isHindi ? "कुल योजनाएं" : "Total Schemes"}</p>
                  </div>

                  {/* By Level */}
                  {stats.by_level && (
                    <div className="flex gap-2 justify-center mb-3">
                      {Object.entries(stats.by_level).map(([level, count]) => (
                        <div key={level} className="bg-gray-50 rounded-lg px-3 py-1.5 text-center">
                          <p className="text-sm font-bold text-[#000080]">{count}</p>
                          <p className="text-[9px] text-gray-500">{level}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* By Sector */}
                {stats.by_sector && Object.keys(stats.by_sector).length > 0 && (
                  <div className="bg-white rounded-xl p-5 border border-gray-100">
                    <h3 className="text-sm font-bold text-[#000080] font-['Mukta'] mb-3">
                      {isHindi ? "क्षेत्र अनुसार" : "By Sector"}
                    </h3>
                    <div className="space-y-1.5">
                      {Object.entries(stats.by_sector)
                        .sort(([, a], [, b]) => b - a)
                        .slice(0, 10)
                        .map(([sector, count]) => (
                          <div key={sector} className="flex items-center justify-between">
                            <span className="text-[11px] text-gray-700 font-['Nunito']">{sector.replace(/_/g, " ")}</span>
                            <div className="flex items-center gap-2">
                              <div className="w-20 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-[#FF9933] rounded-full"
                                  style={{ width: `${Math.min(100, (count / (stats.total_schemes || 1)) * 100)}%` }}
                                />
                              </div>
                              <span className="text-[11px] font-bold text-gray-600 w-5 text-right">{count}</span>
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Portals Tab */}
        {tab === "portals" && (
          <div className="space-y-3 animate-fade-in-up">
            <p className="text-xs text-gray-500 font-['Nunito'] mb-2">
              {portals.length} {isHindi ? "कॉन्फ़िगर किए गए पोर्टल" : "configured portals"}
            </p>
            {portals.map((portal) => (
              <div
                key={portal.name}
                className="bg-white rounded-xl p-4 border border-gray-100 flex items-center gap-3"
              >
                <div className="w-9 h-9 rounded-lg bg-[#F0F0F8] flex items-center justify-center flex-shrink-0">
                  <Globe size={16} className="text-[#000080]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-800 font-['Nunito']">
                    {portal.name.replace(/_/g, " ")}
                  </p>
                  <p className="text-[10px] text-gray-400 truncate">{portal.base_url}</p>
                  <div className="flex gap-1.5 mt-1">
                    <Badge className="bg-blue-50 text-blue-700 text-[9px] px-1.5 py-0">
                      {portal.level}
                    </Badge>
                    <Badge className="bg-gray-50 text-gray-600 text-[9px] px-1.5 py-0">
                      {portal.crawl_strategy}
                    </Badge>
                    {portal.state && (
                      <Badge className="bg-green-50 text-green-700 text-[9px] px-1.5 py-0">
                        {portal.state}
                      </Badge>
                    )}
                  </div>
                </div>
                <div className="flex-shrink-0">
                  <span className="text-xs text-gray-400">P{portal.priority}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Health Tab */}
        {tab === "health" && (
          <div className="space-y-3 animate-fade-in-up">
            {health.length === 0 ? (
              <div className="bg-white rounded-xl p-8 border border-gray-100 text-center">
                <Activity size={32} className="text-gray-300 mx-auto mb-3" />
                <p className="text-sm text-gray-500 font-['Nunito']">
                  {isHindi ? "कोई स्वास्थ्य डेटा नहीं" : "No health data yet. Run a crawl first."}
                </p>
              </div>
            ) : (
              health.map((portal) => {
                const circuit = CIRCUIT_STYLES[portal.circuit_state] || CIRCUIT_STYLES.closed;
                const CircuitIcon = circuit.icon;
                const successRate = portal.total_requests
                  ? Math.round((portal.total_successes / portal.total_requests) * 100)
                  : 0;
                return (
                  <div
                    key={portal.portal_name}
                    className={`${circuit.bg} rounded-xl p-4 border border-gray-100`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <CircuitIcon size={16} className={circuit.text} />
                        <span className="text-sm font-semibold text-gray-800 font-['Nunito']">
                          {portal.portal_name.replace(/_/g, " ")}
                        </span>
                      </div>
                      <Badge className={`${circuit.bg} ${circuit.text} text-[10px]`}>
                        {circuit.label}
                      </Badge>
                    </div>
                    <div className="grid grid-cols-4 gap-2 text-center">
                      <div>
                        <p className="text-sm font-bold text-gray-800">{portal.total_requests}</p>
                        <p className="text-[9px] text-gray-500">Requests</p>
                      </div>
                      <div>
                        <p className="text-sm font-bold text-green-700">{successRate}%</p>
                        <p className="text-[9px] text-gray-500">Success</p>
                      </div>
                      <div>
                        <p className="text-sm font-bold text-gray-800">{Math.round(portal.avg_response_time_ms)}ms</p>
                        <p className="text-[9px] text-gray-500">Avg Time</p>
                      </div>
                      <div>
                        <p className="text-sm font-bold text-[#FF9933]">{portal.schemes_extracted}</p>
                        <p className="text-[9px] text-gray-500">Schemes</p>
                      </div>
                    </div>
                    {portal.last_failure_reason && (
                      <p className="text-[10px] text-red-600 mt-2 truncate">
                        Last error: {portal.last_failure_reason}
                      </p>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>

      <BottomNav />
    </div>
  );
}
