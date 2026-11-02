import { FormEvent, useState } from "react";
import { api } from "../../api/endpoints";
import type { Mode } from "../../api/types";
import { Empty, ErrorBox, Loading, PageHeader, SlotBadge, Where } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { bangkokIso, dayKey, dayLabel, groupBy, range } from "../../lib/format";
import { useLoad } from "../../lib/hooks";

export default function SlotsPage() {
  const toast = useToast();
  const slots = useLoad(() => api.slots({ from_date: dayKey(new Date().toISOString()) }), []);
  const [start, setStart] = useState("");
  const [minutes, setMinutes] = useState(30);
  const [mode, setMode] = useState<Mode>("onsite");
  const [where, setWhere] = useState("");
  const [busy, setBusy] = useState(false);

  async function add(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const startsAt = bangkokIso(start);
      const endsAt = new Date(new Date(startsAt).getTime() + minutes * 60_000).toISOString();
      await api.createSlot({
        starts_at: startsAt,
        ends_at: endsAt,
        mode,
        location: mode === "onsite" ? where || undefined : undefined,
        meeting_url: mode === "online" ? where || undefined : undefined,
      });
      toast.ok("เปิดเวลาว่างแล้ว");
      slots.reload();
    } catch (err) {
      toast.fail(err);
    } finally {
      setBusy(false);
    }
  }

  async function close(id: string) {
    try {
      await api.cancelSlot(id);
      toast.ok("ปิดช่องเวลาแล้ว");
      slots.reload();
    } catch (err) {
      toast.fail(err);
    }
  }

  const groups = groupBy(slots.data?.items ?? [], (s) => dayKey(s.starts_at));

  return (
    <>
      <PageHeader title="เวลาว่างของฉัน" sub="เปิดช่วงเวลาที่นักศึกษาจองเข้าพบได้" />
      <form className="panel form-grid" onSubmit={add}>
        <label className="field"><span>วันและเวลาเริ่ม</span>
          <input type="datetime-local" required value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label className="field"><span>ความยาว</span>
          <select value={minutes} onChange={(e) => setMinutes(+e.target.value)}>
            {[15, 20, 30, 45, 60, 90].map((m) => <option key={m} value={m}>{m} นาที</option>)}
          </select>
        </label>
        <label className="field"><span>รูปแบบ</span>
          <select value={mode} onChange={(e) => { setMode(e.target.value as Mode); setWhere(""); }}>
            <option value="onsite">พบที่ห้อง</option>
            <option value="online">ออนไลน์</option>
          </select>
        </label>
        <label className="field"><span>{mode === "onsite" ? "ห้อง/สถานที่" : "ลิงก์ประชุม"}</span>
          <input value={where} maxLength={mode === "onsite" ? 200 : 500} onChange={(e) => setWhere(e.target.value)} placeholder={mode === "onsite" ? "เช่น ห้อง 5-402" : "https://meet…"} />
        </label>
        <div className="field end"><button className="btn primary" disabled={busy || !start}>เปิดเวลานี้</button></div>
      </form>

      {slots.loading ? <Loading /> : slots.error ? <ErrorBox message={slots.error} retry={slots.reload} /> :
        groups.length === 0 ? <Empty title="ยังไม่มีเวลาที่เปิดไว้" hint="เพิ่มช่วงเวลาด้านบนเพื่อให้นักศึกษาจองได้" /> :
        groups.map(([k, items]) => (
          <section key={k} className="day">
            <h3>{dayLabel(items[0].starts_at)}</h3>
            <div className="list">
              {items.map((s) => (
                <div key={s.id} className="row-item">
                  <strong className="when">{range(s.starts_at, s.ends_at)}</strong>
                  <SlotBadge s={s.status} />
                  <span className="grow muted"><Where mode={s.mode} location={s.location} url={s.meeting_url} />{s.student_name ? " · " + s.student_name : ""}</span>
                  {s.status === "open" && <button className="btn sm" onClick={() => close(s.id)}>ปิดช่องนี้</button>}
                </div>
              ))}
            </div>
          </section>
        ))}
    </>
  );
}
