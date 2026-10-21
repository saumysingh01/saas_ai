/* ── MarketMind AI — Dashboard App Logic ── */

const SUPABASE_URL = "https://zyvpaoggezsxkincafud.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp5dnBhb2dnZXpzeGtpbmNhZnVkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTIyNTcyMDAsImV4cCI6MjEwNzgzMzIwMH0.3UhD-9dZCO2mzJiJKkZwxFIvEB2fBmZJznkwrnPkuMc";
const API_BASE = "http://localhost:8000/api/v1";

const { createClient } = window.supabase;
const sb = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  session: null,
  user: null,
  reports: [],
  usage: { reports_this_month: 0, limit: 5, plan: "free" },
  activeJobs: new Map(),   // job_id → job object
  pollInterval: null,
  currentPage: "dashboard",
  viewingReport: null,
};

// ── Supabase auth ─────────────────────────────────────────────────────────────
async function initAuth() {
  const { data: { session } } = await sb.auth.getSession();
  if (!session) {
    window.location.href = "landing.html";
    return false;
  }
  state.session = session;
  state.user = session.user;
  document.getElementById("user-email").textContent = state.user.email;
  return true;
}

async function logout() {
  await sb.auth.signOut();
  window.location.href = "landing.html";
}

// ── API fetch wrapper ─────────────────────────────────────────────────────────
async function api(path, options = {}) {
  const { data: { session } } = await sb.auth.getSession();
  if (!session) { window.location.href = "landing.html"; return; }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
      ...(options.headers || {}),
    },
  });

  if (res.status === 401) { await logout(); return; }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.detail || `Request failed: ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function toast(msg, type = "info") {
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  document.getElementById("toast-container").appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

// ── Navigation ─────────────────────────────────────────────────────────────────
function navigate(page) {
  state.currentPage = page;
  document.querySelectorAll(".nav-item").forEach(el => {
    el.classList.toggle("active", el.dataset.page === page);
  });
  document.querySelectorAll(".page").forEach(el => {
    el.classList.toggle("hidden", el.id !== `page-${page}`);
  });
  if (page === "dashboard") renderDashboard();
  if (page === "reports")   renderReports();
  if (page === "billing")   renderBilling();
}

// ── Load initial data ─────────────────────────────────────────────────────────
async function loadData() {
  try {
    const [reports, usage, jobs] = await Promise.all([
      api("/reports"),
      api("/usage"),
      api("/jobs"),
    ]);
    state.reports = reports || [];
    state.usage   = usage  || state.usage;

    // Restore any jobs that were queued or running before the page was refreshed.
    // 'done' and 'failed' jobs are historical — no need to resume polling for them.
    const activeStatuses = new Set(["queued", "running"]);
    for (const job of (jobs || [])) {
      if (activeStatuses.has(job.status)) {
        state.activeJobs.set(job.job_id, job);
      }
    }
    if (state.activeJobs.size > 0) {
      startPolling();
    }

    updateUsageBadge();
    renderDashboard();
  } catch (e) {
    toast("Failed to load data: " + e.message, "error");
  }
}

function updateUsageBadge() {
  const el = document.getElementById("usage-badge");
  const { reports_this_month: used, limit } = state.usage;
  el.textContent = `${used}/${limit} reports`;
  el.style.background = used >= limit ? "#fee2e2" : "";
  el.style.color       = used >= limit ? "#991b1b" : "";
}

// ── Dashboard page ────────────────────────────────────────────────────────────
function renderDashboard() {
  // Recent 3 reports
  const recentEl = document.getElementById("recent-reports");
  if (state.reports.length === 0) {
    recentEl.innerHTML = `<p class="text-muted text-sm" style="padding:.5rem 0">No reports yet — run your first analysis above.</p>`;
  } else {
    recentEl.innerHTML = state.reports.slice(0, 5).map(r => reportCard(r, "compact")).join("");
  }

  // Active jobs
  renderActiveJobs();
}

function renderActiveJobs() {
  const el = document.getElementById("active-jobs");
  if (state.activeJobs.size === 0) { el.innerHTML = ""; return; }
  el.innerHTML = Array.from(state.activeJobs.values()).map(job => `
    <div class="job-card card" style="margin-bottom:.75rem">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem">
        <strong style="font-size:.9rem">${escHtml(job.market_topic)}</strong>
        <span class="badge badge-${job.status}">${statusIcon(job.status)} ${job.status}</span>
      </div>
      ${job.status === 'running' ? `
        <div class="progress-bar-wrap">
          <div class="progress-bar-fill" style="width:60%;animation:progress-pulse 2s infinite"></div>
        </div>
        <p class="text-xs text-muted mt-1">Agents are researching the web and writing your report…</p>
      ` : ''}
      ${job.status === 'queued' ? `<p class="text-xs text-muted">Queued — starting shortly…</p>` : ''}
      ${job.status === 'failed' ? `<p class="text-xs" style="color:var(--danger)">${escHtml(job.error || 'Unknown error')}</p>` : ''}
    </div>
  `).join("");
}

// ── Reports page ──────────────────────────────────────────────────────────────
function renderReports() {
  const el = document.getElementById("reports-list");
  if (state.reports.length === 0) {
    el.innerHTML = `<div class="card" style="text-align:center;padding:3rem">
      <p style="font-size:2rem">📊</p>
      <p class="text-muted mt-2">No reports yet. Go to Dashboard to run your first analysis.</p>
    </div>`;
    return;
  }
  el.innerHTML = state.reports.map(r => reportCard(r, "full")).join("");
}

function reportCard(r, mode) {
  const date = new Date(r.created_at).toLocaleDateString("en-IN", { day:"numeric", month:"short", year:"numeric" });
  if (mode === "compact") {
    return `<div class="report-row" onclick="viewReport('${r.id}')">
      <div>
        <div style="font-weight:600;font-size:.9rem">${escHtml(r.market_topic)}</div>
        <div class="text-xs text-muted">${date}</div>
      </div>
      <div style="display:flex;gap:.4rem;flex-shrink:0">
        <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();downloadPdf('${r.id}','${escHtml(r.market_topic)}')">📄 PDF</button>
        <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();shareReport('${r.id}')">🔗 Share</button>
      </div>
    </div>`;
  }
  return `<div class="card" style="margin-bottom:1rem">
    <div class="card-header">
      <div>
        <div class="card-title">${escHtml(r.market_topic)}</div>
        <div class="text-xs text-muted">${date}</div>
      </div>
      <div style="display:flex;gap:.5rem">
        <button class="btn btn-outline btn-sm" onclick="downloadPdf('${r.id}','${escHtml(r.market_topic)}')">📄 Download PDF</button>
        <button class="btn btn-ghost btn-sm" onclick="shareReport('${r.id}')">🔗 Share</button>
        <button class="btn btn-primary btn-sm" onclick="viewReport('${r.id}')">View →</button>
      </div>
    </div>
  </div>`;
}

// ── Billing page ──────────────────────────────────────────────────────────────
function renderBilling() {
  const { reports_this_month: used, limit, plan } = state.usage;
  const pct = Math.min((used / limit) * 100, 100);
  document.getElementById("billing-plan").textContent = plan.charAt(0).toUpperCase() + plan.slice(1);
  document.getElementById("billing-used").textContent = used;
  document.getElementById("billing-limit").textContent = limit;
  document.getElementById("billing-progress").style.width = pct + "%";
  document.getElementById("billing-progress").style.background = used >= limit ? "var(--danger)" : "var(--primary)";
}

// ── View a report ─────────────────────────────────────────────────────────────
async function viewReport(reportId) {
  try {
    const r = await api(`/reports/${reportId}`);
    state.viewingReport = r;
    document.getElementById("report-modal-title").textContent = r.market_topic;
    document.getElementById("report-modal-body").innerHTML =
      DOMPurify.sanitize(marked.parse(r.generated_report));
    document.getElementById("report-modal-pdf").onclick   = () => downloadPdf(r.report_id, r.market_topic);
    document.getElementById("report-modal-share").onclick = () => shareReport(r.report_id);
    document.getElementById("report-modal").classList.remove("hidden");
  } catch (e) {
    toast("Could not load report: " + e.message, "error");
  }
}

function closeReportModal() {
  document.getElementById("report-modal").classList.add("hidden");
  state.viewingReport = null;
}

// ── Submit analysis job ───────────────────────────────────────────────────────
async function submitJob() {
  const topicEl = document.getElementById("topic-input");
  const topic = topicEl.value.trim();
  if (!topic) { topicEl.focus(); return; }

  const { reports_this_month: used, limit } = state.usage;
  if (used >= limit) {
    document.getElementById("upgrade-modal").classList.remove("hidden");
    return;
  }

  const btn = document.getElementById("run-btn");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Submitting…`;

  try {
    const job = await api("/jobs", {
      method: "POST",
      body: JSON.stringify({ market_topic: topic }),
    });

    topicEl.value = "";
    state.activeJobs.set(job.job_id, job);
    renderActiveJobs();
    startPolling();
    toast("Analysis started! Agents are working…", "info");
  } catch (e) {
    if (e.status === 402) {
      document.getElementById("upgrade-modal").classList.remove("hidden");
    } else {
      toast("Failed to start analysis: " + e.message, "error");
    }
  } finally {
    btn.disabled = false;
    btn.innerHTML = `▶ Run Analysis`;
  }
}

