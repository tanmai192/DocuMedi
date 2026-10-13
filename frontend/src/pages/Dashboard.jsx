import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';

export default function Dashboard() {
  const { patient } = useAuth();
  const [cases, setCases] = useState([]);
  const [notes, setNotes] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function loadDashboardData() {
      try {
        const [fetchedCases, fetchedNotes] = await Promise.all([
          api.getCases(),
          api.getNotes(),
        ]);
        setCases(fetchedCases || []);
        setNotes(fetchedNotes || []);
      } catch (err) {
        console.warn('Could not load dashboard data:', err.message);
        setError('Unable to load some medical records.');
      } finally {
        setIsLoading(false);
      }
    }

    loadDashboardData();
  }, []);

  const activeCasesCount = cases.filter((c) => c.status === 'active').length;
  const savedNotesCount = notes.length;

  return (
    <div className="dashboard-container">
      {/* Hero Welcome Banner */}
      <section className="dashboard-hero">
        <div className="hero-text">
          <h1>Welcome, {patient?.full_name || 'Patient'}!</h1>
          <p>
            Your health story, organized. Describe health concerns through an empathetic conversational
            intake session, and generate structured clinical records you can review, edit, and keep.
          </p>
        </div>
        <div className="hero-cta">
          <Link to="/cases/new" className="btn btn-white btn-lg">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Start New Case
          </Link>
        </div>
      </section>

      {/* Patient Stats Grid */}
      <section className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon green">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 14 14" />
            </svg>
          </div>
          <div>
            <div className="stat-number">{activeCasesCount}</div>
            <div className="stat-label">Active Consultations</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon teal">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
          </div>
          <div>
            <div className="stat-number">{savedNotesCount}</div>
            <div className="stat-label">Saved Patient Notes</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon blue">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
          <div>
            <div className="stat-number">{cases.length}</div>
            <div className="stat-label">Total Case Intakes</div>
          </div>
        </div>
      </section>

      {/* Saved Patient Notes Section */}
      <section style={{ marginBottom: '2.5rem' }}>
        <div className="section-header">
          <div>
            <h2 className="section-title">Saved Clinical Notes</h2>
            <span style={{ fontSize: '0.85rem', color: 'var(--color-slate-600)' }}>
              {savedNotesCount} {savedNotesCount === 1 ? 'note' : 'notes'} recorded
            </span>
          </div>
          <Link to="/history" className="btn btn-outline" style={{ padding: '0.45rem 1rem', fontSize: '0.88rem' }}>
            View Full Timeline →
          </Link>
        </div>


        {isLoading ? (
          <div className="card" style={{ textAlign: 'center', padding: '2rem' }}>
            <div className="spinner" style={{ margin: '0 auto 1rem' }}></div>
            <p style={{ color: 'var(--color-slate-600)', fontSize: '0.9rem' }}>Loading records...</p>
          </div>
        ) : savedNotesCount === 0 ? (
          <div className="empty-state-card">
            <div className="empty-state-icon">📋</div>
            <h3 className="empty-state-title">No Medical Notes Saved Yet</h3>
            <p className="empty-state-desc">
              When you complete a case-taking consultation with DocuMedi, your structured 11-section
              clinical notes will be saved and accessible here.
            </p>
            <Link to="/cases/new" className="btn btn-primary">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Start Your First Case
            </Link>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {notes.map((n) => (
              <div
                key={n.id}
                className="card"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '1.25rem 1.5rem',
                  gap: '1rem',
                  flexWrap: 'wrap',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.35rem' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--color-primary)', backgroundColor: 'var(--color-primary-ultralight)', padding: '0.15rem 0.5rem', borderRadius: '4px' }}>
                      NOTE #{n.id}
                    </span>
                    <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--color-dark)' }}>
                      {n.chief_complaint?.slice(0, 70) || 'Clinical Note'}
                    </h3>
                  </div>
                  <p style={{ fontSize: '0.82rem', color: 'var(--color-slate-600)' }}>
                    Saved on {new Date(n.created_at).toLocaleDateString()} at{' '}
                    {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} • Linked to Case #{n.case_id}
                  </p>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <Link
                    to={`/notes/${n.id}`}
                    className="btn btn-primary"
                    style={{ padding: '0.45rem 1rem', fontSize: '0.86rem' }}
                  >
                    View Note →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Case Consultations Section */}
      <section style={{ marginBottom: '2.5rem' }}>
        <div className="section-header">
          <h2 className="section-title">Case Consultation Sessions</h2>
          {cases.length > 0 && (
            <Link to="/cases/new" className="btn btn-outline" style={{ padding: '0.45rem 1rem', fontSize: '0.88rem' }}>
              + New Intake
            </Link>
          )}
        </div>

        {cases.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {cases.map((c) => (
              <div
                key={c.id}
                className="card"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '1.25rem 1.5rem',
                  gap: '1rem',
                  flexWrap: 'wrap',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.35rem' }}>
                    <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--color-dark)' }}>
                      {c.case_title}
                    </h3>
                    <span className={`status-badge ${c.status === 'active' ? 'active' : 'completed'}`}>
                      {c.status === 'active' ? 'Active' : 'Completed'}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.82rem', color: 'var(--color-slate-600)' }}>
                    Started on {new Date(c.created_at).toLocaleDateString()} at{' '}
                    {new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} •{' '}
                    {c.message_count} {c.message_count === 1 ? 'message' : 'messages'}
                  </p>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <Link
                    to={`/cases/${c.id}`}
                    className="btn btn-secondary"
                    style={{ padding: '0.45rem 0.95rem', fontSize: '0.86rem' }}
                  >
                    {c.status === 'active' ? 'Resume Consultation' : 'View Dialogue'}
                  </Link>

                  {c.status === 'completed' && (
                    <Link
                      to={`/cases/${c.id}/review-note`}
                      className="btn btn-primary"
                      style={{ padding: '0.45rem 0.95rem', fontSize: '0.86rem' }}
                    >
                      Generate Note
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Account Info Card */}
      <section className="card">
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '1rem', color: 'var(--color-dark)' }}>
          Patient Information Summary
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
          <div>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-slate-600)', fontWeight: 600, display: 'block' }}>
              Full Legal Name
            </span>
            <span style={{ fontSize: '0.98rem', fontWeight: 600, color: 'var(--color-dark)' }}>
              {patient?.full_name}
            </span>
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-slate-600)', fontWeight: 600, display: 'block' }}>
              Registered Email
            </span>
            <span style={{ fontSize: '0.98rem', fontWeight: 600, color: 'var(--color-dark)' }}>
              {patient?.email}
            </span>
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-slate-600)', fontWeight: 600, display: 'block' }}>
              Member Since
            </span>
            <span style={{ fontSize: '0.98rem', fontWeight: 600, color: 'var(--color-dark)' }}>
              {patient?.created_at ? new Date(patient.created_at).toLocaleDateString() : 'Active Member'}
            </span>
          </div>
        </div>
      </section>
    </div>
  );
}
