import { useState, useEffect } from "react";
import { AppHeader } from "../components/AppHeader";
import { BottomNav } from "../components/BottomNav";
import { Sidebar } from "../components/Sidebar";
import {
  getSchemes, getV2Schemes, getDiscoveredSchemes, downloadSchemesExcel,
  getUserFullProfile, screenAllSchemes,
} from "../lib/api";
import { Badge } from "../components/ui/badge";
import {
  Sprout, HeartPulse, Baby, ExternalLink, ChevronDown, ChevronUp,
  Users, IndianRupee, Home, GraduationCap, Rocket, Briefcase,
  Search, Download, Building2, CheckCircle2, XCircle, HelpCircle, Loader2,
} from "lucide-react";

// How an eligibility outcome is presented on a scheme card.
const ELIGIBILITY_BADGE = {
  approved: {
    icon: CheckCircle2, label: "आप पात्र हैं", labelEn: "You qualify",
    cls: "bg-green-50 text-green-700 border-green-200",
  },
  approved_with_review: {
    icon: CheckCircle2, label: "आप पात्र हैं", labelEn: "You qualify",
    cls: "bg-green-50 text-green-700 border-green-200",
  },
  blocked_not_eligible: {
    icon: XCircle, label: "पात्र नहीं", labelEn: "Not eligible",
    cls: "bg-red-50 text-red-700 border-red-200",
  },
  blocked_invalid_data: {
    icon: XCircle, label: "विवरण जाँचें", labelEn: "Check your details",
    cls: "bg-red-50 text-red-700 border-red-200",
  },
  incomplete: {
    icon: HelpCircle, label: "जानकारी अधूरी", labelEn: "More info needed",
    cls: "bg-amber-50 text-amber-700 border-amber-200",
  },
};

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

