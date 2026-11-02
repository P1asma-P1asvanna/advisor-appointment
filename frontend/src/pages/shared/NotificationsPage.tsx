import { useNavigate } from "react-router-dom";
import { api } from "../../api/endpoints";
import type { AppNotification } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Empty, ErrorBox, Loading, PageHeader } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { dateTime } from "../../lib/format";
import { useLoad } from "../../lib/hooks";

const changed = () => window.dispatchEvent(new Event("notifications:changed"));

export default function NotificationsPage() {
  const { user } = useAuth();
  const nav = useNavigate();
  const toast = useToast();
  const q = useLoad(() => api.notifications(), []);

  async function open(n: AppNotification) {
    try {
      if (!n.read_at) await api.read(n.id);
      changed();
    } catch (e) {
      toast.fail(e);
    }
    if (n.appointment_id && user?.role !== "admin") nav(`/appointments/${n.appointment_id}`);
    else q.reload();
  }

  return (
    <>
      <PageHeader
        title="การแจ้งเตือน"
        sub={q.data ? (q.data.unread ? `ยังไม่ได้อ่าน ${q.data.unread} รายการ` : "อ่านครบแล้ว") : undefined}
        actions={q.data && q.data.unread > 0 ? (
          <button className="btn sm" onClick={async () => { try { await api.readAll(); changed(); q.reload(); } catch (e) { toast.fail(e); } }}>ทำเครื่องหมายว่าอ่านทั้งหมด</button>
        ) : undefined}
      />
      {q.loading ? <Loading /> : q.error ? <ErrorBox message={q.error} retry={q.reload} /> :
        q.data!.items.length === 0 ? <Empty title="ยังไม่มีการแจ้งเตือน" /> :
        <div className="list">
          {q.data!.items.map((n) => (
            <button key={n.id} className={"row-item notif" + (n.read_at ? "" : " unread")} onClick={() => open(n)}>
              <span className="dot" aria-hidden />
              <span className="grow">
                <strong>{n.title}</strong>
                {n.body && <span className="muted block">{n.body}</span>}
              </span>
              <span className="muted">{dateTime(n.created_at)}</span>
            </button>
          ))}
        </div>}
    </>
  );
}
