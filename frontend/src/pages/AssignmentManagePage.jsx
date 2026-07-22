import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getAssignment, listTestCases } from "../api/assignments.js";
import { addTestCase, generateTestCases, regenerateRubric, updateAssignment } from "../api/teacher.js";

export default function AssignmentManagePage() {
  const { assignmentId } = useParams();
  const [assignment, setAssignment] = useState(null);
  const [testCases, setTestCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const reload = async () => {
    const [a, tc] = await Promise.all([getAssignment(assignmentId), listTestCases(assignmentId)]);
    setAssignment(a);
    setTestCases(tc);
  };

  useEffect(() => {
    reload()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [assignmentId]);

  if (loading) return <p className="text-ink/60">Loading…</p>;
  if (error) return <p className="text-brick">{error}</p>;

  const isMcq = assignment.type === "mcq";

  return (
    <div className="space-y-8 max-w-3xl">
      <div>
        <Link to={`/teacher/courses/${assignment.course_id}`} className="text-sm text-pen underline">
          ← Course
        </Link>
        <h1 className="font-display text-3xl font-semibold text-ink mt-2">{assignment.title}</h1>
        <p className="text-ink/70 mt-2 whitespace-pre-wrap">{assignment.description}</p>
      </div>

      <RubricSection assignment={assignment} onUpdated={reload} />

      {isMcq ? (
        // MCQ assignments are graded by exact-match against structured questions, not
        // test cases — the programming test-case UI (manual test cases, AI generation)
        // never applied here and used to render anyway, always sending an MCQ-editing
        // teacher to what looked like the programming assignment page. A dedicated
        // editor replaces all of that below.
        <McqEditorSection assignment={assignment} onUpdated={reload} />
      ) : (
        <>
          {assignment.type === "programming" && (
            <GenerateTestCasesSection assignmentId={assignmentId} onGenerated={reload} />
          )}
          <ManualTestCaseSection assignment={assignment} onAdded={reload} />

          <section>
            <h2 className="font-medium text-ink mb-3">Test cases ({testCases.length})</h2>
            <ul className="space-y-2 font-mono text-xs">
              {testCases.map((tc) => (
                <li key={tc.id} className="p-2 rounded border border-pen/10 bg-white flex items-center justify-between">
                  <span>
                    <span className="uppercase text-pen/70 mr-2">{tc.kind}</span>
                    {JSON.stringify(tc.input)} → {JSON.stringify(tc.expected_output)}
                  </span>
                  <span className="text-ink/40">{tc.points}pt</span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}

function RubricSection({ assignment, onUpdated }) {
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState(null);

  const handleRegenerate = async () => {
    setRegenerating(true);
    setError(null);
    try {
      await regenerateRubric(assignment.id);
      onUpdated();
    } catch (err) {
      setError(err.message);
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <section>
      <div className="flex items-center justify-between mb-2">
        <h2 className="font-medium text-ink">Rubric</h2>
        <button
          onClick={handleRegenerate}
          disabled={regenerating}
          className="text-sm text-pen underline disabled:opacity-60"
        >
          {regenerating ? "Regenerating…" : "Regenerate"}
        </button>
      </div>
      {error && <p className="text-sm text-brick mb-2">{error}</p>}
      <ul className="text-sm space-y-1">
        {(assignment.rubric?.criteria || []).map((c) => (
          <li key={c.name} className="flex justify-between text-ink/70">
            <span className="capitalize">{c.name.replaceAll("_", " ")}</span>
            <span>{Math.round(c.weight * 100)}%</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function GenerateTestCasesSection({ assignmentId, onGenerated }) {
  const [referenceSolution, setReferenceSolution] = useState("");
  const [functionsRaw, setFunctionsRaw] = useState("");
  const [language, setLanguage] = useState("python");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  const handleGenerate = async (e) => {
    e.preventDefault();
    setGenerating(true);
    setError(null);
    try {
      const functions = functionsRaw
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .map((name) => ({ name, signature: "" }));
      await generateTestCases(assignmentId, { referenceSolution, functions, language });
      setReferenceSolution("");
      setFunctionsRaw("");
      onGenerated();
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <section>
      <h2 className="font-medium text-ink mb-2">AI-generate test cases</h2>
      <p className="text-xs text-ink/50 mb-3">
        Proposes test cases from a reference solution, verified by actually compiling/running it (see backend
        assignment_setup_agent.py) — requires an LLM provider configured on the backend.
      </p>
      <form onSubmit={handleGenerate} className="space-y-2">
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="px-2 py-1.5 text-sm rounded border border-pen/30"
        >
          <option value="python">Python reference solution</option>
          <option value="java">Java reference solution</option>
        </select>
        <textarea
          required
          placeholder={language === "java" ? "Reference solution (Java — public class Solution { ... })" : "Reference solution (Python)"}
          rows={6}
          value={referenceSolution}
          onChange={(e) => setReferenceSolution(e.target.value)}
          className="w-full font-mono text-sm px-3 py-2 rounded border border-pen/30"
        />
        <input
          required
          placeholder="Function names, comma-separated (e.g. add, is_even)"
          value={functionsRaw}
          onChange={(e) => setFunctionsRaw(e.target.value)}
          className="w-full px-3 py-2 rounded border border-pen/30"
        />
        {error && <p className="text-sm text-brick">{error}</p>}
        <button
          type="submit"
          disabled={generating}
          className="px-4 py-2 rounded bg-pen text-paper text-sm font-medium hover:bg-pen-dark disabled:opacity-60"
        >
          {generating ? "Generating…" : "Generate"}
        </button>
      </form>
    </section>
  );
}

function ManualTestCaseSection({ assignment, onAdded }) {
  const [kind, setKind] = useState("public");
  const [inputRaw, setInputRaw] = useState("{}");
  const [expectedRaw, setExpectedRaw] = useState("{}");
  const [points, setPoints] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const input = JSON.parse(inputRaw);
      const expected_output = JSON.parse(expectedRaw);
      await addTestCase(assignment.id, { kind, input, expected_output, points: Number(points) });
      setInputRaw("{}");
      setExpectedRaw("{}");
      onAdded();
    } catch (err) {
      setError(err.message.includes("JSON") ? "Input/expected output must be valid JSON." : err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section>
      <h2 className="font-medium text-ink mb-2">Add a test case manually</h2>
      <form onSubmit={handleSubmit} className="space-y-2">
        <div className="grid sm:grid-cols-2 gap-2">
          <textarea
            value={inputRaw}
            onChange={(e) => setInputRaw(e.target.value)}
            placeholder='Input JSON, e.g. {"function": "add", "args": [1, 2]}'
            className="font-mono text-xs px-3 py-2 rounded border border-pen/30"
            rows={3}
          />
          <textarea
            value={expectedRaw}
            onChange={(e) => setExpectedRaw(e.target.value)}
            placeholder='Expected output JSON, e.g. {"value": 3}'
            className="font-mono text-xs px-3 py-2 rounded border border-pen/30"
            rows={3}
          />
        </div>
        <div className="flex gap-2 items-center">
          <select value={kind} onChange={(e) => setKind(e.target.value)} className="px-2 py-1.5 text-sm rounded border border-pen/30">
            <option value="public">public</option>
            <option value="hidden">hidden</option>
            <option value="edge">edge</option>
          </select>
          <input
            type="number"
            min={1}
            value={points}
            onChange={(e) => setPoints(e.target.value)}
            className="w-20 px-2 py-1.5 text-sm rounded border border-pen/30"
          />
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-1.5 rounded bg-pen text-paper text-sm font-medium hover:bg-pen-dark disabled:opacity-60"
          >
            Add
          </button>
        </div>
        {error && <p className="text-sm text-brick">{error}</p>}
      </form>
    </section>
  );
}

function emptyQuestion() {
  return {
    id: `q_${Math.random().toString(36).slice(2, 9)}`,
    text: "",
    options: { A: "", B: "", C: "", D: "" },
    correct_options: [],
    points: 1,
  };
}

function McqEditorSection({ assignment, onUpdated }) {
  const initial = assignment.constraints?.questions?.length
    ? assignment.constraints.questions.map((q) => ({
        ...q,
        options: { ...q.options },
        correct_options: [...(q.correct_options || [])],
      }))
    : [emptyQuestion()];
  const [questions, setQuestions] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [savedAt, setSavedAt] = useState(null);

  const updateQuestion = (idx, patch) => {
    setQuestions((qs) => qs.map((q, i) => (i === idx ? { ...q, ...patch } : q)));
  };

  const updateOption = (idx, key, value) => {
    setQuestions((qs) =>
      qs.map((q, i) => (i === idx ? { ...q, options: { ...q.options, [key]: value } } : q))
    );
  };

  const toggleCorrect = (idx, key) => {
    setQuestions((qs) =>
      qs.map((q, i) => {
        if (i !== idx) return q;
        const has = q.correct_options.includes(key);
        return {
          ...q,
          correct_options: has ? q.correct_options.filter((k) => k !== key) : [...q.correct_options, key],
        };
      })
    );
  };

  const addOption = (idx) => {
    setQuestions((qs) =>
      qs.map((q, i) => {
        if (i !== idx) return q;
        const usedKeys = Object.keys(q.options);
        const nextKey = "ABCDEFGH".split("").find((k) => !usedKeys.includes(k));
        if (!nextKey) return q;
        return { ...q, options: { ...q.options, [nextKey]: "" } };
      })
    );
  };

  const removeOption = (idx, key) => {
    setQuestions((qs) =>
      qs.map((q, i) => {
        if (i !== idx) return q;
        const options = { ...q.options };
        delete options[key];
        return { ...q, options, correct_options: q.correct_options.filter((k) => k !== key) };
      })
    );
  };

  const addQuestion = () => setQuestions((qs) => [...qs, emptyQuestion()]);
  const removeQuestion = (idx) => setQuestions((qs) => qs.filter((_, i) => i !== idx));

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSavedAt(null);
    try {
      for (const q of questions) {
        if (!q.text.trim()) throw new Error("Every question needs text.");
        if (Object.values(q.options).some((v) => !v.trim())) throw new Error("Every option needs text (or remove it).");
        if (q.correct_options.length === 0) throw new Error(`Question "${q.text.slice(0, 30)}" has no correct option selected.`);
      }
      await updateAssignment(assignment.id, {
        constraints: { questions: questions.map((q) => ({ ...q, points: Number(q.points) || 1 })) },
      });
      setSavedAt(Date.now());
      onUpdated();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section>
      <div className="flex items-center justify-between mb-2">
        <h2 className="font-medium text-ink">Questions</h2>
        <button
          type="button"
          onClick={addQuestion}
          className="text-sm text-pen underline"
        >
          + Add question
        </button>
      </div>
      <p className="text-xs text-ink/50 mb-4">
        Check every correct option for a question — one checked is a single-answer question, more than one makes
        it multi-select (students must select exactly the checked options for credit).
      </p>

      <form onSubmit={handleSave} className="space-y-6">
        {questions.map((q, idx) => (
          <div key={q.id} className="p-4 rounded border border-pen/20 bg-white space-y-3">
            <div className="flex items-start gap-2">
              <textarea
                required
                placeholder="Question text"
                value={q.text}
                onChange={(e) => updateQuestion(idx, { text: e.target.value })}
                rows={2}
                className="flex-1 px-3 py-2 rounded border border-pen/30 text-sm"
              />
              <input
                type="number"
                min={1}
                title="Points"
                value={q.points}
                onChange={(e) => updateQuestion(idx, { points: e.target.value })}
                className="w-16 px-2 py-2 rounded border border-pen/30 text-sm"
              />
              {questions.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeQuestion(idx)}
                  className="text-xs text-brick underline shrink-0 mt-2"
                >
                  Remove
                </button>
              )}
            </div>

            <div className="space-y-2">
              {Object.entries(q.options).map(([key, text]) => (
                <div key={key} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={q.correct_options.includes(key)}
                    onChange={() => toggleCorrect(idx, key)}
                    title="Mark as correct"
                  />
                  <span className="w-5 text-xs font-mono text-ink/50">{key}</span>
                  <input
                    required
                    value={text}
                    onChange={(e) => updateOption(idx, key, e.target.value)}
                    placeholder={`Option ${key} text`}
                    className="flex-1 px-2 py-1.5 rounded border border-pen/30 text-sm"
                  />
                  {Object.keys(q.options).length > 2 && (
                    <button
                      type="button"
                      onClick={() => removeOption(idx, key)}
                      className="text-xs text-ink/40 hover:text-brick"
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
              {Object.keys(q.options).length < 8 && (
                <button type="button" onClick={() => addOption(idx)} className="text-xs text-pen underline">
                  + Add option
                </button>
              )}
            </div>
          </div>
        ))}

        {error && <p className="text-sm text-brick">{error}</p>}
        {savedAt && !error && <p className="text-sm text-green-700">Saved.</p>}
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 rounded bg-pen text-paper text-sm font-medium hover:bg-pen-dark disabled:opacity-60"
        >
          {saving ? "Saving…" : "Save questions"}
        </button>
      </form>
    </section>
  );
}
