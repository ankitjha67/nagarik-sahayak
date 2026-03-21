import { useState, useEffect } from "react";
import { AppHeader } from "../components/AppHeader";
import { BottomNav } from "../components/BottomNav";
import { Sidebar } from "../components/Sidebar";
import { getSchemes, getV2Schemes, downloadSchemesExcel } from "../lib/api";
import { Badge } from "../components/ui/badge";
import {
  Sprout, HeartPulse, Baby, ExternalLink, ChevronDown, ChevronUp,
  Users, IndianRupee, Home, GraduationCap, Rocket, Briefcase,
  Search, Download, Filter, Building2,
} from "lucide-react";

const ICON_MAP = {
  sprout: Sprout,
  "heart-pulse": HeartPulse,
  baby: Baby,
  housing: Home,
  education: GraduationCap,
  agriculture: Sprout,
  health: HeartPulse,
  startup: Rocket,
  finance: Briefcase,
  general: Building2,
};

const CATEGORY_COLORS = {
  agriculture: { bg: "bg-green-50", text: "text-green-700", border: "border-green-200" },
  health: { bg: "bg-rose-50", text: "text-rose-700", border: "border-rose-200" },
  savings: { bg: "bg-purple-50", text: "text-purple-700", border: "border-purple-200" },
  housing: { bg: "bg-orange-50", text: "text-orange-700", border: "border-orange-200" },
  education: { bg: "bg-blue-50", text: "text-blue-700", border: "border-blue-200" },
  startup: { bg: "bg-indigo-50", text: "text-indigo-700", border: "border-indigo-200" },
  finance: { bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200" },
  general: { bg: "bg-gray-50", text: "text-gray-700", border: "border-gray-200" },
};

export default function SchemesPage({ language = "hi" }) {
  const [schemes, setSchemes] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");

  useEffect(() => {
    // Load from both V1 and V2 endpoints, merge results
    Promise.all([
      getSchemes().catch(() => ({ data: [] })),
      getV2Schemes().catch(() => ({ data: { schemes: [] } })),
    ]).then(([v1Res, v2Res]) => {
      const v1 = v1Res.data || [];
      const v2 = v2Res.data.schemes || [];
      // Merge: V2 data takes priority, add V1 entries not in V2
      const v2Names = new Set(v2.map(s => s.name));
      const merged = [
        ...v2.map(s => ({
          ...s,
          title: s.name,
          title_hi: s.nameHindi || s.name,
          description: s.description || "",
          description_hi: s.descriptionHindi || s.description || "",
          eligibility: s.eligibilityCriteriaText || "",
          eligibility_hi: s.eligibilityCriteriaText || "",
          category: s.category || "general",
        })),
        ...v1.filter(s => !v2Names.has(s.title)),
      ];
      setSchemes(merged);
    });
  }, []);

  const isHindi = language === "hi";

  // Filter schemes
  const filteredSchemes = schemes.filter(s => {
    if (categoryFilter && s.category !== categoryFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const searchable = `${s.title || ""} ${s.title_hi || ""} ${s.description || ""} ${s.category || ""}`.toLowerCase();
      if (!searchable.includes(q)) return false;
    }
    return true;
  });

  const categories = [...new Set(schemes.map(s => s.category).filter(Boolean))];

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
    <div data-testid="schemes-page" className="min-h-screen bg-gray-50 pb-20">
      <AppHeader title={isHindi ? "सरकारी योजनाएं" : "Government Schemes"} onMenuClick={() => setSidebarOpen(true)} />
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="max-w-md mx-auto px-4 pt-4">
        {/* Search + Download */}
        <div className="flex gap-2 mb-3 animate-fade-in-up">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={isHindi ? "योजना खोजें..." : "Search schemes..."}
              className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-gray-200 text-sm font-['Nunito'] focus:border-[#FF9933] focus:ring-1 focus:ring-[#FF9933] outline-none"
            />
          </div>
          <button
            onClick={handleDownloadExcel}
            className="flex items-center gap-1 px-3 py-2.5 bg-[#000080] text-white rounded-xl text-xs font-semibold hover:bg-[#000060] transition-colors"
            aria-label="Download Excel Report"
          >
            <Download size={14} />
          </button>
        </div>

        {/* Category Filter Chips */}
        {categories.length > 1 && (
          <div className="flex gap-1.5 overflow-x-auto pb-2 mb-3 no-scrollbar animate-fade-in-up">
            <button
              onClick={() => setCategoryFilter("")}
              className={`flex-shrink-0 px-3 py-1.5 rounded-full text-[11px] font-semibold transition-all ${
                !categoryFilter
                  ? "bg-[#FF9933] text-white"
                  : "bg-white text-gray-600 border border-gray-200"
              }`}
            >
              {isHindi ? "सभी" : "All"} ({schemes.length})
            </button>
            {categories.map(cat => (
              <button
                key={cat}
                onClick={() => setCategoryFilter(cat === categoryFilter ? "" : cat)}
                className={`flex-shrink-0 px-3 py-1.5 rounded-full text-[11px] font-semibold transition-all ${
                  categoryFilter === cat
                    ? "bg-[#FF9933] text-white"
                    : "bg-white text-gray-600 border border-gray-200"
                }`}
              >
                {cat} ({schemes.filter(s => s.category === cat).length})
              </button>
            ))}
          </div>
        )}

        {/* Info Banner */}
        <div className="bg-[#FFF0E0] rounded-xl p-4 border border-orange-100 mb-5 animate-fade-in-up">
          <p className="text-sm text-[#000080] font-['Mukta'] font-semibold">
            {isHindi
              ? `${filteredSchemes.length} योजनाओं की जानकारी देखें और अपनी पात्रता जांचें।`
              : `Browse ${filteredSchemes.length} schemes below and check your eligibility.`}
          </p>
        </div>

        {/* Scheme Cards */}
        <div className="space-y-4 stagger-children">
          {filteredSchemes.map((scheme) => {
            const isExpanded = expandedId === scheme.id;
            const IconComp = ICON_MAP[scheme.category] || ICON_MAP[scheme.icon] || Sprout;
            const colors = CATEGORY_COLORS[scheme.category] || CATEGORY_COLORS.general;

            return (
              <div
                key={scheme.id}
                data-testid={`scheme-detail-${scheme.id}`}
                className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden transition-all hover:shadow-md"
              >
                {/* Header */}
                <button
                  data-testid={`scheme-toggle-${scheme.id}`}
                  onClick={() => setExpandedId(isExpanded ? null : scheme.id)}
                  className="w-full p-5 text-left flex items-start gap-3"
                >
                  <div className={`w-10 h-10 rounded-xl ${colors.bg} flex items-center justify-center flex-shrink-0`}>
                    <IconComp size={20} className={colors.text} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-base font-bold text-[#000080] font-['Mukta'] leading-tight">
                      {isHindi ? scheme.title_hi : scheme.title}
                    </h3>
                    <p className="text-sm text-gray-500 font-['Nunito'] mt-1 line-clamp-2">
                      {isHindi ? scheme.description_hi : scheme.description}
                    </p>
                    <div className="flex gap-2 mt-2">
                      <Badge
                        className={`${colors.bg} ${colors.text} ${colors.border} border text-[10px] font-semibold px-2 py-0.5`}
                      >
                        {scheme.category}
                      </Badge>
                    </div>
                  </div>
                  <div className="text-gray-400 mt-1">
                    {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                  </div>
                </button>

                {/* Expanded Content */}
                {isExpanded && (
                  <div className="px-5 pb-5 border-t border-gray-50 animate-fade-in-up">
                    {/* Eligibility */}
                    <div className="mt-4">
                      <div className="flex items-center gap-2 mb-2">
                        <Users size={16} className="text-[#000080]" />
                        <span className="text-sm font-bold text-[#000080] font-['Mukta']">
                          {isHindi ? "पात्रता" : "Eligibility"}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 font-['Nunito'] leading-relaxed pl-6">
                        {isHindi ? scheme.eligibility_hi : scheme.eligibility}
                      </p>
                    </div>

                    {/* Benefits */}
                    <div className="mt-4">
                      <div className="flex items-center gap-2 mb-2">
                        <IndianRupee size={16} className="text-[#138808]" />
                        <span className="text-sm font-bold text-[#138808] font-['Mukta']">
                          {isHindi ? "लाभ" : "Benefits"}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 font-['Nunito'] leading-relaxed pl-6">
                        {isHindi ? scheme.benefits_hi : scheme.benefits}
                      </p>
                    </div>

                    {/* Action Links */}
                    <div className="flex gap-2 mt-4 flex-wrap">
                      {scheme.pdf_url && (
                        <a
                          href={scheme.pdf_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          data-testid={`scheme-pdf-${scheme.id}`}
                          className="inline-flex items-center gap-2 px-4 py-2 bg-[#FFF0E0] rounded-full text-sm font-semibold text-[#000080] hover:bg-[#FFE4C4] transition-colors"
                        >
                          <ExternalLink size={14} />
                          {isHindi ? "दिशानिर्देश (PDF)" : "Guidelines (PDF)"}
                        </a>
                      )}
                      {scheme.officialWebsite && (
                        <a
                          href={scheme.officialWebsite}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-2 px-4 py-2 bg-[#E8EAF6] rounded-full text-sm font-semibold text-[#000080] hover:bg-[#C5CAE9] transition-colors"
                        >
                          <ExternalLink size={14} />
                          {isHindi ? "आधिकारिक वेबसाइट" : "Official Website"}
                        </a>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <BottomNav />
    </div>
  );
}
