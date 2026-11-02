import { Link } from "react-router-dom";
import { api } from "../../api/endpoints";
import type { Task, TaskStatus } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Badge, Empty, ErrorBox, Loading, PageHeader } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { dueLabel } from "../../lib/format";
import { useLoad } from "../../lib/hooks";
import { TASK_STATUS } from "../../lib/labels";

const COLS: TaskStatus[] = ["todo", "doing", "done"];
const MOVES: Record<TaskStatus, [TaskStatus, string][]> = {
  todo: [["doing", "เริ่มทำ →"]],
  doing: [["done", "ทำเสร็จแล้ว ✓"], ["todo", "← ย้อนกลับ"]],
  done: [["todo", "← ย้อนกลับ"]],
  cancelled: [],
};

export default function TasksPage() {
  const { user } = useAuth();
  const toast = useToast();
  const q = useLoad(() => api.tasks(), []);
  const isAdvisor = user?.role === "advisor";

  async function move(t: Task, s: TaskStatus) {
    try {
      await api.setTaskStatus(t.id, s);
      q.reload();
    } catch (e) {
      toast.fail(e);
    }
  }

  return (
    <>
      <PageHeader title={isAdvisor ? "งานที่มอบหมาย" : "งานติดตาม"} sub={isAdvisor ? "ความคืบหน้าของงานที่คุณมอบให้นักศึกษา" : "งานที่อาจารย์มอบหมายหลังการปรึกษา"} />
      {q.loading ? <Loading /> : q.error ? <ErrorBox message={q.error} retry={q.reload} /> :
        q.data!.items.length === 0 ? <Empty title="ยังไม่มีงานติดตาม" hint={isAdvisor ? "มอบงานได้จากหน้ารายละเอียดของนัด" : undefined} /> :
        <div className="board">
          {COLS.map((c) => {
            const items = q.data!.items.filter((t) => t.status === c);
            return (
              <div key={c} className="col">
                <h3>{TASK_STATUS[c]} <span className="count gray">{items.length}</span></h3>
                {items.map((t) => (
                  <div key={t.id} className="task-card">
                    <strong>{t.title}</strong>
                    <span className="muted">{isAdvisor ? t.assignee_name : t.created_by_name} · กำหนด {dueLabel(t.due_date)}</span>
                    {t.is_overdue && <Badge tone="red">เลยกำหนด</Badge>}
                    <Link className="muted" to={`/appointments/${t.appointment_id}`}>จากนัด: {t.appointment_topic}</Link>
                    <div className="row wrap">
                      {MOVES[t.status].map(([s, label]) => <button key={s} className="btn sm" onClick={() => move(t, s)}>{label}</button>)}
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>}
    </>
  );
}
