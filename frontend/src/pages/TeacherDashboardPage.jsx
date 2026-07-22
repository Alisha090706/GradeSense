import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listSubjects, listCourses } from "../api/courses.js";
import { createCourse, createAssignment, listAssignmentTemplates } from "../api/teacher.js";

const ASSIGNMENT_TYPES = ["programming", "sql", "theory", "mcq"];

export default function TeacherDashboardPage() {
  const [courses, setCourses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showNewCourse, setShowNewCourse] = useState(false);

  const reload = async () => {
    const [courseList, subjectList] = await Promise.all([listCourses(), listSubjects()]);
    setCourses(courseList);
    setSubjects(subjectList);
  };

  useEffect(() => {
    reload()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-ink/60">Loading your courses…</p>;

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="font-display text-3xl font-semibold text-ink">Your courses</h1>
        <button
          onClick={() => setShowNewCourse((v) => !v)}
          className="px-4 py-2 rounded bg-pen text-paper text-sm font-medium hover:bg-pen-dark transition-colors"
        >
          {showNewCourse ? "Cancel" : "New course"}
        </button>
      </div>

      {error && <p className="text-brick mb-4">{error}</p>}

      {showNewCourse && (
        <NewCourseForm
          subjects={subjects}
          onCreated={() => {
            setShowNewCourse(false);
            reload();
          }}
        />
      )}

      {courses.length === 0 ? (
        <p className="text-ink/50 mt-4">
          No courses yet — note that only your own courses show here; if this doesn't match what you expect, your
          teacher account may still be pending admin approval.
        </p>
      ) : (
        <div className="grid sm:grid-cols-2 gap-4 mt-6">
          {courses.map((course) => (
            <div key={course.id} className="p-4 rounded border border-pen/15 bg-white">
              <p className="font-medium text-ink">{course.name}</p>
              <div className="flex gap-3 mt-3 text-sm">
                <Link to={`/teacher/courses/${course.id}`} className="text-pen underline">
                  Manage
                </Link>
                <Link to={`/teacher/courses/${course.id}/analytics`} className="text-pen underline">
                  Analytics
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function NewCourseForm({ subjects, onCreated }) {
  const [name, setName] = useState("");
  const [subjectId, setSubjectId] = useState(subjects[0]?.id || "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createCourse({ name, subjectId });
      onCreated();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="p-4 rounded border border-pen/15 bg-white mb-6 flex gap-3 items-end">
      <div className="flex-1">
        <label htmlFor="course-name" className="block text-sm font-medium text-ink mb-1">
          Course name
        </label>
        <input
          id="course-name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full px-3 py-2 rounded border border-pen/30"
        />
      </div>
      <div>
        <label htmlFor="course-subject" className="block text-sm font-medium text-ink mb-1">
          Subject
        </label>
        <select
          id="course-subject"
          value={subjectId}
          onChange={(e) => setSubjectId(e.target.value)}
          className="px-3 py-2 rounded border border-pen/30"
        >
          {subjects.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>
      <button
        type="submit"
        disabled={submitting}
        className="px-4 py-2 rounded bg-pen text-paper text-sm font-medium hover:bg-pen-dark disabled:opacity-60"
      >
        {submitting ? "Creating…" : "Create"}
      </button>
      {error && <p className="text-sm text-brick">{error}</p>}
    </form>
  );
}

export function NewAssignmentForm({ courseId, onCreated }) {
  const [templates, setTemplates] = useState([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState("programming");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    listAssignmentTemplates().then(setTemplates).catch(() => {});
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const template = templates.find((t) => t.assignment_type === type);
      await createAssignment(courseId, {
        title,
        description,
        type,
        template_id: template?.id || null,
      });
      setTitle("");
      setDescription("");
      onCreated();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="p-4 rounded border border-pen/15 bg-white space-y-3">
      <h3 className="font-medium text-ink">New assignment</h3>
      <div className="grid sm:grid-cols-2 gap-3">
        <input
          required
          placeholder="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="px-3 py-2 rounded border border-pen/30"
        />
        <select value={type} onChange={(e) => setType(e.target.value)} className="px-3 py-2 rounded border border-pen/30 capitalize">
          {ASSIGNMENT_TYPES.map((t) => (
            <option key={t} value={t} className="capitalize">
              {t}
            </option>
          ))}
        </select>
      </div>
      <textarea
        required
        placeholder="Description"
        rows={3}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        className="w-full px-3 py-2 rounded border border-pen/30"
      />
      {error && <p className="text-sm text-brick">{error}</p>}
      <button
        type="submit"
        disabled={submitting}
        className="px-4 py-2 rounded bg-pen text-paper text-sm font-medium hover:bg-pen-dark disabled:opacity-60"
      >
        {submitting ? "Creating…" : "Create assignment"}
      </button>
    </form>
  );
}
