import { useState } from "react";
import { api } from "../../api/endpoints";
import { Empty, ErrorBox, Loading, PageHeader } from "../../components/ui";
import { dateTime } from "../../lib/format";
import { useLoad } from "../../lib/hooks";
import { ROLE_TH } from "../../lib/labels";

const FIELD: Record<string, string> = { full_name: "ชื่อ", department: "ภาควิชา", email: "อีเมล", role: "บทบาท", is_active: "สถานะบัญชี" };
const ACTION: Record<string, string> = {
  "user.create": "เพิ่มผู้ใช้",
  "user.update": "แก้ข้อมูลผู้ใช้",
  "user.reset_password": "รีเซ็ตรหัสผ่าน",
  "user.password_reset_by_email": "ตั้งรหัสผ่านใหม่ผ่านอีเมล",
  "policy.update": "แก้กติกาการจอง",
  "admin.bootstrap": "สร้างเจ้าหน้าที่คนแรก",
};

function show(field: string, v: unknown): string {
  if (v === null || v === undefined || v === "") return "(ว่าง)";
  if (field === "is_active") return v ? "เปิดใช้งาน" : "ปิดบัญชี";
  if (field === "role") return ROLE_TH[v as keyof typeof ROLE_TH] ?? String(v);
  return String(v);
}

function summary(action: string, d: Record<string, unknown> | null): string {
  if (!d) return "";
  if (action === "user.update")
    return Object.entries(d).map(([k, c]) => {
      const ch = c as { from: unknown; to: unknown };
      return `${FIELD[k] ?? k}: ${show(k, ch.from)} → ${show(k, ch.to)}`;
    }).join(" · ");
  if (action === "user.create") return `บทบาท ${show("role", d.role)}${d.department ? " · " + d.department : ""}`;
  if (action === "policy.update")
    return `ภาควิชา ${d.department === "*" ? "ทั้งหมด" : d.department}: แจ้งล่วงหน้า ${d.min_notice_hours} ชม. · ยกเลิกก่อน ${d.cancel_before_hours} ชม. · จองค้างได้ ${d.max_active_per_student} นัด · เตือนก่อน ${d.reminder_hours_before} ชม.`;
  return JSON.stringify(d);
}

export default function AuditPage() {
  const [q, setQ] = useState("");
  const [applied, setApplied] = useState("");
  const list = useLoad(() => api.audit(applied || undefined), [applied]);

  return (
    <>
      <PageHeader title="ประวัติการแก้ไข" sub="ใครแก้ข้อมูลสำคัญของใครเมื่อไร (แสดง 200 รายการล่าสุด ไม่มีรหัสผ่านอยู่ในบันทึกนี้)" />
      <form className="row wrap" onSubmit={(e) => { e.preventDefault(); setApplied(q.trim()); }}>
        <input className="grow" placeholder="ค้นหาด้วยอีเมลหรือประเภทการแก้ไข" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="btn">ค้นหา</button>
        {applied && <button type="button" className="btn" onClick={() => { setQ(""); setApplied(""); }}>ล้าง</button>}
      </form>
      {list.loading ? <Loading /> : list.error ? <ErrorBox message={list.error} retry={list.reload} /> :
        list.data!.items.length === 0 ? <Empty title="ยังไม่มีประวัติ" /> :
        <div className="list">
          {list.data!.items.map((i) => (
            <div key={i.id} className="appt">
              <div className="appt-main">
                <div className="row wrap"><strong>{ACTION[i.action] ?? i.action}</strong><span className="muted">{dateTime(i.at)}</span></div>
                <div className="muted">
                  โดย {i.actor_email ?? (i.action === "user.password_reset_by_email" ? "เจ้าของบัญชีเอง" : "ระบบ")}
                  {i.target_email && <> · ผู้ที่ถูกแก้: {i.target_email}</>}
                </div>
                {i.details && <div>{summary(i.action, i.details)}</div>}
              </div>
            </div>
          ))}
        </div>}
    </>
  );
}
