import React from 'react';
import { Link } from 'react-router-dom';

export default function Logo({ showTagline = true, to = '/dashboard' }) {
  return (
    <Link to={to} className="nav-brand" aria-label="DocuMedi Home">
      <svg
        className="brand-logo-icon"
        viewBox="0 0 36 36"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect width="36" height="36" rx="10" fill="#3F6B4F" stroke="#E4D4BA" strokeWidth="1" />
        {/* Document Sheet */}
        <path
          d="M10 8C10 6.89543 10.8954 6 12 6H20L26 12V28C26 29.1046 25.1046 30 24 30H12C10.8954 30 10 29.1046 10 28V8Z"
          fill="#FFFAF0"
          stroke="#E4D4BA"
          strokeWidth="1"
        />
        {/* Document Fold */}
        <path d="M20 6V12H26" fill="#E4D4BA" />
        {/* Medical Cross */}
        <path
          d="M18 16V24M14 20H22"
          stroke="#C2185B"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
      </svg>
      <div className="brand-text-col">
        <span className="brand-title">
          Docu<span>Medi</span>
        </span>
        {showTagline && (
          <span className="brand-tagline">Your Health Story, Organized.</span>
        )}
      </div>
    </Link>
  );
}
