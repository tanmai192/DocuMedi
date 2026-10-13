import React from 'react';
import { Link } from 'react-router-dom';

export default function HistoryPlaceholder() {
  return (
    <div style={{ maxWidth: '640px', margin: '2rem auto' }}>
      <div className="card" style={{ textAlign: 'center', padding: '3rem 2rem' }}>
        <div style={{ fontSize: '3.5rem', marginBottom: '1rem' }}>📅📄</div>
        <h1 style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--color-dark)', marginBottom: '0.5rem' }}>
          My Medical History Timeline
        </h1>
        <p style={{ color: 'var(--color-slate-600)', fontSize: '0.95rem', lineHeight: 1.6, marginBottom: '1.5rem' }}>
          A chronological timeline of all your saved clinical intake cases, complete with structured 11-section
          patient notes and instant PDF report downloads.
        </p>
        <div className="alert alert-info" style={{ textAlign: 'left', marginBottom: '1.75rem' }}>
          <strong>Coming in Stage 7 & 8:</strong> Chronological Medical History Timeline and PDF report generation.
        </div>
        <Link to="/dashboard" className="btn btn-primary">
          ← Return to Dashboard
        </Link>
      </div>
    </div>
  );
}
