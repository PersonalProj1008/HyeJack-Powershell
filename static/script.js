let currentTopic = null;
let topicOffset = 0;
let msgOffset = 0;
const limit = 20;
let loadingTopics = false;
let loadingMsgs = false;
let hasMoreMsgs = true;

// ────────────────────────────────────────────────
// 1. View Switching
document.getElementById("viewToggle").addEventListener("change", (e) => {
  const isVector = e.target.checked;
  document.getElementById("historyView").classList.toggle("active", !isVector);
  document.getElementById("vectorView").classList.toggle("active", isVector);
});

// ────────────────────────────────────────────────
// 2. Reload Buttons
document.getElementById("reloadTopicsBtn").addEventListener("click", () => {
  topicOffset = 0;
  document.getElementById("topicsContainer").innerHTML = "";
  loadTopics();
});

document.getElementById("loadPrevConvBtn").addEventListener("click", () => {
  if (!currentTopic) return;
  msgOffset = 0;
  hasMoreMsgs = true;
  document.getElementById("messagesContainer").innerHTML = "";
  loadMessages(true);
});

// ────────────────────────────────────────────────
// 3. Load Topics
async function loadTopics() {
  if (loadingTopics) return;
  loadingTopics = true;
  try {
    const r = await fetch(`/api/topics?offset=${topicOffset}&limit=${limit}`);
    if (!r.ok) throw new Error("Failed to load topics");
    const data = await r.json();

    const container = document.getElementById("topicsContainer");
    data.forEach((t) => {
      const div = document.createElement("div");
      div.className = "topic-item";
      div.textContent = t.topic_name;
      div.onclick = () => selectTopic(t.topic_name, div);
      container.appendChild(div);
    });

    if (data.length === limit) topicOffset += limit;
  } catch (err) {
    console.error(err);
  } finally {
    loadingTopics = false;
  }
}

// ────────────────────────────────────────────────
// 4. Select Topic
function selectTopic(name, el) {
  document
    .querySelectorAll(".topic-item")
    .forEach((i) => i.classList.remove("active"));
  el.classList.add("active");

  currentTopic = name;
  document.getElementById("currentTopicTitle").textContent = name;
  document.getElementById("chatHeader").style.display = "flex";

  msgOffset = 0;
  hasMoreMsgs = true;
  document.getElementById("messagesContainer").innerHTML = "";
  loadMessages(true);
}

