import { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { homeFor, useAuth } from "./auth/AuthContext";
import type { Role } from "./api/types";
import Layout from "./components/Layout";
import { Loading } from "./components/ui";
import Login from "./pages/Login";
import BookPage from "./pages/student/BookPage";
import SlotsPage from "./pages/advisor/SlotsPage";
import AppointmentsPage from "./pages/shared/AppointmentsPage";
import AppointmentDetailPage from "./pages/shared/AppointmentDetailPage";
import TasksPage from "./pages/shared/TasksPage";
import NotificationsPage from "./pages/shared/NotificationsPage";
import OverviewPage from "./pages/admin/OverviewPage";
import PolicyPage from "./pages/admin/PolicyPage";
import UsersPage from "./pages/admin/UsersPage";
import AccountPage from "./pages/shared/AccountPage";

function Guard({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user } = useAuth();
  const { pathname } = useLocation();
  if (!user) return <Navigate to="/login" replace />;
  // A new or reset account may only change its password until it has done so (the API enforces this too).
  if (user.must_change_password && pathname !== "/account") return <Navigate to="/account" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return <>{children}</>;
}

function Home() {
  const { user } = useAuth();
  return <Navigate to={user ? homeFor(user.role) : "/login"} replace />;
}

export default function App() {
  const { loading } = useAuth();
  if (loading) return <Loading />;
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Guard><Layout /></Guard>}>
        <Route path="/book" element={<Guard roles={["student"]}><BookPage /></Guard>} />
        <Route path="/slots" element={<Guard roles={["advisor"]}><SlotsPage /></Guard>} />
        <Route path="/appointments" element={<Guard roles={["student", "advisor"]}><AppointmentsPage /></Guard>} />
        <Route path="/appointments/:id" element={<Guard roles={["student", "advisor"]}><AppointmentDetailPage /></Guard>} />
        <Route path="/tasks" element={<Guard roles={["student", "advisor"]}><TasksPage /></Guard>} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/overview" element={<Guard roles={["admin"]}><OverviewPage /></Guard>} />
        <Route path="/users" element={<Guard roles={["admin"]}><UsersPage /></Guard>} />
        <Route path="/account" element={<AccountPage />} />
        <Route path="/policy" element={<Guard roles={["admin"]}><PolicyPage /></Guard>} />
      </Route>
      <Route path="*" element={<Home />} />
    </Routes>
  );
}
