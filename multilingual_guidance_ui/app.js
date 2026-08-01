// Base URLs for each independent backend service.
// - BACKEND_BASE:     system_orchestrator/app (document storage, portal redirects)          -> :8000
// - VALIDATION_BASE:  input_validation_security_engine (Phase 1)                      -> :8001
// - EXTRACTION_BASE:  ai_guidance_engine (Phase 2)                            -> :8002
// - GOVERNANCE_BASE:  trust_governance_engine (Phase 4 - human review & submission)   -> :8003
// Override any of these from the browser console or a small inline <script>
// before app.js loads, e.g. `window.SAHAAY_CONFIG = { extractionBase: "..." }`,
// without touching this file (useful once services move off localhost).
const SAHAAY_CONFIG = window.SAHAAY_CONFIG || {};
const BACKEND_BASE = SAHAAY_CONFIG.backendBase || "http://127.0.0.1:8000/api/v1";
const VALIDATION_BASE = SAHAAY_CONFIG.validationBase || "http://127.0.0.1:8001/api/v1";
const EXTRACTION_BASE = SAHAAY_CONFIG.extractionBase || "http://127.0.0.1:8002/api/v1";
const GOVERNANCE_BASE = SAHAAY_CONFIG.governanceBase || "http://127.0.0.1:8003/api/v1";
const REGISTRY_BASE = SAHAAY_CONFIG.registryBase || "http://127.0.0.1:8004/api/v1";

let portalLinks = [];
let referenceCatalog = null;
let serviceCatalog = [];
let validationDocRowCount = 0;
let extractionDocRowCount = 0;

// Holds { applicantId, fields } from the most recent successful extraction
// response, so section 5 can hand it straight to the Governance Engine
// without the caseworker re-typing every field.
let lastExtractionResult = null;

// The application currently loaded/being reviewed in section 5.
let currentGovApplication = null;

// Holds the most recently uploaded file's client-extracted text + metadata so
// the Validation and Extraction sections can reuse it via "Use last upload"
// instead of requiring the applicant to copy/paste OCR text by hand. Note
// this is plain client-side text extraction (file.text()); it is NOT image
// OCR — scanned/image documents still need their text pasted in manually
// until an OCR provider is wired into the backend (see multilingual_guidance_ui/README.md).
let lastUploadedDocument = null;

const portalList = document.getElementById("portal-list");
const portalFeedback = document.getElementById("portal-feedback");
const portalNoteInput = document.getElementById("portal-note");
const portalApiKeyInput = document.getElementById("portal-api-key");
const fileHashEl = document.getElementById("file-hash");
const uploadForm = document.getElementById("upload-form");
const uploadResult = document.getElementById("upload-result");
const fileInput = document.getElementById("doc-file");

const referencePanel = document.getElementById("reference-panel");
const validationServiceIdSelect = document.getElementById("validation-service-id");
const documentTypeOptions = document.getElementById("document-type-options");

const validationForm = document.getElementById("validation-form");
const validationResult = document.getElementById("validation-result");
const validationDocRows = document.getElementById("validation-doc-rows");
const addValidationDocBtn = document.getElementById("add-validation-doc");

const extractForm = document.getElementById("extract-form");
const extractResult = document.getElementById("extract-result");
const extractionDocRows = document.getElementById("extraction-doc-rows");
const addExtractionDocBtn = document.getElementById("add-extraction-doc");

const govActorInput = document.getElementById("gov-actor-id");
const govSendExtractionBtn = document.getElementById("gov-send-extraction-btn");
const govLoadApplicationIdInput = document.getElementById("gov-load-application-id");
const govLoadApplicationBtn = document.getElementById("gov-load-application-btn");
const govIntakeResult = document.getElementById("gov-intake-result");
const govApplicationPanel = document.getElementById("gov-application-panel");
const govAppIdEl = document.getElementById("gov-app-id");
const govAppStatusEl = document.getElementById("gov-app-status");
const govRefreshBtn = document.getElementById("gov-refresh-btn");
const govFieldsList = document.getElementById("gov-fields-list");
const govOtpDestinationInput = document.getElementById("gov-otp-destination");
const govOtpCodeInput = document.getElementById("gov-otp-code");
const govRequestOtpBtn = document.getElementById("gov-request-otp-btn");
const govVerifyOtpBtn = document.getElementById("gov-verify-otp-btn");
const govValidateBtn = document.getElementById("gov-validate-btn");
const govSubmitBtn = document.getElementById("gov-submit-btn");
const govOtpResult = document.getElementById("gov-otp-result");
const govAuditLogBtn = document.getElementById("gov-audit-log-btn");
const govVerifyChainBtn = document.getElementById("gov-verify-chain-btn");
const govReportFormatSelect = document.getElementById("gov-report-format");
const govDownloadReportBtn = document.getElementById("gov-download-report-btn");
const govAuditResult = document.getElementById("gov-audit-result");

const delegateNameInput = document.getElementById("delegate-name");
const delegateRelationshipInput = document.getElementById("delegate-relationship");
const delegateContactInput = document.getElementById("delegate-contact");
const delegateApprovalRequiredInput = document.getElementById("delegate-approval-required");
const delegateConsentByInput = document.getElementById("delegate-consent-by");
const delegateRegisterBtn = document.getElementById("delegate-register-btn");
const delegateLoadBtn = document.getElementById("delegate-load-btn");
const delegateApproveBtn = document.getElementById("delegate-approve-btn");
const delegateRevokeBtn = document.getElementById("delegate-revoke-btn");
const delegateStatusCard = document.getElementById("delegate-status-card");
const delegateResult = document.getElementById("delegate-result");

const conversationWindow = document.getElementById("conversation-window");
const conversationCandidates = document.getElementById("conversation-candidates");
const conversationForm = document.getElementById("conversation-form");
const conversationInput = document.getElementById("conversation-input");
const conversationSendBtn = document.getElementById("conversation-send-btn");
const conversationResetBtn = document.getElementById("conversation-reset-btn");
const conversationIdDisplay = document.getElementById("conversation-id-display");
const conversationResult = document.getElementById("conversation-result");

// Phase D: the active intent_service conversation_id, proxied through
// system_orchestrator's /api/v1/conversation/* routes. null until the
// citizen sends a first message.
let conversationId = null;

/* ------------------------------------------------------------------ */
/* Shared helpers                                                      */
/* ------------------------------------------------------------------ */

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function badgeClass(status) {
  const key = String(status || "").toLowerCase();
  return `badge badge-${key}`;
}

