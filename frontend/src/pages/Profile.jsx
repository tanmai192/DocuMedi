import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Profile() {
  const { patient, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div style={{ maxWidth: '680px', margin: '0 auto' }}>
      <div style={{ marginBottom: '1.75rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--color-dark)' }}>
          Patient Profile
        </h1>
        <p style={{ color: 'var(--color-slate-600)', fontSize: '0.95rem' }}>
          Manage your personal medical record credentials and security
        </p>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '1.25rem', color: 'var(--color-dark)' }}>
          Account Information
        </h2>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ borderBottom: '1px solid var(--color-border)', paddingBottom: '0.75rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-slate-600)', fontWeight: 600, display: 'block' }}>
              Full Name
            </span>
            <span style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--color-dark)' }}>
              {patient?.full_name}
            </span>
          </div>

          <div style={{ borderBottom: '1px solid var(--color-border)', paddingBottom: '0.75rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-slate-600)', fontWeight: 600, display: 'block' }}>
              Email Address
            </span>
            <span style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--color-dark)' }}>
              {patient?.email}
            </span>
          </div>

          <div style={{ borderBottom: '1px solid var(--color-border)', paddingBottom: '0.75rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-slate-600)', fontWeight: 600, display: 'block' }}>
              Account Created
            </span>
            <span style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--color-dark)' }}>
              {patient?.created_at ? new Date(patient.created_at).toLocaleString() : 'Active'}
            </span>
          </div>

          <div>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-slate-600)', fontWeight: 600, display: 'block' }}>
              Data Privacy & Encryption
            </span>
            <span style={{ fontSize: '0.92rem', color: 'var(--color-accent-green)', fontWeight: 600 }}>
              ✓ Passwords hashed with bcrypt (12 rounds) & JWT session active
            </span>
          </div>
        </div>

        <div style={{ marginTop: '1.75rem', paddingTop: '1.25rem', borderTop: '1px solid var(--color-border)' }}>
          <button className="btn btn-danger-outline" onClick={handleLogout}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            Sign Out of Account
          </button>
        </div>
      </div>
    </div>
  );
}
