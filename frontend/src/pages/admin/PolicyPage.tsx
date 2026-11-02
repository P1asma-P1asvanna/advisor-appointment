import { FormEvent, useEffect, useState } from "react";
import { api } from "../../api/endpoints";
import type { Policy } from "../../api/types";
import { ErrorBox, Loading, PageHeader } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { useLoad } from "../../lib/hooks";

export default function PolicyPage() {
  const toast = useToast();
  const q = useLoad(() => api.policy(), []);
  const [p, setP] = useState<Policy | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (q.data) setP(q.data); }, [q.data]);

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!p) return;
    setBusy(true);
    try {
      setP(await api.savePolicy({ ...p, department: "*" }));
      toast.ok("บันทึกกติกาแล้ว");
    } catch (err) {
      toast.fail(err);
    } finally {
      setBusy(false);
    }
  }

  const num = (k: keyof Policy, label: string, unit: string, min: number, max: number) => (
    <label className="field"><span>{label}</span>
      <div className="with-unit">
        <input type="number" required min={min} max={max} value={Number(p![k])} onChange={(e) => setP({ ...p!, [k]: e.target.valueAsNumber })} />
        <span>{unit}</span>
      </div>
    </label>
  );

  return (
    <>
      <PageHeader title="กติกาการจอง" sub="ใช้กับทุกภาควิชา มีผลกับการจองและยกเลิกครั้งต่อไป" />
      {q.loading ? <Loading /> : q.error ? <ErrorBox message={q.error} retry={q.reload} /> : p && (
        <form className="panel form-grid" onSubmit={save}>
          {num("min_notice_hours", "จองล่วงหน้าอย่างน้อย", "ชั่วโมง", 0, 720)}
          {num("cancel_before_hours", "นักศึกษายกเลิกเองได้ก่อนนัด", "ชั่วโมง", 0, 720)}
          {num("max_active_per_student", "นัดที่รออยู่พร้อมกันได้ไม่เกิน", "นัด", 1, 20)}
          {num("reminder_hours_before", "แจ้งเตือนก่อนนัด", "ชั่วโมง", 1, 168)}
          <div className="field end"><button className="btn primary" disabled={busy}>บันทึกกติกา</button></div>
        </form>
      )}
    </>
  );
}
