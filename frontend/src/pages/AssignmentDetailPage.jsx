import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getAssignment, listTestCases } from "../api/assignments.js";
import { getSubmission, listMySubmissions, submit } from "../api/submissions.js";
import { askTutor, getTutorHistory } from "../api/tutor.js";
import ScoreStamp from "../components/ScoreStamp.jsx";

const LANGUAGES = ["python", "java", "cpp", "javascript"];

export default function AssignmentDetailPage() {
  const { assignmentId } = useParams();
  const [assignment, setAssignment] = useState(null);
  const [publicTestCases, setPublicTestCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [content, setContent] = useState("");
  const [language, setLanguage] = useState("python");
  const [mcqAnswers, setMcqAnswers] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [latestResult, setLatestResult] = useState(null);
  const [submissionId, setSubmissionId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [a, testCases, mySubmissions] = await Promise.all([
          getAssignment(assignmentId),
          listTestCases(assignmentId),
          listMySubmissions(assignmentId),
        ]);
        if (cancelled) return;
        setAssignment(a);
        setPublicTestCases(testCases);

        if (mySubmissions.length > 0) {
          const detail = await getSubmission(mySubmissions[0].id);
          if (!cancelled) {
            setSubmissionId(mySubmissions[0].id);
            setLatestResult({
              score: detail.feedback?.score ?? 0,
              total_points: detail.feedback?.total_points ?? 0,
              feedback: detail.feedback?.text ?? "",
              exec_status: detail.execution_result?.status ?? "n/a",
              breakdown: detail.feedback?.breakdown ?? [],
            });
            setContent(detail.content || "");
            if (a.type === "mcq" && detail.content) {
              try {
                setMcqAnswers(JSON.parse(detail.content));
              } catch {
                // fall through with empty answers if a previous submission predates this format
              }
            }
          }
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [assignmentId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (assignment.type === "mcq") {
      const unanswered = (assignment.constraints?.questions || []).filter(
        (q) => !(mcqAnswers[q.id]?.length > 0)
      );
      if (unanswered.length > 0) {
        setError("Please answer every question before submitting.");
        return;
      }
    }
    setSubmitting(true);
    try {
      const submissionContent = assignment.type === "mcq" ? JSON.stringify(mcqAnswers) : content;
      const result = await submit(assignmentId, { content: submissionContent, language });
      setSubmissionId(result.submission_id);
      setLatestResult({
        score: result.score,
        total_points: result.total_points,
        feedback: result.feedback,
        exec_status: result.exec_status,
        similarity_flagged: result.similarity_flagged,
        breakdown: result.breakdown ?? [],
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <p className="text-ink/60">Loading assignment…</p>;
  if (error && !assignment) return <p className="text-brick">{error}</p>;

  return (
    <div className="grid lg:grid-cols-3 gap-8">
      <div className="lg:col-span-2 space-y-6">
        <div>
          <p className="text-xs uppercase tracking-wide text-pen/70 font-medium mb-1">{assignment.type}</p>
          <h1 className="font-display text-3xl font-semibold text-ink">{assignment.title}</h1>
          <p className="text-ink/70 mt-3 whitespace-pre-wrap">{assignment.description}</p>
        </div>

        {publicTestCases.length > 0 && (
          <div>
            <h2 className="font-medium text-ink mb-2">Public test cases</h2>
            <ul className="space-y-2 font-mono text-sm">
              {publicTestCases.map((tc) => (
                <li key={tc.id} className="bg-white border border-pen/10 rounded p-3">
                  <pre className="whitespace-pre-wrap">{JSON.stringify(tc.input)}</pre>
                  <p className="text-ink/50 mt-1">→ {JSON.stringify(tc.expected_output)}</p>
                </li>
              ))}
            </ul>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-medium text-ink">Your submission</h2>
            {assignment.type === "programming" && (
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="text-sm border border-pen/30 rounded px-2 py-1"
              >
                {LANGUAGES.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
            )}
          </div>

          {assignment.type === "mcq" ? (
            <McqAnswerForm
              questions={assignment.constraints?.questions || []}
              answers={mcqAnswers}
              onChange={setMcqAnswers}
            />
          ) : (
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              required
              rows={12}
              placeholder={assignment.type === "sql" ? "Write your SQL query" : "Write your answer"}
              className="w-full font-mono text-sm px-3 py-2 rounded border border-pen/30 bg-white focus:border-pen"
            />
          )}

          {error && (
            <p role="alert" className="text-sm text-brick">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="px-6 py-2.5 rounded bg-pen text-paper font-medium hover:bg-pen-dark transition-colors disabled:opacity-60"
          >
            {submitting ? "Grading…" : "Submit"}
          </button>
        </form>

        {latestResult && (
          <div className="flex gap-4 p-4 rounded border border-pen/15 bg-white">
            <ScoreStamp score={latestResult.score} total={latestResult.total_points} size="lg" />
            <div className="flex-1">
              <p className="text-xs uppercase tracking-wide text-ink/50 mb-1">{latestResult.exec_status}</p>
              <p className="text-ink/80 whitespace-pre-wrap">{latestResult.feedback}</p>
              {latestResult.similarity_flagged?.length > 0 && (
                <p className="text-xs text-brick mt-2">
                  {latestResult.similarity_flagged.length} similarity match(es) flagged for review.
                </p>
              )}
              {assignment.type === "mcq" && latestResult.breakdown?.length > 0 && (
                <ul className="mt-3 space-y-1.5 text-sm">
                  {latestResult.breakdown.map((b) => (
                    <li key={b.category} className="flex items-start justify-between gap-3">
                      <span className={b.earned >= b.possible ? "text-ink/70" : "text-brick"}>
                        {b.detail || b.category}
                      </span>
                      <span className="text-ink/40 shrink-0">
                        {b.earned}/{b.possible}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="lg:col-span-1">
        <TutorPanel submissionId={submissionId} />
      </div>
    </div>
  );
}

function TutorPanel({ submissionId }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [asking, setAsking] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);

  // Real fix from Phase 13: this panel used to never pass submissionId at all
  // (see the Phase 13 README section) — it now both sends it with every
  // question and loads that submission's prior history on mount, same as the
  // full-page TutorChatPage does.
  useEffect(() => {
    let cancelled = false;
    setLoadingHistory(true);
    getTutorHistory(submissionId)
      .then((history) => {
        if (!cancelled) setMessages(history.map((m) => ({ role: m.role, content: m.content })));
      })
      .catch(() => {})
      .finally(() => !cancelled && setLoadingHistory(false));
    return () => {
      cancelled = true;
    };
  }, [submissionId]);

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;
    const q = question;
    setQuestion("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setAsking(true);
    try {
      const result = await askTutor({ question: q, submissionId });
      setMessages((prev) => [...prev, { role: "tutor", content: result.answer }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "tutor", content: `(couldn't get an answer: ${err.message})` }]);
    } finally {
      setAsking(false);
    }
  };

  return (
    <div className="sticky top-6 border border-pen/15 rounded bg-white flex flex-col h-[32rem]">
      <div className="px-4 py-3 border-b border-pen/10 flex items-center justify-between">
        <div>
          <h2 className="font-display font-medium text-pen">Ask the tutor</h2>
          <p className="text-xs text-ink/50">Never gives you the answer — only the way there.</p>
        </div>
        <Link
          to={submissionId ? `/tutor?submission_id=${submissionId}` : "/tutor"}
          className="text-xs text-pen underline shrink-0"
        >
          Full chat
        </Link>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {loadingHistory && <p className="text-sm text-ink/40">Loading…</p>}
        {!loadingHistory && messages.length === 0 && (
          <p className="text-sm text-ink/40">Ask about a failing test, a concept, or a hint.</p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`text-sm p-2.5 rounded max-w-[85%] ${
              m.role === "user" ? "bg-pen/10 ml-auto text-ink" : "bg-paper border border-pen/10 text-ink"
            }`}
          >
            {m.content}
          </div>
        ))}
        {asking && <p className="text-xs text-ink/40">Thinking…</p>}
      </div>
      <form onSubmit={handleAsk} className="p-3 border-t border-pen/10 flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Why did my test fail?"
          className="flex-1 text-sm px-3 py-2 rounded border border-pen/30"
        />
        <button
          type="submit"
          disabled={asking}
          className="px-3 py-2 rounded bg-pen text-paper text-sm font-medium hover:bg-pen-dark disabled:opacity-60"
        >
          Ask
        </button>
      </form>
    </div>
  );
}

function McqAnswerForm({ questions, answers, onChange }) {
  if (questions.length === 0) {
    return <p className="text-sm text-ink/50 italic">This quiz has no questions yet — check back later.</p>;
  }

  const toggle = (questionId, optionKey, isMultiSelect) => {
    const current = answers[questionId] || [];
    let next;
    if (isMultiSelect) {
      next = current.includes(optionKey) ? current.filter((k) => k !== optionKey) : [...current, optionKey];
    } else {
      next = [optionKey];
    }
    onChange({ ...answers, [questionId]: next });
  };

  return (
    <div className="space-y-5">
      {questions.map((q, idx) => {
        // A question intended as single-answer still lets a student pick more than one
        // option in the UI if we don't distinguish input types — radio buttons make
        // single-answer questions behave correctly by construction. There's no
        // "intended" single vs multi flag stored server-side (the grading rule is the
        // same exact-set-match either way), so this uses radios only when the question
        // was authored with exactly one correct option, which is the common case and
        // matches student expectations for "select one" wording.
        const isMultiSelect = (q.correct_options || []).length > 1;
        const selected = answers[q.id] || [];
        return (
          <div key={q.id} className="p-4 rounded border border-pen/15 bg-white">
            <p className="text-ink font-medium mb-3">
              {idx + 1}. {q.text}
              {isMultiSelect && <span className="text-xs text-ink/40 font-normal ml-2">(select all that apply)</span>}
            </p>
            <div className="space-y-2">
              {Object.entries(q.options || {}).map(([key, text]) => (
                <label key={key} className="flex items-center gap-2 text-sm text-ink/80 cursor-pointer">
                  <input
                    type={isMultiSelect ? "checkbox" : "radio"}
                    name={`q-${q.id}`}
                    checked={selected.includes(key)}
                    onChange={() => toggle(q.id, key, isMultiSelect)}
                  />
                  <span className="font-mono text-xs text-ink/40 w-4">{key}</span>
                  <span>{text}</span>
                </label>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
