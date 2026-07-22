import React, { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { askTutor, getTutorHistory } from "../api/tutor.js";

/**
 * Full-page version of the chat panel embedded in AssignmentDetailPage
 * (Phase 11) — same API, but with real history (GET /tutor/history, built
 * in Phase 10 but unused by the frontend until now) and room to actually
 * read back a longer conversation. A "conversation" here is implicitly
 * every message for (this student, this submission) — or (this student,
 * no submission) for general questions — per the backend's design; there's
 * no separate thread-switcher because there's no separate thread concept
 * to switch between beyond that.
 */
export default function TutorChatPage() {
  const [searchParams] = useSearchParams();
  const submissionId = searchParams.get("submission_id");

  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(true);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getTutorHistory(submissionId)
      .then((history) => {
        if (!cancelled) setMessages(history.map((m) => ({ role: m.role, content: m.content })));
      })
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [submissionId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;
    const q = question;
    setQuestion("");
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setAsking(true);
    try {
      const result = await askTutor({ question: q, submissionId });
      setMessages((prev) => [...prev, { role: "tutor", content: result.answer }]);
    } catch (err) {
      setError(err.message);
      // Roll back the optimistic user message so a failed send doesn't leave
      // a question sitting in the thread with no reply and no error context.
      setMessages((prev) => prev.slice(0, -1));
      setQuestion(q);
    } finally {
      setAsking(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto flex flex-col h-[calc(100vh-12rem)]">
      <div className="mb-4">
        <h1 className="font-display text-3xl font-semibold text-ink">Ask the tutor</h1>
        <p className="text-sm text-ink/50 mt-1">
          {submissionId
            ? "Talking about a specific submission — questions here can reference its test results directly."
            : "General questions — for something about a specific submission, open the tutor from that assignment's page instead."}
        </p>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto border border-pen/15 rounded-t bg-white px-4 py-4 space-y-3"
      >
        {loading && <p className="text-sm text-ink/40">Loading conversation…</p>}
        {!loading && messages.length === 0 && (
          <p className="text-sm text-ink/40">
            Nothing here yet. Ask about a failing test, a concept you're stuck on, or for a hint — never a full
            solution.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`text-sm p-3 rounded max-w-[80%] whitespace-pre-wrap ${
              m.role === "user" ? "bg-pen/10 ml-auto text-ink" : "bg-paper border border-pen/10 text-ink"
            }`}
          >
            {m.content}
          </div>
        ))}
        {asking && <p className="text-xs text-ink/40">Thinking…</p>}
      </div>

      {error && (
        <p role="alert" className="text-sm text-brick px-1 py-2">
          {error}
        </p>
      )}

      <form onSubmit={handleAsk} className="flex gap-2 p-3 border border-t-0 border-pen/15 rounded-b bg-white">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question…"
          className="flex-1 px-3 py-2 rounded border border-pen/30 focus:border-pen"
          disabled={asking}
        />
        <button
          type="submit"
          disabled={asking || !question.trim()}
          className="px-5 py-2 rounded bg-pen text-paper font-medium hover:bg-pen-dark disabled:opacity-60"
        >
          Ask
        </button>
      </form>
    </div>
  );
}
