import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getCourse } from "../api/courses.js";
import { getCourseAnalytics, refreshCourseAnalytics } from "../api/analytics.js";
import ScoreStamp from "../components/ScoreStamp.jsx";

export default function CourseAnalyticsPage() {
  const { courseId } = useParams();
  const [course, setCourse] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [generatedAt, setGeneratedAt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [notComputedYet, setNotComputedYet] = useState(false);

  const loadExisting = async () => {
    setNotComputedYet(false);
    try {
      const snap = await getCourseAnalytics(courseId);
      setMetrics(snap.metrics);
      setGeneratedAt(snap.generated_at);
    } catch (err) {
      if (err.status === 404) {
        setNotComputedYet(true);
      } else {
        throw err;
      }
    }
  };

  useEffect(() => {
    Promise.all([getCourse(courseId).then(setCourse), loadExisting()])
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [courseId]);

  const handleRefresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      const snap = await refreshCourseAnalytics(courseId);
      setMetrics(snap.metrics);
      setGeneratedAt(snap.generated_at);
      setNotComputedYet(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) return <p className="text-ink/60">Loading…</p>;

  return (
    <div className="max-w-3xl">
      <Link to={`/teacher/courses/${courseId}`} className="text-sm text-pen underline">
        ← {course?.name || "Course"}
      </Link>
      <div className="flex items-center justify-between mt-2 mb-6">
        <h1 className="font-display text-3xl font-semibold text-ink">Analytics</h1>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="px-4 py-2 rounded bg-pen text-paper text-sm font-medium hover:bg-pen-dark disabled:opacity-60"
        >
          {refreshing ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {error && <p className="text-brick mb-4">{error}</p>}

      {notComputedYet && !metrics && (
        <p className="text-ink/60">
          No analytics computed yet for this course — click Refresh to compute the first snapshot.
        </p>
      )}

      {metrics && (
        <div className="space-y-6">
          <p className="text-xs text-ink/40">
            Last refreshed: {generatedAt ? new Date(generatedAt).toLocaleString() : "—"}
          </p>

          <div className="flex items-center gap-6 p-5 rounded border border-pen/15 bg-white">
            {metrics.average_score_pct != null ? (
              <ScoreStamp score={metrics.average_score_pct} total={100} size="lg" />
            ) : (
              <div className="w-24 h-24 rounded-stamp border-4 border-dashed border-ink/20 shrink-0" />
            )}
            <div>
              <p className="text-sm text-ink/50">
                {metrics.assignment_count} assignment(s) · {metrics.student_submission_count} submission(s)
              </p>
              {metrics.weakest_assignment && (
                <p className="text-sm text-brick mt-1">Weakest: {metrics.weakest_assignment}</p>
              )}
              {metrics.total_plagiarism_flagged_pair_count > 0 && (
                <p className="text-sm text-gold mt-1">
                  {metrics.total_plagiarism_flagged_pair_count} similarity match(es) flagged across the course
                </p>
              )}
            </div>
          </div>

          <div>
            <h2 className="font-medium text-ink mb-3">Per-assignment performance</h2>
            <div className="space-y-2">
              {metrics.per_assignment_performance.map((a) => (
                <div key={a.assignment_id} className="flex items-center gap-4 p-3 rounded border border-pen/10 bg-white">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-ink">{a.title}</p>
                    <p className="text-xs text-ink/40">{a.submission_count} submission(s)</p>
                  </div>
                  {a.average_score_pct != null ? (
                    <div className="w-32 h-2 bg-ink/10 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${a.average_score_pct >= 60 ? "bg-sage" : "bg-brick"}`}
                        style={{ width: `${a.average_score_pct}%` }}
                      />
                    </div>
                  ) : (
                    <span className="text-xs text-ink/30">no submissions</span>
                  )}
                  <span className="text-sm text-ink/60 w-12 text-right">
                    {a.average_score_pct != null ? `${a.average_score_pct}%` : "—"}
                  </span>
                  <Link to={`/teacher/assignments/${a.assignment_id}/analytics`} className="text-xs text-pen underline">
                    Detail
                  </Link>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
