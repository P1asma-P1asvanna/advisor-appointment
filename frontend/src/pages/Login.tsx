import { FormEvent, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { homeFor, useAuth } from "../auth/AuthContext";
import type { Role } from "../api/types";
import { ROLE_TH } from "../lib/labels";
import { Tabs } from "../components/ui";
import { ApiError } from "../api/client";


export default function Login() {
  const { user, login } = useAuth();
  const [role, setRole] = useState<Role>("student");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homeFor(user.role)} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password, role);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "เข้าสู่ระบบไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit}>
        <div className="brand big"><span className="logo" aria-hidden>▤</span> นัดหมายอาจารย์</div>
        <p className="muted">จองเวลาปรึกษา บันทึกประเด็น และติดตามงานหลังพบอาจารย์</p>
        <Tabs value={role} onChange={(r) => { setRole(r); setError(null); }} items={(Object.keys(ROLE_TH) as Role[]).map((r) => [r, ROLE_TH[r]])} />
        <label className="field"><span>อีเมล</span>
          <input type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@example.edu" />
        </label>
        <label className="field"><span>รหัสผ่าน</span>
          <input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <div className="form-error" role="alert">{error}</div>}
        <button className="btn primary block" disabled={busy}>{busy ? "กำลังเข้าสู่ระบบ…" : "เข้าสู่ระบบ"}</button>
        <p className="center"><Link to="/forgot-password">ลืมรหัสผ่าน?</Link></p>
      </form>
    </div>
  );
}
