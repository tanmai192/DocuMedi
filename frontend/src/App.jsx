import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import Navbar from './components/Navbar';
import ProtectedRoute from './components/ProtectedRoute';
import PublicRoute from './components/PublicRoute';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Profile from './pages/Profile';
import CaseChat from './pages/CaseChat';
import NoteReview from './pages/NoteReview';
import NoteDetail from './pages/NoteDetail';

import HistoryPlaceholder from './pages/HistoryPlaceholder';
import NotFound from './pages/NotFound';
import './styles/index.css';


export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="app-layout">
          <Navbar />
          <main className="main-content">
            <Routes>
              {/* Root redirect */}
              <Route path="/" element={<Navigate to="/dashboard" replace />} />

              {/* Public-only authentication routes */}
              <Route
                path="/login"
                element={
                  <PublicRoute>
                    <Login />
                  </PublicRoute>
                }
              />
              <Route
                path="/register"
                element={
                  <PublicRoute>
                    <Register />
                  </PublicRoute>
                }
              />

              {/* Protected patient routes */}
              <Route
                path="/dashboard"
                element={
                  <ProtectedRoute>
                    <Dashboard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/cases/new"
                element={
                  <ProtectedRoute>
                    <CaseChat />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/cases/:caseId"
                element={
                  <ProtectedRoute>
                    <CaseChat />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/cases/:caseId/review-note"
                element={
                  <ProtectedRoute>
                    <NoteReview />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/notes/:noteId"
                element={
                  <ProtectedRoute>
                    <NoteDetail />
                  </ProtectedRoute>
                }
              />


              <Route
                path="/history"
                element={
                  <ProtectedRoute>
                    <HistoryPlaceholder />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/profile"
                element={
                  <ProtectedRoute>
                    <Profile />
                  </ProtectedRoute>
                }
              />

              {/* 404 Catch-All */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </main>

          {/* Medical Safety Disclaimer Footer */}
          <footer className="medical-disclaimer">
            <p>
              <strong>Medical Disclaimer:</strong> DocuMedi is an AI-assisted personal health documentation platform.
              It does not diagnose medical conditions, provide clinical treatments, or replace licensed medical advice.
              If you are experiencing a medical emergency, call your local emergency services immediately.
            </p>
          </footer>
        </div>
      </AuthProvider>
    </BrowserRouter>
  );
}
