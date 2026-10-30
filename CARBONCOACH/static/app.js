/**
 * Carbon Coach Frontend Controller
 * Manages chat interactions, tool trace inspection, live metrics,
 * campus leaderboard, and real-time golden evals.
 */

let currentSessionId = localStorage.getItem("carbon_coach_session") || "session_" + Math.random().toString(36).substring(2, 9);
localStorage.setItem("carbon_coach_session", currentSessionId);

let currentLanguage = "en";
let toolCallHistory = [];

document.addEventListener("DOMContentLoaded", () => {
  initLanguageSelector();
  initTabs();
  initChat();
  initTraceCollapsible();
  initQuickPrompts();
  initEvals();
  initResetSession();
  initApiKeyModal();
  checkApiKeyStatus();

  // Initial dashboard load
  refreshDashboard();
  loadLeaderboard();
  loadReductions();
});

// 1. Language Selector
function initLanguageSelector() {
  const buttons = document.querySelectorAll(".lang-btn");
  buttons.forEach(btn => {
    btn.addEventListener("click", () => {
      buttons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentLanguage = btn.getAttribute("data-lang");
    });
  });
}

// 2. Tabs Navigation
function initTabs() {
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      tabButtons.forEach(b => b.classList.remove("active"));
      tabPanes.forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      const targetPane = document.getElementById(targetId);
      if (targetPane) {
        targetPane.classList.add("active");
      }

      if (targetId === "tab-campus") {
        loadLeaderboard();
      } else if (targetId === "tab-reductions") {
        loadReductions();
      }
    });
  });
}

// 3. Chat System
function initChat() {
  const chatForm = document.getElementById("chatForm");
  const chatInput = document.getElementById("chatInput");

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    appendUserMessage(message);
    chatInput.value = "";
    chatInput.focus();

    // Show bot typing indicator
    const typingMsg = appendTypingIndicator();

    try {
      const storedApiKey = localStorage.getItem("carbon_coach_gemini_key") || "";
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: message,
          session_id: currentSessionId,
          language: currentLanguage,
          api_key: storedApiKey
        })
      });

      const data = await response.json();
      removeTypingIndicator(typingMsg);

      appendBotMessage(data.reply);
      recordToolCalls(data.tool_calls);
      updateDashboardWithSummary(data.summary);
      loadRecentActivities();
      loadReductions();
    } catch (err) {
      removeTypingIndicator(typingMsg);
      appendBotMessage("⚠️ Error communicating with agent server. Please make sure the service is running.");
      console.error(err);
    }
  });
}

function appendUserMessage(text) {
  const container = document.getElementById("chatMessages");
  const msgDiv = document.createElement("div");
  msgDiv.className = "message user-message";
  msgDiv.innerHTML = `
    <div class="avatar">👤</div>
    <div class="message-content">
      <p>${escapeHtml(text)}</p>
    </div>
  `;
  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;
}

function appendBotMessage(markdownText) {
  const container = document.getElementById("chatMessages");
  const msgDiv = document.createElement("div");
  msgDiv.className = "message bot-message";
  msgDiv.innerHTML = `
    <div class="avatar">🌱</div>
    <div class="message-content">
      ${formatSimpleMarkdown(markdownText)}
    </div>
  `;
  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;
}

function appendTypingIndicator() {
  const container = document.getElementById("chatMessages");
  const msgDiv = document.createElement("div");
  msgDiv.className = "message bot-message typing-indicator-msg";
  msgDiv.innerHTML = `
    <div class="avatar">🌱</div>
    <div class="message-content">
      <p><em>Calculating emissions via Google ADK tools...</em></p>
    </div>
  `;
  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;
  return msgDiv;
}

function removeTypingIndicator(elem) {
  if (elem && elem.parentNode) {
    elem.parentNode.removeChild(elem);
  }
}