// Disables a submit button, swaps its label to a busy label, and shows a
// small inline spinner while an in-flight request is pending. Returns a
// restore() function that undoes all of that — always call it in a
// finally block so the button never gets stuck disabled after an error.
function setButtonBusy(button, busyLabel) {
  const originalLabel = button.textContent;
  const originalDisabled = button.disabled;
  button.disabled = true;
  button.classList.add("is-loading");
  button.textContent = busyLabel;
  return function restore() {
    button.disabled = originalDisabled;
    button.classList.remove("is-loading");
    button.textContent = originalLabel;
  };
}

async function readErrorDetail(response) {
  try {
    const data = await response.json();
    if (Array.isArray(data.detail)) {
      // FastAPI validation error format
      return data.detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
    }
    return data.detail || response.statusText;
  } catch {
    return response.statusText;
  }
}

// Phase D Security Shield: system_orchestrator responds 409 with
// detail = { message, findings: [...] } when risk_engine says a redirect
// should be paused (e.g. domain not on the official whitelist, HTTPS
// missing). This is a deliberate pause for human review, not a generic
// error, so it gets its own distinct panel instead of an error string.
async function renderPortalConfirmError(response, feedbackEl = portalFeedback) {
  let data = null;
  try {
    data = await response.json();
  } catch {
    // fall through to generic handling below
  }

  const detail = data ? data.detail : null;
  if (response.status === 409 && detail && Array.isArray(detail.findings)) {
    feedbackEl.innerHTML = `
      <div class="risk-blocked">
        <strong>⚠ Redirect paused by the Security Shield</strong>
        <p>${escapeHtml(detail.message || "This redirect was paused pending human review.")}</p>
        <ul>${detail.findings.map((finding) => `<li>${escapeHtml(finding)}</li>`).join("")}</ul>
        <p class="risk-blocked-note">
          Sahaay.AI paused before handing you off because this redirect didn't pass a security check —
          this is not a bug. Please verify the site yourself, or check with your Trusted Delegate or a
          caseworker before continuing. Sahaay.AI never overrides this pause automatically.
        </p>
      </div>
    `;
    return;
  }

  const genericDetail = detail
    ? Array.isArray(detail)
      ? detail.map((item) => item.msg || JSON.stringify(item)).join("; ")
      : typeof detail === "string"
      ? detail
      : response.statusText
    : response.statusText;
  feedbackEl.textContent = `Portal confirmation failed: ${genericDetail}`;
}

