import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Logo from './Logo';

export default function Navbar() {
  const { isAuthenticated, patient, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getInitials = (name) => {
    if (!name) return 'P';
    const parts = name.trim().split(' ');
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  };

  return (
    <header className="navbar">
      <div className="nav-container">
        <Logo to={isAuthenticated ? '/dashboard' : '/login'} />

        <button
          className="mobile-toggle"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle Navigation Menu"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            {mobileMenuOpen ? (
              <path d="M18 6L6 18M6 6l12 12" />
            ) : (
              <path d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>

        {isAuthenticated ? (
          <nav className={`nav-menu ${mobileMenuOpen ? 'mobile-open' : ''}`}>
            <NavLink
              to="/dashboard"
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Dashboard
            </NavLink>
            <NavLink
              to="/cases/new"
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Start New Case
            </NavLink>
            <NavLink
              to="/history"
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              onClick={() => setMobileMenuOpen(false)}
            >
              My Medical History
            </NavLink>
            <NavLink
              to="/profile"
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Profile
            </NavLink>

            <div className="nav-actions">
              <div className="patient-badge" title={`Signed in as ${patient?.email}`}>
                <div className="patient-avatar">
                  {getInitials(patient?.full_name)}
                </div>
                <span>{patient?.full_name?.split(' ')[0]}</span>
              </div>
              <button
                className="btn btn-secondary"
                style={{ padding: '0.45rem 0.9rem', fontSize: '0.85rem' }}
                onClick={handleLogout}
              >
                Log Out
              </button>
            </div>
          </nav>
        ) : (
          <nav className={`nav-menu ${mobileMenuOpen ? 'mobile-open' : ''}`}>
            <NavLink
              to="/login"
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Sign In
            </NavLink>
            <NavLink
              to="/register"
              className="btn btn-primary"
              style={{ padding: '0.45rem 1.1rem', fontSize: '0.88rem' }}
              onClick={() => setMobileMenuOpen(false)}
            >
              Create Account
            </NavLink>
          </nav>
        )}
      </div>
    </header>
  );
}
