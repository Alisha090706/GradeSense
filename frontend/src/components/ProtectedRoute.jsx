import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function ProtectedRoute({ children, role }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="max-w-5xl mx-auto px-6 py-16 text-center text-ink/60">Loading…</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (role && user.user.role !== role) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-16 text-center text-brick">
        This page is for {role} accounts — you're signed in as a {user.user.role}.
      </div>
    );
  }
  return children;
}
