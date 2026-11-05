import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/endpoints";
import type { Appointment, Slot } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { ApptBadge, Empty, ErrorBox, Loading, PageHeader, Where } from "../../components/ui";
import { dayKey, dayLabel, range, timeLabel } from "../../lib/format";
import { useLoad } from "../../lib/hooks";
import { APPT_STATUS } from "../../lib/labels";

const WEEKDAYS = ["อา.", "จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส."];
const monthName = new Intl.DateTimeFormat("th-TH", { timeZone: "UTC", month: "long", year: "numeric" });
const pad = (n: number) => String(n).padStart(2, "0");
const ymd = (y: number, m: number, d: number) => `${y}-${pad(m + 1)}-${pad(d)}`; // m is 0-based

/** Sunday-first grid of yyyy-mm-dd keys (null = blank cell) for one month. */
function monthGrid(y: number, m: number): (string | null)[] {
  const first = new Date(Date.UTC(y, m, 1)).getUTCDay();
  const days = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
  const cells: (string | null)[] = Array(first).fill(null);
  for (let d = 1; d <= days; d++) cells.push(ymd(y, m, d));
  while (cells.length % 7) cells.push(null);
  return cells;
}

export default function CalendarPage() {
  const { user } = useAuth();
  const isAdvisor = user?.role === "advisor";
  const today = dayKey(new Date().toISOString());
  const [ty, tm] = today.split("-").map(Number);
  const [year, setYear] = useState(ty);
  const [month, setMonth] = useState(tm - 1);
  const [selected, setSelected] = useState(today);
  const list = useLoad(() => api.appointments("all"), []);
  // Advisors also see the time they have opened but nobody has booked yet.
  const openSlots = useLoad(() => (isAdvisor ? api.slots({ status: "open", from_date: today }) : Promise.resolve({ items: [] as Slot[] })), [isAdvisor]);

  const byDay = useMemo(() => {
    const m = new Map<string, Appointment[]>();
    for (const a of list.data?.items ?? []) {
      if (a.status === "cancelled") continue;
      const k = dayKey(a.starts_at);
      (m.get(k) ?? m.set(k, []).get(k)!).push(a);
    }
    for (const arr of m.values()) arr.sort((a, b) => a.starts_at.localeCompare(b.starts_at));
    return m;
  }, [list.data]);

  const openByDay = useMemo(() => {
    const m = new Map<string, Slot[]>();
    for (const sl of openSlots.data?.items ?? []) {
      if (sl.status !== "open") continue;
      const k = dayKey(sl.starts_at);
      (m.get(k) ?? m.set(k, []).get(k)!).push(sl);
    }
    for (const arr of m.values()) arr.sort((a, b) => a.starts_at.localeCompare(b.starts_at));
    return m;
  }, [openSlots.data]);

  function go(delta: number) {
    const d = new Date(Date.UTC(year, month + delta, 1));
    setYear(d.getUTCFullYear());
    setMonth(d.getUTCMonth());
  }
  function goToday() {
    setYear(ty);
    setMonth(tm - 1);
    setSelected(today);
  }

  const dayItems = byDay.get(selected) ?? [];
  const dayOpen = openByDay.get(selected) ?? [];
  return (
    <>
      <PageHeader title="ปฏิทิน" sub={isAdvisor ? "นัดที่นักศึกษาจองเข้าพบ ดูเป็นรายเดือน" : "นัดของคุณ ดูเป็นรายเดือน"} />
      {list.loading ? <Loading /> : list.error ? <ErrorBox message={list.error} retry={list.reload} /> : (
        <>
          <div className="cal-bar">
            <button className="btn sm" onClick={() => go(-1)} aria-label="เดือนก่อนหน้า">‹</button>
            <strong className="cal-title">{monthName.format(new Date(Date.UTC(year, month, 1)))}</strong>
            <button className="btn sm" onClick={() => go(1)} aria-label="เดือนถัดไป">›</button>
            <button className="btn sm" onClick={goToday}>วันนี้</button>
          </div>
          <div className="cal" role="grid">
            {WEEKDAYS.map((w) => <div key={w} className="cal-head" role="columnheader">{w}</div>)}
            {monthGrid(year, month).map((k, i) => {
              if (!k) return <div key={i} className="cal-cell blank" />;
              const items = byDay.get(k) ?? [];
              const opens = openByDay.get(k) ?? [];
              const cls = "cal-cell" + (k === today ? " today" : "") + (k === selected ? " sel" : "");
              return (
                <button key={k} className={cls} onClick={() => setSelected(k)} aria-label={`${Number(k.slice(8))} มีนัด ${items.length} รายการ`}>
                  <span className="cal-num">{Number(k.slice(8))}</span>
                  {items.slice(0, 2).map((a) => (
                    <span key={a.id} className={"cal-chip " + APPT_STATUS[a.status].tone}>
                      {timeLabel(a.starts_at)} {isAdvisor ? a.student.name : a.advisor.name}
                    </span>
                  ))}
                  {opens.slice(0, Math.max(0, 2 - items.length)).map((sl) => (
                    <span key={sl.id} className="cal-chip open">{timeLabel(sl.starts_at)} ว่าง</span>
                  ))}
                  {items.length + opens.length > 2 && <span className="cal-more">+{items.length + opens.length - 2}</span>}
                  {items.length > 0 && <span className="cal-dot">{items.length}</span>}
                  {opens.length > 0 && <span className="cal-dot open" title="ช่องว่าง">{opens.length}</span>}
                </button>
              );
            })}
          </div>

          <h2>{dayLabel(selected + "T12:00:00+07:00")}</h2>
          {dayItems.length === 0 && dayOpen.length === 0 ? <Empty title="ไม่มีนัดในวันนี้" hint={!isAdvisor ? "ไปที่เมนู จองนัดหมาย เพื่อเลือกเวลา" : undefined} /> : (
            <div className="list">
              {dayItems.map((a) => (
                <div key={a.id} className="appt">
                  <div className="appt-main">
                    <div className="row wrap"><strong>{range(a.starts_at, a.ends_at)}</strong><ApptBadge s={a.status} /></div>
                    <div>{a.topic}</div>
                    <div className="muted">
                      {isAdvisor ? a.student.name : `${a.advisor.name} · ${a.advisor.department ?? ""}`} · <Where mode={a.mode} location={a.location} url={a.meeting_url} />
                    </div>
                  </div>
                  <Link className="btn sm" to={`/appointments/${a.id}`}>{isAdvisor ? "บันทึก/งาน" : "รายละเอียด"}</Link>
                </div>
              ))}
            </div>
          )}
          {dayOpen.length > 0 && (
            <>
              <h3>ช่องเวลาว่าง (ยังไม่มีคนจอง)</h3>
              <div className="list">
                {dayOpen.map((sl) => (
                  <div key={sl.id} className="appt">
                    <div className="appt-main">
                      <strong>{range(sl.starts_at, sl.ends_at)}</strong>
                      <div className="muted"><Where mode={sl.mode} location={sl.location} url={sl.meeting_url} /></div>
                    </div>
                    <Link className="btn sm" to="/slots">แก้ไขที่หน้าเวลาว่างของฉัน</Link>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}
