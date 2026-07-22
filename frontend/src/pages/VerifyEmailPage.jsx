import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { verifyEmail } from "../api/auth.js";

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState("verifying"); // verifying | done | error
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setError("No verification token in the link.");
      return;
    }
    verifyEmail(token)
      .then(() => setStatus("done"))
      .catch((err) => {
        setStatus("error");
        setError(err.message);
      });
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center px-6 text-center">
      <div className="max-w-sm">
        {status === "verifying" && <p className="text-ink/60">Verifying your email…</p>}
        {status === "done" && (
          <>
            <h1 className="font-display text-2xl font-semibold text-sage mb-3">Email verified</h1>
            <Link to="/login" className="text-pen underline">
              Sign in now
            </Link>
          </>
        )}
        {status === "error" && (
          <>
            <h1 className="font-display text-2xl font-semibold text-brick mb-3">Couldn't verify</h1>
            <p className="text-ink/70">{error}</p>
          </>
        )}
      </div>
    </div>
  );
}
