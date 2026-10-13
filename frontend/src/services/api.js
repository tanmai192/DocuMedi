/**
 * api.js — Centralized API service for DocuMedi
 * Connects the React frontend to the FastAPI backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

class ApiClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
  }

  /**
   * Helper to retrieve the current token from localStorage
   */
  getToken() {
    return localStorage.getItem('documedi_token');
  }

  /**
   * Base fetch wrapper that injects headers and handles JSON responses/errors
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const token = this.getToken();

    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      // Handle non-JSON responses (or empty bodies like 204)
      const contentType = response.headers.get('content-type');
      let data = null;
      if (contentType && contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        // Extract friendly error message from FastAPI HTTPException detail
        let errorMessage = 'An unexpected error occurred. Please try again.';
        if (data && typeof data === 'object') {
          if (typeof data.detail === 'string') {
            errorMessage = data.detail;
          } else if (Array.isArray(data.detail)) {
            // Pydantic validation errors list
            errorMessage = data.detail.map(err => err.msg || `${err.loc?.join('.')}: invalid input`).join(', ');
          } else if (data.message) {
            errorMessage = data.message;
          }
        }
        const error = new Error(errorMessage);
        error.status = response.status;
        error.data = data;
        throw error;
      }

      return data;
    } catch (err) {
      // Network error or fetch abort
      if (!err.status) {
        throw new Error('Unable to connect to DocuMedi server. Please check your network or ensure backend is running.');
      }
      throw err;
    }
  }

  // --- Auth Endpoints ---

  async register(patientData) {
    return this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(patientData),
    });
  }

  async login(credentials) {
    return this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
  }

  async getMe() {
    return this.request('/auth/me', {
      method: 'GET',
    });
  }

  async healthCheck() {
    return this.request('/', {
      method: 'GET',
    });
  }

  // --- Cases & Conversational AI Endpoints (Stage 5) ---

  async createCase(caseTitle = 'Health Concern Consultation') {
    return this.request('/cases', {
      method: 'POST',
      body: JSON.stringify({ case_title: caseTitle }),
    });
  }

  async getCases() {
    return this.request('/cases', {
      method: 'GET',
    });
  }

  async getCaseDetails(caseId) {
    return this.request(`/cases/${caseId}`, {
      method: 'GET',
    });
  }

  async sendMessage(caseId, messageContent) {
    return this.request(`/cases/${caseId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ message_content: messageContent }),
    });
  }

  async endCase(caseId) {
    return this.request(`/cases/${caseId}/end`, {
      method: 'POST',
    });
  }

  // --- Notes Endpoints (Stage 6) ---

  async generateNote(caseId) {
    return this.request(`/cases/${caseId}/generate-note`, {
      method: 'POST',
    });
  }

  async saveCaseNote(caseId, noteData) {
    return this.request(`/cases/${caseId}/notes`, {
      method: 'POST',
      body: JSON.stringify(noteData),
    });
  }

  async getNotes() {
    return this.request('/notes', {
      method: 'GET',
    });
  }

  async getTimeline() {
    return this.request('/notes/timeline', {
      method: 'GET',
    });
  }

  async getNoteDetails(noteId) {
    return this.request(`/notes/${noteId}`, {
      method: 'GET',
    });
  }


  async updateNote(noteId, noteData) {
    return this.request(`/notes/${noteId}`, {
      method: 'PUT',
      body: JSON.stringify(noteData),
    });
  }
}

export const api = new ApiClient(API_BASE_URL);
export default api;

