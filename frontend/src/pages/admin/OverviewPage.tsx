import { useState } from "react";
import { api } from "../../api/endpoints";
import { Empty, ErrorBox, Loading, PageHeader } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { pct } from "../../lib/format";
import { useLoad } from "../../lib/hooks";

export default function OverviewPage() {
  const toast = useToast();
  const [dept, setDept] = useState("");
  const q = useLoad(() => api.overview(dept || undefined), [dept]);

  async function remind() {
    try {
      const r = await api.sendReminders();
      toast.ok(r.created ? `สร้างการแจ้งเตือนใหม่ ${r.created} รายการ` : "ไม่มีรายการที่ต้องแจ้งเตือนเพิ่ม");
      q.reload();
    } catch (e) {
      toast.fail(e);
    }
  }

  const k = q.data?.kpis;
  return (
    <>
      <PageHeader
        title="ภาพรวมภาควิชา"
        sub="แสดงเฉพาะจำนวนและชื่อ ไม่แสดงหัวข้อหรือบันทึกการปรึกษา"
        actions={<button className="btn sm" onClick={remind}>ส่งแจ้งเตือนตอนนี้</button>}
      />
      <div className="filters">
        <label className="field inline"><span>ภาควิชา</span>
          <select value={dept} onChange={(e) => setDept(e.target.value)}>
            <option value="">ทุกภาควิชา</option>
            {(q.data?.departments ?? []).map((d) => <option key={d}>{d}</option>)}
          </select>
        </label>
      </div>
      {q.loading && !q.data ? <Loading /> : q.error ? <ErrorBox message={q.error} retry={q.reload} /> : q.data && k && (
        <>
          <div className="kpis">
            <Kpi label="อัตราการใช้เวลาว่าง" value={pct(k.utilization)} sub={`จอง ${k.slots_booked} จาก ${k.slots_total} ช่อง`} />
            <Kpi label="นัดที่กำลังจะมาถึง" value={String(k.appts_upcoming)} />
            <Kpi label="ปรึกษาเสร็จสิ้น" value={String(k.appts_completed)} />
            <Kpi label="อัตราไม่มาตามนัด" value={pct(k.no_show_rate)} sub={`${k.appts_no_show} ครั้ง`} tone={k.no_show_rate && k.no_show_rate > 0.2 ? "warn" : undefined} />
            <Kpi label="งานเลยกำหนด" value={String(k.overdue_tasks)} tone={k.overdue_tasks ? "warn" : undefined} />
          </div>

          <h2>รายอาจารย์</h2>
          {q.data.advisors.length === 0 ? <Empty title="ไม่มีข้อมูลอาจารย์" /> : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>อาจารย์</th><th>ภาควิชา</th><th>ช่องที่เปิด</th><th>ถูกจอง</th><th>การใช้งาน</th><th>เสร็จสิ้น</th><th>ไม่มา</th><th>กำลังจะมาถึง</th></tr></thead>
                <tbody>
                  {q.data.advisors.map((a) => (
                    <tr key={a.id}>
                      <td>{a.full_name}</td><td>{a.department}</td><td>{a.slots_total}</td><td>{a.slots_booked}</td>
                      <td><div className="bar"><i style={{ width: pct(a.utilization) === "–" ? "0" : pct(a.utilization) }} /></div> {pct(a.utilization)}</td>
                      <td>{a.appts_completed}</td><td>{a.appts_no_show}</td><td>{a.appts_upcoming}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h2>นักศึกษาที่ควรติดตาม</h2>
          {q.data.watchlist.length === 0 ? <Empty title="ไม่มีนักศึกษาที่ต้องติดตามตอนนี้" /> : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>นักศึกษา</th><th>ไม่มาตามนัด (ครั้ง)</th><th>งานเลยกำหนด</th></tr></thead>
                <tbody>{q.data.watchlist.map((w) => <tr key={w.id}><td>{w.full_name}</td><td>{w.no_shows}</td><td>{w.overdue_tasks}</td></tr>)}</tbody>
              </table>
            </div>
          )}
        </>
      )}
    </>
  );
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "warn" }) {
  return (
    <div className={"kpi" + (tone ? " " + tone : "")}>
      <span className="muted">{label}</span>
      <strong>{value}</strong>
      {sub && <span className="muted">{sub}</span>}
    </div>
  );
}
