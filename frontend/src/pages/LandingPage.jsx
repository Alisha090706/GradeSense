import React from "react";
import { Link } from "react-router-dom";

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="max-w-5xl mx-auto w-full px-6 py-6 flex items-center justify-between">
        <span className="font-display text-2xl font-semibold text-pen">GradeSense</span>
        <nav className="flex gap-3">
          <Link to="/login" className="px-4 py-2 text-pen hover:underline">
            Sign in
          </Link>
          <Link to="/register" className="px-4 py-2 rounded bg-pen text-paper hover:bg-pen-dark transition-colors">
            Get started
          </Link>
        </nav>
      </header>

      <main className="flex-1 flex items-center">
        <div className="max-w-5xl mx-auto w-full px-6 py-16 grid md:grid-cols-2 gap-12 items-center">
          <div>
            <h1 className="font-display text-5xl md:text-6xl font-semibold text-ink leading-[1.05] mb-6">
              Every submission,
              <br />
              actually explained.
            </h1>
            <p className="text-lg text-ink/70 mb-8 max-w-md">
              GradeSense grades code, queries, and written answers — then tells you{" "}
              <em className="not-italic text-pen font-medium">why</em>, not just what. Ask a follow-up question and
              get a real answer, never the solution handed to you.
            </p>
            <Link
              to="/register"
              className="inline-block px-6 py-3 rounded bg-pen text-paper font-medium hover:bg-pen-dark transition-colors"
            >
              Create your account
            </Link>
          </div>

          <div className="relative">
            <div
              className="mx-auto w-56 h-56 rounded-stamp border-8 border-gold flex flex-col items-center justify-center bg-pen-dark text-gold-light font-display shadow-xl"
              style={{ transform: "rotate(-6deg)" }}
              aria-hidden="true"
            >
              <span className="text-5xl font-semibold leading-none">92%</span>
              <span className="text-sm opacity-80 mt-2">GRADED</span>
            </div>
          </div>
        </div>
      </main>

      <footer className="border-t border-pen/10 py-6 text-center text-xs text-ink/50">
        GradeSense — an AI-assisted assessment platform
      </footer>
    </div>
  );
}
