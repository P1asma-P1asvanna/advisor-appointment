import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/endpoints";
import type { AppointmentDetail, AppointmentTask, Note, TaskStatus, Visibility } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { ApptBadge, Badge, Empty, ErrorBox, Loading, PageHeader, Where } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { dateTime, dayLabel, dueLabel, range } from "../../lib/format";
import { useLoad } from "../../lib/hooks";
import { TASK_STATUS } from "../../lib/labels";

export default function AppointmentDetailPage() {
  const { id = "" } = useParams();
  const { user } = useAuth();
  const q = useLoad(() => api.appointment(id), [id]);
  const toast = useToast();
  const isAdvisor = user?.role === "advisor";
  const [editTopic, setEditTopic] = useState(false);
  const [topic, setTopic] = useState("");

  if (q.loading) return <Loading />;
  if (q.error || !q.data) return <ErrorBox message={q.error ?? "ไม่พบนัดหมายนี้"} />;
  const a = q.data;
  const canRecord = isAdvisor && a.status !== "cancelled";
  const canEditTopic = user?.role === "student" && (a.status === "pending" || a.status === "confirmed") && new Date(a.starts_at).getTime() > Date.now();

  async function saveTopic(e: FormEvent) {
    e.preventDefault();
    try {
      await api.updateTopic(a.id, topic.trim());
      toast.ok("แก้หัวข้อแล้ว");
      setEditTopic(false);
      q.reload();
    } catch (err) {
      toast.fail(err);
    }
  }

  return (
    <>
      <p><Link to="/appointments">← กลับไปรายการนัด</Link></p>
      <PageHeader title={a.topic} sub={`${dayLabel(a.starts_at)} · ${range(a.starts_at, a.ends_at)}`} actions={<ApptBadge s={a.status} />} />
      {canEditTopic && (editTopic ? (
        <form className="panel row wrap" onSubmit={saveTopic}>
          <input className="grow" required maxLength={300} value={topic} onChange={(e) => setTopic(e.target.value)} />
          <button className="btn sm primary">บันทึกหัวข้อ</button>
          <button type="button" className="btn sm" onClick={() => setEditTopic(false)}>ยกเลิก</button>
        </form>
      ) : <p><button className="btn sm" onClick={() => { setTopic(a.topic); setEditTopic(true); }}>แก้หัวข้อ</button></p>)}
      <dl className="facts panel">
        <dt>{isAdvisor ? "นักศึกษา" : "อาจารย์"}</dt><dd>{isAdvisor ? a.student.name : `${a.advisor.name} · ${a.advisor.department ?? ""}`}</dd>
        <dt>สถานที่</dt><dd><Where mode={a.mode} location={a.location} url={a.meeting_url} /></dd>
        {a.cancel_reason && (<><dt>เหตุผลที่ยกเลิก</dt><dd>{a.cancel_reason}</dd></>)}
      </dl>

      <section>
        <h2>บันทึกการปรึกษา</h2>
        {a.notes.length === 0 && !canRecord && <Empty title="ยังไม่มีบันทึกที่แชร์" hint="อาจารย์จะบันทึกสรุปหลังพบ และแจ้งให้ทราบ" />}
        {a.notes.map((n) => <NoteCard key={n.id} note={n} editable={canRecord} onSaved={q.reload} />)}
        {canRecord && a.notes.length === 0 && <NoteForm appointmentId={a.id} onSaved={q.reload} />}
      </section>

      <section>
        <h2>งานติดตามหลังปรึกษา</h2>
        {a.tasks.length === 0 && <Empty title="ยังไม่มีงานติดตาม" />}
        <div className="list">
          {a.tasks.map((t) => <TaskRow key={t.id} t={t} onChanged={q.reload} />)}
        </div>
        {canRecord && <TaskForm a={a} onSaved={q.reload} />}
      </section>
    </>
  );
}

function NoteCard({ note, editable, onSaved }: { note: Note; editable: boolean; onSaved(): void }) {
  const [edit, setEdit] = useState(false);
  if (edit) return <NoteForm note={note} onSaved={() => { setEdit(false); onSaved(); }} onCancel={() => setEdit(false)} />;
  return (
    <div className="panel note">
      <div className="row wrap">
        <Badge tone={note.visibility === "shared" ? "teal" : "gray"}>{note.visibility === "shared" ? "แชร์ให้นักศึกษา" : "ส่วนตัว (เฉพาะอาจารย์)"}</Badge>
        <span className="muted grow">อัปเดต {dateTime(note.updated_at)}</span>
        {editable && <button className="btn sm" onClick={() => setEdit(true)}>แก้ไข</button>}
      </div>
      {note.issues && (<><h4>ประเด็นที่คุย</h4><p className="pre">{note.issues}</p></>)}
      {note.summary && (<><h4>สรุป</h4><p className="pre">{note.summary}</p></>)}
    </div>
  );
}

