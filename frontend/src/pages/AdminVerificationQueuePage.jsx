import React, { useEffect, useState } from "react";
import { approveVerificationRequest, listVerificationRequests, rejectVerificationRequest } from "../api/admin.js";

export default function AdminVerificationQueuePage() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actingOn, setActingOn] = useState(null);

  const load = async () => {
    const data = await listVerificationRequests("pending");
    setRequests(data);
  };

  useEffect(() => {
    load()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleDecision = async (requestId, decision) => {
    setActingOn(requestId);
    setError(null);
    try {
      const action = decision === "approve" ? approveVerificationRequest : rejectVerificationRequest;
      await action(requestId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setActingOn(null);
    }
  };

  if (loading) return <p className="text-ink/60">Loading…</p>;

  return (
    <div className="max-w-2xl">
      <h1 className="font-display text-3xl font-semibold text-ink mb-2">Teacher verification</h1>
      <p className="text-ink/60 mb-6">
        Pending teacher accounts. An institutional-looking email domain is only a hint here — approval is always a
        real decision, not automatic (see backend auth_service.py's is_institutional_domain).
      </p>

      {error && <p className="text-brick mb-4">{error}</p>}

      {requests.length === 0 ? (
        <p className="text-ink/50">Nothing pending.</p>
      ) : (
        <div className="space-y-3">
          {requests.map((r) => (
            <div key={r.id} className="p-4 rounded border border-pen/15 bg-white flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="font-medium text-ink truncate">{r.teacher_email}</p>
                <p className="text-sm text-ink/50">
                  {r.institution || "No institution given"} · {r.submitted_email_domain}
                  {r.likely_institutional && (
                    <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-sage/10 text-sage">
                      looks institutional
                    </span>
                  )}
                </p>
              </div>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => handleDecision(r.id, "reject")}
                  disabled={actingOn === r.id}
                  className="px-3 py-1.5 rounded border border-brick/40 text-brick text-sm hover:bg-brick/5 disabled:opacity-60"
                >
                  Reject
                </button>
                <button
                  onClick={() => handleDecision(r.id, "approve")}
                  disabled={actingOn === r.id}
                  className="px-3 py-1.5 rounded bg-sage text-paper text-sm hover:opacity-90 disabled:opacity-60"
                >
                  Approve
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
