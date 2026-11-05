import { get, patch, post, put } from "./client";
import type {
  AdvisorRef, AuditItem, AppNotification, Appointment, AppointmentDetail, LoginResult, ManagedUser, Mode, Note, Overview, Policy,
  Role, Slot, Task, TaskStatus, User, Visibility,
} from "./types";

export const api = {
  login: (email: string, password: string, role?: Role) => post<LoginResult>("/auth/login", { email, password, role }),
  me: () => get<User>("/me"),
  updateMe: (full_name: string) => patch<User>("/me", { full_name }),
  features: () => get<{ password_reset: boolean }>("/auth/features"),
  forgotPassword: (email: string) => post<{ ok: boolean }>("/auth/forgot-password", { email }),
  resetPassword: (token: string, new_password: string) => post<{ ok: boolean }>("/auth/reset-password", { token, new_password }),
  changePassword: (current_password: string, new_password: string) =>
    post<LoginResult>("/auth/change-password", { current_password, new_password }),

  users: (q: { role?: Role; q?: string } = {}) => get<{ items: ManagedUser[] }>("/admin/users", q),
  createUser: (b: { email: string; full_name: string; role: Role; department?: string; password: string }) =>
    post<ManagedUser>("/admin/users", b),
  updateUser: (id: string, b: { full_name?: string; department?: string; is_active?: boolean; email?: string; role?: Role }) =>
    patch<ManagedUser>(`/admin/users/${id}`, b),
  adminResetPassword: (id: string, password: string) => post<{ ok: boolean }>(`/admin/users/${id}/reset-password`, { password }),
  advisors: (department?: string) => get<{ items: AdvisorRef[] }>("/advisors", { department }),

  slots: (q: { advisor_id?: string; department?: string; status?: string; from_date?: string; to_date?: string } = {}) =>
    get<{ items: Slot[] }>("/slots", q),
  audit: (q?: string) => get<{ items: AuditItem[] }>("/admin/audit", { q }),
  createSlot: (b: { starts_at: string; ends_at: string; mode: Mode; location?: string; meeting_url?: string }) =>
    post<Slot>("/slots", b),
  updateSlot: (id: string, b: { starts_at?: string; ends_at?: string; mode?: Mode; location?: string; meeting_url?: string }) =>
    patch<Slot>(`/slots/${id}`, b),
  cancelSlot: (id: string) => post<Slot>(`/slots/${id}/cancel`),

  updateTopic: (id: string, topic: string) => patch<Appointment>(`/appointments/${id}`, { topic }),
  book: (slot_id: string, topic: string) => post<Appointment>("/appointments", { slot_id, topic }),
  appointments: (view: "upcoming" | "past" | "all" = "all") => get<{ items: Appointment[] }>("/appointments", { view }),
  appointment: (id: string) => get<AppointmentDetail>(`/appointments/${id}`),
  cancelAppointment: (id: string, reason?: string) => post<Appointment>(`/appointments/${id}/cancel`, { reason }),
  setStatus: (id: string, status: "completed" | "no_show") => post<Appointment>(`/appointments/${id}/status`, { status }),
  addNote: (id: string, b: { issues?: string; summary?: string; visibility: Visibility }) =>
    post<Note>(`/appointments/${id}/notes`, b),
  patchNote: (id: string, b: { issues?: string; summary?: string; visibility?: Visibility }) =>
    patch<Note>(`/notes/${id}`, b),

  tasks: () => get<{ items: Task[] }>("/tasks"),
  addTask: (appointmentId: string, b: { title: string; description?: string; due_date?: string; note_id?: string }) =>
    post<Task>(`/appointments/${appointmentId}/tasks`, b),
  setTaskStatus: (id: string, status: TaskStatus) => patch<Task>(`/tasks/${id}`, { status }),

  notifications: () => get<{ items: AppNotification[]; unread: number }>("/notifications"),
  readAll: () => post<{ marked: number }>("/notifications/read-all"),
  read: (id: string) => post<AppNotification>(`/notifications/${id}/read`),

  policy: (department?: string) => get<Policy>("/policy", { department }),
  savePolicy: (p: Policy) => put<Policy>("/admin/policy", p),
  overview: (department?: string) => get<Overview>("/admin/overview", { department }),
  sendReminders: () => post<{ created: number }>("/admin/jobs/send-reminders"),
};