// 4. Tool Execution Trace Inspector
function recordToolCalls(toolCalls) {
  if (!toolCalls || !toolCalls.length) return;
  toolCallHistory.push(...toolCalls);

  const badge = document.getElementById("toolCountBadge");
  badge.textContent = `${toolCallHistory.length} call${toolCallHistory.length === 1 ? '' : 's'}`;

  const traceLogs = document.getElementById("traceLogs");
  // Remove empty placeholder
  const emptyElem = traceLogs.querySelector(".empty-trace");
  if (emptyElem) emptyElem.remove();

  toolCalls.forEach(call => {
    const entry = document.createElement("div");
    entry.className = "trace-entry";
    entry.innerHTML = `
      <div class="trace-top-line">
        <span class="trace-agent-tag">[${call.agent || 'agent'}]</span>
        <span class="trace-tool-name">${call.tool}()</span>
        <span style="color: #64748b; font-size: 10.5px;">${new Date().toLocaleTimeString()}</span>
      </div>
      <div class="trace-args"><strong>args:</strong> ${JSON.stringify(call.args)}</div>
      <div class="trace-output"><strong>result:</strong> ${JSON.stringify(call.output)}</div>
    `;
    traceLogs.prepend(entry);
  });
}

function initTraceCollapsible() {
  const header = document.getElementById("traceHeader");
  const body = document.getElementById("traceBody");
  const arrow = document.getElementById("traceArrow");

  header.addEventListener("click", () => {
    if (body.style.display === "none") {
      body.style.display = "flex";
      arrow.textContent = "▼";
    } else {
      body.style.display = "none";
      arrow.textContent = "▶";
    }
  });
}

// 5. Quick Prompts
function initQuickPrompts() {
  const chips = document.querySelectorAll(".prompt-chip");
  const chatInput = document.getElementById("chatInput");
  const chatForm = document.getElementById("chatForm");

  chips.forEach(chip => {
    chip.addEventListener("click", () => {
      const text = chip.getAttribute("data-text");
      chatInput.value = text;
      chatForm.dispatchEvent(new Event("submit"));
    });
  });
}

// 6. Dashboard Updates & Summary
async function refreshDashboard() {
  try {
    const res = await fetch(`/api/summary?session_id=${currentSessionId}`);
    const summary = await res.json();
    updateDashboardWithSummary(summary);
    loadRecentActivities();
  } catch (e) {
    console.error("Failed to load summary", e);
  }
}

function updateDashboardWithSummary(summary) {
  if (!summary) return;
  const total = summary.total_emissions_kg_co2e || 0.0;
  const totalElem = document.getElementById("totalEmissions");
  totalElem.textContent = total.toFixed(2);

  const countElem = document.getElementById("activityCount");
  countElem.textContent = summary.activity_count || 0;

  const targetBadge = document.getElementById("targetBadge");
  const target = 3.5;
  if (total <= target) {
    targetBadge.textContent = "On Track 🌱";
    targetBadge.style.color = "#34d399";
    targetBadge.style.background = "rgba(16, 185, 129, 0.15)";
  } else if (total <= 5.0) {
    targetBadge.textContent = "Moderate ⚠️";
    targetBadge.style.color = "#fbbf24";
    targetBadge.style.background = "rgba(251, 191, 36, 0.15)";
  } else {
    targetBadge.textContent = "High Footprint 🔴";
    targetBadge.style.color = "#f87171";
    targetBadge.style.background = "rgba(239, 68, 68, 0.15)";
  }

  // Benchmark progress
  const userText = document.getElementById("userFootprintText");
  const userProgress = document.getElementById("userProgress");
  userText.textContent = `${total.toFixed(2)} kg`;
  const maxBenchmark = 12.8; // Global average
  const pct = Math.min(100, Math.round((total / maxBenchmark) * 100));
  userProgress.style.width = `${pct}%`;

  // Categories
  const breakdown = summary.category_breakdown || {};
  document.getElementById("catTravelVal").textContent = `${(breakdown.travel ? breakdown.travel.total_kg : 0).toFixed(2)} kg`;
  document.getElementById("catElecVal").textContent = `${(breakdown.electricity ? breakdown.electricity.total_kg : 0).toFixed(2)} kg`;
  document.getElementById("catFoodVal").textContent = `${(breakdown.food ? breakdown.food.total_kg : 0).toFixed(2)} kg`;
  document.getElementById("catWasteVal").textContent = `${(breakdown.waste ? breakdown.waste.total_kg : 0).toFixed(2)} kg`;
}

