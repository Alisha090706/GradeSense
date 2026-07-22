import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAssignments } from "../api/assignments.js";
import { listCourses } from "../api/courses.js";
import { listMySubmissions } from "../api/submissions.js";
import ScoreStamp from "../components/ScoreStamp.jsx";

/**
 * Fetches every course's assignments and, for each, this student's most
 * recent submission (if any) — enough to show status/score without a
 * dedicated "my dashboard summary" endpoint, which doesn't exist yet
 * (a reasonable Phase 14+ addition if this N+1-ish fetch pattern becomes
 * a real performance concern with many courses/assignments).
 */
function useDashboardData() {
  const [courses, setCourses] = useState([]);
  const [assignmentsByCourse, setAssignmentsByCourse] = useState({});
  const [latestSubmissionByAssignment, setLatestSubmissionByAssignment] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const courseList = await listCourses();
        if (cancelled) return;
        setCourses(courseList);

        const assignmentEntries = await Promise.all(
          courseList.map(async (course) => [course.id, await listAssignments(course.id)]),
        );
        if (cancelled) return;
        const assignmentsMap = Object.fromEntries(assignmentEntries);
        setAssignmentsByCourse(assignmentsMap);

        const allAssignments = Object.values(assignmentsMap).flat();
        const submissionEntries = await Promise.all(
          allAssignments.map(async (a) => {
            const subs = await listMySubmissions(a.id).catch(() => []);
            return [a.id, subs[0] || null]; // most recent first, per the backend's ordering
          }),
        );
        if (cancelled) return;
        setLatestSubmissionByAssignment(Object.fromEntries(submissionEntries));
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
  }, []);

  return { courses, assignmentsByCourse, latestSubmissionByAssignment, loading, error };
}

export default function StudentDashboardPage() {
  const { courses, assignmentsByCourse, latestSubmissionByAssignment, loading, error } = useDashboardData();

  if (loading) {
    return <p className="text-ink/60">Loading your courses…</p>;
  }

  if (error) {
    return (
      <div className="text-brick">
        <p className="font-medium">Couldn't load your dashboard.</p>
        <p className="text-sm mt-1">{error}</p>
      </div>
    );
  }

  if (courses.length === 0) {
    return (
      <div className="text-center py-16">
        <h1 className="font-display text-2xl text-ink mb-2">Nothing here yet</h1>
        <p className="text-ink/60">
          You're not enrolled in any courses yet. Once a teacher adds a course you're part of, it'll show up here.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold text-ink mb-8">Your courses</h1>

      <div className="space-y-10">
        {courses.map((course) => {
          const assignments = assignmentsByCourse[course.id] || [];
          return (
            <section key={course.id}>
              <h2 className="font-display text-xl font-medium text-pen mb-4">{course.name}</h2>

              {assignments.length === 0 ? (
                <p className="text-sm text-ink/50">No assignments posted yet.</p>
              ) : (
                <div className="grid sm:grid-cols-2 gap-4">
                  {assignments.map((assignment) => {
                    const submission = latestSubmissionByAssignment[assignment.id];
                    return (
                      <Link
                        key={assignment.id}
                        to={`/assignments/${assignment.id}`}
                        className="flex items-center gap-4 p-4 rounded border border-pen/15 bg-white hover:border-pen/40 hover:shadow-sm transition-all"
                      >
                        <AssignmentStatusStamp submission={submission} />
                        <div className="min-w-0">
                          <p className="font-medium text-ink truncate">{assignment.title}</p>
                          <p className="text-xs text-ink/50 capitalize">
                            {assignment.type} · {submission ? "submitted" : "not submitted yet"}
                          </p>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
}

function AssignmentStatusStamp({ submission }) {
  // The dashboard's list endpoint (submissions/mine) doesn't include the score
  // itself yet — only id/created_at/language (see backend api/v1/submissions.py) —
  // so this shows submitted/not-submitted rather than a real score stamp here;
  // the full score stamp appears on the assignment detail page, which fetches
  // the actual submission detail (GET /submissions/{id}) that does include it.
  if (!submission) {
    return (
      <div className="w-12 h-12 rounded-stamp border-2 border-dashed border-ink/20 shrink-0" aria-hidden="true" />
    );
  }
  return (
    <div
      className="w-12 h-12 rounded-stamp border-4 border-pen/40 bg-pen-dark shrink-0"
      style={{ transform: "rotate(-4deg)" }}
      aria-label="Submitted"
    />
  );
}
