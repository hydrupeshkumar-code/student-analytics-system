import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { download } from "../lib/api";
import { ReportIllustration } from "./Illustrations";
import { useAuth } from "../lib/auth";
import {
  IconBook, IconBrain, IconGear, IconHome, IconKey, IconLayers, IconLog, IconLogout, IconMenu, IconMoon, IconRubric,
  IconSun, IconTarget, IconUsers,
} from "./icons";

type Item = { to: string; label: string; icon: () => React.JSX.Element; end?: boolean };

const NAV: Record<string, { section?: string; items: Item[] }[]> = {
  admin: [
    { items: [{ to: "/", label: "Overview", icon: IconHome, end: true }] },
    { section: "Academics", items: [
      { to: "/courses", label: "Courses", icon: IconBook },
      { to: "/programs", label: "Programs & POs", icon: IconLayers },
      { to: "/attainment", label: "PO attainment", icon: IconTarget },
      { to: "/rubrics", label: "Rubric library", icon: IconRubric },
    ] },
    { section: "Administration", items: [
      { to: "/users", label: "Users", icon: IconUsers },
      { to: "/ml", label: "Early-warning model", icon: IconBrain },
      { to: "/settings", label: "Settings", icon: IconGear },
      { to: "/audit", label: "Audit log", icon: IconLog },
    ] },
  ],
  faculty: [
    { items: [{ to: "/", label: "Dashboard", icon: IconHome, end: true }] },
    { section: "Teaching", items: [
      { to: "/courses", label: "My courses", icon: IconBook },
      { to: "/rubrics", label: "Rubric library", icon: IconRubric },
    ] },
  ],
  student: [
    { items: [{ to: "/", label: "My performance", icon: IconHome, end: true }] },
  ],
};

function useTheme() {
  const [theme, setTheme] = useState<string | null>(() => { try { return localStorage.getItem("saap.theme"); } catch { return null; } });
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
    try { if (theme) localStorage.setItem("saap.theme", theme); } catch { /* ignore */ }
  }, [theme]);
  const isDark = theme ? theme === "dark" : window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  return { isDark, toggle: () => setTheme(isDark ? "light" : "dark") };
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);
  if (!user) return null;
  const initials = user.name.split(/\s+/).filter((w) => /[A-Za-z]/.test(w[0])).slice(0, 2).map((w) => w[0]).join("").toUpperCase();

  return (
    <div className="app">
      <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Main navigation">
        <div className="brand">
          <div className="brand-mark">S</div>
          <div><div className="brand-name">SAAP</div><div className="brand-sub">Assessment & Analytics</div></div>
        </div>
        <nav className="nav">
          {NAV[user.role].map((g, i) => (
            <div key={i} style={{ display: "contents" }}>
              {g.section && <div className="nav-section">{g.section}</div>}
              {g.items.map((it) => (
                <NavLink key={it.to} to={it.to} end={it.end}><it.icon />{it.label}</NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="help-card">
            <ReportIllustration />
            <strong className="small">{user.role === "student" ? "Your performance report" : user.role === "faculty" ? "Grade faster with rubrics" : "Keep predictions accurate"}</strong>
            <p>{user.role === "student" ? "All courses, marks and grades in one PDF." : user.role === "faculty" ? "Reusable rubrics score assignments automatically." : "Retrain the early-warning model each semester."}</p>
            {user.role === "student"
              ? <button className="btn btn-primary btn-sm" style={{ width: "100%" }} onClick={() => download("/me/report.pdf")}>Download PDF</button>
              : <Link className="btn btn-primary btn-sm" style={{ width: "100%" }} to={user.role === "faculty" ? "/rubrics" : "/ml"}>{user.role === "faculty" ? "Open rubric library" : "Open model"}</Link>}
          </div>
          <div className="user-chip">
            <div className="avatar">{initials}</div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{user.name}</div>
              <div className="small muted" style={{ textTransform: "capitalize" }}>{user.role}{user.student_profile ? ` · ${user.student_profile.roll_no}` : ""}</div>
            </div>
          </div>
          <div className="nav">
            <NavLink to="/account"><IconKey />Account & password</NavLink>
            <a href="#" onClick={(e) => { e.preventDefault(); toggle(); }}>{isDark ? <IconSun /> : <IconMoon />}{isDark ? "Light mode" : "Dark mode"}</a>
            <a href="#" onClick={(e) => { e.preventDefault(); logout(); }}><IconLogout />Sign out</a>
          </div>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="btn btn-ghost icon-btn" onClick={() => setOpen(true)} aria-label="Open menu"><IconMenu /></button>
          <strong>SAAP</strong>
          <button className="btn btn-ghost icon-btn" onClick={toggle} aria-label="Toggle theme">{isDark ? <IconSun /> : <IconMoon />}</button>
        </header>
        <div className="appbar">
          <div className="appbar-date">{new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</div>
          <div className="row" style={{ gap: 10 }}>
            <button className="btn btn-ghost icon-btn appbar-btn" onClick={toggle} aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}>{isDark ? <IconSun /> : <IconMoon />}</button>
            <NavLink to="/account" className="appbar-user" aria-label="Account">
              <div className="avatar">{initials}</div>
              <div><div className="appbar-name">{user.name}</div><div className="small muted" style={{ textTransform: "capitalize" }}>{user.role}</div></div>
            </NavLink>
          </div>
        </div>
        <main className="content"><Outlet /></main>
      </div>
    </div>
  );
}
