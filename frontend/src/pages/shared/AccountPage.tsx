import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/endpoints";
import { homeFor, useAuth } from "../../auth/AuthContext";
import { PageHeader } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { ROLE_TH } from "../../lib/labels";

export default function AccountPage() {
  const { user, setSession } = useAuth();
  const toast = useToast();
  const nav = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  if (!user) return null;

  const mismatch = again !== "" && next !== again;
  const tooShort = next !== "" && next.length < 8;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api.changePassword(current, next);
      setSession(r.access_token, r.user); // the old token stops working once the password changes
      toast.ok("เปลี่ยนรหัสผ่านแล้ว");
      setCurrent(""); setNext(""); setAgain("");
      if (user!.must_change_password) nav(homeFor(r.user.role), { replace: true });
    } catch (err) {
      toast.fail(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="บัญชีของฉัน" />
      {user.must_change_password && (
        <div className="notice warn">บัญชีของคุณเพิ่งถูกสร้างหรือถูกรีเซ็ตรหัสผ่าน กรุณาตั้งรหัสผ่านใหม่ของคุณเองก่อนเริ่มใช้งาน</div>
      )}
      <dl className="facts panel">
        <dt>ชื่อ</dt><dd>{user.full_name}</dd>
        <dt>อีเมล</dt><dd>{user.email}</dd>
        <dt>บทบาท</dt><dd>{ROLE_TH[user.role]}{user.department ? " · " + user.department : ""}</dd>
      </dl>

      <h2>เปลี่ยนรหัสผ่าน</h2>
      <form className="panel narrow" onSubmit={submit}>
        <label className="field"><span>รหัสผ่านปัจจุบัน{user.must_change_password ? " (รหัสชั่วคราวที่เจ้าหน้าที่ให้)" : ""}</span>
          <input type="password" required autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
        </label>
        <label className="field"><span>รหัสผ่านใหม่ (อย่างน้อย 8 ตัวอักษร)</span>
          <input type="password" required minLength={8} autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
        </label>
        <label className="field"><span>พิมพ์รหัสผ่านใหม่อีกครั้ง</span>
          <input type="password" required autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} />
        </label>
        {tooShort && <div className="form-error">รหัสผ่านใหม่ต้องยาวอย่างน้อย 8 ตัวอักษร</div>}
        {mismatch && <div className="form-error">รหัสผ่านใหม่สองช่องไม่ตรงกัน</div>}
        <button className="btn primary" disabled={busy || mismatch || tooShort || !current || !next || !again}>บันทึกรหัสผ่านใหม่</button>
        <p className="muted">เมื่อเปลี่ยนแล้ว อุปกรณ์อื่นที่เคยเข้าสู่ระบบไว้จะถูกออกจากระบบ</p>
      </form>
    </>
  );
}
