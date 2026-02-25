/**
 * API Client for Biometrics Attendance System
 */

// In production (Docker), API is served via nginx at /api
// In development, Vite proxy forwards /api → http://localhost:8000/api
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

// Store auth token
let authToken = null;

/**
 * Set authentication token
 */
function setAuthToken(token) {
    authToken = token;
}

/**
 * Make API request with error handling
 */
async function request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;

    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        },
    };

    // Add authentication header if token exists
    if (authToken) {
        defaultOptions.headers['Authorization'] = `Bearer ${authToken}`;
    }

    const config = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers,
        },
    };

    // Don't set Content-Type for FormData
    if (options.body instanceof FormData) {
        delete config.headers['Content-Type'];
    }

    try {
        const response = await fetch(url, config);

        // Handle 401 Unauthorized
        if (response.status === 401) {
            localStorage.removeItem('auth_token');
            localStorage.removeItem('auth_user');
            authToken = null;
            window.location.href = '/login';
            throw new Error('Unauthorized');
        }

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'An error occurred' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        // Handle CSV/file downloads
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('text/csv')) {
            return response.blob();
        }

        return response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

/**
 * API methods
 */
export const api = {
    // Set authentication token
    setAuthToken,

    // Authentication

    // Get auth config (Google Client ID etc.)
    getAuthConfig: () => request('/auth/config'),

    // Google OAuth login
    googleLogin: async (credential) => {
        const response = await request('/auth/google', {
            method: 'POST',
            body: JSON.stringify({ credential })
        });
        return response;
    },

    // Email login (password not validated per README)
    login: async (email, password) => {
        const response = await request('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password })
        });
        return response;
    },

    logout: () => request('/auth/logout', { method: 'POST' }),

    getCurrentUser: () => request('/auth/me'),

    // Employee Attendance (for employees)
    getEmployeeAttendance: (params = {}) => {
        const searchParams = new URLSearchParams(params);
        return request(`/employee/attendance?${searchParams}`);
    },

    getEmployeeWeeklyCompliance: (params = {}) => {
        const searchParams = new URLSearchParams(params);
        return request(`/employee/weekly-compliance?${searchParams}`);
    },

    // Dashboard
    getDashboardSummary: () => request('/reports/dashboard'),

    getDashboardStats: (params = {}) => {
        const searchParams = new URLSearchParams(params);
        return request(`/reports/dashboard-stats?${searchParams}`);
    },

    getDailyDetails: (params = {}) => {
        const searchParams = new URLSearchParams(params);
        return request(`/reports/daily-details?${searchParams}`);
    },

    getWeeklyComplianceStats: (params = {}) => {
        const searchParams = new URLSearchParams(params);
        return request(`/reports/weekly-compliance-stats?${searchParams}`);
    },

    // Settings
    getSettings: () => request('/settings'),

    updateSettings: (data) => request('/settings', {
        method: 'PUT',
        body: JSON.stringify(data)
    }),

    // Upload
    uploadFile: async (file) => {
        const formData = new FormData();
        formData.append('file', file);

        return request('/upload/', {
            method: 'POST',
            body: formData,
        });
    },

    // Employees
    getEmployees: (params = {}) => {
        const searchParams = new URLSearchParams(params);
        return request(`/employees/?${searchParams}`);
    },

    getEmployee: (code) => request(`/employees/${code}`),

    createEmployee: (data) => request('/employees/', {
        method: 'POST',
        body: JSON.stringify(data),
    }),

    updateEmployee: (code, data) => request(`/employees/${code}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    }),

    // Reports
    getAllEmployeesReport: (params = {}) => {
        const searchParams = new URLSearchParams(params);
        return request(`/reports/all-employees?${searchParams}`);
    },

    getIndividualReport: (code, params = {}) => {
        const searchParams = new URLSearchParams(params);
        return request(`/reports/individual/${code}?${searchParams}`);
    },

    getWFOComplianceReport: (params = {}) => {
        const searchParams = new URLSearchParams(params);
        return request(`/reports/wfo-compliance?${searchParams}`);
    },

    getAvailableWeeks: () => request('/reports/weeks'),

    // Monthly Report (Admin)
    getMonthlyReport: async (params = {}) => {
        const searchParams = new URLSearchParams();
        if (params.month) searchParams.set('month', params.month);
        if (params.search) searchParams.set('search', params.search);
        if (params.work_mode) searchParams.set('work_mode', params.work_mode);
        const res = await request(`/reports/monthly-report?${searchParams}`);

        // handle both cases safely
        if (!res) return [];
        if (Array.isArray(res)) return res;
        if (res.data) return res.data;

        return [];
    },

    exportMonthlyReportCSV: async (params = {}) => {
        const searchParams = new URLSearchParams();
        if (params.month) searchParams.set('month', params.month);
        if (params.work_mode) searchParams.set('work_mode', params.work_mode);

        const blob = await request(`/reports/monthly-report/export?${searchParams}`);

        let filename = "monthly_report.csv";

        if (params.month) {
            const [year, m] = params.month.split("-");
            const monthName = new Date(params.month + "-01")
                .toLocaleDateString("en-US", { month: "long" })
                .toLowerCase();
            const modeLabel = params.work_mode ? `_${params.work_mode.toLowerCase()}` : '';
            filename = `monthly_report${modeLabel}_${monthName}_${year}.csv`;
        }

        downloadBlob(blob, filename);
    },


    exportMonthlyIndividual: async (employeeCode, month) => {
        const blob = await request(`/reports/monthly-report/export/${employeeCode}?month=${month}`);
        downloadBlob(blob, `${employeeCode}_${month}_report.csv`);
    },
    // BU Head (Redmine integration)
    getBUHeads: () => request('/employees/bu-heads/list'),

    getEmployeesWithProjectBU: () => request('/employees/with-project-bu'),

    getEmployeesByBUHead: (buHead) => {
        const searchParams = new URLSearchParams({ bu_head: buHead });
        return request(`/employees/by-bu-head?${searchParams}`);
    },

    // Exports
    exportAllEmployees: async (filters = {}) => {
        const searchParams = new URLSearchParams();
        if (filters.week_start) searchParams.set('week_start', filters.week_start);
        if (filters.work_mode) searchParams.set('work_mode', filters.work_mode);
        if (filters.status_filter) searchParams.set('status_filter', filters.status_filter);
        if (filters.sort_by) searchParams.set('sort_by', filters.sort_by);
        if (filters.sort_order) searchParams.set('sort_order', filters.sort_order);
        const qs = searchParams.toString();
        const blob = await request(`/reports/export/all-employees${qs ? `?${qs}` : ''}`);
        downloadBlob(blob, 'all_employees_report.csv');
    },

    exportWFOCompliance: async (weekStart) => {
        const params = weekStart ? `?week_start=${weekStart}` : '';
        const blob = await request(`/reports/export/wfo-compliance${params}`);
        downloadBlob(blob, 'wfo_compliance_report.csv');
    },

    exportIndividual: async (code, params = {}) => {
        const searchParams = new URLSearchParams(params);
        const blob = await request(`/reports/export/individual/${code}?${searchParams}`);
        downloadBlob(blob, `${code}_report.csv`);
    },
};

/**
 * Download blob as file
 */
function downloadBlob(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

export default api;
