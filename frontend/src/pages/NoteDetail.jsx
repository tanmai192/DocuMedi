import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';

const SECTION_CONFIG = [
  { key: 'chief_complaint', number: '1', title: 'Chief Complaint' },
  { key: 'hpi', number: '2', title: 'HPI (History of Present Illness)' },
  { key: 'past_medical_history', number: '3', title: 'Past Medical History' },
  { key: 'medications', number: '4', title: 'Current Medications' },
  { key: 'allergies', number: '5', title: 'Allergies' },
  { key: 'family_history', number: '6', title: 'Family History' },
  { key: 'social_history', number: '7', title: 'Social History' },
  { key: 'review_of_systems', number: '8', title: 'Review of Systems' },
  { key: 'physical_examination', number: '9', title: 'Physical Examination', readOnly: true },
  { key: 'assessment_and_plan', number: '10', title: 'Assessment and Plan' },
  { key: 'follow_up', number: '11', title: 'Follow-up' },
];

export default function NoteDetail() {
  const { noteId } = useParams();
  const { patient } = useAuth();

  const [note, setNote] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [pdfError, setPdfError] = useState('');
  const [pdfSuccess, setPdfSuccess] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let isMounted = true;

    async function loadNote() {
      setIsLoading(true);
      setError('');
      try {
        const data = await api.getNoteDetails(noteId);
        if (isMounted) {
          setNote(data);
          setFormData(data);
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message || 'Failed to load saved patient note.');
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadNote();

    return () => {
      isMounted = false;
    };
  }, [noteId]);

  const handleFieldChange = (key, value) => {
    setFormData((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleSaveEdits = async () => {
    setIsSaving(true);
    setError('');
    setSaveSuccess(false);
    try {
      const updated = await api.updateNote(noteId, formData);
      setNote(updated);
      setFormData(updated);
      setIsEditing(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (err) {
      setError(err.message || 'Failed to update note.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancelEdits = () => {
    setFormData(note);
    setIsEditing(false);
    setError('');
  };

  const handleDownloadPdf = async () => {
    if (!noteId || isDownloadingPdf) return;
    setIsDownloadingPdf(true);
    setPdfError('');
    setPdfSuccess(false);

    try {
      await api.downloadNotePdf(noteId);
      setPdfSuccess(true);
      setTimeout(() => setPdfSuccess(false), 4000);
    } catch (err) {
      setPdfError(err.message || 'Failed to download clinical note PDF.');
    } finally {
      setIsDownloadingPdf(false);
    }
  };

  if (isLoading) {
    return (
      <div className="spinner-container">
        <div className="spinner"></div>
        <p style={{ color: 'var(--color-slate-600)', fontSize: '0.92rem' }}>
          Loading your clinical medical record...
        </p>
      </div>
    );
  }

  if (error && !note) {
    return (
      <div style={{ maxWidth: '600px', margin: '3rem auto', textAlign: 'center' }}>
        <div className="card">
          <h2 style={{ color: 'var(--color-danger)', marginBottom: '0.5rem' }}>Record Access Error</h2>
          <p style={{ color: 'var(--color-slate-600)', marginBottom: '1.5rem' }}>{error}</p>
          <Link to="/dashboard" className="btn btn-primary">
            Return to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Sticky Top Toolbar */}
      <div className="document-actions-sticky">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Link to="/dashboard" className="btn btn-secondary" style={{ fontSize: '0.86rem', padding: '0.45rem 0.9rem' }}>
            ← Dashboard
          </Link>
          <Link to={`/cases/${note?.case_id}`} className="btn btn-secondary" style={{ fontSize: '0.86rem', padding: '0.45rem 0.9rem' }}>
            View Dialogue
          </Link>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          {/* Functional PDF Download Button */}
          <button
            type="button"
            className="btn btn-outline"
            style={{ fontSize: '0.88rem' }}
            title="Download authoritative clinical record as PDF"
            onClick={handleDownloadPdf}
            disabled={isDownloadingPdf}
          >
            {isDownloadingPdf ? '⏳ Generating PDF...' : '📄 Download PDF'}
          </button>


          {!isEditing ? (
            <button
              type="button"
              className="btn btn-primary"
              style={{ fontSize: '0.88rem' }}
              onClick={() => setIsEditing(true)}
            >
              ✏️ Edit Note
            </button>
          ) : (
            <>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ fontSize: '0.88rem' }}
                onClick={handleCancelEdits}
                disabled={isSaving}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                style={{ fontSize: '0.88rem' }}
                onClick={handleSaveEdits}
                disabled={isSaving}
              >
                {isSaving ? 'Saving Changes...' : 'Save Updates'}
              </button>
            </>
          )}
        </div>
      </div>

      {saveSuccess && (
        <div className="alert alert-success" style={{ maxWidth: '900px', margin: '0 auto 1.5rem' }}>
          ✓ Clinical note updated successfully in your records!
        </div>
      )}

      {pdfSuccess && (
        <div className="alert alert-success" style={{ maxWidth: '900px', margin: '0 auto 1.5rem' }}>
          ✓ Clinical PDF report generated and downloaded successfully!
        </div>
      )}

      {pdfError && (
        <div className="alert alert-danger" style={{ maxWidth: '900px', margin: '0 auto 1.5rem' }}>
          ⚠️ {pdfError}
        </div>
      )}


      {error && (
        <div className="alert alert-danger" style={{ maxWidth: '900px', margin: '0 auto 1.5rem' }}>
          {error}
        </div>
      )}

      {/* Verified Document Presentation */}
      <article className="document-sheet">
        <header className="document-header">
          <div className="document-title-block">
            <span style={{ fontSize: '0.78rem', color: 'var(--color-brand-dark)', backgroundColor: 'var(--color-primary-light)', padding: '0.2rem 0.65rem', borderRadius: 'var(--radius-full)', display: 'inline-block', marginBottom: '0.35rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Confirmed Clinical Record #{note?.id}
            </span>
            <h1>DocuMedi Clinical Patient Note</h1>
            <div className="document-meta">
              <span><strong>Patient:</strong> {patient?.full_name}</span>
              <span><strong>Email:</strong> {patient?.email}</span>
              <span><strong>Date Created:</strong> {note?.created_at ? new Date(note.created_at).toLocaleDateString() : ''}</span>
              {note?.updated_at && note?.updated_at !== note?.created_at && (
                <span><strong>Last Updated:</strong> {new Date(note.updated_at).toLocaleDateString()}</span>
              )}
            </div>
          </div>
        </header>

        {/* 11 Headings in Strict Order */}
        {SECTION_CONFIG.map(({ key, number, title, readOnly }) => {
          const content = isEditing ? formData[key] : note?.[key];

          return (
            <section key={key} className="document-section">
              <h2 className="document-section-label">
                <span className="document-section-number">{number}</span>
                <span>{title}</span>
              </h2>

              {isEditing && !readOnly ? (
                <textarea
                  className="document-textarea"
                  rows={key === 'hpi' ? 4 : 2}
                  value={content || ''}
                  onChange={(e) => handleFieldChange(key, e.target.value)}
                  disabled={isSaving}
                />
              ) : (
                <div className="document-section-body">
                  {content || 'Not provided'}
                </div>
              )}
            </section>
          );
        })}

        {/* Footer Medical Disclaimer */}
        <footer style={{ marginTop: '2.5rem', paddingTop: '1.5rem', borderTop: '2px solid var(--color-border-light)' }}>
          <p style={{ fontSize: '0.82rem', color: 'var(--color-slate-600)', lineHeight: 1.5 }}>
            <strong>DocuMedi Record Notice:</strong> This clinical document was generated with AI assistance from
            patient-reported intake dialogue and verified by the patient. It does not replace a clinical examination
            by a licensed medical practitioner.
          </p>
        </footer>
      </article>
    </div>
  );
}