// Shared confirm/redirect logic for "open this official portal", used by
// both the section 4 portal cards AND the new section 3 conversation flow
// (once it resolves a single service) — one code path, so Security Shield
// handling and the confirmation prompt behave identically either way.
async function confirmPortalRedirect(portal, { feedbackEl = portalFeedback, buttonEl = null, busyLabel = "Confirming..." } = {}) {
  feedbackEl.textContent = "";
  const confirmRedirect = confirm(`You are about to open ${portal.name}. Do you want to continue?`);
  if (!confirmRedirect) {
    feedbackEl.textContent = "Portal redirect canceled by user.";
    return null;
  }

  const userNote = portalNoteInput.value.trim();
  const apiKey = portalApiKeyInput.value.trim();

  const restoreBtn = buttonEl ? setButtonBusy(buttonEl, busyLabel) : () => {};
  try {
    const response = await fetch(`${BACKEND_BASE}/portals/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        portal_id: portal.id,
        permission_given: true,
        user_note: userNote || undefined,
        api_key: apiKey || undefined,
      }),
    });

    if (!response.ok) {
      await renderPortalConfirmError(response, feedbackEl);
      return null;
    }

    const data = await response.json();
    feedbackEl.textContent = data.message;
    window.open(data.redirect_url, "_blank");
    return data;
  } catch (error) {
    feedbackEl.textContent = `Error confirming portal: ${error.message}`;
    return null;
  } finally {
    restoreBtn();
  }
}

/* ------------------------------------------------------------------ */
/* 1. Document Upload & Hash (system_orchestrator/app)                             */
/* ------------------------------------------------------------------ */

async function computeSHA256(file) {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

fileInput.addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) {
    fileHashEl.textContent = "No file selected";
    return;
  }
  fileHashEl.textContent = "Computing hash...";
  const hash = await computeSHA256(file);
  fileHashEl.textContent = hash;
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = document.getElementById("doc-title").value.trim();
  const source = document.getElementById("doc-source").value.trim();
  const file = fileInput.files[0];
  if (!file) {
    uploadResult.textContent = "Please select a file before uploading.";
    return;
  }
  const confirmUpload = confirm(
    "Upload the selected document and create a secure hashed record?"
  );
  if (!confirmUpload) {
    uploadResult.textContent = "Upload canceled by user.";
    return;
  }

  const content = await file.text();
  const submitBtn = uploadForm.querySelector("button[type=submit]");
  const restoreBtn = setButtonBusy(submitBtn, "Uploading...");
  uploadResult.textContent = "Uploading...";
  try {
    const response = await fetch(`${BACKEND_BASE}/documents`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, source, content }),
    });

    if (!response.ok) {
      uploadResult.textContent = `Upload failed: ${await readErrorDetail(response)}`;
      return;
    }

    const data = await response.json();
    uploadResult.textContent = `Uploaded successfully. Document ID: ${data.id}, SHA-256: ${fileHashEl.textContent}`;

    // Remember this file's text + metadata so Validation/Extraction doc rows
    // can pull it in with "Use last upload" instead of manual copy/paste.
    lastUploadedDocument = {
      fileName: file.name,
      mimeType: file.type || "application/octet-stream",
      sizeBytes: file.size,
      text: content,
    };
  } catch (error) {
    uploadResult.textContent = `Upload error: ${error.message}`;
  } finally {
    restoreBtn();
  }
});

/* ------------------------------------------------------------------ */
/* 2. Document Validation (input_validation_security_engine, Phase 1)        */
/* ------------------------------------------------------------------ */

// Renders the two independent reference groups (document types from the
// Input Validation & Security Engine, official services from the Official
// Service Registry) into the same panel. Each group renders/clears
// independently so one source being unreachable doesn't blank out the other.
function renderDocumentTypesGroup(supportedDocumentTypes) {
  const docTags = supportedDocumentTypes
    .map((type) => `<span class="tag">${escapeHtml(type)}</span>`)
    .join("");
  let group = referencePanel.querySelector('[data-reference-group="documents"]');
  if (!group) {
    group = document.createElement("div");
    group.className = "reference-group";
    group.dataset.referenceGroup = "documents";
    referencePanel.appendChild(group);
  }
  group.innerHTML = `<span class="reference-group-label">Document types:</span>${docTags}`;

  documentTypeOptions.innerHTML = supportedDocumentTypes
    .map((type) => `<option value="${escapeHtml(type)}"></option>`)
    .join("");
}

function renderServicesGroup(services) {
  const serviceTags = services
    .map((service) => `<span class="tag">${escapeHtml(service.service_name)} (${escapeHtml(service.service_id)})</span>`)
    .join("");
  let group = referencePanel.querySelector('[data-reference-group="services"]');
  if (!group) {
    group = document.createElement("div");
    group.className = "reference-group";
    group.dataset.referenceGroup = "services";
    referencePanel.appendChild(group);
  }
  group.innerHTML = `<span class="reference-group-label">Official services:</span>${serviceTags}`;

  const previouslySelected = validationServiceIdSelect.value;
  validationServiceIdSelect.innerHTML =
    `<option value="">-- Select a service (optional) --</option>` +
    services
      .map(
        (service) =>
          `<option value="${escapeHtml(service.service_id)}">${escapeHtml(service.service_name)} (${escapeHtml(
            service.category
          )})</option>`
      )
      .join("");
  if (previouslySelected && services.some((service) => service.service_id === previouslySelected)) {
    validationServiceIdSelect.value = previouslySelected;
  }
}

function renderReferenceError(message) {
  let group = referencePanel.querySelector('[data-reference-group="error"]');
  if (!group) {
    group = document.createElement("div");
    group.dataset.referenceGroup = "error";
    referencePanel.appendChild(group);
  }
  group.innerHTML = `<span class="reference-error">${message}</span>`;
}

async function loadReferenceCatalog() {
  // Clear the initial "Loading..." placeholder once this source resolves,
  // success or failure — it's shared with loadServiceCatalog below, so
  // whichever call finishes first clears it.
  try {
    const response = await fetch(`${VALIDATION_BASE}/document-types`);
    referencePanel.querySelector(".reference-loading")?.remove();
    if (!response.ok) {
      renderReferenceError(
        `Unable to load document types: ${escapeHtml(await readErrorDetail(response))}`
      );
      return;
    }
    referenceCatalog = await response.json();
    renderDocumentTypesGroup(referenceCatalog.supported_document_types);
  } catch (error) {
    referencePanel.querySelector(".reference-loading")?.remove();
    renderReferenceError(
      `Unable to reach Input Validation &amp; Security Engine at ${VALIDATION_BASE}: ${escapeHtml(error.message)}`
    );
  }
}

async function loadServiceCatalog() {
  try {
    const response = await fetch(`${REGISTRY_BASE}/services`);
    referencePanel.querySelector(".reference-loading")?.remove();
    if (!response.ok) {
      renderReferenceError(
        `Unable to load official services: ${escapeHtml(await readErrorDetail(response))}`
      );
      return;
    }
    serviceCatalog = await response.json();
    renderServicesGroup(serviceCatalog);
  } catch (error) {
    renderReferenceError(
      `Unable to reach Official Service Registry at ${REGISTRY_BASE}: ${escapeHtml(error.message)}`
    );
  }
}

function buildDocRow(container, index, { withMetadata }) {
  const row = document.createElement("div");
  row.className = "doc-row";
  row.dataset.rowIndex = String(index);

  row.innerHTML = `
    <div class="doc-row-header">
      <span class="doc-row-title">Document ${index + 1}</span>
      <div class="doc-row-header-actions">
        <button type="button" class="use-upload-btn secondary-btn">Use last upload</button>
        <button type="button" class="remove-doc-btn">Remove</button>
      </div>
    </div>
    <label>Document Type<input type="text" class="doc-type-input" list="document-type-options" placeholder="aadhaar" required /></label>
    <label>OCR Text<textarea class="doc-text-input" rows="3" placeholder="Paste OCR extracted text for this document, or click &quot;Use last upload&quot; above"></textarea></label>
    ${
      withMetadata
        ? `<div class="metadata-fields">
             <label>File Name<input type="text" class="doc-meta-filename" placeholder="aadhaar.pdf" /></label>
             <label>MIME Type<input type="text" class="doc-meta-mime" placeholder="application/pdf" /></label>
             <label>Size (bytes)<input type="number" class="doc-meta-size" min="0" placeholder="204800" /></label>
             <label>Page Count<input type="number" class="doc-meta-pages" min="1" placeholder="1" /></label>
           </div>`
        : ""
    }
  `;

  row.querySelector(".remove-doc-btn").addEventListener("click", () => {
    row.remove();
  });

  // Pulls the text (and, where present, file metadata) from the most
  // recently uploaded document in section 1 into this row, so the applicant
  // doesn't have to copy/paste OCR text between sections by hand.
  row.querySelector(".use-upload-btn").addEventListener("click", () => {
    if (!lastUploadedDocument) {
      alert('No document has been uploaded yet. Upload one in "1. Document Upload & Hash" first.');
      return;
    }
    row.querySelector(".doc-text-input").value = lastUploadedDocument.text;
    if (withMetadata) {
      row.querySelector(".doc-meta-filename").value = lastUploadedDocument.fileName;
      row.querySelector(".doc-meta-mime").value = lastUploadedDocument.mimeType;
      row.querySelector(".doc-meta-size").value = String(lastUploadedDocument.sizeBytes);
    }
  });

  container.appendChild(row);
  return row;
}

addValidationDocBtn.addEventListener("click", () => {
  buildDocRow(validationDocRows, validationDocRowCount++, { withMetadata: true });
});

addExtractionDocBtn.addEventListener("click", () => {
  buildDocRow(extractionDocRows, extractionDocRowCount++, { withMetadata: false });
});

function readDocRows(container, { withMetadata }) {
  const rows = Array.from(container.querySelectorAll(".doc-row"));
  return rows.map((row) => {
    const type = row.querySelector(".doc-type-input").value.trim();
    const text = row.querySelector(".doc-text-input").value.trim();
    const doc = { type, text };

    if (withMetadata) {
      const fileName = row.querySelector(".doc-meta-filename").value.trim();
      const mimeType = row.querySelector(".doc-meta-mime").value.trim();
      const sizeRaw = row.querySelector(".doc-meta-size").value.trim();
      const pagesRaw = row.querySelector(".doc-meta-pages").value.trim();

      if (fileName && mimeType && sizeRaw) {
        doc.metadata = {
          file_name: fileName,
          mime_type: mimeType,
          size_bytes: Number(sizeRaw),
          page_count: pagesRaw ? Number(pagesRaw) : null,
        };
      }
    }

    return doc;
  });
}

function renderValidationResponse(data) {
  const missingDocs = data.missing_required_documents.length
    ? `<p><strong>Missing required documents:</strong> ${data.missing_required_documents
        .map((doc) => `<span class="tag">${escapeHtml(doc)}</span>`)
        .join(" ")}</p>`
    : "";

  const eligibility = data.eligibility_pre_check
    ? `<p><strong>Eligibility pre-check (${escapeHtml(
        data.eligibility_pre_check.service_id
      )}):</strong> ${
        data.eligibility_pre_check.is_eligible === null
          ? "Not evaluated"
          : data.eligibility_pre_check.is_eligible
          ? "Eligible"
          : "Not eligible"
      }${
        data.eligibility_pre_check.rule_results.length
          ? `<ul class="issues-list">${data.eligibility_pre_check.rule_results
              .map(
                (rule) =>
                  `<li><span class="${badgeClass(
                    rule.passed === null ? "manual_review" : rule.passed ? "valid" : "invalid"
                  )}">${
                    rule.passed === null ? "unknown" : rule.passed ? "passed" : "failed"
                  }</span> ${escapeHtml(rule.message)}</li>`
              )
              .join("")}</ul>`
          : ""
      }${
        data.eligibility_pre_check.notes.length
          ? `<span class="field-meta">${escapeHtml(data.eligibility_pre_check.notes.join(" "))}</span>`
          : ""
      }</p>`
    : "";

  const docCards = data.documents
    .map((doc) => {
      const issues = doc.issues.length
        ? `<ul class="issues-list">${doc.issues
            .map(
              (issue) =>
                `<li><span class="${badgeClass(issue.severity)}">${escapeHtml(
                  issue.severity
                )}</span> [${escapeHtml(issue.code)}] ${escapeHtml(issue.message)}</li>`
            )
            .join("")}</ul>`
        : `<p class="field-meta">No issues found.</p>`;

      return `
        <div class="doc-result-card">
          <div class="result-heading">
            <strong>${escapeHtml(doc.type)}</strong>
            <span class="${badgeClass(doc.is_valid ? "valid" : "invalid")}">${
        doc.is_valid ? "Valid" : "Invalid"
      }</span>
          </div>
          <p class="field-meta">
            Supported type: ${doc.is_supported_type ? "Yes" : "No"} ·
            Metadata valid: ${doc.metadata_valid ? "Yes" : "No"} ·
            OCR valid: ${doc.ocr_valid ? "Yes" : "No"}
          </p>
          ${issues}
        </div>
      `;
    })
    .join("");

  validationResult.innerHTML = `
    <div class="result-heading">
      <strong>Applicant ${escapeHtml(data.applicant_id)}</strong>
      <span class="${badgeClass(data.status)}">${escapeHtml(data.status)}</span>
    </div>
    ${missingDocs}
    ${eligibility}
    ${docCards}
  `;
}

validationForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const applicantId = document.getElementById("validation-applicant-id").value.trim();
  const serviceId = validationServiceIdSelect.value.trim();
  const applicantAgeRaw = document.getElementById("validation-applicant-age").value.trim();
  const documents = readDocRows(validationDocRows, { withMetadata: true });

  if (!documents.length) {
    validationResult.textContent = "Add at least one document before validating.";
    return;
  }
  if (documents.some((doc) => !doc.type || !doc.text)) {
    validationResult.textContent = "Every document needs a type and OCR text.";
    return;
  }

  const payload = {
    applicant_id: applicantId,
    documents,
  };
  if (serviceId) payload.service_id = serviceId;
  if (applicantAgeRaw) payload.applicant_age = Number(applicantAgeRaw);

  const submitBtn = validationForm.querySelector("button[type=submit]");
  const restoreBtn = setButtonBusy(submitBtn, "Validating...");
  validationResult.textContent = "Validating...";
  try {
    const response = await fetch(`${VALIDATION_BASE}/validate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      validationResult.textContent = `Validation failed: ${await readErrorDetail(response)}`;
      return;
    }

    renderValidationResponse(await response.json());
  } catch (error) {
    validationResult.textContent = `Unable to reach Document Validation Engine at ${VALIDATION_BASE}: ${error.message}`;
  } finally {
    restoreBtn();
  }
});

