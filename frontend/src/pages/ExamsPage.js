import { useState, useEffect } from "react";
import { AppHeader } from "../components/AppHeader";
import { BottomNav } from "../components/BottomNav";
import { Sidebar } from "../components/Sidebar";
import { getExamAlerts, getExams, getExamStats } from "../lib/api";
import { Badge } from "../components/ui/badge";
import {
  AlertTriangle, Bell, Calendar, ChevronDown, ChevronUp,
  Clock, ExternalLink, FileText, GraduationCap, Search,
  Shield, Users, TrendingUp, Download,
} from "lucide-react";

const URGENCY_STYLES = {
  critical: { bg: "bg-red-50", border: "border-red-200", text: "text-red-700", badge: "bg-red-100 text-red-800" },
  high: { bg: "bg-orange-50", border: "border-orange-200", text: "text-orange-700", badge: "bg-orange-100 text-orange-800" },
  medium: { bg: "bg-yellow-50", border: "border-yellow-200", text: "text-yellow-700", badge: "bg-yellow-100 text-yellow-800" },
  low: { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-700", badge: "bg-blue-100 text-blue-800" },
};

const ALERT_ICONS = {
  deadline: Clock,
  admit_card: FileText,
  result: TrendingUp,
  new: Bell,
};

const CATEGORY_COLORS = {
  Civil_Services: "bg-purple-100 text-purple-800",
  Banking: "bg-green-100 text-green-800",
  Railway: "bg-orange-100 text-orange-800",
  Defence: "bg-red-100 text-red-800",
  SSC: "bg-blue-100 text-blue-800",
  Police: "bg-gray-100 text-gray-800",
  Engineering: "bg-indigo-100 text-indigo-800",
  Medical: "bg-pink-100 text-pink-800",
  Teaching: "bg-teal-100 text-teal-800",
  State_PSC: "bg-amber-100 text-amber-800",
};

export default function ExamsPage({ language = "hi" }) {
  const [alerts, setAlerts] = useState([]);
  const [exams, setExams] = useState([]);
  const [stats, setStats] = useState(null);
  const [tab, setTab] = useState("alerts"); // alerts | browse | stats
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [expandedId, setExpandedId] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const isHindi = language === "hi";

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (tab === "browse") loadExams();
    if (tab === "stats") loadStats();
  }, [tab, search, categoryFilter]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [alertsRes, statsRes] = await Promise.all([
        getExamAlerts(30).catch(() => ({ data: { alerts: [] } })),
        getExamStats().catch(() => ({ data: {} })),
      ]);
      setAlerts(alertsRes.data.alerts || []);
      setStats(statsRes.data);
    } catch (e) {}
    setLoading(false);
  };

  const loadExams = async () => {
    try {
      const res = await getExams({
        search, category: categoryFilter, limit: 50,
      });
      setExams(res.data.exams || []);
    } catch (e) {}
  };

  const loadStats = async () => {
    try {
      const res = await getExamStats();
      setStats(res.data);
    } catch (e) {}
  };

  return (
    <div data-testid="exams-page" className="min-h-screen bg-gray-50 pb-20">
      <AppHeader
        title={isHindi ? "सरकारी परीक्षाएं" : "Government Exams"}
        onMenuClick={() => setSidebarOpen(true)}
      />
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="max-w-md mx-auto px-4 pt-4">
        {/* Tab Bar */}
        <div className="flex gap-1 bg-white rounded-xl p-1 border border-gray-100 mb-4">
          {[
            { key: "alerts", label: isHindi ? "अलर्ट" : "Alerts", icon: Bell },
            { key: "browse", label: isHindi ? "परीक्षाएं" : "Browse", icon: GraduationCap },
            { key: "stats", label: isHindi ? "आंकड़े" : "Stats", icon: TrendingUp },
          ].map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                tab === key
                  ? "bg-[#FF9933] text-white shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>

        {/* Alerts Tab */}
        {tab === "alerts" && (
          <div className="space-y-3 animate-fade-in-up">
            {/* Summary Cards */}
            {stats && (
              <div className="grid grid-cols-3 gap-2 mb-2">
                <div className="bg-white rounded-xl p-3 border border-gray-100 text-center">
                  <p className="text-lg font-bold text-[#000080]">{stats.total_exams || 0}</p>
                  <p className="text-[10px] text-gray-500 font-['Mukta']">
                    {isHindi ? "कुल परीक्षाएं" : "Total Exams"}
                  </p>
                </div>
                <div className="bg-white rounded-xl p-3 border border-gray-100 text-center">
                  <p className="text-lg font-bold text-[#FF9933]">{stats.upcoming_deadlines_30d || 0}</p>
                  <p className="text-[10px] text-gray-500 font-['Mukta']">
                    {isHindi ? "30 दिन में" : "In 30 Days"}
                  </p>
                </div>
                <div className="bg-white rounded-xl p-3 border border-gray-100 text-center">
                  <p className="text-lg font-bold text-[#138808]">{alerts.length}</p>
                  <p className="text-[10px] text-gray-500 font-['Mukta']">
                    {isHindi ? "अलर्ट" : "Alerts"}
                  </p>
                </div>
              </div>
            )}

            {loading ? (
              <div className="text-center py-8 text-gray-400">Loading...</div>
            ) : alerts.length === 0 ? (
              <div className="bg-white rounded-xl p-8 border border-gray-100 text-center">
                <Bell size={32} className="text-gray-300 mx-auto mb-3" />
                <p className="text-sm text-gray-500 font-['Nunito']">
                  {isHindi ? "कोई अलर्ट नहीं" : "No alerts right now"}
                </p>
              </div>
            ) : (
              alerts.map((alert, idx) => {
                const style = URGENCY_STYLES[alert.urgency] || URGENCY_STYLES.low;
                const AlertIcon = ALERT_ICONS[alert.type] || Bell;
                return (
                  <div
                    key={idx}
                    className={`${style.bg} ${style.border} border rounded-xl p-4 transition-all`}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`w-9 h-9 rounded-lg ${style.badge} flex items-center justify-center flex-shrink-0`}>
                        <AlertIcon size={16} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-bold text-gray-800 font-['Mukta'] leading-tight">
                          {alert.exam_name}
                        </p>
                        <p className="text-xs text-gray-600 mt-0.5">
                          {alert.conducting_body}
                        </p>
                        <div className="flex items-center gap-2 mt-2">
                          <Badge className={`${style.badge} text-[10px] px-2 py-0.5`}>
                            {isHindi ? alert.message_hi : alert.message_en}
                          </Badge>
                          {alert.days_left != null && (
                            <span className={`text-[10px] font-bold ${style.text}`}>
                              {alert.days_left}d
                            </span>
                          )}
                        </div>
                        {(alert.apply_url || alert.url) && (
                          <a
                            href={alert.apply_url || alert.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-2 inline-flex items-center gap-1 text-xs text-[#000080] font-semibold hover:underline"
                          >
                            <ExternalLink size={12} />
                            {isHindi ? "लिंक खोलें" : "Open Link"}
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* Browse Tab */}
        {tab === "browse" && (
          <div className="animate-fade-in-up">
            {/* Search */}
            <div className="relative mb-3">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={isHindi ? "परीक्षा खोजें..." : "Search exams..."}
                className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-gray-200 text-sm font-['Nunito'] focus:border-[#FF9933] focus:ring-1 focus:ring-[#FF9933] outline-none"
              />
            </div>

            {/* Category Filter */}
            <div className="flex gap-1.5 overflow-x-auto pb-2 mb-3 no-scrollbar">
              {["", "Civil_Services", "Banking", "SSC", "Railway", "Defence", "State_PSC"].map(
                (cat) => (
                  <button
                    key={cat}
                    onClick={() => setCategoryFilter(cat)}
                    className={`flex-shrink-0 px-3 py-1.5 rounded-full text-[11px] font-semibold transition-all ${
                      categoryFilter === cat
                        ? "bg-[#FF9933] text-white"
                        : "bg-white text-gray-600 border border-gray-200"
                    }`}
                  >
                    {cat || (isHindi ? "सभी" : "All")}
                  </button>
                )
              )}
            </div>

            {/* Exam List */}
            <div className="space-y-3">
              {exams.map((exam) => {
                const isExpanded = expandedId === exam.exam_id;
                const catColor = CATEGORY_COLORS[exam.category] || "bg-gray-100 text-gray-800";
                return (
                  <div
                    key={exam.exam_id}
                    className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden"
                  >
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : exam.exam_id)}
                      className="w-full p-4 text-left flex items-start gap-3"
                    >
                      <div className="w-9 h-9 rounded-lg bg-[#F0F0F8] flex items-center justify-center flex-shrink-0">
                        <GraduationCap size={16} className="text-[#000080]" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-bold text-[#000080] font-['Mukta'] leading-tight">
                          {exam.exam_name}
                        </p>
                        <p className="text-xs text-gray-500 mt-0.5">{exam.conducting_body}</p>
                        <div className="flex gap-1.5 mt-1.5 flex-wrap">
                          <Badge className={`${catColor} text-[10px] px-2 py-0.5`}>
                            {exam.category}
                          </Badge>
                          {exam.status && (
                            <Badge className="bg-blue-50 text-blue-700 text-[10px] px-2 py-0.5">
                              {exam.status}
                            </Badge>
                          )}
                          {exam.total_vacancies && (
                            <Badge className="bg-green-50 text-green-700 text-[10px] px-2 py-0.5">
                              <Users size={10} className="mr-0.5 inline" />
                              {exam.total_vacancies}
                            </Badge>
                          )}
                        </div>
                      </div>
                      {isExpanded ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
                    </button>

                    {isExpanded && (
                      <div className="px-4 pb-4 border-t border-gray-50 space-y-2 animate-fade-in-up">
                        {exam.application_start && (
                          <div className="flex items-center gap-2 text-xs text-gray-600 mt-2">
                            <Calendar size={12} />
                            <span>{isHindi ? "आवेदन:" : "Apply:"} {exam.application_start} — {exam.application_end || "TBD"}</span>
                          </div>
                        )}
                        {exam.qualification && (
                          <div className="flex items-center gap-2 text-xs text-gray-600">
                            <GraduationCap size={12} />
                            <span>{exam.qualification}</span>
                          </div>
                        )}
                        {exam.fee_general != null && (
                          <div className="flex items-center gap-2 text-xs text-gray-600">
                            <span>{isHindi ? "शुल्क:" : "Fee:"} General ₹{exam.fee_general} | SC/ST ₹{exam.fee_sc_st || "N/A"}</span>
                          </div>
                        )}
                        <div className="flex gap-2 mt-2 flex-wrap">
                          {exam.apply_url && (
                            <a href={exam.apply_url} target="_blank" rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 px-3 py-1.5 bg-[#FF9933] text-white rounded-full text-xs font-semibold">
                              <ExternalLink size={11} />
                              {isHindi ? "आवेदन करें" : "Apply"}
                            </a>
                          )}
                          {exam.admit_card_url && (
                            <a href={exam.admit_card_url} target="_blank" rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 px-3 py-1.5 bg-[#000080] text-white rounded-full text-xs font-semibold">
                              <FileText size={11} />
                              {isHindi ? "एडमिट कार्ड" : "Admit Card"}
                            </a>
                          )}
                          {exam.official_website && (
                            <a href={exam.official_website} target="_blank" rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 px-3 py-1.5 bg-gray-100 text-gray-700 rounded-full text-xs font-semibold">
                              <ExternalLink size={11} />
                              {isHindi ? "वेबसाइट" : "Website"}
                            </a>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
              {exams.length === 0 && (
                <div className="bg-white rounded-xl p-8 border border-gray-100 text-center">
                  <GraduationCap size={32} className="text-gray-300 mx-auto mb-3" />
                  <p className="text-sm text-gray-500 font-['Nunito']">
                    {isHindi ? "कोई परीक्षा नहीं मिली" : "No exams found"}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Stats Tab */}
        {tab === "stats" && stats && (
          <div className="space-y-4 animate-fade-in-up">
            {/* Overview */}
            <div className="bg-white rounded-xl p-5 border border-gray-100">
              <h3 className="text-sm font-bold text-[#000080] font-['Mukta'] mb-3">
                {isHindi ? "सारांश" : "Overview"}
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#FFF0E0] rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-[#FF9933]">{stats.total_exams || 0}</p>
                  <p className="text-[10px] text-gray-600 font-['Mukta']">{isHindi ? "कुल परीक्षाएं" : "Total Exams"}</p>
                </div>
                <div className="bg-[#E6F4EA] rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-[#138808]">{stats.upcoming_deadlines_30d || 0}</p>
                  <p className="text-[10px] text-gray-600 font-['Mukta']">{isHindi ? "आगामी डेडलाइन" : "Upcoming Deadlines"}</p>
                </div>
              </div>
            </div>

            {/* By Category */}
            {stats.by_category && Object.keys(stats.by_category).length > 0 && (
              <div className="bg-white rounded-xl p-5 border border-gray-100">
                <h3 className="text-sm font-bold text-[#000080] font-['Mukta'] mb-3">
                  {isHindi ? "श्रेणी अनुसार" : "By Category"}
                </h3>
                <div className="space-y-2">
                  {Object.entries(stats.by_category)
                    .sort(([, a], [, b]) => b - a)
                    .map(([cat, count]) => (
                      <div key={cat} className="flex items-center justify-between">
                        <span className="text-xs text-gray-700 font-['Nunito']">{cat.replace(/_/g, " ")}</span>
                        <div className="flex items-center gap-2">
                          <div className="w-24 h-2 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-[#FF9933] rounded-full"
                              style={{ width: `${Math.min(100, (count / (stats.total_exams || 1)) * 100)}%` }}
                            />
                          </div>
                          <span className="text-xs font-bold text-gray-600 w-6 text-right">{count}</span>
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* By Status */}
            {stats.by_status && Object.keys(stats.by_status).length > 0 && (
              <div className="bg-white rounded-xl p-5 border border-gray-100">
                <h3 className="text-sm font-bold text-[#000080] font-['Mukta'] mb-3">
                  {isHindi ? "स्थिति अनुसार" : "By Status"}
                </h3>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(stats.by_status).map(([status, count]) => (
                    <div key={status} className="bg-gray-50 rounded-lg px-3 py-2 text-center">
                      <p className="text-sm font-bold text-[#000080]">{count}</p>
                      <p className="text-[10px] text-gray-500">{status.replace(/_/g, " ")}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <BottomNav />
    </div>
  );
}
