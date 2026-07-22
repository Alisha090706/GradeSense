import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

const HOME_PATH_BY_ROLE = {
  student: "/dashboard",
  teacher: "/teacher",
  admin: "/admin/verification-queue",
};

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const homePath = user ? HOME_PATH_BY_ROLE[user.user.role] ?? "/" : "/";

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-pen/10 bg-paper">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to={homePath} className="font-display text-2xl font-semibold text-pen">
            GradeSense
          </Link>
          {user && (
            <div className="flex items-center gap-4 text-sm">
              {user.user.role === "student" && (
                <Link to="/tutor" className="text-pen hover:underline">
                  Tutor
                </Link>
              )}
              <span className="text-ink/70">{user.user.email}</span>
              <button
                onClick={handleLogout}
                className="px-3 py-1.5 rounded border border-pen/30 text-pen hover:bg-pen hover:text-paper transition-colors"
              >
                Log out
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="flex-1 max-w-5xl w-full mx-auto px-6 py-8">{children}</main>
      <footer className="border-t border-pen/10 py-4 text-center text-xs text-ink/50">
        GradeSense — an AI-assisted assessment platform
      </footer>
    </div>
  );
}