/* ------------------------------------------------------------------ */
/* 3. Guided Banking Portal (system_orchestrator/app)                              */
/* ------------------------------------------------------------------ */

function renderPortals() {
  portalList.innerHTML = "";
  portalLinks.forEach((portal) => {
    const card = document.createElement("div");
    card.className = "portal-card";
    card.innerHTML = `
      <div>
        <strong>${escapeHtml(portal.name)}</strong>
        <p>${escapeHtml(portal.description)}</p>
      </div>
      <button type="button">Open</button>
    `;

    card.querySelector("button").addEventListener("click", async () => {
      const openBtn = card.querySelector("button");
      await confirmPortalRedirect(portal, { feedbackEl: portalFeedback, buttonEl: openBtn, busyLabel: "Confirming..." });
    });

    portalList.appendChild(card);
  });
}

async function loadPortals() {
  try {
    const response = await fetch(`${BACKEND_BASE}/portals`);
    if (!response.ok) {
      portalFeedback.textContent = `Unable to load portals: ${await readErrorDetail(response)}`;
      return;
    }
    portalLinks = await response.json();
    renderPortals();
  } catch (error) {
    portalFeedback.textContent = `Unable to load portals: ${error.message}`;
  }
}

/* ------------------------------------------------------------------ */
/* 3. Ask Sahaay.AI — conversational guidance                          */
/* (system_orchestrator/app's /api/v1/conversation/* proxy to           */
/* intent_service, Phase C1-C4). This is an ADDITIVE second entry       */
/* point into the exact same POST /portals/confirm flow the portal      */
/* cards above already use — see confirmPortalRedirect(). Neither path  */
/* replaces the other; a citizen can use either, or both.               */
/* ------------------------------------------------------------------ */

function appendConversationMessage(role, text) {
  conversationWindow.querySelector(".conversation-placeholder")?.remove();
  const bubble = document.createElement("div");
  bubble.className = `conversation-bubble conversation-bubble-${role}`;
  bubble.textContent = text;
  conversationWindow.appendChild(bubble);
  conversationWindow.scrollTop = conversationWindow.scrollHeight;
}

function renderConversationCandidates(candidates) {
  if (!candidates || !candidates.length) {
    conversationCandidates.hidden = true;
    conversationCandidates.innerHTML = "";
    return;
  }
  // Clicking a candidate sends its 1-based index as the next message —
  // intent_service's disambiguation handler accepts either a number or the
  // service name typed by hand, so this is just a shortcut for the same
  // thing a citizen could type themselves.
  conversationCandidates.hidden = false;
  conversationCandidates.innerHTML = candidates
    .map(
      (candidate, index) =>
        `<button type="button" class="candidate-chip" data-choice="${index + 1}">${index + 1}. ${escapeHtml(
          candidate.service_name
        )}</button>`
    )
    .join("");
  conversationCandidates.querySelectorAll(".candidate-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      conversationInput.value = chip.dataset.choice;
      conversationForm.requestSubmit();
    });
  });
}

