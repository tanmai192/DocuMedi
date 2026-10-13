import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';

const SECTION_CONFIG = [
  { key: 'chief_complaint', number: '1', title: 'Chief Complaint', hint: 'Primary symptom or main reason for consultation.' },
  { key: 'hpi', number: '2', title: 'HPI (History of Present Illness)', hint: 'Detailed narrative: onset, duration, character, and severity.' },
  { key: 'past_medical_history', number: '3', title: 'Past Medical History', hint: 'Chronic conditions or previous diagnoses (or "Not provided").' },
  { key: 'medications', number: '4', title: 'Current Medications', hint: 'Prescription medications, OTC drugs, and vitamins.' },
  { key: 'allergies', number: '5', title: 'Allergies', hint: 'Medication, food, or environmental allergies.' },
  { key: 'family_history', number: '6', title: 'Family History', hint: 'Relevant health history of immediate family.' },
  { key: 'social_history', number: '7', title: 'Social History', hint: 'Lifestyle factors, occupation, habits.' },
  { key: 'review_of_systems', number: '8', title: 'Review of Systems', hint: 'Summary of body systems and associated symptoms.' },
  { key: 'physical_examination', number: '9', title: 'Physical Examination', hint: 'Documentation standard: Physical exam was not conducted during patient chat.', readOnly: true },
  { key: 'assessment_and_plan', number: '10', title: 'Assessment and Plan', hint: 'Neutral summary of concerns. Professional evaluation required.' },
  { key: 'follow_up', number: '11', title: 'Follow-up', hint: 'Recommended healthcare consultation guidance.' },
];

