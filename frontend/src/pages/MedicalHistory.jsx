import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';

export default function MedicalHistory() {
  const { patient } = useAuth();
  const [timeline, setTimeline] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [downloadingNoteId, setDownloadingNoteId] = useState(null);
  const [actionFeedback, setActionFeedback] = useState({ type: '', message: '' });

  const fetchTimeline = async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await api.getTimeline();
      setTimeline(data || []);
    } catch (err) {
      console.warn('Could not load timeline records:', err.message);
      setError(err.message || 'Unable to retrieve your medical history timeline.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadPdf = async (noteId) => {
    if (downloadingNoteId) return;
    setDownloadingNoteId(noteId);
    setActionFeedback({ type: '', message: '' });

    try {
      await api.downloadNotePdf(noteId);
      setActionFeedback({
        type: 'success',
        message: `Clinical PDF report for Note #${noteId} downloaded successfully!`
      });
      setTimeout(() => setActionFeedback({ type: '', message: '' }), 4000);
    } catch (err) {
      setActionFeedback({
        type: 'error',
        message: err.message || `Failed to download PDF for Note #${noteId}.`
      });
    } finally {
      setDownloadingNoteId(null);
    }
  };


  useEffect(() => {
    fetchTimeline();
  }, []);

  return (
    <div className="timeline-wrapper">
      {/* Header and Call to Action */}
      <header className="timeline-header-area">
        <div>
          <h1 style={{ fontSize: '1.85rem', fontWeight: 800, color: 'var(--color-dark)', letterSpacing: '-0.02em', marginBottom: '0.25rem' }}>
            My Medical History
          </h1>
          <p style={{ color: 'var(--color-slate-600)', fontSize: '0.95rem' }}>
            A chronological timeline of your verified clinical consultation notes and intake records
          </p>
        </div>

        <Link to="/cases/new" className="btn btn-primary">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Start New Case
        </Link>
      </header>

      {/* Action feedback for PDF downloads */}
      {actionFeedback.message && (
        <div
          className={`alert ${actionFeedback.type === 'error' ? 'alert-danger' : 'alert-success'}`}
          style={{ marginBottom: '1.5rem' }}
        >
          {actionFeedback.type === 'error' ? '⚠️ ' : '✓ '}
          {actionFeedback.message}
        </div>
      )}

      {/* Error state with retry */}
      {error && (
        <div className="alert alert-danger" style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span>{error}</span>
          <button
            onClick={fetchTimeline}
            className="btn btn-secondary"
            style={{ padding: '0.35rem 0.8rem', fontSize: '0.82rem' }}
          >
            Try Again
          </button>
        </div>
      )}

      {/* Loading state */}
      {isLoading ? (
        <div className="spinner-container">
          <div className="spinner"></div>
          <p style={{ color: 'var(--color-slate-600)', fontSize: '0.92rem' }}>
            Loading your medical history records...
          </p>
        </div>
      ) : timeline.length === 0 ? (
        /* Empty State */
        <div className="empty-state-card" style={{ padding: '3.5rem 2rem' }}>
          <div className="empty-state-icon">📅</div>
          <h2 className="empty-state-title">No Medical History Recorded Yet</h2>
          <p className="empty-state-desc">
            You don't have any saved clinical notes yet. When you complete a consultation with DocuMedi
            and confirm your 11-section note, your permanent medical history timeline will be built here.
          </p>
          <Link to="/cases/new" className="btn btn-primary btn-lg">
            Start Your First Consultation Case
          </Link>
        </div>
      ) : (
        /* Chronological Timeline Entries */
        <div className="timeline-track">
          {timeline.map((entry) => (
            <div key={entry.note_id} className="timeline-entry">
              {/* Timeline dot marker */}
              <div className="timeline-node" />

              <div className="timeline-card">
                <header className="timeline-entry-header">
                  <div>
                    <span style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--color-primary)', backgroundColor: 'var(--color-primary-ultralight)', padding: '0.2rem 0.55rem', borderRadius: '4px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Verified Clinical Record #{entry.note_id}
                    </span>
                    <h3 className="timeline-case-title" style={{ marginTop: '0.35rem' }}>
                      {entry.case_title}
                    </h3>
                  </div>

                  <span className="timeline-timestamp">
                    🗓️ {new Date(entry.created_at).toLocaleDateString(undefined, {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    })} at {new Date(entry.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </header>

                <div className="timeline-complaint">
                  <strong>Chief Complaint:</strong> {entry.chief_complaint}
                </div>

                <div className="timeline-summary-text">
                  <strong>Clinical Summary:</strong> {entry.summary}
                </div>

                <footer className="timeline-actions">
                  <Link
                    to={`/notes/${entry.note_id}`}
                    className="btn btn-primary"
                    style={{ fontSize: '0.88rem', padding: '0.5rem 1.15rem' }}
                  >
                    📄 View Clinical Note
                  </Link>

                  <Link
                    to={`/cases/${entry.case_id}`}
                    className="btn btn-secondary"
                    style={{ fontSize: '0.88rem', padding: '0.5rem 1.15rem' }}
                  >
                    💬 View Consultation Case
                  </Link>

                  {/* Functional Stage 8 PDF Download Button */}
                  <button
                    type="button"
                    className="btn btn-outline"
                    style={{ fontSize: '0.88rem', padding: '0.5rem 1.15rem' }}
                    onClick={() => handleDownloadPdf(entry.note_id)}
                    disabled={downloadingNoteId === entry.note_id}
                    title="Download authoritative clinical record as PDF"
                  >
                    {downloadingNoteId === entry.note_id ? '⏳ Generating PDF...' : '📥 Download PDF'}
                  </button>
                </footer>

              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