// Renders the "you're done, here's the service we found" state, with a
// button that reuses confirmPortalRedirect() — the identical Security
// Shield-checked confirm/redirect path the portal cards in section 4 use.
function renderResolvedService(resolvedService) {
  if (!resolvedService) {
    conversationResult.innerHTML = "";
    return;
  }
  conversationResult.innerHTML = `
    <div class="conversation-resolved">
      <strong>${escapeHtml(resolvedService.service_name)}</strong>
      <p>${escapeHtml(resolvedService.description || "")}</p>
      <button type="button" id="conversation-continue-btn" class="secondary-btn">
        Continue to official site
      </button>
    </div>
  `;
  document.getElementById("conversation-continue-btn").addEventListener("click", async (event) => {
    await confirmPortalRedirect(
      {
        id: resolvedService.service_id,
        name: resolvedService.service_name,
        description: resolvedService.description || "",
      },
      { feedbackEl: conversationResult, buttonEl: event.currentTarget, busyLabel: "Confirming..." }
    );
  });
}

function renderConversationTurn(data) {
  appendConversationMessage("sahaay", data.message);
  conversationId = data.conversation_id;
  conversationIdDisplay.textContent = `Conversation: ${conversationId} (${data.state}, turn ${data.turn_count})`;

  renderConversationCandidates(data.state === "disambiguating_service" ? data.candidate_matches : []);

  if (data.state === "completed" && data.resolved_service) {
    renderResolvedService(data.resolved_service);
  } else {
    conversationResult.innerHTML = "";
  }

  if (data.eligibility_result) {
    const el = data.eligibility_result;
    const note = el.is_eligible === null ? "Eligibility not evaluated" : el.is_eligible ? "Eligible" : "Not eligible";
    appendConversationMessage("sahaay", `Eligibility check (${el.service_id}): ${note}`);
  }
  if (!data.registry_available) {
    appendConversationMessage(
      "sahaay",
      "Note: the Official Service Registry is unreachable right now, so service matching is limited."
    );
  }
}

conversationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = conversationInput.value.trim();
  if (!text) return;

  appendConversationMessage("citizen", text);
  conversationInput.value = "";

  const restoreBtn = setButtonBusy(conversationSendBtn, "Sending...");
  try {
    const response = await fetch(`${BACKEND_BASE}/conversation/message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, conversation_id: conversationId }),
    });
    if (!response.ok) {
      appendConversationMessage("sahaay", `Error: ${await readErrorDetail(response)}`);
      return;
    }
    renderConversationTurn(await response.json());
  } catch (error) {
    appendConversationMessage("sahaay", `Error reaching Sahaay.AI: ${error.message}`);
  } finally {
    restoreBtn();
  }
});

conversationResetBtn.addEventListener("click", async () => {
  if (conversationId) {
    try {
      await fetch(`${BACKEND_BASE}/conversation/${conversationId}`, { method: "DELETE" });
    } catch {
      // Best-effort only — clearing local state below is what actually
      // lets the citizen start over even if the delete call itself fails.
    }
  }
  conversationId = null;
  conversationIdDisplay.textContent = "";
  conversationCandidates.hidden = true;
  conversationCandidates.innerHTML = "";
  conversationResult.innerHTML = "";
  conversationWindow.innerHTML = `<div class="conversation-placeholder">Say hello, or describe what you need help with, to get started.</div>`;
});

/* ------------------------------------------------------------------ */
/* 4. AI Field Extraction (ai_guidance_engine, Phase 2)              */
/* ------------------------------------------------------------------ */

function renderExtractionResponse(data) {
  const fieldCards = data.fields
    .map(
      (field) => `
        <div class="field-card">
          <div class="field-card-top">
            <span class="field-name">${escapeHtml(field.field)}</span>
            <span class="${badgeClass(field.confidence_level)}">${escapeHtml(
        field.confidence_level
      )} (${(field.confidence * 100).toFixed(0)}%)</span>
          </div>
          <span class="field-value">${escapeHtml(field.value ?? "—")}</span>
          <span class="field-meta">Source: ${escapeHtml(field.source_document)} · ${escapeHtml(
        field.reason
      )}</span>
        </div>
      `
    )
    .join("");

  extractResult.innerHTML = `
    <div class="result-heading">
      <strong>Provider: ${escapeHtml(data.provider)}</strong>
      <span class="${badgeClass(data.status)}">${escapeHtml(data.status)}</span>
    </div>
    ${fieldCards || '<p class="field-meta">No fields returned.</p>'}
  `;
}

// Remembers the extraction result so "5. Human Review & Governance" can hand
// it straight to the Governance Engine without re-typing every field, and
// enables the button that does so once there's something to send.
function rememberExtractionForGovernance(applicantId, data) {
  if (!data.fields || !data.fields.length) return;
  lastExtractionResult = { applicantId, fields: data.fields };
  govSendExtractionBtn.disabled = false;
}

extractForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const applicantId = document.getElementById("extract-applicant-id").value.trim();
  const documents = readDocRows(extractionDocRows, { withMetadata: false });

  if (!documents.length) {
    extractResult.textContent = "Add at least one document before running extraction.";
    return;
  }
  if (documents.some((doc) => !doc.type || !doc.text)) {
    extractResult.textContent = "Every document needs a type and OCR text.";
    return;
  }

  const confirmExtract = confirm(
    "Run AI field extraction on these documents? This calls an external AI provider."
  );
  if (!confirmExtract) {
    extractResult.textContent = "Extraction canceled by user.";
    return;
  }

  const submitBtn = extractForm.querySelector("button[type=submit]");
  const restoreBtn = setButtonBusy(submitBtn, "Extracting...");
  extractResult.textContent = "Extracting...";
  try {
    const response = await fetch(`${EXTRACTION_BASE}/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ applicant_id: applicantId, documents }),
    });

    if (!response.ok) {
      extractResult.textContent = `Extraction failed: ${await readErrorDetail(response)}`;
      return;
    }

    const data = await response.json();
    renderExtractionResponse(data);
    rememberExtractionForGovernance(applicantId, data);
  } catch (error) {
    extractResult.textContent = `Unable to reach AI Extraction Engine at ${EXTRACTION_BASE}: ${error.message}`;
  } finally {
    restoreBtn();
  }
});

/* ------------------------------------------------------------------ */
/* 5. Human Review & Governance (trust_governance_engine, Phase 4)           */
/* ------------------------------------------------------------------ */

function currentActor() {
  return govActorInput.value.trim() || "caseworker:web";
}

function statusLabel(status) {
  return String(status || "").replace(/_/g, " ");
}

