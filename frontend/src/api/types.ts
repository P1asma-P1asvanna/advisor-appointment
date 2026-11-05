export type Role = "student" | "advisor" | "admin";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  department: string | null;
  must_change_password: boolean;
}

export interface ManagedUser {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  department: string | null;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
}

export interface LoginResult {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface AdvisorRef {
  id: string;
  name: string;
  department: string | null;
}

export type SlotStatus = "open" | "booked" | "cancelled";
export type Mode = "onsite" | "online";

export interface Slot {
  id: string;
  advisor: AdvisorRef;
  starts_at: string;
  ends_at: string;
  mode: Mode;
  location: string | null;
  meeting_url: string | null;
  status: SlotStatus;
  appointment_id?: string | null; // advisors/admins only
  student_name?: string | null; // advisors/admins only
}

export type AppointmentStatus = "pending" | "confirmed" | "completed" | "cancelled" | "no_show";

export interface Appointment {
  id: string;
  status: AppointmentStatus;
  topic: string;
  cancel_reason: string | null;
  slot_id: string;
  starts_at: string;
  ends_at: string;
  mode: Mode;
  location: string | null;
  meeting_url: string | null;
  advisor: AdvisorRef;
  student: { id: string; name: string };
  created_at: string;
  updated_at: string;
}

export type Visibility = "private" | "shared";

export interface Note {
  id: string;
  author_id: string;
  issues: string | null;
  summary: string | null;
  visibility: Visibility;
  created_at: string;
  updated_at: string;
}

export type TaskStatus = "todo" | "doing" | "done" | "cancelled";

export interface AppointmentTask {
  id: string;
  note_id: string | null;
  title: string;
  description: string | null;
  due_date: string | null;
  status: TaskStatus;
  completed_at: string | null;
  is_overdue: boolean;
}

export interface AppointmentDetail extends Appointment {
  notes: Note[];
  tasks: AppointmentTask[];
}

export interface Task extends AppointmentTask {
  appointment_id: string;
  appointment_topic: string;
  assignee_id: string;
  assignee_name: string;
  created_by: string;
  created_by_name: string;
  created_at: string;
}

export interface AppNotification {
  id: string;
  type: string;
  title: string;
  body: string | null;
  appointment_id: string | null;
  created_at: string;
  read_at: string | null;
}

export interface Policy {
  department: string;
  min_notice_hours: number;
  cancel_before_hours: number;
  max_active_per_student: number;
  reminder_hours_before: number;
}

export interface AdvisorStat {
  id: string;
  full_name: string;
  department: string | null;
  slots_total: number;
  slots_booked: number;
  appts_completed: number;
  appts_no_show: number;
  appts_upcoming: number;
  utilization: number | null;
}

export interface Overview {
  department: string | null;
  departments: string[];
  kpis: {
    slots_total: number;
    slots_booked: number;
    utilization: number | null;
    appts_completed: number;
    appts_no_show: number;
    no_show_rate: number | null;
    appts_upcoming: number;
    overdue_tasks: number;
  };
  advisors: AdvisorStat[];
  watchlist: { id: string; full_name: string; no_shows: number; overdue_tasks: number }[];
}

export interface AuditItem {
  id: number;
  at: string;
  actor_email: string | null; // null = the system or the person themselves via an emailed link
  action: string;
  target_email: string | null;
  details: Record<string, unknown> | null;
}
