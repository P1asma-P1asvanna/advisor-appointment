import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import type { Role } from "../api/types";
import { ROLE_TH } from "../lib/labels";

const NAV: Record<Role, [string, string][]> = {
  student: [["/book", "จองนัดหมาย"], ["/appointments", "นัดของฉัน"], ["/tasks", "งานติดตาม"], ["/notifications", "การแจ้งเตือน"]],
  advisor: [["/slots", "เวลาว่างของฉัน"], ["/appointments", "นัดหมาย"], ["/tasks", "งานที่มอบหมาย"], ["/notifications", "การแจ้งเตือน"]],
  admin: [["/overview", "ภาพรวมภาควิชา"], ["/policy", "กติกาการจอง"], ["/notifications", "การแจ้งเตือน"]],
};

export default function Layout() {
  const { user, logout } = useAuth();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    const tick = () => api.notifications().then((r) => alive && setUnread(r.unread)).catch(() => {});
    tick();
    const id = setInterval(tick, 60_000);
    const onChange = () => tick();
    window.addEventListener("notifications:changed", onChange);
    return () => { alive = false; clearInterval(id); window.removeEventListener("notifications:changed", onChange); };
  }, []);

  if (!user) return null;
  return (
    <div className="shell">
      <button className="burger" onClick={() => setOpen(!open)} aria-label="เมนู">☰</button>
      <aside className={"side" + (open ? " open" : "")} onClick={() => setOpen(false)}>
        <div className="brand"><span className="logo" aria-hidden>▤</span> นัดหมายอาจารย์</div>
        <nav>
          {NAV[user.role].map(([to, label]) => (
            <NavLink key={to} to={to} className={({ isActive }) => (isActive ? "on" : "")}>
              {label}
              {to === "/notifications" && unread > 0 && <span className="count">{unread}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="usercard">
          <strong>{user.full_name}</strong>
          <span className="muted">{ROLE_TH[user.role]}{user.department ? " · " + user.department : ""}</span>
          <button className="btn sm" onClick={logout}>ออกจากระบบ</button>
        </div>
      </aside>
      <main className="main"><Outlet /></main>
    </div>
  );
}
