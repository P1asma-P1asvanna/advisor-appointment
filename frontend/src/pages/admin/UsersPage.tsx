import { FormEvent, useState } from "react";
import { api } from "../../api/endpoints";
import type { ManagedUser, Role } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Badge, Empty, ErrorBox, Loading, Modal, PageHeader, Tabs } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { useLoad } from "../../lib/hooks";
import { ROLE_TH } from "../../lib/labels";

const ROLES: Role[] = ["student", "advisor", "admin"];

/** A readable temporary password, e.g. "kemu-4721-rolo". Shown once to the admin to hand over. */
function tempPassword() {
  const syl = "bdfghjkmnprstvz", vow = "aeiou";
  const pick = (s: string) => s[Math.floor(Math.random() * s.length)];
  const word = () => pick(syl) + pick(vow) + pick(syl) + pick(vow);
  const n = Math.floor(1000 + Math.random() * 9000);
  return `${word()}-${n}-${word()}`;
}

export default function UsersPage() {
  const { user: me } = useAuth();
  const toast = useToast();
  const [role, setRole] = useState<Role | "all">("all");
  const [q, setQ] = useState("");
  const [adding, setAdding] = useState(false);
  const [resetting, setResetting] = useState<ManagedUser | null>(null);
  const [created, setCreated] = useState<{ email: string; password: string } | null>(null);
  const list = useLoad(() => api.users({ role: role === "all" ? undefined : role, q: q.trim() || undefined }), [role, q]);

  async function toggle(u: ManagedUser) {
    const off = u.is_active;
    const warn = off && u.role === "advisor" ? "\n\nเวลาว่างที่อาจารย์เปิดไว้และยังไม่ถูกจองจะถูกปิดทั้งหมด ส่วนนัดที่จองไปแล้วจะยังอยู่" : "";
    if (!window.confirm(`${off ? "ปิดการใช้งาน" : "เปิดใช้งานอีกครั้ง"}บัญชี ${u.full_name}?${warn}`)) return;
    try {
      await api.updateUser(u.id, { is_active: !u.is_active });
      toast.ok(off ? "ปิดการใช้งานแล้ว" : "เปิดใช้งานแล้ว");
      list.reload();
    } catch (e) {
      toast.fail(e);
    }
  }

  return (
    <>
      <PageHeader title="จัดการผู้ใช้" sub="เพิ่มบัญชี ปิดบัญชี และรีเซ็ตรหัสผ่าน (ไม่มีการลบ เพื่อให้ประวัติการนัดยังอยู่)"
        actions={<button className="btn primary" onClick={() => setAdding(true)}>+ เพิ่มผู้ใช้</button>} />
      <div className="filters">
        <Tabs<Role | "all"> value={role} onChange={setRole} items={[["all", "ทั้งหมด"], ["student", "นักศึกษา"], ["advisor", "อาจารย์"], ["admin", "เจ้าหน้าที่"]]} />
        <label className="field inline grow"><span>ค้นหาชื่อหรืออีเมล</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="พิมพ์เพื่อค้นหา" />
        </label>
      </div>

      {list.loading && !list.data ? <Loading /> : list.error ? <ErrorBox message={list.error} retry={list.reload} /> :
        list.data!.items.length === 0 ? <Empty title="ไม่พบผู้ใช้" hint="ลองเปลี่ยนตัวกรอง หรือกด เพิ่มผู้ใช้" /> :
        <div className="table-wrap">
          <table>
            <thead><tr><th>ชื่อ</th><th>อีเมล</th><th>บทบาท</th><th>ภาควิชา</th><th>สถานะ</th><th></th></tr></thead>
            <tbody>
              {list.data!.items.map((u) => (
                <tr key={u.id} className={u.is_active ? "" : "off"}>
                  <td>{u.full_name}</td>
                  <td>{u.email}</td>
                  <td>{ROLE_TH[u.role]}</td>
                  <td>{u.department ?? "–"}</td>
                  <td>
                    {u.is_active ? <Badge tone="green">ใช้งานอยู่</Badge> : <Badge tone="gray">ปิดแล้ว</Badge>}{" "}
                    {u.must_change_password && <Badge tone="amber">รอตั้งรหัสใหม่</Badge>}
                  </td>
                  <td>
                    {u.id !== me?.id && (
                      <div className="row">
                        <button className="btn sm" onClick={() => setResetting(u)}>รีเซ็ตรหัสผ่าน</button>
                        <button className="btn sm" onClick={() => toggle(u)}>{u.is_active ? "ปิดบัญชี" : "เปิดบัญชี"}</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>}

      {adding && <AddUserModal onClose={() => setAdding(false)} onCreated={(email, password) => { setAdding(false); setCreated({ email, password }); list.reload(); }} />}
      {resetting && <ResetModal user={resetting} onClose={() => setResetting(null)} onDone={(email, password) => { setResetting(null); setCreated({ email, password }); list.reload(); }} />}
      {created && (
        <Modal title="ส่งรหัสผ่านชั่วคราวให้ผู้ใช้" onClose={() => setCreated(null)}>
          <p>ให้ <b>{created.email}</b> เข้าสู่ระบบด้วยรหัสผ่านนี้ แล้วระบบจะให้ตั้งรหัสใหม่ของตัวเองทันที</p>
          <p className="secret">{created.password}</p>
          <p className="muted">รหัสนี้แสดงครั้งเดียว ปิดหน้าต่างแล้วดูอีกไม่ได้ (ลืมให้กดรีเซ็ตรหัสผ่านใหม่)</p>
          <div className="row end">
            <button className="btn" onClick={() => navigator.clipboard?.writeText(created.password).then(() => toast.ok("คัดลอกแล้ว"), () => {})}>คัดลอก</button>
            <button className="btn primary" onClick={() => setCreated(null)}>เรียบร้อย</button>
          </div>
        </Modal>
      )}
    </>
  );
}

function AddUserModal({ onClose, onCreated }: { onClose(): void; onCreated(email: string, password: string): void }) {
  const toast = useToast();
  const [role, setRole] = useState<Role>("student");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [dept, setDept] = useState("");
  const [password, setPassword] = useState(tempPassword);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await api.createUser({ email, full_name: name, role, department: dept || undefined, password });
      toast.ok("สร้างบัญชีแล้ว");
      onCreated(u.email, password);
    } catch (err) {
      toast.fail(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="เพิ่มผู้ใช้" onClose={onClose}>
      <form onSubmit={submit}>
        <label className="field"><span>บทบาท</span>
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}>{ROLES.map((r) => <option key={r} value={r}>{ROLE_TH[r]}</option>)}</select>
        </label>
        <label className="field"><span>ชื่อ-นามสกุล</span><input required value={name} onChange={(e) => setName(e.target.value)} placeholder={role === "advisor" ? "เช่น อ.สมชาย ใจดี" : "เช่น สมหญิง ศรีสุข"} /></label>
        <label className="field"><span>อีเมล (ใช้ล็อกอิน)</span><input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label className="field"><span>ภาควิชา{role === "admin" ? " (ไม่บังคับ)" : ""}</span><input required={role !== "admin"} value={dept} onChange={(e) => setDept(e.target.value)} placeholder="เช่น วิศวกรรมคอมพิวเตอร์" /></label>
        <label className="field"><span>รหัสผ่านชั่วคราว</span>
          <div className="row">
            <input required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
            <button type="button" className="btn sm" onClick={() => setPassword(tempPassword())}>สุ่มใหม่</button>
          </div>
        </label>
        <p className="muted">ภาควิชาของนักศึกษาและอาจารย์ต้องสะกดให้ตรงกัน เพราะใช้กรองในหน้าจองนัด</p>
        <div className="row end">
          <button type="button" className="btn" onClick={onClose}>ยกเลิก</button>
          <button className="btn primary" disabled={busy}>สร้างบัญชี</button>
        </div>
      </form>
    </Modal>
  );
}

function ResetModal({ user, onClose, onDone }: { user: ManagedUser; onClose(): void; onDone(email: string, password: string): void }) {
  const toast = useToast();
  const [password, setPassword] = useState(tempPassword);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.resetPassword(user.id, password);
      onDone(user.email, password);
    } catch (err) {
      toast.fail(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={`รีเซ็ตรหัสผ่าน: ${user.full_name}`} onClose={onClose}>
      <form onSubmit={submit}>
        <p className="muted">เขาจะถูกออกจากระบบทุกอุปกรณ์ และต้องตั้งรหัสผ่านใหม่ตอนเข้าสู่ระบบครั้งถัดไป การล็อกจากการใส่รหัสผิดจะถูกปลดด้วย</p>
        <label className="field"><span>รหัสผ่านชั่วคราวใหม่</span>
          <div className="row">
            <input required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
            <button type="button" className="btn sm" onClick={() => setPassword(tempPassword())}>สุ่มใหม่</button>
          </div>
        </label>
        <div className="row end">
          <button type="button" className="btn" onClick={onClose}>ยกเลิก</button>
          <button className="btn primary" disabled={busy}>รีเซ็ตรหัสผ่าน</button>
        </div>
      </form>
    </Modal>
  );
}