// ── Job polling ───────────────────────────────────────────────────────────────
function startPolling() {
  if (state.pollInterval) return;
  state.pollInterval = setInterval(pollJobs, 5000);
}

function stopPolling() {
  if (state.pollInterval) { clearInterval(state.pollInterval); state.pollInterval = null; }
}

async function pollJobs() {
  if (state.activeJobs.size === 0) { stopPolling(); return; }

  const toRemove = [];
  for (const [jobId] of state.activeJobs) {
    try {
      const job = await api(`/jobs/${jobId}`);
      state.activeJobs.set(jobId, job);

      if (job.status === "done") {
        toRemove.push(jobId);
        toast(`✓ Report ready: "${job.market_topic}"`, "success");
        // Reload reports and usage
        const [reports, usage] = await Promise.all([api("/reports"), api("/usage")]);
        state.reports = reports || state.reports;
        state.usage   = usage  || state.usage;
        updateUsageBadge();
        if (state.currentPage === "reports") renderReports();
      } else if (job.status === "failed") {
        toRemove.push(jobId);
        toast(`Analysis failed: ${job.error || "Unknown error"}`, "error");
      }
    } catch (_) { /* ignore transient poll errors */ }
  }

  toRemove.forEach(id => state.activeJobs.delete(id));
  renderActiveJobs();
  renderDashboard();
  if (state.activeJobs.size === 0) stopPolling();
}

