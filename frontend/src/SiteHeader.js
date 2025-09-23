// SiteHeader.js
import { Link, NavLink } from "react-router-dom";
import { SunIcon, MoonIcon } from "@heroicons/react/24/solid";
import useDarkMode from "./useDarkMode";

export default function SiteHeader() {
  const { isDark, setIsDark } = useDarkMode();

  const linkCls = ({ isActive }) =>
    isActive
      ? "text-blue-600 dark:text-blue-400 font-semibold"
      : "text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white";

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-gray-900/70 backdrop-blur">
      <div className="mx-auto max-w-5xl px-4 py-3 flex items-center justify-between">
        {/* Clickable wordmark → Home */}
        <Link to="/" aria-label="Home" className="flex items-center gap-2">
          <span className="text-2xl">📈</span>
          <span className="text-2xl font-extrabold tracking-tight">PeerStocks</span>
        </Link>

        {/* Nav + Dark Toggle */}
        <div className="flex items-center gap-4">
          <nav className="flex items-center gap-6 text-sm">
            <NavLink to="/" end className={linkCls}>Home</NavLink>
            <NavLink to="/advanced-search" className={linkCls}>Advanced Search</NavLink>
            <NavLink to="/compare" className={linkCls}>Compare</NavLink>
          </nav>

          <button
            onClick={() => setIsDark(!isDark)}
            className="w-8 h-8 grid place-items-center rounded-md border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
            aria-label="Toggle dark mode"
            title="Toggle dark mode"
          >
            {isDark ? <SunIcon className="w-5 h-5 text-yellow-300" /> : <MoonIcon className="w-5 h-5 text-slate-700" />}
          </button>
        </div>
      </div>
    </header>
  );
}
