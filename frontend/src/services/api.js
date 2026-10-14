/**
 * Clean and normalize API base URL:
 * - Trims whitespace
 * - Strips trailing slashes
 * - Strips accidental paths like /docs or /auth/register if pasted by mistake
 */
function cleanBaseUrl(url) {
  if (!url || typeof url !== 'string') {
    return 'http://127.0.0.1:8000';
  }
  let cleaned = url.trim();
  cleaned = cleaned.replace(/\/+$/, '');
  cleaned = cleaned.replace(/\/(?:docs|auth\/register|openapi\.json)$/i, '');
  return cleaned.replace(/\/+$/, '') || 'http://127.0.0.1:8000';
}

const API_BASE_URL = cleanBaseUrl(import.meta.env.VITE_API_BASE_URL);

class ApiClient {
  constructor(baseUrl) {
    this.baseUrl = cleanBaseUrl(baseUrl);
  }

  /**
   * Helper to retrieve the current token from localStorage
   */
  getToken() {
    return localStorage.getItem('documedi_token');
  }

  /**
   * Safely formats endpoint URL preventing duplicate slashes
   */
  buildUrl(endpoint) {
    const cleanEndpoint = endpoint ? (endpoint.startsWith('/') ? endpoint : `/${endpoint}`) : '';
    return `${this.baseUrl}${cleanEndpoint}`;
  }

  /**
   * Base fetch wrapper that injects headers and handles JSON responses/errors
   */
  async request(endpoint, options = {}) {
    const url = this.buildUrl(endpoint);
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
        // Extract friendly error message from FastAPI HTTPException detail or plain text
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
        } else if (typeof data === 'string' && data.trim()) {
          if (response.status === 400 && data.includes('CORS')) {
            errorMessage = 'Cross-Origin Request Blocked (CORS error). Please verify allowed origins in backend configuration.';
          } else if (response.status === 503) {
            errorMessage = 'Database or server unavailable. Please ensure database connection is active.';
          } else if (response.status === 500) {
            errorMessage = 'DocuMedi server encountered an internal error. Please check server and database logs.';
          } else {
            errorMessage = data.trim();
          }
        }
        const error = new Error(errorMessage);
        error.status = response.status;
        error.data = data;
        throw error;
      }

      return data;
    } catch (err) {
      // Network error, CORS preflight failure, or fetch abort
      if (!err.status) {
        const error = new Error('Unable to connect to DocuMedi server. Please check your network or ensure backend is running.');
        error.isNetworkError = true;
        throw error;
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

  /**
   * Downloads a clinical note PDF as a binary Blob and triggers browser file save.
   * Handles binary stream, safe filename extraction, and cleans up object URLs.
   */
  async downloadNotePdf(noteId, customFilename = null) {
    const url = this.buildUrl(`/notes/${noteId}/pdf`);
    const token = this.getToken();

    const headers = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers,
      });

      if (!response.ok) {
        let errorMessage = 'Failed to download clinical note PDF. Please try again.';
        try {
          const errData = await response.json();
          if (errData && errData.detail) {
            errorMessage = errData.detail;
          }
        } catch (_) {
          // Non-JSON error body fallback
        }
        const error = new Error(errorMessage);
        error.status = response.status;
        throw error;
      }

      // Extract filename from Content-Disposition header if available
      let filename = customFilename;
      if (!filename) {
        const disposition = response.headers.get('content-disposition');
        if (disposition && disposition.includes('filename=')) {
          const match = disposition.match(/filename=["']?([^"';]+)["']?/);
          if (match && match[1]) {
            filename = match[1].trim();
          }
        }
      }
      if (!filename) {
        filename = `DocuMedi_Report_Note_${noteId}.pdf`;
      }

      // Convert response to Blob
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);

      // Create temporary anchor to trigger browser download
      const link = document.createElement('a');
      link.href = blobUrl;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();

      // Cleanup DOM node and blob URL
      document.body.removeChild(link);
      setTimeout(() => {
        window.URL.revokeObjectURL(blobUrl);
      }, 200);

      return { success: true, filename };
    } catch (err) {
      if (!err.status) {
        throw new Error('Unable to connect to DocuMedi server to download PDF.');
      }
      throw err;
    }
  }
}


export const api = new ApiClient(API_BASE_URL);
export default api;

