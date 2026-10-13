import React from 'react';
import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div style={{ maxWidth: '520px', margin: '4rem auto', textAlign: 'center' }}>
      <div className="card" style={{ padding: '3rem 2rem' }}>
        <div style={{ fontSize: '3rem', fontWeight: 900, color: 'var(--color-primary)', marginBottom: '0.5rem' }}>
          404
        </div>
        <h1 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--color-dark)' }}>
          Page Not Found
        </h1>
        <p style={{ color: 'var(--color-slate-600)', fontSize: '0.92rem', marginBottom: '1.5rem' }}>
          The page or medical record you requested could not be located.
        </p>
        <Link to="/dashboard" className="btn btn-primary">
          Back to Safety (Dashboard)
        </Link>
      </div>
    </div>
  );
}
