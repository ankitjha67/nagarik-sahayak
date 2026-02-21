import { useState, useEffect } from "react";
import { AppHeader } from "../components/AppHeader";
import { BottomNav } from "../components/BottomNav";
import { getSchemes } from "../lib/api";
import { Badge } from "../components/ui/badge";
import { Sprout, HeartPulse, Baby, ExternalLink, ChevronDown, ChevronUp, Users, IndianRupee } from "lucide-react";

const ICON_MAP = {
  sprout: Sprout,
  "heart-pulse": HeartPulse,
  baby: Baby,
};

const CATEGORY_COLORS = {
  agriculture: { bg: "bg-green-50", text: "text-green-700", border: "border-green-200" },
  health: { bg: "bg-rose-50", text: "text-rose-700", border: "border-rose-200" },
  savings: { bg: "bg-purple-50", text: "text-purple-700", border: "border-purple-200" },
};

export default function SchemesPage({ language = "hi" }) {
  const [schemes, setSchemes] = useState([]);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    getSchemes()
      .then((r) => setSchemes(r.data || []))
      .catch(() => {});
  }, []);

  const isHindi = language === "hi";

  return (
    <div data-testid="schemes-page" className="min-h-screen bg-gray-50 pb-20">
      <AppHeader title={isHindi ? "सरकारी योजनाएं" : "Government Schemes"} />

      <div className="max-w-md mx-auto px-4 pt-4">
        {/* Info Banner */}
        <div className="bg-[#FFF0E0] rounded-xl p-4 border border-orange-100 mb-5 animate-fade-in-up">
          <p className="text-sm text-[#000080] font-['Mukta'] font-semibold">
            {isHindi
              ? "नीचे दी गई योजनाओं की जानकारी देखें और अपनी पात्रता जांचें।"
              : "Browse the schemes below and check your eligibility."}
          </p>
        </div>

        {/* Scheme Cards */}
        <div className="space-y-4 stagger-children">
          {schemes.map((scheme) => {
            const isExpanded = expandedId === scheme.id;
            const IconComp = ICON_MAP[scheme.icon] || Sprout;
            const colors = CATEGORY_COLORS[scheme.category] || CATEGORY_COLORS.agriculture;

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

                    {/* PDF Link */}
                    <a
                      href={scheme.pdf_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      data-testid={`scheme-pdf-${scheme.id}`}
                      className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-[#FFF0E0] rounded-full text-sm font-semibold text-[#000080] hover:bg-[#FFE4C4] transition-colors"
                    >
                      <ExternalLink size={14} />
                      {isHindi ? "विस्तृत दिशानिर्देश (PDF)" : "Detailed Guidelines (PDF)"}
                    </a>
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
