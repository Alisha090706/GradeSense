import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getAssignmentAnalytics, refreshAssignmentAnalytics } from "../api/analytics.js";
import ScoreStamp from "../components/ScoreStamp.jsx";

export default function AssignmentAnalyticsPage() {
  const { assignmentId } = useParams();
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [notComputedYet, setNotComputedYet] = useState(false);

  const load = async () => {
    setNotComputedYet(false);
    try {
      const snap = await getAssignmentAnalytics(assignmentId);
      setMetrics(snap.metrics);
    } catch (err) {
      if (err.status === 404) setNotComputedYet(true);
      else throw err;
    }
  };

  useEffect(() => {
    load()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [assignmentId]);

  const handleRefresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      const snap = await refreshAssignmentAnalytics(assignmentId);
      setMetrics(snap.metrics);
      setNotComputedYet(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) return <p className="text-ink/60">Loading…</p>;

  return (
    <div className="max-w-2xl">
      <Link to=".." relative="path" className="text-sm text-pen underline">
        ← Assignment
      </Link>
      <div className="flex items-center justify-between mt-2 mb-6">
        <h1 className="font-display text-2xl font-semibold text-ink">
          {metrics?.assignment_title || "Analytics"}
        </h1>
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
        <p className="text-ink/60">No analytics computed yet — click Refresh to compute the first snapshot.</p>
      )}

      {metrics && (
        <div className="space-y-6">
          <div className="flex items-center gap-6 p-5 rounded border border-pen/15 bg-white">
            {metrics.average_score_pct != null ? (
              <ScoreStamp score={metrics.average_score_pct} total={100} size="lg" />
            ) : (
              <div className="w-24 h-24 rounded-stamp border-4 border-dashed border-ink/20 shrink-0" />
            )}
            <div>
              <p className="text-sm text-ink/50">{metrics.submission_count} submission(s)</p>
              {metrics.most_failed_category && (
                <p className="text-sm text-brick mt-1">Most failed: {metrics.most_failed_category}</p>
              )}
              {metrics.plagiarism_flagged_pair_count > 0 && (
                <p className="text-sm text-gold mt-1">
                  {metrics.plagiarism_flagged_pair_count} similarity match(es) flagged
                </p>
              )}
            </div>
          </div>

          <div>
            <h2 className="font-medium text-ink mb-3">Score distribution</h2>
            <div className="space-y-1.5">
              {metrics.score_distribution.map((bucket) => (
                <div key={bucket.range_label} className="flex items-center gap-3 text-sm">
                  <span className="w-16 text-ink/50">{bucket.range_label}</span>
                  <div className="flex-1 h-4 bg-ink/5 rounded overflow-hidden">
                    <div
                      className="h-full bg-pen"
                      style={{
                        width: `${metrics.submission_count > 0 ? (bucket.count / metrics.submission_count) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <span className="w-6 text-right text-ink/40">{bucket.count}</span>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h2 className="font-medium text-ink mb-3">Failure rate by category</h2>
            <div className="space-y-1.5">
              {metrics.category_failure_rates.length === 0 && (
                <p className="text-sm text-ink/40">No failures recorded.</p>
              )}
              {metrics.category_failure_rates.map((c) => (
                <div key={c.category} className="flex items-center gap-3 text-sm">
                  <span className="w-32 text-ink/70 capitalize truncate">{c.category.replaceAll("_", " ")}</span>
                  <div className="flex-1 h-4 bg-ink/5 rounded overflow-hidden">
                    <div className="h-full bg-brick" style={{ width: `${c.failure_rate * 100}%` }} />
                  </div>
                  <span className="w-10 text-right text-ink/40">{Math.round(c.failure_rate * 100)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
