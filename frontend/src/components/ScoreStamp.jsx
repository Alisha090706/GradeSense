import React from "react";

/**
 * The signature element of the design (see the Phase 11 README section for
 * the full design plan) — a circular grading stamp, used everywhere a score
 * appears (dashboard cards, assignment lists, submission results) so the
 * one recurring visual motif is tied directly to what this platform
 * actually does: marking work.
 */
export default function ScoreStamp({ score, total, size = "md" }) {
  const pct = total > 0 ? Math.round((score / total) * 100) : 0;

  const tier = pct >= 90 ? "gold" : pct >= 60 ? "sage" : "brick";
  const tierClasses = {
    gold: "border-gold text-gold-light bg-pen-dark",
    sage: "border-sage text-sage bg-pen-dark",
    brick: "border-brick text-brick bg-pen-dark",
  };

  const sizeClasses = {
    sm: "w-12 h-12 text-xs",
    md: "w-16 h-16 text-sm",
    lg: "w-24 h-24 text-lg",
  };

  return (
    <div
      className={`relative flex flex-col items-center justify-center rounded-stamp border-4 font-display font-semibold shrink-0 ${tierClasses[tier]} ${sizeClasses[size]}`}
      style={{ transform: "rotate(-4deg)" }}
      role="img"
      aria-label={`Score: ${score} out of ${total}, ${pct} percent`}
    >
      <span className="leading-none">{pct}%</span>
      <span className="text-[0.6em] opacity-80 leading-none mt-0.5">
        {score}/{total}
      </span>
    </div>
  );
}