function NoteForm({ appointmentId, note, onSaved, onCancel }: { appointmentId?: string; note?: Note; onSaved(): void; onCancel?(): void }) {
  const toast = useToast();
  const [issues, setIssues] = useState(note?.issues ?? "");
  const [summary, setSummary] = useState(note?.summary ?? "");
  const [vis, setVis] = useState<Visibility>(note?.visibility ?? "shared");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      if (note) await api.patchNote(note.id, { issues, summary, visibility: vis });
      else await api.addNote(appointmentId!, { issues: issues || undefined, summary: summary || undefined, visibility: vis });
      toast.ok("บันทึกแล้ว");
      onSaved();
    } catch (err) {
      toast.fail(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={submit}>
      <label className="field"><span>ประเด็นที่คุย</span><textarea rows={3} value={issues} onChange={(e) => setIssues(e.target.value)} /></label>
      <label className="field"><span>สรุปและข้อตกลง</span><textarea rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} /></label>
      <div className="row wrap">
        <label className="check"><input type="radio" checked={vis === "shared"} onChange={() => setVis("shared")} /> แชร์ให้นักศึกษา (และแจ้งเตือน)</label>
        <label className="check"><input type="radio" checked={vis === "private"} onChange={() => setVis("private")} /> ส่วนตัว</label>
        <span className="grow" />
        {onCancel && <button type="button" className="btn" onClick={onCancel}>ยกเลิก</button>}
        <button className="btn primary" disabled={busy || (!issues.trim() && !summary.trim())}>บันทึก</button>
      </div>
    </form>
  );
}

const NEXT: Record<TaskStatus, [TaskStatus, string][]> = {
  todo: [["doing", "เริ่มทำ"], ["done", "ทำเสร็จแล้ว"]],
  doing: [["done", "ทำเสร็จแล้ว"], ["todo", "ย้อนกลับ"]],
  done: [["todo", "ย้อนกลับ"]],
  cancelled: [],
};

function TaskRow({ t, onChanged }: { t: AppointmentTask; onChanged(): void }) {
  const toast = useToast();
  return (
    <div className="row-item">
      <div className="grow">
        <strong>{t.title}</strong>
        {t.description && <div className="muted">{t.description}</div>}
        <div className="muted">กำหนดส่ง {dueLabel(t.due_date)} {t.is_overdue && <Badge tone="red">เลยกำหนด</Badge>}</div>
      </div>
      <Badge tone={t.status === "done" ? "green" : t.status === "doing" ? "teal" : "amber"}>{TASK_STATUS[t.status]}</Badge>
      {NEXT[t.status].map(([s, label]) => (
        <button key={s} className="btn sm" onClick={async () => { try { await api.setTaskStatus(t.id, s); onChanged(); } catch (e) { toast.fail(e); } }}>{label}</button>
      ))}
    </div>
  );
}

function TaskForm({ a, onSaved }: { a: AppointmentDetail; onSaved(): void }) {
  const toast = useToast();
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.addTask(a.id, { title, description: description || undefined, due_date: due || undefined, note_id: a.notes[0]?.id });
      toast.ok("มอบงานให้ " + a.student.name + " แล้ว");
      setTitle(""); setDue(""); setDescription("");
      onSaved();
    } catch (err) {
      toast.fail(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel form-grid" onSubmit={submit}>
      <label className="field wide"><span>มอบหมายให้ {a.student.name}</span><input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="เช่น ส่งแผนการเรียนฉบับร่าง" /></label>
      <label className="field"><span>กำหนดส่ง</span><input type="date" value={due} onChange={(e) => setDue(e.target.value)} /></label>
      <label className="field wide"><span>รายละเอียด (ไม่บังคับ)</span><input value={description} onChange={(e) => setDescription(e.target.value)} /></label>
      <div className="field end"><button className="btn primary" disabled={busy || !title.trim()}>มอบหมายงาน</button></div>
    </form>
  );
}
