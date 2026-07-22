import React from "react";
import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import AdminVerificationQueuePage from "./pages/AdminVerificationQueuePage.jsx";
import AssignmentAnalyticsPage from "./pages/AssignmentAnalyticsPage.jsx";
import AssignmentDetailPage from "./pages/AssignmentDetailPage.jsx";
import AssignmentManagePage from "./pages/AssignmentManagePage.jsx";
import CourseAnalyticsPage from "./pages/CourseAnalyticsPage.jsx";
import CourseManagePage from "./pages/CourseManagePage.jsx";
import LandingPage from "./pages/LandingPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import RegisterPage from "./pages/RegisterPage.jsx";
import StudentDashboardPage from "./pages/StudentDashboardPage.jsx";
import TeacherDashboardPage from "./pages/TeacherDashboardPage.jsx";
import TutorChatPage from "./pages/TutorChatPage.jsx";
import VerifyEmailPage from "./pages/VerifyEmailPage.jsx";

function Protected({ role, children }) {
  return (
    <ProtectedRoute role={role}>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />

      {/* Student — Phase 11 */}
      <Route
        path="/dashboard"
        element={
          <Protected role="student">
            <StudentDashboardPage />
          </Protected>
        }
      />
      <Route
        path="/assignments/:assignmentId"
        element={
          <Protected role="student">
            <AssignmentDetailPage />
          </Protected>
        }
      />
      <Route
        path="/tutor"
        element={
          <Protected role="student">
            <TutorChatPage />
          </Protected>
        }
      />

      {/* Teacher — Phase 12 */}
      <Route
        path="/teacher"
        element={
          <Protected role="teacher">
            <TeacherDashboardPage />
          </Protected>
        }
      />
      <Route
        path="/teacher/courses/:courseId"
        element={
          <Protected role="teacher">
            <CourseManagePage />
          </Protected>
        }
      />
      <Route
        path="/teacher/courses/:courseId/analytics"
        element={
          <Protected role="teacher">
            <CourseAnalyticsPage />
          </Protected>
        }
      />
      <Route
        path="/teacher/assignments/:assignmentId"
        element={
          <Protected role="teacher">
            <AssignmentManagePage />
          </Protected>
        }
      />
      <Route
        path="/teacher/assignments/:assignmentId/analytics"
        element={
          <Protected role="teacher">
            <AssignmentAnalyticsPage />
          </Protected>
        }
      />

      {/* Admin — Phase 12 */}
      <Route
        path="/admin/verification-queue"
        element={
          <Protected role="admin">
            <AdminVerificationQueuePage />
          </Protected>
        }
      />
    </Routes>
  );
}
