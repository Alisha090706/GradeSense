import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { listAssignments } from "../api/assignments.js";
import { getCourse } from "../api/courses.js";
import { listDocuments, uploadDocument } from "../api/teacher.js";
import { NewAssignmentForm } from "./TeacherDashboardPage.jsx";

export default function CourseManagePage() {
  const { courseId } = useParams();
  const [course, setCourse] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const reload = async () => {
    const [c, a, d] = await Promise.all([getCourse(courseId), listAssignments(courseId), listDocuments(courseId)]);
    setCourse(c);
    setAssignments(a);
    setDocuments(d);
  };

  useEffect(() => {
    reload()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [courseId]);

  if (loading) return <p className="text-ink/60">Loading…</p>;
  if (error) return <p className="text-brick">{error}</p>;

  return (
    <div className="space-y-10">
      <div>
        <Link to="/teacher" className="text-sm text-pen underline">
          ← All courses
        </Link>
        <h1 className="font-display text-3xl font-semibold text-ink mt-2">{course.name}</h1>
        <Link to={`/teacher/courses/${courseId}/analytics`} className="text-sm text-pen underline">
          View analytics →
        </Link>
      </div>

      <section>
        <h2 className="font-medium text-ink mb-3">Assignments</h2>
        <div className="space-y-2 mb-6">
          {assignments.length === 0 && <p className="text-sm text-ink/50">None yet.</p>}
          {assignments.map((a) => (
            <div key={a.id} className="p-3 rounded border border-pen/15 bg-white flex items-center justify-between">
              <div>
                <p className="font-medium text-ink">{a.title}</p>
                <p className="text-xs text-ink/50 capitalize">{a.type}</p>
              </div>
              <Link to={`/teacher/assignments/${a.id}`} className="text-sm text-pen underline">
                Manage
              </Link>
            </div>
          ))}
        </div>
        <NewAssignmentForm courseId={courseId} onCreated={reload} />
      </section>

      <section>
        <h2 className="font-medium text-ink mb-3">Course documents</h2>
        <p className="text-xs text-ink/50 mb-3">
          Uploaded here become searchable by the Tutor for this course's students (RAG-grounded answers) —
          requires an embedding model configured on the backend; see the backend README's Phase 9 section.
        </p>
        <DocumentUpload courseId={courseId} documents={documents} onUploaded={reload} />
      </section>
    </div>
  );
}

function DocumentUpload({ documents, courseId, onUploaded }) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [lastResult, setLastResult] = useState(null);

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const result = await uploadDocument(courseId, file);
      setLastResult(result);
      onUploaded();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  return (
    <div>
      <ul className="space-y-1 mb-3 text-sm">
        {documents.map((d) => (
          <li key={d.id} className="text-ink/70">
            {d.filename}
          </li>
        ))}
      </ul>
      <label className="inline-block px-4 py-2 rounded border border-pen/30 text-pen text-sm cursor-pointer hover:bg-pen/5">
        {uploading ? "Uploading…" : "Upload document (.txt, .md, .pdf)"}
        <input type="file" accept=".txt,.md,.pdf" className="hidden" onChange={handleFileChange} disabled={uploading} />
      </label>
      {error && <p className="text-sm text-brick mt-2">{error}</p>}
      {lastResult && !lastResult.indexed && (
        <p className="text-sm text-gold mt-2">
          Uploaded, but not yet searchable: {lastResult.note}
        </p>
      )}
    </div>
  );
}