function renderGovApplication(data) {
  currentGovApplication = data;
  govApplicationPanel.hidden = false;
  govAppIdEl.textContent = data.application_id;
  govAppStatusEl.className = badgeClass(data.status);
  govAppStatusEl.textContent = statusLabel(data.status);

  const locked = data.status === "submitted";

  govFieldsList.innerHTML = data.fields
    .map((field) => {
      const decidedNote = field.decided_by
        ? `<span class="gov-field-decided">Decided by ${escapeHtml(field.decided_by)}${
            field.decided_at ? ` at ${escapeHtml(field.decided_at)}` : ""
          }${field.decision_note ? ` — ${escapeHtml(field.decision_note)}` : ""}</span>`
        : "";
      const editedNote = field.is_edited
        ? `<span class="field-meta">Edited — original value: ${escapeHtml(field.original_value ?? "—")}</span>`
        : "";

      return `
        <div class="gov-field-card" data-field-name="${escapeHtml(field.field)}">
          <div class="field-card-top">
            <span class="field-name">${escapeHtml(field.field)}</span>
            <span class="${badgeClass(field.confidence_level)}">${escapeHtml(
        field.confidence_level
      )} (${(field.confidence * 100).toFixed(0)}%)</span>
            <span class="${badgeClass(field.decision_status)}">${escapeHtml(field.decision_status)}</span>
            <span class="tag">${field.required ? "required" : "optional"}</span>
          </div>
          <span class="field-value">${escapeHtml(field.current_value ?? "—")}</span>
          <span class="field-meta">Source: ${escapeHtml(field.source_document)} · ${escapeHtml(field.reason)}</span>
          ${editedNote}
          <div class="gov-field-actions">
            <button type="button" class="gov-approve-btn" ${locked ? "disabled" : ""}>Approve</button>
            <input type="text" class="gov-reject-reason" placeholder="Rejection reason" ${locked ? "disabled" : ""} />
            <button type="button" class="gov-reject-btn" ${locked ? "disabled" : ""}>Reject</button>
            <input type="text" class="gov-edit-value" placeholder="Corrected value" ${locked ? "disabled" : ""} />
            <input type="text" class="gov-edit-reason" placeholder="Edit reason" ${locked ? "disabled" : ""} />
            <button type="button" class="gov-edit-btn" ${locked ? "disabled" : ""}>Save Edit</button>
          </div>
          ${decidedNote}
        </div>
      `;
    })
    .join("");

  govFieldsList.querySelectorAll(".gov-field-card").forEach((card) => {
    const fieldName = card.dataset.fieldName;

    card.querySelector(".gov-approve-btn").addEventListener("click", async () => {
      await runFieldDecision(card, () =>
        callGovernanceApi(`/applications/${data.application_id}/fields/${encodeURIComponent(fieldName)}/approve`, {
          actor: currentActor(),
        })
      );
    });

    card.querySelector(".gov-reject-btn").addEventListener("click", async () => {
      const reason = card.querySelector(".gov-reject-reason").value.trim();
      if (!reason) {
        alert("Enter a rejection reason first.");
        return;
      }
      await runFieldDecision(card, () =>
        callGovernanceApi(`/applications/${data.application_id}/fields/${encodeURIComponent(fieldName)}/reject`, {
          actor: currentActor(),
          reason,
        })
      );
    });

    card.querySelector(".gov-edit-btn").addEventListener("click", async () => {
      const newValue = card.querySelector(".gov-edit-value").value.trim();
      const reason = card.querySelector(".gov-edit-reason").value.trim();
      if (!newValue || !reason) {
        alert("Enter both a corrected value and an edit reason first.");
        return;
      }
      await runFieldDecision(card, () =>
        callGovernanceApi(`/applications/${data.application_id}/fields/${encodeURIComponent(fieldName)}/edit`, {
          actor: currentActor(),
          new_value: newValue,
          reason,
        })
      );
    });
  });
}

async function runFieldDecision(card, requestFn) {
  const buttons = card.querySelectorAll("button");
  buttons.forEach((btn) => (btn.disabled = true));
  try {
    const { ok, data, errorText } = await requestFn();
    if (!ok) {
      alert(`Decision failed: ${errorText}`);
      return;
    }
    renderGovApplication(data);
  } catch (error) {
    alert(`Unable to reach Governance Engine at ${GOVERNANCE_BASE}: ${error.message}`);
  } finally {
    buttons.forEach((btn) => (btn.disabled = false));
  }
}