// 7. Recent Activities Ledger
async function loadRecentActivities() {
  try {
    const res = await fetch(`/api/activities?session_id=${currentSessionId}`);
    const activities = await res.json();
    const tbody = document.getElementById("activityTableBody");
    tbody.innerHTML = "";

    if (!activities.length) {
      tbody.innerHTML = `<tr><td colspan="3" class="empty-table-cell">No activities logged yet in this session.</td></tr>`;
      return;
    }

    activities.forEach(item => {
      const tr = document.createElement("tr");
      const icon = item.category === "travel" ? "🚌" :
                   item.category === "electricity" ? "⚡" :
                   item.category === "food" ? "🥗" : "♻️";
      tr.innerHTML = `
        <td><span style="margin-right: 6px;">${icon}</span><strong>${item.category.toUpperCase()}</strong></td>
        <td>${escapeHtml(item.description)}</td>
        <td style="font-family: var(--font-mono); color: #34d399; font-weight: 700;">${item.emissions_kg} kg</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.error("Error loading activities", e);
  }
}

// 8. Actionable Reductions
async function loadReductions() {
  try {
    const res = await fetch(`/api/reductions?session_id=${currentSessionId}`);
    const data = await res.json();
    const badge = document.getElementById("potentialSavingsBadge");
    badge.textContent = `Potential: ${data.total_potential_weekly_savings_kg} kg/wk`;

    const container = document.getElementById("reductionCardsList");
    container.innerHTML = "";

    if (!data.recommendations || !data.recommendations.length) {
      container.innerHTML = `<div class="empty-trace">Log travel or electricity to see personalized suggestions!</div>`;
      return;
    }

    data.recommendations.forEach(rec => {
      const card = document.createElement("div");
      card.className = "reduction-item-card";
      card.innerHTML = `
        <div class="rec-header-row">
          <span class="rec-action-title">${rec.action}</span>
          <span class="rec-saving-pill">-${rec.weekly_saving_kg} kg CO₂e / wk</span>
        </div>
        <div class="rec-basis"><strong>Calculation Basis:</strong> ${rec.basis}</div>
        <div class="rec-meta-row">
          <span>🎯 Difficulty: <strong>${rec.difficulty}</strong></span>
          <span>💚 Co-benefit: ${rec.co_benefit}</span>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    console.error("Error loading reductions", e);
  }
}

// 9. Campus Leaderboard
async function loadLeaderboard() {
  try {
    const res = await fetch("/api/leaderboard");
    const data = await res.json();
    const tbody = document.getElementById("leaderboardBody");
    tbody.innerHTML = "";

    data.leaderboard.forEach(item => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong style="font-family: var(--font-mono); font-size: 14px;">#${item.rank}</strong></td>
        <td><strong>${item.name}</strong></td>
        <td><span class="badge-pill devfest-pill" style="font-size: 10px;">${item.type}</span></td>
        <td>${item.residents}</td>
        <td style="font-family: var(--font-mono); font-weight: 700; color: #38bdf8;">${item.current_daily_kg} kg</td>
        <td style="color: #34d399; font-weight: 700;">-${item.reduction_percentage}%</td>
        <td>${item.badge}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.error("Error loading leaderboard", e);
  }
}

// 10. Golden Evals Executor
function initEvals() {
  const btn = document.getElementById("runEvalsBtn");
  btn.addEventListener("click", async () => {
    btn.textContent = "⏳ Running Evals...";
    btn.disabled = true;

    try {
      const res = await fetch("/api/evals/run");
      const result = await res.json();
      btn.textContent = "▶ Re-run Live Evals";
      btn.disabled = false;

      const banner = document.getElementById("evalsResultBanner");
      if (result.status === "passed") {
        banner.className = "evals-banner passed";
        banner.innerHTML = `
          <div class="evals-banner-title">✅ ALL ${result.tests_run} GOLDEN EVALS PASSED (0 Failures, 0 Hallucinations)</div>
          <div>All calculations matched DEFRA 2023, CEA India Baseline v19, and Science 2018 benchmark figures exactly.</div>
        `;
      } else {
        banner.className = "evals-banner failed";
        banner.innerHTML = `
          <div class="evals-banner-title">❌ Evals Failed: ${result.failures_count} failures</div>
        `;
      }
    } catch (e) {
      btn.textContent = "▶ Run Live Evals";
      btn.disabled = false;
      console.error("Evals failed", e);
    }
  });
}

// 11. Session Reset
function initResetSession() {
  const btn = document.getElementById("resetSessionBtn");
  btn.addEventListener("click", async () => {
    if (confirm("Reset current session activities?")) {
      await fetch(`/api/reset?session_id=${currentSessionId}`, { method: "POST" });
      currentSessionId = "session_" + Math.random().toString(36).substring(2, 9);
      localStorage.setItem("carbon_coach_session", currentSessionId);
      toolCallHistory = [];
      document.getElementById("toolCountBadge").textContent = "0 calls";
      document.getElementById("traceLogs").innerHTML = `<div class="empty-trace">Waiting for activities... Try sending a message above!</div>`;
      document.getElementById("chatMessages").innerHTML = `
        <div class="message bot-message">
          <div class="avatar">🌱</div>
          <div class="message-content">
            <p>Session reset! I am ready to measure your day's carbon footprint.</p>
          </div>
        </div>
      `;
      refreshDashboard();
      loadReductions();
    }
  });
}

// Helper: Escape HTML
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Helper: Simple Markdown Formatter
function formatSimpleMarkdown(text) {
  if (!text) return "";
  let html = text
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^#### (.*$)/gim, '<h4>$1</h4>')
    .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/gim, '<em>$1</em>')
    .replace(/^- (.*$)/gim, '<li>$1</li>');

  // Wrap loose <li> in <ul>
  html = html.replace(/(<li>.*<\/li>)/gims, '<ul>$1</ul>');
  // Format linebreaks into paragraphs
  const paras = html.split('\n\n');
  return paras.map(p => {
    if (p.startsWith('<h3>') || p.startsWith('<h4>') || p.startsWith('<ul>')) return p;
    return `<p>${p.replace(/\n/g, '<br>')}</p>`;
  }).join('');
}


// 12. Gemini API Key Modal Management
function initApiKeyModal() {
  const modal = document.getElementById("apiKeyModal");
  const openBtn = document.getElementById("apiKeyModalBtn");
  const closeBtn = document.getElementById("closeApiKeyModal");
  const saveBtn = document.getElementById("saveApiKeyBtn");
  const clearBtn = document.getElementById("clearApiKeyBtn");
  const input = document.getElementById("apiKeyInput");
  const feedback = document.getElementById("apiKeyFeedback");

  if (!modal || !openBtn) return;

  openBtn.addEventListener("click", () => {
    modal.style.display = "flex";
    input.value = localStorage.getItem("carbon_coach_gemini_key") || "";
    feedback.textContent = "";
    input.focus();
  });

  closeBtn.addEventListener("click", () => {
    modal.style.display = "none";
  });

  window.addEventListener("click", (e) => {
    if (e.target === modal) modal.style.display = "none";
  });

  saveBtn.addEventListener("click", async () => {
    const key = input.value.trim();
    if (!key) {
      feedback.className = "api-feedback error";
      feedback.textContent = "Please enter a valid Gemini API key.";
      return;
    }

    feedback.className = "api-feedback";
    feedback.textContent = "Saving key...";

    try {
      const res = await fetch("/api/save_api_key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: key })
      });
      const data = await res.json();
      if (res.ok) {
        localStorage.setItem("carbon_coach_gemini_key", key);
        feedback.className = "api-feedback success";
        feedback.textContent = "✅ Gemini API Key saved & activated!";
        updateApiKeyBadge(true);
        setTimeout(() => { modal.style.display = "none"; }, 1200);
      } else {
        feedback.className = "api-feedback error";
        feedback.textContent = data.message || "Failed to save API key.";
      }
    } catch (e) {
      feedback.className = "api-feedback error";
      feedback.textContent = "Error saving key to server.";
    }
  });

  clearBtn.addEventListener("click", () => {
    localStorage.removeItem("carbon_coach_gemini_key");
    input.value = "";
    feedback.className = "api-feedback success";
    feedback.textContent = "Switched to fast offline tool mode.";
    updateApiKeyBadge(false);
    setTimeout(() => { modal.style.display = "none"; }, 1000);
  });
}

async function checkApiKeyStatus() {
  try {
    const res = await fetch("/api/get_api_key_status");
    const data = await res.json();
    const hasLocal = !!localStorage.getItem("carbon_coach_gemini_key");
    if (data.has_api_key || hasLocal) {
      updateApiKeyBadge(true);
    } else {
      updateApiKeyBadge(false);
    }
  } catch (e) {
    updateApiKeyBadge(false);
  }
}

function updateApiKeyBadge(isActive) {
  const label = document.getElementById("apiKeyBtnLabel");
  const btn = document.getElementById("apiKeyModalBtn");
  if (!label || !btn) return;

  if (isActive) {
    label.textContent = "Gemini Live 🟢";
    btn.classList.add("active-key");
  } else {
    label.textContent = "Set API Key";
    btn.classList.remove("active-key");
  }
}