// ── PDF download ──────────────────────────────────────────────────────────────
async function downloadPdf(reportId, topic) {
  toast("Generating PDF…", "info");
  try {
    const { data: { session } } = await sb.auth.getSession();
    const res = await fetch(`${API_BASE}/reports/${reportId}/pdf`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    });
    if (!res.ok) throw new Error("PDF generation failed");
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = Object.assign(document.createElement("a"), {
      href: url,
      download: (topic || "report").replace(/\s+/g, "_").slice(0, 50) + ".pdf",
    });
    a.click();
    URL.revokeObjectURL(url);
    toast("PDF downloaded!", "success");
  } catch (e) {
    toast("PDF failed: " + e.message, "error");
  }
}

// ── Share report ──────────────────────────────────────────────────────────────
async function shareReport(reportId) {
  try {
    const data = await api(`/reports/${reportId}/share`, { method: "POST" });
    await navigator.clipboard.writeText(data.share_url).catch(() => {});
    document.getElementById("share-url-input").value = data.share_url;
    document.getElementById("share-modal").classList.remove("hidden");
  } catch (e) {
    toast("Could not create share link: " + e.message, "error");
  }
}

function copyShareUrl() {
  const val = document.getElementById("share-url-input").value;
  navigator.clipboard.writeText(val).then(() => toast("Link copied!", "success"));
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function statusIcon(s) {
  return { queued:"🕐", running:"⚡", done:"✓", failed:"✗" }[s] || "";
}

// ── Init ──────────────────────────────────────────────────────────────────────
(async () => {
  const ok = await initAuth();
  if (!ok) return;
  await loadData();
  navigate("dashboard");

  // Allow Enter to submit
  document.getElementById("topic-input").addEventListener("keydown", e => {
    if (e.key === "Enter") submitJob();
  });
})();
