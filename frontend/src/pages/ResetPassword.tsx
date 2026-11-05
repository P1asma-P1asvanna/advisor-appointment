import { FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/endpoints";
import { ApiError } from "../api/client";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (pw.length < 8) return setError("รหัสผ่านต้องยาวอย่างน้อย 8 ตัวอักษร");
    if (pw !== pw2) return setError("รหัสผ่านสองช่องไม่ตรงกัน");
    setBusy(true);
    setError(null);
    try {
      await api.resetPassword(token, pw);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ตั้งรหัสผ่านไม่สำเร็จ ลองใหม่อีกครั้ง");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit}>
        <div className="brand big"><span className="logo" aria-hidden>▤</span> ตั้งรหัสผ่านใหม่</div>
        {!token ? (
          <p>ลิงก์นี้ไม่ถูกต้อง กรุณาขอลิงก์ใหม่จากหน้าลืมรหัสผ่าน</p>
        ) : done ? (
          <>
            <p>ตั้งรหัสผ่านใหม่เรียบร้อยแล้ว ทุกอุปกรณ์ที่เคยเข้าสู่ระบบอยู่ถูกออกจากระบบแล้ว</p>
            <Link className="btn primary block" to="/login">ไปหน้าเข้าสู่ระบบ</Link>
          </>
        ) : (
          <>
            <label className="field"><span>รหัสผ่านใหม่ (อย่างน้อย 8 ตัว)</span>
              <input type="password" required minLength={8} autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} />
            </label>
            <label className="field"><span>พิมพ์รหัสผ่านใหม่อีกครั้ง</span>
              <input type="password" required autoComplete="new-password" value={pw2} onChange={(e) => setPw2(e.target.value)} />
            </label>
            {error && <div className="form-error" role="alert">{error}</div>}
            <button className="btn primary block" disabled={busy}>{busy ? "กำลังบันทึก…" : "ตั้งรหัสผ่านใหม่"}</button>
          </>
        )}
        {!done && <p><Link to="/forgot-password">ขอลิงก์ใหม่</Link></p>}
      </form>
    </div>
  );
}
