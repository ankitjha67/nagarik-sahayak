import { useLocation, useNavigate } from "react-router-dom";
import { Home, BookOpen, UserCircle2, MessageCircle, GraduationCap } from "lucide-react";

const navItems = [
  { path: "/home", icon: Home, label: "Home", labelHi: "होम" },
  { path: "/chat", icon: MessageCircle, label: "Chat", labelHi: "चैट" },
  { path: "/schemes", icon: BookOpen, label: "Schemes", labelHi: "योजनाएं" },
  { path: "/exams", icon: GraduationCap, label: "Exams", labelHi: "परीक्षा" },
  { path: "/profile", icon: UserCircle2, label: "Profile", labelHi: "प्रोफाइल" },
];

export const BottomNav = () => {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <nav
      data-testid="bottom-nav"
      className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 z-40"
    >
      <div className="max-w-md mx-auto flex items-center justify-around py-2">
        {navItems.map(({ path, icon: Icon, label, labelHi }) => {
          const isActive = location.pathname === path;
          return (
            <button
              key={path}
              data-testid={`nav-${label.toLowerCase()}`}
              onClick={() => navigate(path)}
              aria-label={label}
              className={`flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl transition-all duration-200 ${
                isActive
                  ? "text-[#FF9933]"
                  : "text-gray-400 hover:text-gray-600"
              }`}
            >
              <Icon
                size={22}
                strokeWidth={isActive ? 2.5 : 2}
                className="transition-all"
              />
              <span className="text-[10px] font-semibold font-['Mukta']">
                {labelHi}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