// Thin wrapper around fetch for the Governance Engine: returns a uniform
// { ok, data, errorText } shape so callers don't each repeat try/catch and
// error-detail parsing.
async function callGovernanceApi(path, body, { method = "POST" } = {}) {
  const response = await fetch(`${GOVERNANCE_BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    return { ok: false, errorText: await readErrorDetail(response) };
  }
  return { ok: true, data: await response.json() };
}

async function loadGovApplication(applicationId) {
  govIntakeResult.textContent = "Loading application...";
  try {
    const response = await fetch(`${GOVERNANCE_BASE}/applications/${encodeURIComponent(applicationId)}`);
    if (!response.ok) {
      govIntakeResult.textContent = `Unable to load application: ${await readErrorDetail(response)}`;
      return;
    }
    renderGovApplication(await response.json());
    govIntakeResult.textContent = "";
    loadDelegate(applicationId, { silent: true });
  } catch (error) {
    govIntakeResult.textContent = `Unable to reach Governance Engine at ${GOVERNANCE_BASE}: ${error.message}`;
  }
}

govSendExtractionBtn.addEventListener("click", async () => {
  if (!lastExtractionResult) {
    alert('Run an extraction in "4. AI Field Extraction" first.');
    return;
  }
  const restoreBtn = setButtonBusy(govSendExtractionBtn, "Sending...");
  govIntakeResult.textContent = "Creating governed application...";
  try {
    const payload = {
      applicant_id: lastExtractionResult.applicantId,
      fields: lastExtractionResult.fields.map((f) => ({
        field: f.field,
        value: f.value,
        confidence: f.confidence,
        confidence_level: f.confidence_level,
        source_document: f.source_document,
        reason: f.reason,
      })),
    };
    const response = await fetch(`${GOVERNANCE_BASE}/applications`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      govIntakeResult.textContent = `Unable to create application: ${await readErrorDetail(response)}`;
      return;
    }
    const data = await response.json();
    govLoadApplicationIdInput.value = data.application_id;
    renderGovApplication(data);
    renderDelegate(null);
    govIntakeResult.textContent = `Application ${data.application_id} created from the last extraction.`;
  } catch (error) {
    govIntakeResult.textContent = `Unable to reach Governance Engine at ${GOVERNANCE_BASE}: ${error.message}`;
  } finally {
    restoreBtn();
  }
});

govLoadApplicationBtn.addEventListener("click", () => {
  const applicationId = govLoadApplicationIdInput.value.trim();
  if (!applicationId) {
    alert("Enter an application ID to load.");
    return;
  }
  loadGovApplication(applicationId);
});

govRefreshBtn.addEventListener("click", () => {
  if (!currentGovApplication) return;
  loadGovApplication(currentGovApplication.application_id);
});

govRequestOtpBtn.addEventListener("click", async () => {
  if (!currentGovApplication) return;
  const destination = govOtpDestinationInput.value.trim();
  const restoreBtn = setButtonBusy(govRequestOtpBtn, "Requesting...");
  govOtpResult.textContent = "Requesting OTP...";
  try {
    const { ok, data, errorText } = await callGovernanceApi(
      `/applications/${currentGovApplication.application_id}/otp/request`,
      { destination: destination || undefined }
    );
    if (!ok) {
      govOtpResult.textContent = `OTP request failed: ${errorText}`;
      return;
    }
    govOtpResult.textContent = data.otp_code
      ? `OTP sent via ${data.delivery_channel}. Dev-mode code: ${data.otp_code} (expires ${data.expires_at})`
      : `OTP sent via ${data.delivery_channel}, expires ${data.expires_at}.`;
  } catch (error) {
    govOtpResult.textContent = `Unable to reach Governance Engine at ${GOVERNANCE_BASE}: ${error.message}`;
  } finally {
    restoreBtn();
  }
});

govVerifyOtpBtn.addEventListener("click", async () => {
  if (!currentGovApplication) return;
  const code = govOtpCodeInput.value.trim();
  if (!code) {
    alert("Enter the OTP code first.");
    return;
  }
  const restoreBtn = setButtonBusy(govVerifyOtpBtn, "Verifying...");
  govOtpResult.textContent = "Verifying OTP...";
  try {
    const { ok, data, errorText } = await callGovernanceApi(
      `/applications/${currentGovApplication.application_id}/otp/verify`,
      { code }
    );
    if (!ok) {
      govOtpResult.textContent = `OTP verification failed: ${errorText}`;
      return;
    }
    govOtpResult.textContent = data.detail;
    await loadGovApplication(currentGovApplication.application_id);
  } catch (error) {
    govOtpResult.textContent = `Unable to reach Governance Engine at ${GOVERNANCE_BASE}: ${error.message}`;
  } finally {
    restoreBtn();
  }
});

govValidateBtn.addEventListener("click", async () => {
  if (!currentGovApplication) return;
  govOtpResult.textContent = "Checking submission readiness...";
  try {
    const response = await fetch(
      `${GOVERNANCE_BASE}/applications/${currentGovApplication.application_id}/submission/validate`
    );
    if (!response.ok) {
      govOtpResult.textContent = `Unable to check readiness: ${await readErrorDetail(response)}`;
      return;
    }
    const data = await response.json();
    govOtpResult.textContent = data.can_submit
      ? "Ready to submit — every field is decided and OTP is verified."
      : `Not ready to submit:\n- ${data.blocking_reasons.join("\n- ")}`;
  } catch (error) {
    govOtpResult.textContent = `Unable to reach Governance Engine at ${GOVERNANCE_BASE}: ${error.message}`;
  }
});

govSubmitBtn.addEventListener("click", async () => {
  if (!currentGovApplication) return;
  const confirmSubmit = confirm(
    `Submit application ${currentGovApplication.application_id}? This locks it permanently.`
  );
  if (!confirmSubmit) return;

  const restoreBtn = setButtonBusy(govSubmitBtn, "Submitting...");
  govOtpResult.textContent = "Submitting...";
  try {
    const { ok, data, errorText } = await callGovernanceApi(
      `/applications/${currentGovApplication.application_id}/submit`,
      { actor: currentActor() }
    );
    if (!ok) {
      govOtpResult.textContent = `Submission failed: ${errorText}`;
      return;
    }
    govOtpResult.textContent = `Submitted successfully. Submission hash: ${data.submission_hash}`;
    await loadGovApplication(currentGovApplication.application_id);
  } catch (error) {
    govOtpResult.textContent = `Unable to reach Governance Engine at ${GOVERNANCE_BASE}: ${error.message}`;
  } finally {
    restoreBtn();
  }
});

govAuditLogBtn.addEventListener("click", async () => {
  if (!currentGovApplication) return;
  govAuditResult.textContent = "Loading audit log...";
  try {
    const response = await fetch(
      `${GOVERNANCE_BASE}/applications/${currentGovApplication.application_id}/audit-log`
    );
    if (!response.ok) {
      govAuditResult.textContent = `Unable to load audit log: ${await readErrorDetail(response)}`;
      return;
    }
    const entries = await response.json();
    const rows = entries
      .map(
        (entry) => `
          <tr>
            <td>${entry.sequence_number}</td>
            <td>${escapeHtml(entry.action)}</td>
            <td>${escapeHtml(entry.field_name ?? "—")}</td>
            <td>${escapeHtml(entry.actor)}</td>
            <td>${escapeHtml(entry.created_at)}</td>
          </tr>
        `
      )
      .join("");
    govAuditResult.innerHTML = `
      <table class="gov-audit-table">
        <thead>
          <tr><th>#</th><th>Action</th><th>Field</th><th>Actor</th><th>When</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  } catch (error) {
    govAuditResult.textContent = `Unable to reach Governance Engine at ${GOVERNANCE_BASE}: ${error.message}`;
  }
});

govVerifyChainBtn.addEventListener("click", async () => {
  if (!currentGovApplication) return;
  govAuditResult.textContent = "Verifying audit chain...";
  try {
    const response = await fetch(
      `${GOVERNANCE_BASE}/applications/${currentGovApplication.application_id}/audit-log/verify`
    );
    if (!response.ok) {
      govAuditResult.textContent = `Unable to verify audit chain: ${await readErrorDetail(response)}`;
      return;
    }
    const data = await response.json();
    govAuditResult.textContent = `${data.is_valid ? "✓ Chain intact" : "✗ Chain broken"} — ${data.detail} (${
      data.entries_checked
    } entries checked)`;
  } catch (error) {
    govAuditResult.textContent = `Unable to reach Governance Engine at ${GOVERNANCE_BASE}: ${error.message}`;
  }
});

