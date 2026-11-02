import { FormEvent, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/endpoints";
import type { Slot } from "../../api/types";
import { Empty, ErrorBox, Loading, Modal, PageHeader, Where } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { dayKey, dayLabel, groupBy, range } from "../../lib/format";
import { useLoad } from "../../lib/hooks";

export default function BookPage() {
  const toast = useToast();
  const nav = useNavigate();
  const [department, setDepartment] = useState("");
  const [advisorId, setAdvisorId] = useState("");
  const [picked, setPicked] = useState<Slot | null>(null);

  const advisors = useLoad(() => api.advisors(), []);
  const policy = useLoad(() => api.policy(department || undefined), [department]);
  const slots = useLoad(() => api.slots({ department: department || undefined, advisor_id: advisorId || undefined }), [department, advisorId]);

  const departments = useMemo(
    () => [...new Set((advisors.data?.items ?? []).map((a) => a.department).filter(Boolean))] as string[],
    [advisors.data],
  );
  const advisorOptions = (advisors.data?.items ?? []).filter((a) => !department || a.department === department);
  const groups = groupBy(slots.data?.items ?? [], (s) => dayKey(s.starts_at));

  return (
    <>
      <PageHeader title="จองนัดหมายอาจารย์" sub="เลือกเวลาว่างที่สะดวก แล้วบอกประเด็นที่อยากปรึกษา" />
      {policy.data && (
        <div className="notice">
          จองล่วงหน้าอย่างน้อย <b>{policy.data.min_notice_hours} ชม.</b> · ยกเลิกเองได้ก่อนนัด <b>{policy.data.cancel_before_hours} ชม.</b> ·
          มีนัดที่รออยู่ได้พร้อมกันไม่เกิน <b>{policy.data.max_active_per_student} นัด</b>
        </div>
      )}
      <div className="filters">
        <label className="field inline"><span>ภาควิชา</span>
          <select value={department} onChange={(e) => { setDepartment(e.target.value); setAdvisorId(""); }}>
            <option value="">ทุกภาควิชา</option>
            {departments.map((d) => <option key={d}>{d}</option>)}
          </select>
        </label>
        <label className="field inline"><span>อาจารย์</span>
          <select value={advisorId} onChange={(e) => setAdvisorId(e.target.value)}>
            <option value="">ทุกท่าน</option>
            {advisorOptions.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </label>
      </div>

      {slots.loading ? <Loading /> : slots.error ? <ErrorBox message={slots.error} retry={slots.reload} /> :
        groups.length === 0 ? <Empty title="ยังไม่มีเวลาว่างตามที่เลือก" hint="ลองเปลี่ยนภาควิชาหรืออาจารย์ หรือกลับมาดูใหม่ภายหลัง" /> :
        groups.map(([key, items]) => (
          <section key={key} className="day">
            <h3>{dayLabel(items[0].starts_at)}</h3>
            <div className="cards">
              {items.map((s) => (
                <button key={s.id} className="slot-card" onClick={() => setPicked(s)}>
                  <strong>{range(s.starts_at, s.ends_at)}</strong>
                  <span>{s.advisor.name}</span>
                  <span className="muted">{s.advisor.department}</span>
                  <span className="muted"><Where mode={s.mode} location={s.location} url={null} /></span>
                </button>
              ))}
            </div>
          </section>
        ))}

      {picked && (
        <BookModal
          slot={picked}
          onClose={() => setPicked(null)}
          onBooked={() => { toast.ok("จองนัดเรียบร้อยแล้ว"); nav("/appointments"); }}
          onConflict={() => { setPicked(null); slots.reload(); }}
        />
      )}
    </>
  );
}

function BookModal({ slot, onClose, onBooked, onConflict }: { slot: Slot; onClose(): void; onBooked(): void; onConflict(): void }) {
  const toast = useToast();
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.book(slot.id, topic);
      onBooked();
    } catch (err: any) {
      toast.fail(err);
      if (err?.status === 409) onConflict(); // slot taken / rules: refresh the list
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="ยืนยันการจอง" onClose={onClose}>
      <form onSubmit={submit}>
        <dl className="facts">
          <dt>อาจารย์</dt><dd>{slot.advisor.name} · {slot.advisor.department}</dd>
          <dt>เวลา</dt><dd>{dayLabel(slot.starts_at)} {range(slot.starts_at, slot.ends_at)}</dd>
          <dt>สถานที่</dt><dd><Where mode={slot.mode} location={slot.location} url={null} /></dd>
        </dl>
        <label className="field"><span>ประเด็นที่อยากปรึกษา</span>
          <textarea required rows={3} maxLength={300} value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="เช่น วางแผนลงทะเบียนเรียนภาคการศึกษาหน้า" autoFocus />
        </label>
        <div className="row end">
          <button type="button" className="btn" onClick={onClose}>ยกเลิก</button>
          <button className="btn primary" disabled={busy || !topic.trim()}>{busy ? "กำลังจอง…" : "ยืนยันการจอง"}</button>
        </div>
      </form>
    </Modal>
  );
}
