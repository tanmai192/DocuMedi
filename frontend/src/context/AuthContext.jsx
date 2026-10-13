import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [patient, setPatient] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('documedi_token'));
  const [isLoading, setIsLoading] = useState(true);

  // Validate existing token on initial startup
  useEffect(() => {
    async function loadInitialUser() {
      const storedToken = localStorage.getItem('documedi_token');
      if (!storedToken) {
        setIsLoading(false);
        return;
      }

      try {
        const userProfile = await api.getMe();
        setPatient(userProfile);
      } catch (err) {
        // Token is invalid, expired, or backend was reset
        console.warn('Session expired or invalid token:', err.message);
        localStorage.removeItem('documedi_token');
        setToken(null);
        setPatient(null);
      } finally {
        setIsLoading(false);
      }
    }

    loadInitialUser();
  }, []);

  /**
   * Save token and authenticated patient upon login
   */
  const login = (authToken, patientData) => {
    localStorage.setItem('documedi_token', authToken);
    setToken(authToken);
    setPatient(patientData);
  };

  /**
   * Clear session on logout
   */
  const logout = () => {
    localStorage.removeItem('documedi_token');
    setToken(null);
    setPatient(null);
  };

  const value = {
    patient,
    token,
    isAuthenticated: Boolean(token && patient),
    isLoading,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