govDownloadReportBtn.addEventListener("click", async () => {
  if (!currentGovApplication) return;
  const format = govReportFormatSelect.value;
  const restoreBtn = setButtonBusy(govDownloadReportBtn, "Preparing...");
  govAuditResult.textContent = `Generating ${format.toUpperCase()} report...`;
  try {
    const response = await fetch(
      `${GOVERNANCE_BASE}/applications/${currentGovApplication.application_id}/report?format=${format}`
    );
    if (!response.ok) {
      govAuditResult.textContent = `Unable to generate report: ${await readErrorDetail(response)}`;
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `application-${currentGovApplication.application_id}-report.${format}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    govAuditResult.textContent = `Report downloaded (${format.toUpperCase()}).`;
  } catch (error) {
    govAuditResult.textContent = `Unable to reach Governance Engine at ${GOVERNANCE_BASE}: ${error.message}`;
  } finally {
    restoreBtn();
  }
});

/* ------------------------------------------------------------------ */
/* 5b. Trusted Delegate (trust_governance_engine, Phase F)                    */
/* ------------------------------------------------------------------ */

function renderDelegate(delegate) {
  if (!delegate) {
    delegateStatusCard.hidden = true;
    delegateStatusCard.innerHTML = "";
    return;
  }
  delegateStatusCard.hidden = false;

  let statusBadge;
  if (delegate.revoked_at) {
    statusBadge = `<span class="badge badge-rejected">revoked</span>`;
  } else if (delegate.approved) {
    statusBadge = `<span class="badge badge-approved">approved</span>`;
  } else if (delegate.approval_required) {
    statusBadge = `<span class="badge badge-pending">awaiting approval</span>`;
  } else {
    statusBadge = `<span class="badge badge-success">registered (approval not required)</span>`;
  }

  delegateStatusCard.innerHTML = `
    <div class="field-card-top">
      <span class="field-name">${escapeHtml(delegate.delegate_name)}</span>
      <span class="tag">${escapeHtml(delegate.relationship_to_applicant)}</span>
      ${statusBadge}
    </div>
    <span class="field-meta">Contact: ${escapeHtml(delegate.contact)}</span>
    <span class="field-meta">Registered by ${escapeHtml(delegate.consent_given_by)} at ${escapeHtml(
    delegate.consent_given_at || "—"
  )}</span>
    ${delegate.approved_at ? `<span class="field-meta">Approved at ${escapeHtml(delegate.approved_at)}</span>` : ""}
    ${delegate.revoked_at ? `<span class="field-meta">Revoked at ${escapeHtml(delegate.revoked_at)}</span>` : ""}
  `;
}

async function loadDelegate(applicationId, { silent = false } = {}) {
  try {
    const response = await fetch(
      `${GOVERNANCE_BASE}/applications/${encodeURIComponent(applicationId)}/delegate`
    );
    if (response.status === 404) {
      renderDelegate(null);
      if (!silent) delegateResult.textContent = "No active Trusted Delegate is registered for this application.";
      return;
    }
    if (!response.ok) {
      delegateResult.textContent = `Unable to load delegate: ${await readErrorDetail(response)}`;
      return;
    }
    renderDelegate(await response.json());
    if (!silent) delegateResult.textContent = "";
  } catch (error) {
    delegateResult.textContent = `Unable to reach Governance Engine at ${GOVERNANCE_BASE}: ${error.message}`;
  }
}

delegateRegisterBtn.addEventListener("click", async () => {
  if (!currentGovApplication) {
    alert("Load or create an application in section 5 first.");
    return;
  }
  const delegateName = delegateNameInput.value.trim();
  const relationship = delegateRelationshipInput.value.trim();
  const contact = delegateContactInput.value.trim();
  const consentGivenBy = delegateConsentByInput.value.trim() || currentActor();
  if (!delegateName || !relationship || !contact) {
    alert("Enter the delegate's name, relationship, and contact first.");
    return;
  }

  const restoreBtn = setButtonBusy(delegateRegisterBtn, "Registering...");
  delegateResult.textContent = "Registering Trusted Delegate...";
  try {
    const { ok, data, errorText } = await callGovernanceApi(
      `/applications/${currentGovApplication.application_id}/delegate`,
      {
        delegate_name: delegateName,
        relationship_to_applicant: relationship,
        contact,
        approval_required: delegateApprovalRequiredInput.checked,
        consent_given_by: consentGivenBy,
      }
    );
    if (!ok) {
      delegateResult.textContent = `Unable to register delegate: ${errorText}`;
      return;
    }
    renderDelegate(data);
    delegateResult.textContent = `Trusted Delegate "${data.delegate_name}" registered.`;
  } catch (error) {
    delegateResult.textContent = `Unable to reach Governance Engine at ${GOVERNANCE_BASE}: ${error.message}`;
  } finally {
    restoreBtn();
  }
});

delegateLoadBtn.addEventListener("click", () => {
  if (!currentGovApplication) {
    alert("Load or create an application in section 5 first.");
    return;
  }
  loadDelegate(currentGovApplication.application_id);
});

delegateApproveBtn.addEventListener("click", async () => {
  if (!currentGovApplication) {
    alert("Load or create an application in section 5 first.");
    return;
  }
  const restoreBtn = setButtonBusy(delegateApproveBtn, "Approving...");
  delegateResult.textContent = "Recording delegate approval...";
  try {
    const { ok, data, errorText } = await callGovernanceApi(
      `/applications/${currentGovApplication.application_id}/delegate/approve`,
      { actor: currentActor() }
    );
    if (!ok) {
      delegateResult.textContent = `Unable to approve as delegate: ${errorText}`;
      return;
    }
    renderDelegate(data);
    delegateResult.textContent = "Delegate approval recorded. Refresh the application above to see it unblock.";
  } catch (error) {
    delegateResult.textContent = `Unable to reach Governance Engine at ${GOVERNANCE_BASE}: ${error.message}`;
  } finally {
    restoreBtn();
  }
});

delegateRevokeBtn.addEventListener("click", async () => {
  if (!currentGovApplication) {
    alert("Load or create an application in section 5 first.");
    return;
  }
  const confirmRevoke = confirm("Revoke the current Trusted Delegate for this application?");
  if (!confirmRevoke) return;

  const restoreBtn = setButtonBusy(delegateRevokeBtn, "Revoking...");
  delegateResult.textContent = "Revoking Trusted Delegate...";
  try {
    const { ok, data, errorText } = await callGovernanceApi(
      `/applications/${currentGovApplication.application_id}/delegate/revoke`,
      { actor: currentActor() }
    );
    if (!ok) {
      delegateResult.textContent = `Unable to revoke delegate: ${errorText}`;
      return;
    }
    renderDelegate(data);
    delegateResult.textContent = "Trusted Delegate revoked.";
  } catch (error) {
    delegateResult.textContent = `Unable to reach Governance Engine at ${GOVERNANCE_BASE}: ${error.message}`;
  } finally {
    restoreBtn();
  }
});

/* ------------------------------------------------------------------ */
/* Init                                                                 */
/* ------------------------------------------------------------------ */

// Seed one document row in each builder so the forms aren't empty on load.
buildDocRow(validationDocRows, validationDocRowCount++, { withMetadata: true });
buildDocRow(extractionDocRows, extractionDocRowCount++, { withMetadata: false });

loadPortals();
loadReferenceCatalog();
loadServiceCatalog();