export default function SchemesPage({ userId, language = "hi" }) {
  const [schemes, setSchemes] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  // scheme name -> {outcome, reasons_hi, reasons_en, benefit}
  const [eligibility, setEligibility] = useState({});
  const [checkingEligibility, setCheckingEligibility] = useState(false);
  const [onlyEligible, setOnlyEligible] = useState(false);

  // Screen the citizen's stored profile against every scheme so the list can
  // answer the question people actually have — "what am I entitled to?" —
  // instead of leaving them to read criteria and guess.
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    setCheckingEligibility(true);
    getUserFullProfile(userId)
      .then((r) => {
        const profile = r.data?.fullProfile || {};
        if (!Object.keys(profile).length) return null;
        return screenAllSchemes(profile, userId);
      })
      .then((res) => {
        if (cancelled || !res) return;
        const map = {};
        for (const group of ["eligible", "not_eligible", "needs_more_info"]) {
          for (const item of res.data[group] || []) map[item.scheme] = item;
        }
        setEligibility(map);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setCheckingEligibility(false); });
    return () => { cancelled = true; };
  }, [userId]);

  useEffect(() => {
    // Load curated (V1+V2) and crawler-discovered (V3) schemes, merge results
    Promise.all([
      getSchemes().catch(() => ({ data: [] })),
      getV2Schemes().catch(() => ({ data: { schemes: [] } })),
      getDiscoveredSchemes({ limit: 100 }).catch(() => ({ data: { schemes: [] } })),
    ]).then(([v1Res, v2Res, v3Res]) => {
      const v1 = v1Res.data || [];
      const v2 = v2Res.data.schemes || [];
      const v3 = v3Res.data.schemes || [];
      // Merge: V2 (curated, has forms) first, then V1 not in V2, then V3 discovered
      const v2Names = new Set(v2.map(s => s.name));
      const curatedNames = new Set([...v2Names, ...v1.map(s => s.title)]);
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
        ...v3
          .filter(s => s.name && !curatedNames.has(s.name))
          .map(s => ({
            id: s.scheme_id,
            title: s.name,
            title_hi: s.name,
            description: s.summary || "",
            description_hi: s.summary || "",
            eligibility: s.eligibility || "",
            eligibility_hi: s.eligibility || "",
            benefits: s.benefit_amount || "",
            benefits_hi: s.benefit_amount || "",
            category: (s.sector || "general").toLowerCase(),
            officialWebsite: s.official_website || s.detail_url || "",
            discovered: true,
            level: s.level,
            state: s.state,
          })),
      ];
      setSchemes(merged);
    });
  }, []);

  const isHindi = language === "hi";

  // Filter schemes
  const eligibleOutcomes = new Set(["approved", "approved_with_review"]);
  const eligibleCount = Object.values(eligibility)
    .filter(e => eligibleOutcomes.has(e.outcome)).length;

  const filteredSchemes = schemes.filter(s => {
    if (onlyEligible) {
      const e = eligibility[s.title];
      if (!e || !eligibleOutcomes.has(e.outcome)) return false;
    }
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

        {/* Eligibility summary — what this citizen actually qualifies for */}
        {checkingEligibility ? (
          <div className="bg-white rounded-xl p-4 border border-gray-100 mb-5 flex items-center gap-2">
            <Loader2 size={14} className="animate-spin text-[#FF9933]" />
            <span className="text-xs text-gray-500 font-['Nunito']">
              {isHindi ? "आपकी पात्रता जाँची जा रही है…" : "Checking your eligibility…"}
            </span>
          </div>
        ) : Object.keys(eligibility).length > 0 ? (
          <button
            onClick={() => setOnlyEligible(v => !v)}
            className={`w-full text-left rounded-xl p-4 border mb-5 transition-all animate-fade-in-up ${
              onlyEligible
                ? "bg-green-50 border-green-300"
                : "bg-[#E6F4EA] border-green-100 hover:border-green-300"
            }`}
          >
            <div className="flex items-center gap-2">
              <CheckCircle2 size={16} className="text-[#138808] flex-shrink-0" />
              <p className="text-sm text-[#000080] font-['Mukta'] font-semibold flex-1">
                {isHindi
                  ? `आप ${eligibleCount} योजनाओं के लिए पात्र हैं`
                  : `You qualify for ${eligibleCount} scheme${eligibleCount === 1 ? "" : "s"}`}
              </p>
            </div>
            <p className="text-[11px] text-gray-600 font-['Nunito'] mt-0.5 ml-6">
              {onlyEligible
                ? (isHindi ? "सभी योजनाएं देखने के लिए टैप करें" : "Tap to show all schemes")
                : (isHindi ? "केवल पात्र योजनाएं देखने के लिए टैप करें" : "Tap to show only these")}
            </p>
          </button>
        ) : (
          <div className="bg-[#FFF0E0] rounded-xl p-4 border border-orange-100 mb-5 animate-fade-in-up">
            <p className="text-sm text-[#000080] font-['Mukta'] font-semibold">
              {isHindi
                ? `${filteredSchemes.length} योजनाओं की जानकारी देखें और अपनी पात्रता जांचें।`
                : `Browse ${filteredSchemes.length} schemes below and check your eligibility.`}
            </p>
          </div>
        )}

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
                    <div className="flex gap-2 mt-2 flex-wrap">
                      <Badge
                        className={`${colors.bg} ${colors.text} ${colors.border} border text-[10px] font-semibold px-2 py-0.5`}
                      >
                        {scheme.category}
                      </Badge>
                      {(() => {
                        const e = eligibility[scheme.title];
                        const badge = e && ELIGIBILITY_BADGE[e.outcome];
                        if (!badge) return null;
                        const BadgeIcon = badge.icon;
                        return (
                          <Badge className={`${badge.cls} border text-[10px] font-semibold px-2 py-0.5 flex items-center gap-1`}>
                            <BadgeIcon size={10} />
                            {isHindi ? badge.label : badge.labelEn}
                          </Badge>
                        );
                      })()}
                      {scheme.discovered && (
                        <Badge className="bg-indigo-50 text-indigo-700 border-indigo-200 border text-[10px] font-semibold px-2 py-0.5">
                          {isHindi ? "खोजी गई" : "Discovered"}
                        </Badge>
                      )}
                      {scheme.state && (
                        <Badge className="bg-gray-50 text-gray-600 border-gray-200 border text-[10px] font-semibold px-2 py-0.5">
                          {scheme.state.replace(/_/g, " ")}
                        </Badge>
                      )}
                    </div>
                  </div>
                  <div className="text-gray-400 mt-1">
                    {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                  </div>
                </button>

                {/* Expanded Content */}
                {isExpanded && (
                  <div className="px-5 pb-5 border-t border-gray-50 animate-fade-in-up">
                    {/* Why this citizen does or does not qualify. A bare verdict
                        is not actionable — the specific unmet condition is. */}
                    {(() => {
                      const e = eligibility[scheme.title];
                      if (!e) return null;
                      const reasons = (isHindi && e.reasons_hi?.length)
                        ? e.reasons_hi : (e.reasons_en || []);
                      const qualifies = ["approved", "approved_with_review"].includes(e.outcome);
                      if (qualifies) {
                        return (
                          <div className="mt-4 rounded-lg bg-green-50 border border-green-200 p-3">
                            <div className="flex items-center gap-1.5">
                              <CheckCircle2 size={13} className="text-green-600" />
                              <span className="text-[11px] font-bold text-green-800 font-['Mukta']">
                                {isHindi ? "आप इस योजना के लिए पात्र हैं" : "You qualify for this scheme"}
                              </span>
                            </div>
                            {e.benefit && (
                              <p className="text-[11px] text-green-700 font-['Nunito'] mt-1 ml-5">
                                {isHindi ? "लाभ: " : "Benefit: "}{e.benefit}
                              </p>
                            )}
                          </div>
                        );
                      }
                      if (!reasons.length) return null;
                      const isIncomplete = e.outcome === "incomplete";
                      return (
                        <div className={`mt-4 rounded-lg border p-3 ${
                          isIncomplete
                            ? "bg-amber-50 border-amber-200"
                            : "bg-red-50 border-red-200"}`}>
                          <div className="flex items-center gap-1.5 mb-1">
                            {isIncomplete
                              ? <HelpCircle size={13} className="text-amber-600" />
                              : <XCircle size={13} className="text-red-600" />}
                            <span className={`text-[11px] font-bold font-['Mukta'] ${
                              isIncomplete ? "text-amber-800" : "text-red-800"}`}>
                              {isIncomplete
                                ? (isHindi ? "और जानकारी चाहिए" : "More information needed")
                                : (isHindi ? "आप अभी पात्र नहीं हैं" : "You do not currently qualify")}
                            </span>
                          </div>
                          {reasons.map((r, i) => (
                            <p key={i} className={`text-[10px] font-['Nunito'] leading-snug ml-5 ${
                              isIncomplete ? "text-amber-700" : "text-red-700"}`}>
                              • {r}
                            </p>
                          ))}
                        </div>
                      );
                    })()}

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
