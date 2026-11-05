import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/endpoints";
import { ApiError } from "../api/client";
import { useLoad } from "../lib/hooks";

export default function ForgotPassword() {
  const features = useLoad(() => api.features(), []);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.forgotPassword(email.trim());
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ส่งคำขอไม่สำเร็จ ลองใหม่อีกครั้ง");
    } finally {
      setBusy(false);
    }
  }

  const off = !features.loading && features.data && !features.data.password_reset;
  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit}>
        <div className="brand big"><span className="logo" aria-hidden>▤</span> ลืมรหัสผ่าน</div>
        {off ? (
          <p>ระบบยังไม่ได้เปิดการส่งอีเมล กรุณาติดต่อเจ้าหน้าที่ภาควิชาให้รีเซ็ตรหัสผ่านให้</p>
        ) : sent ? (
          <p>ถ้าอีเมลนี้มีบัญชีอยู่ในระบบ เราได้ส่งลิงก์ตั้งรหัสผ่านใหม่ไปให้แล้ว ลิงก์ใช้ได้ภายใน 30 นาที และใช้ได้ครั้งเดียว ถ้าไม่พบอีเมล ให้ดูในกล่องจดหมายขยะ</p>
        ) : (
          <>
            <p className="muted">ใส่อีเมลที่ใช้เข้าสู่ระบบ เราจะส่งลิงก์สำหรับตั้งรหัสผ่านใหม่ให้</p>
            <label className="field"><span>อีเมล</span>
              <input type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@example.edu" />
            </label>
            {error && <div className="form-error" role="alert">{error}</div>}
            <button className="btn primary block" disabled={busy}>{busy ? "กำลังส่ง…" : "ส่งลิงก์ตั้งรหัสผ่านใหม่"}</button>
          </>
        )}
        <p><Link to="/login">กลับไปหน้าเข้าสู่ระบบ</Link></p>
      </form>
    </div>
  );
}
