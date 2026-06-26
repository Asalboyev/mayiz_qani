const API_BASE = "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || "Server xatosi");
  }

  return data;
}

async function uploadRequest(path, formData) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: formData,
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || "Server xatosi");
  }

  return data;
}

export const api = {
  base: API_BASE,

  health() {
    return request("/health");
  },

  loginOperator(username, password) {
    return request("/auth/operator-login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  },

  getAlerts() {
    return request("/alerts");
  },

  createDemoAlert() {
    return request("/alerts/demo", {
      method: "POST",
    });
  },

  updateAlertStatus(alertId, status, reviewNote = "", reviewedBy = "admin") {
    return request(`/alerts/${alertId}/status`, {
      method: "PATCH",
      body: JSON.stringify({
        status,
        reviewed_by: reviewedBy,
        review_note: reviewNote,
      }),
    });
  },

  getCitizenReports() {
    return request("/citizen/reports");
  },

  createCitizenReport(payload) {
    return request("/citizen/reports", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  createCitizenReportWithEvidence(formData) {
    return uploadRequest("/citizen/reports/upload", formData);
  },

  updateCitizenReportStatus(reportId, status, reviewNote = "", reviewedBy = "admin") {
    return request(`/citizen/reports/${reportId}/status`, {
      method: "PATCH",
      body: JSON.stringify({
        status,
        reviewed_by: reviewedBy,
        review_note: reviewNote,
      }),
    });
  },

  getAuditLogs() {
    return request("/audit/logs");
  },
  registerCitizen(payload) {
  return request("/citizens/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
},

loginCitizen(phone) {
  return request("/citizens/login", {
    method: "POST",
    body: JSON.stringify({ phone }),
  });
},
};