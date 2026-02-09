import { NavLink, useLocation } from "react-router-dom";
import { BookOpen, Home, PlusCircle, Library, Settings, Sparkles } from "lucide-react";

const navItems = [
  { path: "/", icon: Home, label: "Dashboard" },
  { path: "/create", icon: PlusCircle, label: "New Book" },
  { path: "/library", icon: Library, label: "Library" },
  { path: "/settings", icon: Settings, label: "Settings" },
];

export default function Sidebar() {
  const location = useLocation();

  return (
    <aside
      data-testid="sidebar-nav"
      className="fixed left-0 top-0 bottom-0 w-64 bg-[#0A0A0A] border-r border-white/5 flex flex-col z-50"
    >
      {/* Logo */}
      <div className="px-6 py-8 flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-indigo-500/20 flex items-center justify-center">
          <Sparkles className="w-5 h-5 text-indigo-400" />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-white tracking-tight" style={{ fontFamily: "'Fraunces', serif" }}>
            Lumina Press
          </h1>
          <p className="text-[10px] font-mono tracking-widest uppercase text-white/40">
            KDP Creator
          </p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 space-y-1">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              data-testid={`nav-${item.label.toLowerCase().replace(/\s/g, "-")}`}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm transition-all duration-300 group ${
                isActive
                  ? "bg-indigo-500/10 text-white border border-indigo-500/20"
                  : "text-white/50 hover:text-white hover:bg-white/5"
              }`}
            >
              <item.icon
                className={`w-4 h-4 transition-colors ${
                  isActive ? "text-indigo-400" : "text-white/40 group-hover:text-white/70"
                }`}
              />
              <span style={{ fontFamily: "'Manrope', sans-serif" }}>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-6 py-6 border-t border-white/5">
        <div className="flex items-center gap-2 text-white/30">
          <BookOpen className="w-3.5 h-3.5" />
          <span className="text-xs font-mono">Amazon KDP Ready</span>
        </div>
      </div>
    </aside>
  );
}
