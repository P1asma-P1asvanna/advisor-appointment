import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/endpoints";
import type { Appointment } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { ApptBadge, Empty, ErrorBox, Loading, PageHeader, ReasonModal, Tabs, Where } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { dayLabel, range } from "../../lib/format";
import { useLoad } from "../../lib/hooks";

export default function AppointmentsPage() {
  const { user } = useAuth();
  const toast = useToast();
  const isAdvisor = user?.role === "advisor";
  const [view, setView] = useState<"upcoming" | "past">("upcoming");
  const list = useLoad(() => api.appointments(view), [view]);
  const [cancelling, setCancelling] = useState<Appointment | null>(null);

  async function mark(a: Appointment, status: "completed" | "no_show") {
    try {
      await api.setStatus(a.id, status);
      toast.ok(status === "completed" ? "บันทึกว่าปรึกษาเสร็จสิ้นแล้ว" : "บันทึกว่าไม่มาตามนัดแล้ว");
      list.reload();
    } catch (e) {
      toast.fail(e);
    }
  }

  return (
    <>
      <PageHeader title={isAdvisor ? "นัดหมาย" : "นัดของฉัน"} sub={isAdvisor ? "นัดที่นักศึกษาจองเข้าพบ" : "นัดที่คุณจองไว้และประวัติการพบ"}
        actions={<button className="btn" onClick={() => api.downloadCalendar().catch((e) => toast.fail(e))}>ส่งออกนัดทั้งหมดเข้าปฏิทิน (.ics)</button>} />
      <Tabs<"upcoming" | "past"> value={view} onChange={setView} items={[["upcoming", "กำลังจะมาถึง"], ["past", "ที่ผ่านมา"]]} />
      {list.loading ? <Loading /> : list.error ? <ErrorBox message={list.error} retry={list.reload} /> :
        list.data!.items.length === 0 ? <Empty title={view === "upcoming" ? "ไม่มีนัดที่กำลังจะมาถึง" : "ยังไม่มีประวัติการพบ"} hint={!isAdvisor && view === "upcoming" ? "ไปที่เมนู จองนัดหมาย เพื่อเลือกเวลา" : undefined} /> :
        <div className="list">
          {list.data!.items.map((a) => {
            const active = a.status === "pending" || a.status === "confirmed";
            const started = new Date(a.starts_at).getTime() <= Date.now();
            return (
              <div key={a.id} className="appt">
                <div className="appt-main">
                  <div className="row wrap">
                    <strong>{dayLabel(a.starts_at)} · {range(a.starts_at, a.ends_at)}</strong>
                    <ApptBadge s={a.status} />
                  </div>
                  <div>{a.topic}</div>
                  <div className="muted">
                    {isAdvisor ? a.student.name : `${a.advisor.name} · ${a.advisor.department ?? ""}`} · <Where mode={a.mode} location={a.location} url={a.meeting_url} />
                  </div>
                  {a.cancel_reason && <div className="muted">เหตุผลที่ยกเลิก: {a.cancel_reason}</div>}
                </div>
                <div className="row wrap">
                  <Link className="btn sm" to={`/appointments/${a.id}`}>{isAdvisor ? "บันทึก/งาน" : "รายละเอียด"}</Link>
                  {isAdvisor && active && started && (
                    <>
                      <button className="btn sm primary" onClick={() => mark(a, "completed")}>ปรึกษาเสร็จสิ้น</button>
                      <button className="btn sm" onClick={() => mark(a, "no_show")}>ไม่มาตามนัด</button>
                    </>
                  )}
                  {active && !started && <button className="btn sm danger-ghost" onClick={() => setCancelling(a)}>ยกเลิกนัด</button>}
                </div>
              </div>
            );
          })}
        </div>}

      {cancelling && (
        <ReasonModal
          title="ยกเลิกนัดนี้?"
          label={isAdvisor ? "เหตุผล (นักศึกษาจะได้รับแจ้ง)" : "เหตุผล (ไม่บังคับ)"}
          confirmLabel="ยืนยันยกเลิกนัด"
          onClose={() => setCancelling(null)}
          onConfirm={async (reason) => {
            try {
              await api.cancelAppointment(cancelling.id, reason || undefined);
              toast.ok("ยกเลิกนัดแล้ว");
              setCancelling(null);
              list.reload();
            } catch (e) {
              toast.fail(e);
            }
          }}
        />
      )}
    </>
  );
}
