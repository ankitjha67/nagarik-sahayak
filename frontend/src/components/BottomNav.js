import { useLocation, useNavigate } from "react-router-dom";
import { Home, BookOpen, UserCircle2, MessageCircle, GraduationCap } from "lucide-react";
import { useLanguage } from "../lib/i18n";

// Labels come from the message catalogue rather than being hardcoded Hindi.
// The primary navigation is the most-read text in the app; leaving it in one
// language undoes the language picker for everyone who used it.
const navItems = [
  { path: "/home", icon: Home, key: "nav.home", id: "home" },
  { path: "/chat", icon: MessageCircle, key: "nav.chat", id: "chat" },
  { path: "/schemes", icon: BookOpen, key: "nav.schemes", id: "schemes" },
  { path: "/exams", icon: GraduationCap, key: "nav.exams", id: "exams" },
  { path: "/profile", icon: UserCircle2, key: "nav.profile", id: "profile" },
];

export const BottomNav = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useLanguage();

  return (
    <nav
      data-testid="bottom-nav"
      className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 z-40"
    >
      <div className="max-w-md mx-auto flex items-center justify-around py-2">
        {navItems.map(({ path, icon: Icon, key, id }) => {
          const isActive = location.pathname === path;
          const label = t(key);
          return (
            <button
              key={path}
              data-testid={`nav-${id}`}
              onClick={() => navigate(path)}
              aria-label={label}
              aria-current={isActive ? "page" : undefined}
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
              {/* Scripts vary widely in width; the label is allowed to wrap and
                  truncate rather than pushing the bar out of shape. */}
              <span className="text-[10px] font-semibold max-w-[64px] truncate">
                {label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
