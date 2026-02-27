import { useState, useEffect } from "react";
import { getV2Schemes } from "../lib/api";
import { Home, GraduationCap, Rocket, Wheat, ChevronRight, Check } from "lucide-react";

const CATEGORY_CONFIG = {
  housing: { icon: Home, color: "#FF6B35", bg: "#FFF3ED" },
  education: { icon: GraduationCap, color: "#2563EB", bg: "#EFF6FF" },
  startup: { icon: Rocket, color: "#7C3AED", bg: "#F5F3FF" },
  agriculture: { icon: Wheat, color: "#16A34A", bg: "#F0FDF4" },
};

export const SchemeSelector = ({ onSchemesSelected, userId }) => {
  const [schemes, setSchemes] = useState([]);
  const [selected, setSelected] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getV2Schemes()
      .then((res) => setSchemes(res.data.schemes || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const toggleScheme = (name) => {
    setSelected((prev) =>
      prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name]
    );
  };

  const handleProceed = () => {
    if (selected.length > 0) onSchemesSelected(selected);
  };

  if (loading) {
    return (
      <div data-testid="scheme-selector-loading" className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-3 border-[#FF9933] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div data-testid="scheme-selector" className="space-y-3 animate-fade-in-up">
      <div className="text-center mb-4">
        <h2 className="text-base font-bold text-[#000080] font-['Mukta']">
          योजना चुनें / Select Scheme(s)
        </h2>
        <p className="text-xs text-gray-500 font-['Nunito'] mt-0.5">
          एक या अधिक योजनाएं चुनें जिनके लिए आवेदन करना है
        </p>
      </div>

      {schemes.map((scheme) => {
        const cfg = CATEGORY_CONFIG[scheme.category] || CATEGORY_CONFIG.housing;
        const Icon = cfg.icon;
        const isSelected = selected.includes(scheme.name);

        return (
          <button
            key={scheme.id}
            data-testid={`scheme-card-${scheme.category}`}
            onClick={() => toggleScheme(scheme.name)}
            className={`w-full text-left p-3 rounded-xl border-2 transition-all duration-200 ${
              isSelected
                ? "border-[#000080] bg-[#F0F0F8] shadow-md scale-[1.01]"
                : "border-gray-100 bg-white hover:border-gray-200 hover:shadow-sm"
            }`}
          >
            <div className="flex items-start gap-3">
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ backgroundColor: cfg.bg }}
              >
                <Icon size={20} style={{ color: cfg.color }} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-gray-900 font-['Mukta'] leading-tight">
                    {scheme.nameHindi || scheme.name}
                  </span>
                  {isSelected && (
                    <div className="w-5 h-5 rounded-full bg-[#000080] flex items-center justify-center flex-shrink-0">
                      <Check size={12} className="text-white" />
                    </div>
                  )}
                </div>
                <p className="text-[11px] text-gray-600 font-['Nunito'] mt-0.5 leading-snug">
                  {scheme.descriptionHindi || scheme.description}
                </p>
                <span
                  className="inline-block mt-1 text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
                  style={{ color: cfg.color, backgroundColor: cfg.bg }}
                >
                  {scheme.category}
                </span>
              </div>
              <ChevronRight
                size={16}
                className={`flex-shrink-0 mt-1 transition-colors ${
                  isSelected ? "text-[#000080]" : "text-gray-300"
                }`}
              />
            </div>
          </button>
        );
      })}

      {selected.length > 0 && (
        <button
          data-testid="scheme-proceed-btn"
          onClick={handleProceed}
          className="w-full py-3 bg-[#000080] hover:bg-[#000060] text-white rounded-xl font-bold font-['Mukta'] text-sm transition-all hover:-translate-y-0.5 shadow-md"
        >
          {selected.length === 1
            ? "आवेदन शुरू करें"
            : `${selected.length} योजनाओं के लिए आवेदन शुरू करें`}
          <ChevronRight size={16} className="inline ml-1" />
        </button>
      )}
    </div>
  );
};
