// script.js
// Handles the form submission, calls the Page Pulse backend API,
// and renders loading / error / report states.

// Change this if your backend runs on a different host/port.
const API_BASE_URL = "https://page-pulse-1ni2.onrender.com";

const form = document.getElementById("audit-form");
const urlInput = document.getElementById("url-input");
const auditButton = document.getElementById("audit-button");
const statusArea = document.getElementById("status-area");
const reportArea = document.getElementById("report-area");

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const url = urlInput.value.trim();
  if (!url) {
    showError("Please enter a URL.");
    return;
  }

  await runAudit(url);
});

async function runAudit(url) {
  setLoading(true);
  clearStatus();
  clearReport();

  try {
    const response = await fetch(`${API_BASE_URL}/api/audit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error("Received an unexpected response from the server.");
    }

    if (!response.ok) {
      // FastAPI error responses look like { "detail": "..." }
      const message =
        (data && data.detail) || `Request failed with status ${response.status}.`;
      showError(message);
      return;
    }

    renderReport(data);
  } catch (err) {
    // Network-level failure: backend unreachable, CORS issue, etc.
    if (err instanceof TypeError) {
      showError(
        "Could not reach the Page Pulse backend. Make sure the server is running."
      );
    } else {
      showError(err.message || "Something went wrong. Please try again.");
    }
  } finally {
    setLoading(false);
  }
}

function setLoading(isLoading) {
  auditButton.disabled = isLoading;
  auditButton.textContent = isLoading ? "Auditing..." : "Audit";
  if (isLoading) {
    statusArea.innerHTML = `<p class="status-loading">Fetching and analyzing the page...</p>`;
  }
}

function clearStatus() {
  statusArea.innerHTML = "";
}

function clearReport() {
  reportArea.innerHTML = "";
}

function showError(message) {
  statusArea.innerHTML = `<div class="status-error">${escapeHtml(message)}</div>`;
}

function renderReport(data) {
  clearStatus();

  const title = data.title ?? null;
  const metaDescription = data.meta_description ?? null;

  reportArea.innerHTML = `
    <div class="report-card">
      <h2>${escapeHtml(data.url)}</h2>
      <div class="metric-grid">
        <div class="metric">
          <div class="metric-label">HTTP Status</div>
          <div class="metric-value ${data.http_status < 400 ? "ok" : "warn"}">${data.http_status}</div>
        </div>
        <div class="metric">
          <div class="metric-label">Response Time</div>
          <div class="metric-value">${data.response_time_ms} ms</div>
        </div>
        <div class="metric full-width">
          <div class="metric-label">Page Title</div>
          <div class="metric-value ${title ? "" : "missing"}">${
            title ? escapeHtml(title) : "Missing"
          }</div>
        </div>
        <div class="metric full-width">
          <div class="metric-label">Meta Description</div>
          <div class="metric-value ${metaDescription ? "" : "missing"}">${
            metaDescription ? escapeHtml(metaDescription) : "Missing"
          }</div>
        </div>
        <div class="metric">
          <div class="metric-label">H1 Count</div>
          <div class="metric-value ${data.h1_count === 1 ? "ok" : "warn"}">${data.h1_count}</div>
        </div>
        <div class="metric">
          <div class="metric-label">Images Missing Alt</div>
          <div class="metric-value ${data.images_missing_alt === 0 ? "ok" : "warn"}">${
            data.images_missing_alt
          }</div>
        </div>
        <div class="metric full-width">
          <div class="metric-label">Word Count</div>
          <div class="metric-value">${data.word_count}</div>
        </div>
      </div>
    </div>
  `;
}

// Basic HTML-escaping so page content (titles, descriptions, URLs)
// can never inject markup into our own page.
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