export default function NoteReview() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const { patient } = useAuth();

  const [caseTitle, setCaseTitle] = useState('Clinical Consultation');
  const [note, setNote] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');
  const [systemNotice, setSystemNotice] = useState(null);

  // Generate note on initial page load
  useEffect(() => {
    let isMounted = true;

    async function fetchGeneratedNote() {
      setIsLoading(true);
      setError('');
      try {
        const res = await api.generateNote(caseId);
        if (isMounted) {
          setCaseTitle(res.case_title || 'Clinical Consultation');
          setNote(res.note);
          if (res.system_notice) {
            setSystemNotice(res.system_notice);
          }
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message || 'Failed to generate patient note from conversation.');
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    fetchGeneratedNote();

    return () => {
      isMounted = false;
    };
  }, [caseId]);

  const handleFieldChange = (key, value) => {
    setNote((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleRegenerate = async () => {
    if (!window.confirm('Regenerate note? Any custom edits you made in the form below will be refreshed.')) {
      return;
    }
    setIsLoading(true);
    setError('');
    try {
      const res = await api.generateNote(caseId);
      setNote(res.note);
      if (res.system_notice) setSystemNotice(res.system_notice);
    } catch (err) {
      setError(err.message || 'Failed to regenerate note.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveConfirmedNote = async () => {
    if (!note) return;
    setIsSaving(true);
    setError('');

    try {
      const saved = await api.saveCaseNote(caseId, note);
      // Navigate to saved note detail page
      navigate(`/notes/${saved.id}`, { replace: true });
    } catch (err) {
      setError(err.message || 'Failed to save confirmed note. Please try again.');
      setIsSaving(false);
    }
  };

  const handleSaveAndDownloadPdf = async () => {
    if (!note || isSaving) return;
    setIsSaving(true);
    setError('');

    try {
      // 1. Confirm and save the note to MySQL records first
      const saved = await api.saveCaseNote(caseId, note);

      // 2. Trigger official PDF generation and download
      try {
        await api.downloadNotePdf(saved.id);
      } catch (pdfErr) {
        console.warn('PDF download warning:', pdfErr.message);
      }

      // 3. Navigate to the verified note detail view
      navigate(`/notes/${saved.id}`, { replace: true });
    } catch (err) {
      setError(err.message || 'Failed to save confirmed note. Please try again.');
      setIsSaving(false);
    }
  };


  if (isLoading) {
    return (
      <div className="spinner-container">
        <div className="spinner"></div>
        <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-dark)' }}>
          Generating Structured Clinical Patient Note...
        </h3>
        <p style={{ color: 'var(--color-slate-600)', fontSize: '0.92rem', maxWidth: '460px', textAlign: 'center' }}>
          Organizing your reported symptoms into the 11 clinical standard headings. Please wait a moment.
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Sticky Top Action Toolbar */}
      <div className="document-actions-sticky">
        <div>
          <span style={{ fontSize: '0.85rem', color: 'var(--color-slate-600)', fontWeight: 600 }}>
            Reviewing Draft Note for Case #{caseId}
          </span>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--color-dark)', lineHeight: 1.2 }}>
            {caseTitle}
          </h2>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <Link to={`/cases/${caseId}`} className="btn btn-secondary" style={{ fontSize: '0.88rem' }}>
            Cancel & Return to Chat
          </Link>

          <button
            type="button"
            className="btn btn-outline"
            style={{ fontSize: '0.88rem' }}
            onClick={handleRegenerate}
            disabled={isSaving}
          >
            🔄 Regenerate Note
          </button>

          <button
            type="button"
            className="btn btn-outline"
            style={{ fontSize: '0.88rem' }}
            onClick={handleSaveAndDownloadPdf}
            disabled={isSaving}
            title="Official clinical PDFs are generated from saved medical records. Confirms and saves this note, then downloads the PDF."
          >
            {isSaving ? '⏳ Saving & Generating...' : '📄 Save & Download PDF'}
          </button>

          <button
            type="button"
            className="btn btn-primary"
            style={{ fontSize: '0.92rem' }}
            onClick={handleSaveConfirmedNote}
            disabled={isSaving}
          >
            {isSaving ? 'Saving to Records...' : '✓ Save Confirmed Note'}
          </button>
        </div>
      </div>


      {error && (
        <div className="alert alert-danger" style={{ maxWidth: '900px', margin: '0 auto 1.5rem' }}>
          <span>{error}</span>
        </div>
      )}

      <div className="alert alert-info" style={{ maxWidth: '900px', margin: '0 auto 1.5rem', fontSize: '0.88rem' }}>
        <span>📄 <strong>Official Record Policy:</strong> Official clinical PDFs are generated strictly from saved, verified medical records. Clicking <strong>Save & Download PDF</strong> confirms and saves this note permanently to your MySQL records and generates your downloadable PDF report.</span>
      </div>

      {systemNotice && (
        <div className="alert alert-info" style={{ maxWidth: '900px', margin: '0 auto 1.5rem' }}>
          <span>ℹ️ {systemNotice}</span>
        </div>
      )}

      {/* Document Review Canvas */}
      <article className="document-sheet">
        <header className="document-header">
          <div className="document-title-block">
            <h1>DocuMedi Clinical Patient Note (Draft)</h1>
            <p style={{ color: 'var(--color-slate-600)', fontSize: '0.92rem' }}>
              Please review and edit each section. You may correct, clarify, or expand any details before permanently saving.
            </p>
            <div className="document-meta">
              <span><strong>Patient:</strong> {patient?.full_name}</span>
              <span><strong>Case:</strong> {caseTitle}</span>
              <span><strong>Status:</strong> Pending Confirmation</span>
            </div>
          </div>
        </header>

        {/* The 11 Standard Clinical Sections in Exact Order */}
        {SECTION_CONFIG.map(({ key, number, title, hint, readOnly }) => (
          <section key={key} className="document-section">
            <label className="document-section-label" htmlFor={`section-${key}`}>
              <span className="document-section-number">{number}</span>
              <span>{title}</span>
            </label>
            <p style={{ fontSize: '0.8rem', color: 'var(--color-slate-400)', marginBottom: '0.45rem' }}>
              {hint}
            </p>

            <textarea
              id={`section-${key}`}
              className="document-textarea"
              rows={key === 'hpi' ? 4 : 2}
              value={note?.[key] || ''}
              onChange={(e) => handleFieldChange(key, e.target.value)}
              disabled={readOnly || isSaving}
              placeholder="Not provided"
              style={readOnly ? { backgroundColor: '#f1f5f9', cursor: 'not-allowed', color: '#64748b' } : {}}
            />
          </section>
        ))}

        {/* Footer Guidance */}
        <footer style={{ marginTop: '2.5rem', paddingTop: '1.5rem', borderTop: '2px solid var(--color-border-light)' }}>
          <div className="alert alert-info" style={{ marginBottom: '1.5rem' }}>
            <strong>Documentation Notice:</strong> This clinical note is compiled from patient-reported information.
            It does not constitute a clinical diagnosis or treatment prescription.
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <Link to={`/cases/${caseId}`} className="btn btn-secondary">
              Cancel
            </Link>
            <button
              type="button"
              className="btn btn-primary btn-lg"
              onClick={handleSaveConfirmedNote}
              disabled={isSaving}
            >
              {isSaving ? 'Saving to Database...' : 'Save Confirmed Note to Records'}
            </button>
          </div>
        </footer>
      </article>
    </div>
  );
}