// ────────────────────────────────────────────────
// 5. Render Message (main logic with null handling)
function renderMessage(m) {
  const div = document.createElement("div");
  div.className = `msg ${m.is_user ? "user" : "bot"}`;

  let contentHTML = "";
  const dt = new Date(m.datetime);
  const dateStr = dt.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
  const timeStr = dt.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  // Header with date & time
  contentHTML += `<div class="msg-header">${dateStr} • ${timeStr}</div>`;

  // Handle null/undefined content properly
  let raw = m.content;

  // If content is null, undefined, or empty string, don't display anything
  if (!raw || raw === null || raw === undefined || raw === "") {
    // Just show an empty message indicator
    contentHTML += `<div class="text-block plain" style="color: #888; font-style: italic;">[Empty message]</div>`;
    div.innerHTML = contentHTML;
    return div;
  }

  // Ensure raw is a string and trim it
  raw = String(raw).trim();

  // If after trimming it's empty
  if (raw === "") {
    contentHTML += `<div class="text-block plain" style="color: #888; font-style: italic;">[Empty message]</div>`;
    div.innerHTML = contentHTML;
    return div;
  }

  // Try to parse as structured JSON
  let isJson = false;
  let agentic = null;
  let info = null;

  if (raw.startsWith("{") && raw.endsWith("}")) {
    try {
      const parsed = JSON.parse(raw);
      agentic = parsed.Agentic_Data;
      // Development Stage Agentic_Data
      if (agentic && agentic.step) {
        agentic = agentic.step;
      }
      info = parsed.Info_Data;
      isJson = true;
    } catch (e) {
      // Not valid JSON, treat as plain text
      isJson = false;
    }
  }

  if (isJson) {
    // ── Agentic_Data section ─────────────────────────────
    if (agentic && Object.keys(agentic).length > 0) {
      contentHTML += `<div class="section agentic"><strong>AGENTIC WORKFLOW:</strong><ul>`;
      Object.values(agentic).forEach((step) => {
        if (step && step.step_name) {
          contentHTML += `<li>${escapeHtml(step.step_name)}</li>`;
        }
      });
      contentHTML += `</ul></div>`;
    }

    // ── Info_Data section ────────────────────────────────
    if (info && Object.keys(info).length > 0) {
      contentHTML += `<div class="section info"><strong>LLM REPLY:</strong>`;
      Object.values(info).forEach((item) => {
        if (item && item.type === "text" && item.value) {
          contentHTML += `<div class="text-block">${escapeHtml(item.value)}</div>`;
        } else if (item && item.type === "code" && item.value) {
          contentHTML += `
            <div class="code-wrapper">
              <button class="copy-btn" onclick="navigator.clipboard.writeText(this.nextElementSibling.textContent)">Copy</button>
              <pre><code class="language-python">${escapeHtml(item.value)}</code></pre>
            </div>`;
        }
      });
      contentHTML += `</div>`;
    }

    // If neither agentic nor info had content, show raw as plain text
    if (
      (!agentic || Object.keys(agentic).length === 0) &&
      (!info || Object.keys(info).length === 0)
    ) {
      contentHTML += `<div class="text-block plain">${escapeHtml(raw)}</div>`;
    }
  } else {
    // Plain text message
    contentHTML += `<div class="text-block plain">${escapeHtml(raw)}</div>`;
    contentHTML += `
      <div class="code-wrapper plain-copy">
        <button class="copy-btn" onclick="navigator.clipboard.writeText(this.closest('.msg').querySelector('.text-block').textContent)">Copy</button>
      </div>`;
  }

  div.innerHTML = contentHTML;
  return div;
}

function escapeHtml(unsafe) {
  if (!unsafe) return "";
  return String(unsafe)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ────────────────────────────────────────────────
// 6. Load Messages
async function loadMessages(initial = false) {
  if (!currentTopic || loadingMsgs || (!initial && !hasMoreMsgs)) return;
  loadingMsgs = true;

  const container = document.getElementById("messagesContainer");
  const chatWindow = document.getElementById("chatWindow");
  const prevHeight = chatWindow.scrollHeight;

  try {
    const r = await fetch(
      `/api/messages/${encodeURIComponent(currentTopic)}?offset=${msgOffset}&limit=${limit}`,
    );
    if (!r.ok) throw new Error("Failed to load messages");
    const data = await r.json();

    if (data.length < limit) hasMoreMsgs = false;

    // Reverse so oldest comes first when prepending
    data.reverse().forEach((m) => {
      const msgEl = renderMessage(m);
      container.prepend(msgEl);
    });

    if (data.length > 0) msgOffset += limit;

    // Scroll behavior
    if (initial) {
      chatWindow.scrollTop = chatWindow.scrollHeight;
    } else {
      chatWindow.scrollTop = chatWindow.scrollHeight - prevHeight;
    }
  } catch (err) {
    console.error(err);
  } finally {
    loadingMsgs = false;
  }
}

// ────────────────────────────────────────────────
// 7. Infinite Scroll
const topicObserver = new IntersectionObserver(
  (entries) => {
    if (entries[0].isIntersecting) loadTopics();
  },
  { threshold: 0.1 },
);

const chatObserver = new IntersectionObserver(
  (entries) => {
    if (entries[0].isIntersecting && currentTopic && !loadingMsgs) {
      loadMessages(false);
    }
  },
  { threshold: 0.1 },
);

// Safely observe elements with null checks
const topicSentinel = document.getElementById("topicSentinel");
const chatSentinel = document.getElementById("chatSentinel");

if (topicSentinel) {
  topicObserver.observe(topicSentinel);
}

if (chatSentinel) {
  chatObserver.observe(chatSentinel);
}

// Start
loadTopics();
