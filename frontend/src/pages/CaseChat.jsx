import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';

export default function CaseChat() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const { patient } = useAuth();

  const [caseData, setCaseData] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isThinking, setIsThinking] = useState(false);
  const [error, setError] = useState('');
  const [systemNotice, setSystemNotice] = useState(null);
  const [showEndConfirm, setShowEndConfirm] = useState(false);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isThinking]);

  // Load case or initialize new one
  useEffect(() => {
    let isMounted = true;

    async function initCase() {
      setIsLoading(true);
      setError('');

      try {
        if (!caseId || caseId === 'new') {
          // Create a new consultation case
          const created = await api.createCase('Health Concern Consultation');
          if (isMounted) {
            navigate(`/cases/${created.id}`, { replace: true });
          }
          return;
        }

        // Fetch existing case by ID
        const data = await api.getCaseDetails(caseId);
        if (isMounted) {
          setCaseData(data);
          setMessages(data.messages || []);
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message || 'Failed to load case consultation.');
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    initCase();

    return () => {
      isMounted = false;
    };
  }, [caseId, navigate]);

  // Handle message submission
  const handleSendMessage = async (e) => {
    e?.preventDefault();
    const content = inputText.trim();
    if (!content || isThinking || caseData?.status !== 'active') return;

    setInputText('');
    setError('');

    // Optimistically add patient message
    const tempPatientMsg = {
      id: Date.now(),
      case_id: Number(caseId),
      sender_role: 'patient',
      message_content: content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempPatientMsg]);
    setIsThinking(true);

    try {
      const response = await api.sendMessage(caseId, content);
      // Replace or append confirmed messages
      setMessages((prev) => {
        const filtered = prev.filter((m) => m.id !== tempPatientMsg.id);
        return [...filtered, response.patient_message, response.ai_response];
      });

      if (response.system_notice) {
        setSystemNotice(response.system_notice);
      }
    } catch (err) {
      setError(err.message || 'Failed to receive AI response. Please try again.');
      // Keep patient message so they don't lose their input
    } finally {
      setIsThinking(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  // Handle ending consultation
  const handleEndConsultation = async () => {
    setShowEndConfirm(false);
    setIsLoading(true);
    try {
      const updated = await api.endCase(caseId);
      setCaseData(updated);
      setMessages(updated.messages || []);
    } catch (err) {
      setError(err.message || 'Failed to end consultation.');
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading && (!messages || messages.length === 0)) {
    return (
      <div className="spinner-container">
        <div className="spinner"></div>
        <p style={{ color: 'var(--color-slate-600)', fontSize: '0.92rem' }}>
          Preparing your confidential clinical consultation session...
        </p>
      </div>
    );
  }

  const isCompleted = caseData?.status === 'completed';

  return (
    <div className="chat-wrapper">
      {/* Chat Top Header */}
      <header className="chat-header">
        <div className="chat-header-title">
          <h2>{caseData?.case_title || 'Clinical Consultation'}</h2>
          <span className={`status-badge ${isCompleted ? 'completed' : 'active'}`}>
            {!isCompleted && <span className="status-pulse" />}
            {isCompleted ? 'Completed' : 'Active Intake'}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {!isCompleted ? (
            <button
              className="btn btn-secondary"
              style={{ padding: '0.45rem 0.95rem', fontSize: '0.86rem' }}
              onClick={() => setShowEndConfirm(true)}
              title="Finish consultation and save dialogue"
            >
              Finish Consultation
            </button>
          ) : (
            <Link
              to="/dashboard"
              className="btn btn-primary"
              style={{ padding: '0.45rem 1rem', fontSize: '0.86rem' }}
            >
              Dashboard
            </Link>
          )}
        </div>
      </header>

      {/* Medical Safety & Emergency Notice */}
      <div className="chat-safety-banner">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
        <span>
          <strong>Documentation Notice:</strong> DocuMedi is a documentation tool, not a doctor. If you are experiencing a life-threatening emergency in India, call <strong>112</strong> immediately (or <strong>108</strong> for ambulance services).
        </span>
      </div>

      {/* Provider / System Banner */}
      {systemNotice && (
        <div style={{ backgroundColor: 'var(--color-info-bg)', borderBottom: '1px solid var(--color-info-border)', padding: '0.45rem 1.25rem', fontSize: '0.8rem', color: 'var(--color-secondary)' }}>
          ℹ️ {systemNotice}
        </div>
      )}

      {/* Confirmation Modal */}
      {showEndConfirm && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(51, 43, 39, 0.5)', zIndex: 100,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem'
        }}>
          <div className="card" style={{ maxWidth: '440px', width: '100%', padding: '1.75rem', boxShadow: 'var(--shadow-card)', border: '1px solid var(--color-border)' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--color-dark)' }}>
              End Case Consultation?
            </h3>
            <p style={{ fontSize: '0.92rem', color: 'var(--color-slate-600)', marginBottom: '1.5rem', lineHeight: 1.5 }}>
              This will conclude your conversation and lock the case for structured patient note generation.
              All messages are permanently saved to your records.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button className="btn btn-secondary" onClick={() => setShowEndConfirm(false)}>
                Continue Chatting
              </button>
              <button className="btn btn-primary" onClick={handleEndConsultation}>
                Yes, Finish Consultation
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Message List Area */}
      <div className="chat-messages">
        {messages.map((msg, index) => {
          const isAi = msg.sender_role === 'ai';
          const isSystem = msg.sender_role === 'system';
          const isPatient = msg.sender_role === 'patient';

          if (isSystem) {
            return (
              <div key={msg.id || index} className="message-row system">
                <div className="message-bubble">{msg.message_content}</div>
              </div>
            );
          }

          return (
            <div
              key={msg.id || index}
              className={`message-row ${isAi ? 'ai' : 'patient'}`}
            >
              {isAi ? (
                <div className="ai-avatar" title="DocuMedi Clinical Assistant">
                  🩺
                </div>
              ) : (
                <div className="patient-avatar-chat" title={patient?.full_name || 'You'}>
                  {patient?.full_name ? patient.full_name[0].toUpperCase() : 'P'}
                </div>
              )}

              <div className="message-bubble">
                <div style={{ whiteSpace: 'pre-wrap' }}>{msg.message_content}</div>
                <div className="message-time">
                  {msg.created_at
                    ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    : ''}
                </div>
              </div>
            </div>
          );
        })}

        {/* AI Typing Indicator */}
        {isThinking && (
          <div className="message-row ai">
            <div className="ai-avatar">🩺</div>
            <div className="message-bubble">
              <div className="typing-dots">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
              </div>
            </div>
          </div>
        )}

        {/* Error Banner with Retry */}
        {error && (
          <div className="alert alert-danger" style={{ margin: '0.5rem 0' }}>
            <span>{error}</span>
            <button
              onClick={() => handleSendMessage()}
              style={{ marginLeft: 'auto', background: 'none', border: 'underline', color: 'inherit', fontWeight: 600, cursor: 'pointer' }}
            >
              Retry
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Completed State Banner */}
      {isCompleted ? (
        <div className="chat-completed-banner">
          <h3>✓ Consultation Complete</h3>
          <p>
            Your consultation dialogue has been saved to MySQL. You can now generate, review, and edit your
            structured 11-section clinical patient note.
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <Link to={`/cases/${caseId}/review-note`} className="btn btn-primary" style={{ fontSize: '0.92rem' }}>
              📋 Generate & Review Patient Note →
            </Link>
            <Link to="/dashboard" className="btn btn-secondary" style={{ fontSize: '0.88rem' }}>
              Return to Dashboard
            </Link>
          </div>
        </div>
      ) : (

        /* Active Input Area */
        <div className="chat-input-area">
          <form className="chat-form" onSubmit={handleSendMessage}>
            <input
              ref={inputRef}
              type="text"
              className="chat-input"
              placeholder="Type your response here... (e.g. My symptoms started two days ago)"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              disabled={isThinking || isCompleted}
              autoFocus
            />
            <button
              type="submit"
              className="btn btn-primary chat-send-btn"
              disabled={!inputText.trim() || isThinking || isCompleted}
              aria-label="Send Message"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
