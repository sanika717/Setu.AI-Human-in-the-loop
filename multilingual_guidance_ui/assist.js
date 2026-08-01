/* ============================================================================
 * assist.js — SAHAAY.AI Human Assistance (DEMO ONLY).
 *
 * This is a demo workflow: it simulates a support officer joining a citizen's
 * session, sending guidance, and taking/returning control, using localStorage
 * as a shared "bus" between browser tabs on the same origin (open the app in
 * a second tab to play the officer). There is NO screen sharing, remote
 * desktop, WebRTC, or actual browser control here — "Take Control" only
 * flips a status label and hands the citizen a "Return Control" button.
 * No backend call is made anywhere in this file; nothing here touches
 * app.js, app-ui.js, or any microservice.
 *
 * Load order: app.js, then app-ui.js, then this file — so every element this
 * file reaches for already exists in the DOM and every page/nav/i18n hook
 * app-ui.js set up is already running.
 * ==========================================================================*/

(function () {
  "use strict";

  const STORE_KEY = "sahaay_assist_demo_v1";
  const MY_REQUEST_KEY = "sahaay_assist_my_request_id"; // sessionStorage: per-tab "who am I" for the citizen side
  const OFFICER_NAME_KEY = "sahaay_assist_officer_name";

  /* ------------------------------------------------------------------ */
  /* Store — localStorage-backed, shared across tabs on this origin.     */
  /* ------------------------------------------------------------------ */

  function loadStore() {
    try {
      const raw = localStorage.getItem(STORE_KEY);
      return raw ? JSON.parse(raw) : { requests: [] };
    } catch (error) {
      return { requests: [] };
    }
  }

  function saveStore(store) {
    localStorage.setItem(STORE_KEY, JSON.stringify(store));
    // localStorage's own "storage" event only fires in *other* tabs, not this
    // one, so dispatch a custom event to refresh this tab's own UI too.
    window.dispatchEvent(new CustomEvent("sahaay-assist-update"));
  }

  function findRequest(store, id) {
    return store.requests.find((request) => request.id === id) || null;
  }

  function pushTimeline(request, actor, action) {
    request.timeline.push({ ts: new Date().toISOString(), actor, action });
    request.updatedAt = request.timeline[request.timeline.length - 1].ts;
  }

  function uid() {
    return "REQ-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 6);
  }

  function formatTime(iso) {
    try {
      return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch (error) {
      return iso;
    }
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[ch]));
  }

  /* ------------------------------------------------------------------ */
  /* Context helpers — best-effort read of what the citizen is currently */
  /* doing, from fields app.js/app-ui.js already put on the page. Never   */
  /* writes to any of them, only reads.                                   */
  /* ------------------------------------------------------------------ */

  function currentStepLabel() {
    const titleEl = document.getElementById("page-title");
    return (titleEl && titleEl.textContent.trim()) || "Dashboard";
  }

  function guessApplicant() {
    const candidates = ["validation-applicant-id", "gov-actor-id"];
    for (const id of candidates) {
      const el = document.getElementById(id);
      if (el && el.value && el.value.trim()) return el.value.trim();
    }
    return "Guest applicant";
  }

  function guessService() {
    const select = document.getElementById("validation-service-id");
    if (select && select.value) {
      const option = select.options[select.selectedIndex];
      if (option && option.textContent.trim() && option.value) return option.textContent.trim();
    }
    return "Not specified yet";
  }

  function guessBank() {
    // No dedicated "bank" field exists elsewhere in the app today; this is a
    // best-effort label only, editable later by the officer via guidance —
    // never a value sent anywhere.
    const service = guessService();
    return service !== "Not specified yet" ? service : "Not specified yet";
  }

  /* ------------------------------------------------------------------ */
  /* Citizen side                                                        */
  /* ------------------------------------------------------------------ */

  const needHelpBtn = document.getElementById("need-help-btn");
  const requestModalOverlay = document.getElementById("assist-request-modal-overlay");
  const requestCancelBtn = document.getElementById("assist-request-cancel");
  const requestAllowBtn = document.getElementById("assist-request-allow");

  const citizenPanel = document.getElementById("assist-citizen-panel");
  const citizenTitle = document.getElementById("assist-citizen-title");
  const citizenStatus = document.getElementById("assist-citizen-status");
  const citizenMessages = document.getElementById("assist-citizen-messages");
  const citizenTimelineToggle = document.getElementById("assist-citizen-timeline-toggle");
  const citizenTimelineList = document.getElementById("assist-citizen-timeline-list");
  const citizenCancelBtn = document.getElementById("assist-cancel-btn");
  const citizenReturnControlBtn = document.getElementById("assist-return-control-btn");

  const controlModalOverlay = document.getElementById("assist-control-modal-overlay");
  const controlApproveBtn = document.getElementById("assist-control-approve");
  const controlDenyBtn = document.getElementById("assist-control-deny");

  const WORKFLOW_PAGES = new Set(["chat", "upload", "validate", "extract", "review", "portal"]);

  function hideAssistModals() {
    if (controlModalOverlay) {
      controlModalOverlay.hidden = true;
      controlModalOverlay.setAttribute("hidden", "");
      controlModalOverlay.style.display = "none";
    }
    if (requestModalOverlay) {
      requestModalOverlay.hidden = true;
      requestModalOverlay.setAttribute("hidden", "");
      requestModalOverlay.style.display = "none";
    }
  }

  hideAssistModals();

  function currentPageFromHash() {
    return (window.location.hash || "#dashboard").replace("#", "") || "dashboard";
  }

  function refreshNeedHelpVisibility() {
    const hasActiveRequest = !!sessionStorage.getItem(MY_REQUEST_KEY);
    needHelpBtn.hidden = hasActiveRequest || !WORKFLOW_PAGES.has(currentPageFromHash());
  }

  window.addEventListener("hashchange", refreshNeedHelpVisibility);

  needHelpBtn.addEventListener("click", () => {
    requestModalOverlay.hidden = false;
  });

  requestCancelBtn.addEventListener("click", () => {
    requestModalOverlay.hidden = true;
  });

  requestAllowBtn.addEventListener("click", () => {
    requestModalOverlay.hidden = true;
    const store = loadStore();
    const request = {
      id: uid(),
      applicant: guessApplicant(),
      bank: guessBank(),
      service: guessService(),
      step: currentStepLabel(),
      status: "pending",
      officer: null,
      controlState: "ai",
      messages: [],
      timeline: [],
      createdAt: new Date().toISOString(),
    };
    pushTimeline(request, "citizen", "Requested human assistance");
    store.requests.push(request);
    saveStore(store);
    sessionStorage.setItem(MY_REQUEST_KEY, request.id);
    refreshNeedHelpVisibility();
    renderCitizenPanel();
  });

  citizenCancelBtn.addEventListener("click", () => {
    const myId = sessionStorage.getItem(MY_REQUEST_KEY);
    if (myId) {
      const store = loadStore();
      const request = findRequest(store, myId);
      if (request && request.status !== "ended") {
        request.status = "ended";
        request.controlState = "ai";
        pushTimeline(request, "citizen", "Session ended by applicant");
        saveStore(store);
      }
    }
    sessionStorage.removeItem(MY_REQUEST_KEY);
    citizenPanel.hidden = true;
    refreshNeedHelpVisibility();
  });

  citizenReturnControlBtn.addEventListener("click", () => {
    const myId = sessionStorage.getItem(MY_REQUEST_KEY);
    if (!myId) return;
    const store = loadStore();
    const request = findRequest(store, myId);
    if (request) {
      request.controlState = "ai";
      pushTimeline(request, "citizen", "Returned control to self");
      saveStore(store);
    }
    renderCitizenPanel();
  });

  citizenTimelineToggle.addEventListener("click", () => {
    const showing = !citizenTimelineList.hidden;
    citizenTimelineList.hidden = showing;
    citizenTimelineToggle.textContent = showing ? "View activity log" : "Hide activity log";
  });

  let lastControlModalRequestState = null;
  const DEMO_DISABLE_CONTROL_MODAL = true;

  function autoApproveControlRequest(requestId) {
    const store = loadStore();
    const request = findRequest(store, requestId);
    if (!request || request.controlState !== "officer_requested") return false;
    request.controlState = "officer";
    request.status = "active";
    request.officer = request.officer || officerName();
    pushTimeline(request, "citizen", "Demo: auto-approved officer control");
    saveStore(store);
    return true;
  }

  controlApproveBtn.addEventListener("click", () => {
    const myId = sessionStorage.getItem(MY_REQUEST_KEY);
    controlModalOverlay.hidden = true;
    if (!myId) return;
    const store = loadStore();
    const request = findRequest(store, myId);
    if (request) {
      request.controlState = "officer";
      request.status = "active";
      request.officer = request.officer || officerName();
      pushTimeline(request, "citizen", "Approved: officer took control");
      saveStore(store);
    }
  });

  controlDenyBtn.addEventListener("click", () => {
    const myId = sessionStorage.getItem(MY_REQUEST_KEY);
    controlModalOverlay.hidden = true;
    if (!myId) return;
    const store = loadStore();
    const request = findRequest(store, myId);
    if (request) {
      request.controlState = "ai";
      pushTimeline(request, "citizen", "Denied officer's control request");
      saveStore(store);
    }
  });

  function renderCitizenPanel() {
    hideAssistModals();
    const myId = sessionStorage.getItem(MY_REQUEST_KEY);
    if (!myId) {
      citizenPanel.hidden = true;
      return;
    }
    const store = loadStore();
    const request = findRequest(store, myId);
    if (!request || request.status === "ended") {
      sessionStorage.removeItem(MY_REQUEST_KEY);
      citizenPanel.hidden = true;
      refreshNeedHelpVisibility();
      return;
    }

    if (DEMO_DISABLE_CONTROL_MODAL && request.controlState === "officer_requested") {
      autoApproveControlRequest(myId);
    }

    citizenPanel.hidden = false;

    if (request.controlState === "officer") {
      citizenTitle.textContent = `🧑‍💼 ${request.officer || "Support Officer"} is assisting`;
      citizenStatus.textContent = "The support officer is currently guiding this step. Sahaay.AI's AI assistant is still available alongside them.";
      citizenReturnControlBtn.hidden = false;
    } else if (request.status === "pending") {
      citizenTitle.textContent = "Waiting for a support officer…";
      citizenStatus.textContent = "AI stays active while you wait. You can cancel this request any time.";
      citizenMessages.hidden = true;
      citizenReturnControlBtn.hidden = true;
    } else {
      citizenTitle.textContent = `Connected with ${request.officer || "a support officer"}`;
      citizenStatus.textContent = "They can see your current step and send you guidance below.";
      citizenReturnControlBtn.hidden = true;
    }

    if (request.messages.length > 0) {
      citizenMessages.hidden = false;
      citizenMessages.innerHTML = request.messages
        .map((msg) => `<div><strong>${formatTime(msg.ts)} —</strong> ${escapeHtml(msg.text)}</div>`)
        .join("");
      citizenMessages.scrollTop = citizenMessages.scrollHeight;
    }

    citizenTimelineToggle.hidden = request.timeline.length === 0;
    citizenTimelineList.innerHTML = request.timeline
      .map((entry) => `<li><strong>${formatTime(entry.ts)}</strong> · ${escapeHtml(entry.action)}</li>`)
      .join("");

    // Demo mode: bypass the permission prompt entirely and move the request
    // straight into the assisted state so the UI remains usable.
    if (DEMO_DISABLE_CONTROL_MODAL) {
      controlModalOverlay.hidden = true;
      lastControlModalRequestState = null;
    } else if (request.controlState === "officer_requested" && lastControlModalRequestState !== request.id + "_requested") {
      lastControlModalRequestState = request.id + "_requested";
      controlModalOverlay.hidden = false;
    } else if (request.controlState !== "officer_requested") {
      lastControlModalRequestState = null;
    }
  }

  /* ------------------------------------------------------------------ */
  /* Officer side — Support Dashboard page                                */
  /* ------------------------------------------------------------------ */

  const officerNameInput = document.getElementById("assist-officer-name");
  const requestTbody = document.getElementById("assist-request-tbody");
  const sessionPanel = document.getElementById("assist-session-panel");
  const sessionTitle = document.getElementById("assist-session-title");
  const sessionStatusBadge = document.getElementById("assist-session-status");
  const endSessionBtn = document.getElementById("assist-end-session-btn");
  const messageLog = document.getElementById("assist-message-log");
  const sendGuidanceForm = document.getElementById("assist-send-guidance-form");
  const guidanceInput = document.getElementById("assist-guidance-input");
  const takeControlBtn = document.getElementById("assist-take-control-btn");
  const controlStatusEl = document.getElementById("assist-control-status");
  const timelineList = document.getElementById("assist-timeline-list");

  let openSessionId = null;

  officerNameInput.value = localStorage.getItem(OFFICER_NAME_KEY) || "";
  officerNameInput.addEventListener("input", () => {
    localStorage.setItem(OFFICER_NAME_KEY, officerNameInput.value.trim());
  });

  function officerName() {
    return officerNameInput.value.trim() || "Support Officer";
  }

  function badgeClassFor(status) {
    return `badge badge-${String(status || "").toLowerCase()}`;
  }

  function renderRequestTable() {
    const store = loadStore();
    const visible = store.requests.filter((request) => request.status !== "ended");
    if (visible.length === 0) {
      requestTbody.innerHTML =
        '<tr class="assist-request-empty-row"><td colspan="6">No assistance requests yet. Click "Need Help" from any workflow page to create one (open this app in a second tab to see it appear here live).</td></tr>';
      return;
    }
    requestTbody.innerHTML = visible
      .map((request) => {
        const isThisOfficersSession = request.status === "active" && request.officer === officerName();
        const joinLabel = request.status === "pending" ? "Join Session" : isThisOfficersSession ? "Open" : "Joined";
        const disabled = request.status === "active" && !isThisOfficersSession ? "disabled" : "";
        return `
          <tr>
            <td>${escapeHtml(request.applicant)}</td>
            <td>${escapeHtml(request.bank)}</td>
            <td>${escapeHtml(request.service)}</td>
            <td>${escapeHtml(request.step)}</td>
            <td><span class="${badgeClassFor(request.status)}">${escapeHtml(request.status)}</span></td>
            <td><button type="button" class="assist-join-btn" data-request-id="${request.id}" ${disabled}>${joinLabel}</button></td>
          </tr>
        `;
      })
      .join("");

    requestTbody.querySelectorAll(".assist-join-btn").forEach((btn) => {
      btn.addEventListener("click", () => joinSession(btn.dataset.requestId));
    });
  }

  function joinSession(requestId) {
    const store = loadStore();
    const request = findRequest(store, requestId);
    if (!request) return;
    if (request.status === "pending") {
      request.status = "active";
      request.officer = officerName();
      pushTimeline(request, "officer", `${officerName()} joined the session`);
      saveStore(store);
    }
    openSessionId = requestId;
    renderSessionPanel();
  }

  function renderSessionPanel() {
    if (!openSessionId) {
      sessionPanel.hidden = true;
      return;
    }
    const store = loadStore();
    const request = findRequest(store, openSessionId);
    if (!request || request.status === "ended") {
      openSessionId = null;
      sessionPanel.hidden = true;
      renderRequestTable();
      return;
    }

    sessionPanel.hidden = false;
    sessionTitle.textContent = `${request.applicant} — ${request.service} (currently on: ${request.step})`;
    sessionStatusBadge.className = badgeClassFor(request.status);
    sessionStatusBadge.textContent = request.status;

    messageLog.innerHTML =
      request.messages.length === 0
        ? '<div class="assist-message-empty">No guidance sent yet.</div>'
        : request.messages
            .map((msg) => `<div class="assist-message"><strong>${formatTime(msg.ts)}</strong> — ${escapeHtml(msg.text)}</div>`)
            .join("");
    messageLog.scrollTop = messageLog.scrollHeight;

    if (request.controlState === "officer") {
      takeControlBtn.textContent = "Return Control to Applicant";
      controlStatusEl.textContent = "You are currently guiding this step.";
      takeControlBtn.disabled = false;
    } else if (request.controlState === "officer_requested") {
      takeControlBtn.textContent = "Waiting for approval…";
      takeControlBtn.disabled = true;
      controlStatusEl.textContent = "Asking the applicant for permission…";
    } else {
      takeControlBtn.textContent = "Take Control";
      takeControlBtn.disabled = false;
      controlStatusEl.textContent = "The applicant (with the AI) is currently in control.";
    }

    timelineList.innerHTML = request.timeline
      .map((entry) => `<li><strong>${formatTime(entry.ts)}</strong> · [${escapeHtml(entry.actor)}] ${escapeHtml(entry.action)}</li>`)
      .join("");
  }

  sendGuidanceForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = guidanceInput.value.trim();
    if (!text || !openSessionId) return;
    const store = loadStore();
    const request = findRequest(store, openSessionId);
    if (!request) return;
    request.messages.push({ from: "officer", text, ts: new Date().toISOString() });
    pushTimeline(request, "officer", `Sent guidance: "${text}"`);
    saveStore(store);
    guidanceInput.value = "";
  });

  takeControlBtn.addEventListener("click", () => {
    if (!openSessionId) return;
    const store = loadStore();
    const request = findRequest(store, openSessionId);
    if (!request) return;
    if (request.controlState === "officer") {
      request.controlState = "ai";
      pushTimeline(request, "officer", "Returned control to applicant");
    } else if (request.controlState !== "officer_requested") {
      request.controlState = "officer_requested";
      pushTimeline(request, "officer", "Requested permission to take control");
    }
    saveStore(store);
  });

  endSessionBtn.addEventListener("click", () => {
    if (!openSessionId) return;
    const store = loadStore();
    const request = findRequest(store, openSessionId);
    if (request) {
      request.status = "ended";
      request.controlState = "ai";
      pushTimeline(request, "officer", "Session ended by officer");
      saveStore(store);
    }
    openSessionId = null;
    sessionPanel.hidden = true;
    renderRequestTable();
  });

  /* ------------------------------------------------------------------ */
  /* Cross-tab / same-tab sync                                           */
  /* ------------------------------------------------------------------ */

  function refreshAll() {
    renderCitizenPanel();
    renderRequestTable();
    renderSessionPanel();
  }

  window.addEventListener("storage", (event) => {
    if (event.key === STORE_KEY) refreshAll();
  });
  window.addEventListener("sahaay-assist-update", refreshAll);
  // Fallback poll in case a browser fires neither event promptly for same-
  // machine multi-tab demos; harmless no-op if nothing changed.
  setInterval(refreshAll, 3000);

  /* ------------------------------------------------------------------ */
  /* Init                                                                 */
  /* ------------------------------------------------------------------ */

  refreshNeedHelpVisibility();
  renderCitizenPanel();
  renderRequestTable();
})();
