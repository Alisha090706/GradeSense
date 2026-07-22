import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { registerStudent, registerTeacher } from "../api/auth.js";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [role, setRole] = useState("student");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [institution, setInstitution] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const response =
        role === "student"
          ? await registerStudent({ email, password })
          : await registerTeacher({ email, password, institution });
      setResult(response);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (result) {
    // The backend has no SMTP configured yet (see backend README's Phase 1
    // section) — it hands back a dev_verification_token directly instead of
    // emailing it. This screen surfaces that honestly rather than pretending
    // an email was sent.
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <div className="w-full max-w-md text-center">
          <h1 className="font-display text-2xl font-semibold text-pen mb-4">Almost there</h1>
          <p className="text-ink/80 mb-4">{result.message}</p>
          <div className="bg-pen/5 border border-pen/20 rounded p-4 text-left text-sm">
            <p className="text-ink/60 mb-2">
              No email service is configured yet, so here's your verification link directly:
            </p>
            <Link
              to={`/verify-email?token=${encodeURIComponent(result.dev_verification_token)}`}
              className="text-pen underline break-all"
            >
              Verify my email
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <h1 className="font-display text-3xl font-semibold text-pen mb-1">Create an account</h1>

        <div className="flex gap-2 my-6" role="radiogroup" aria-label="Account type">
          {["student", "teacher"].map((r) => (
            <button
              key={r}
              type="button"
              role="radio"
              aria-checked={role === r}
              onClick={() => setRole(r)}
              className={`flex-1 py-2 rounded border capitalize transition-colors ${
                role === r ? "border-pen bg-pen text-paper" : "border-pen/30 text-ink"
              }`}
            >
              {r}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-ink mb-1">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 rounded border border-pen/30 bg-white focus:border-pen"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-ink mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 rounded border border-pen/30 bg-white focus:border-pen"
            />
          </div>
          {role === "teacher" && (
            <div>
              <label htmlFor="institution" className="block text-sm font-medium text-ink mb-1">
                Institution (optional)
              </label>
              <input
                id="institution"
                type="text"
                value={institution}
                onChange={(e) => setInstitution(e.target.value)}
                className="w-full px-3 py-2 rounded border border-pen/30 bg-white focus:border-pen"
              />
              <p className="text-xs text-ink/50 mt-1">
                Teacher accounts need admin approval after email verification — see the platform's teacher
                verification flow.
              </p>
            </div>
          )}

          {error && (
            <p role="alert" className="text-sm text-brick">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2.5 rounded bg-pen text-paper font-medium hover:bg-pen-dark transition-colors disabled:opacity-60"
          >
            {submitting ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-sm text-ink/60 text-center">
          Already have an account?{" "}
          <Link to="/login" className="text-pen underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
