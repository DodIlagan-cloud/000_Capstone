// M12 - Email Ingestion Module Start
// Drives the Email Setup page for centrally stored mailbox source profiles.
const emailState = document.querySelector("#email-setup-state");
const emailFormState = document.querySelector("#email-form-state");
const emailRunState = document.querySelector("#email-run-state");
const sourceForm = document.querySelector("#email-source-form");
const sourceFormTitle = document.querySelector("#email-source-form-title");
const appPasswordHint = document.querySelector("#email-app-password-hint");
const sourcesEmpty = document.querySelector("#email-sources-empty");
const sourcesTableWrap = document.querySelector("#email-sources-table-wrap");
const sourcesTableBody = document.querySelector("#email-sources-table-body");
const sourcesCount = document.querySelector("#email-sources-count");
const sourcesPagination = document.querySelector("#email-sources-pagination");
const runTableWrap = document.querySelector("#email-run-table-wrap");
const runTableBody = document.querySelector("#email-run-table-body");
const runPagination = document.querySelector("#email-run-pagination");
const selectedSourceIdInput = document.querySelector("#email-source-id");
const providerInput = document.querySelector("#email-provider");
const customImapFields = document.querySelector("#email-custom-imap-fields");
const pollingCadenceInput = document.querySelector("#email-polling-cadence");
const pollingTimeField = document.querySelector("#email-polling-time-field");
const pdfRulesList = document.querySelector("#email-pdf-rules-list");
const pdfRulesEmpty = document.querySelector("#email-pdf-rules-empty");
const pdfRulesCount = document.querySelector("#email-pdf-rules-count");
const pdfRulesSection = document.querySelector("#email-pdf-rules-section");
const pdfRuleTemplate = document.querySelector("#email-pdf-rule-template");
const dryRunButton = document.querySelector("#email-dry-run-button");
const importRunButton = document.querySelector("#email-import-run-button");
const ingestDbButton = document.querySelector("#email-ingest-db-button");
const runMaxMessagesInput = document.querySelector("#email-run-max-messages");
const runNoLimitInput = document.querySelector("#email-run-no-limit");
const runMetrics = {
  messages: document.querySelector("#email-run-messages"),
  attachments: document.querySelector("#email-run-attachments"),
  imported: document.querySelector("#email-run-imported"),
  passwords: document.querySelector("#email-run-passwords"),
};
const recentRunsEmpty = document.querySelector("#email-recent-runs-empty");
const recentRunsTableWrap = document.querySelector("#email-recent-runs-table-wrap");
const recentRunsBody = document.querySelector("#email-recent-runs-body");
const recentRunsCount = document.querySelector("#email-recent-runs-count");

const RECENT_RUNS_LIMIT = 5;

let emailSources = [];
let selectedSourceId = "";
let sourcesPage = 1;
let runCandidates = [];
let runPage = 1;
let latestImportRunId = "";
const SOURCES_PAGE_SIZE = 10;
const RUN_PAGE_SIZE = 10;

function emailApiUrl(path) {
  return window.statsAccess.apiUrl(path);
}

function setEmailState(message, tone = "pending") {
  emailState.textContent = message;
  emailState.dataset.tone = tone;
}

function setEmailFormState(message, tone = "pending") {
  if (!emailFormState) {
    return;
  }
  emailFormState.textContent = message;
  emailFormState.dataset.tone = tone;
}

function setRunState(message, tone = "pending") {
  emailRunState.textContent = message;
  emailRunState.dataset.tone = tone;
}

function setRunButtonsDisabled(isDisabled) {
  dryRunButton.disabled = isDisabled;
  importRunButton.disabled = isDisabled;
  if (ingestDbButton) {
    ingestDbButton.disabled = isDisabled;
  }
}

function selectedRunMaxMessages() {
  if (runNoLimitInput.checked) {
    return 0;
  }
  const value = Number(runMaxMessagesInput.value || 25);
  return Math.max(1, Math.floor(value));
}

function updateRunLimitControl() {
  runMaxMessagesInput.disabled = runNoLimitInput.checked;
}

function csvValues(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function slugValue(value, fallback = "pdf-password") {
  const slug = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || fallback;
}

function ruleField(card, name) {
  return card.querySelector(`[data-rule-field="${name}"]`);
}

function ruleFieldValue(card, name) {
  const field = ruleField(card, name);
  return field ? field.value.trim() : "";
}

function updatePdfRulesEmptyState() {
  const count = pdfRulesList.querySelectorAll("[data-pdf-rule]").length;
  pdfRulesEmpty.hidden = count > 0;
  if (pdfRulesCount) {
    pdfRulesCount.textContent = `${count} saved`;
  }
}

function updateRuleTitle(card) {
  const title = card.querySelector("[data-pdf-rule-title]");
  if (!title) {
    return;
  }
  const label = ruleFieldValue(card, "display_name") || ruleFieldValue(card, "password_secret_ref");
  title.textContent = label || "New password";
}

function addPdfRule(rule = {}) {
  const card = pdfRuleTemplate.content.firstElementChild.cloneNode(true);
  ruleField(card, "rule_id").value = rule.rule_id || "";
  ruleField(card, "display_name").value = rule.display_name || "";
  ruleField(card, "password_secret_ref").value = rule.password_secret_ref || "";
  ruleField(card, "password").value = "";
  ruleField(card, "enabled").checked = rule.enabled !== false;

  card.querySelector("[data-pdf-rule-remove]").addEventListener("click", () => {
    card.remove();
    updatePdfRulesEmptyState();
  });
  const passwordField = ruleField(card, "password");
  const passwordToggle = card.querySelector(".password-toggle");
  if (passwordField && passwordToggle) {
    passwordToggle.textContent = "Show";
    passwordToggle.addEventListener("click", () => {
      const isVisible = passwordField.type === "text";
      passwordField.type = isVisible ? "password" : "text";
      passwordToggle.textContent = isVisible ? "Show" : "Hide";
      passwordToggle.setAttribute("aria-label", `${isVisible ? "Show" : "Hide"} PDF password`);
      passwordToggle.title = `${isVisible ? "Show" : "Hide"} PDF password`;
    });
  }
  ruleField(card, "display_name").addEventListener("input", () => updateRuleTitle(card));
  ruleField(card, "password_secret_ref").addEventListener("input", () => updateRuleTitle(card));

  pdfRulesList.append(card);
  updateRuleTitle(card);
  updatePdfRulesEmptyState();
  return card;
}

function renderPdfRules(rules) {
  pdfRulesList.replaceChildren();
  (rules || []).forEach((rule) => addPdfRule(rule));
  updatePdfRulesEmptyState();
  if (pdfRulesSection) {
    pdfRulesSection.open = false;
  }
}

function collectPdfRules() {
  const rules = [];
  pdfRulesList.querySelectorAll("[data-pdf-rule]").forEach((card) => {
    const ruleId = ruleFieldValue(card, "rule_id");
    const displayName = ruleFieldValue(card, "display_name");
    const secretRef = ruleFieldValue(card, "password_secret_ref");
    if (!ruleId && !displayName && !secretRef) {
      return;
    }
    if (!secretRef) {
      throw new Error(`Saved PDF password "${displayName || "unnamed"}" needs a password secret reference.`);
    }
    const generatedRuleId = ruleId || slugValue(displayName || secretRef);
    const rule = {
      rule_id: generatedRuleId,
      display_name: displayName || generatedRuleId,
      password_secret_ref: secretRef,
      sender_contains: [],
      subject_contains: [],
      filename_contains: [],
      enabled: ruleField(card, "enabled").checked,
    };
    const password = ruleFieldValue(card, "password");
    if (password) {
      rule.password = password;
    }
    rules.push(rule);
  });
  return rules;
}

function formatStatus(value) {
  return String(value || "unknown").replaceAll("_", " ");
}

function formatLastRun(source) {
  if (source.last_run_at) {
    return formatRunTime(source.last_run_at);
  }
  // Ran before the timestamp was recorded vs never ran.
  return source.last_run_status ? "—" : "Never";
}

function authJsonHeaders() {
  return {
    ...window.statsAccess.authHeaders(),
    "Content-Type": "application/json",
  };
}

async function errorMessageFromResponse(response, fallback) {
  let detail = "";
  try {
    const payload = await response.json();
    detail = payload?.detail?.message || payload?.detail || payload?.message || payload?.error || "";
  } catch {
    try {
      detail = await response.text();
    } catch {
      detail = "";
    }
  }

  if (typeof detail !== "string") {
    detail = JSON.stringify(detail);
  }
  detail = detail.trim();
  return detail ? `${fallback} ${detail}` : fallback;
}

function updateProviderFields() {
  const isCustomImap = providerInput.value === "custom_imap";
  customImapFields.hidden = !isCustomImap;
  sourceForm.elements.imap_host.required = isCustomImap;
}

function updatePollingFields() {
  if (pollingTimeField) {
    pollingTimeField.hidden = pollingCadenceInput.value !== "daily";
  }
}

function updateAppPasswordHint(hasSavedSecret) {
  if (!appPasswordHint) {
    return;
  }
  appPasswordHint.textContent = hasSavedSecret
    ? "Saved mailbox app password is available. Leave blank to keep using it."
    : "Enter once to save or replace the mailbox app password.";
}

function profilePayload() {
  const form = new FormData(sourceForm);
  const maxMb = Number(form.get("max_attachment_mb") || 25);
  const passwordRules = collectPdfRules();
  const payload = {
    source_id: form.get("source_id") || undefined,
    display_name: form.get("display_name"),
    provider: form.get("provider") || "custom_imap",
    email_address: form.get("email_address"),
    enabled: form.get("enabled") === "on",
    folder: form.get("folder") || "Inbox",
    connection_settings: {
      imap_host: form.get("imap_host") || null,
      imap_port: 993,
      use_ssl: true,
    },
    sender_allowlist: csvValues(form.get("sender_allowlist")),
    subject_contains: csvValues(form.get("subject_contains")),
    attachment_policy: {
      allowed_extensions: [".pdf"],
      allowed_mime_types: ["application/pdf"],
      max_attachment_size_bytes: Math.max(1, maxMb) * 1024 * 1024,
    },
    pdf_password_policy: {
      default_action: form.get("pdf_default_action") || "ask_user",
      password_secret_ref: form.get("pdf_password_secret_ref") || null,
      password_rules: passwordRules,
      allow_one_time_password: true,
    },
    post_process_policy: {
      mark_as_read: false,
      move_to_folder: null,
    },
    polling_schedule: {
      cadence: form.get("polling_cadence") || "off",
      time_of_day: form.get("polling_time") || null,
    },
  };

  const appPassword = form.get("app_password");
  const secretRef = form.get("secret_ref");
  if (appPassword) {
    payload.app_password = appPassword;
  }
  if (secretRef) {
    payload.secret_ref = secretRef;
  }
  return payload;
}

async function loadSources() {
  setEmailState("Loading email sources.", "pending");
  try {
    const response = await fetch(emailApiUrl("/api/v1/email-ingestion-sources"), {
      headers: window.statsAccess.authHeaders(),
    });
    if (!response.ok) {
      throw new Error("Email source profiles could not be loaded.");
    }
    const payload = await response.json();
    emailSources = payload.sources || [];
    renderSources();
    setEmailState(`${emailSources.length} source${emailSources.length === 1 ? "" : "s"} loaded.`, "success");
  } catch (error) {
    setEmailState(error.message || "Email source profiles could not be loaded.", "error");
  }
}

function renderSources() {
  sourcesTableBody.replaceChildren();
  if (sourcesCount) {
    sourcesCount.textContent = `${emailSources.length} source${emailSources.length === 1 ? "" : "s"}`;
  }
  if (!emailSources.length) {
    sourcesEmpty.hidden = false;
    sourcesTableWrap.hidden = true;
    renderSourcesPagination(0);
    return;
  }

  const pageCount = Math.ceil(emailSources.length / SOURCES_PAGE_SIZE);
  sourcesPage = Math.min(Math.max(1, sourcesPage), pageCount);
  const pageStart = (sourcesPage - 1) * SOURCES_PAGE_SIZE;
  const visibleSources = emailSources.slice(pageStart, pageStart + SOURCES_PAGE_SIZE);

  visibleSources.forEach((source) => {
    const row = document.createElement("tr");
    const profileCell = document.createElement("td");
    const profileName = document.createElement("strong");
    profileName.textContent = source.display_name;
    const provider = document.createElement("p");
    provider.className = "table-note";
    provider.textContent = source.provider;
    profileCell.append(profileName, provider);

    const emailCell = document.createElement("td");
    emailCell.textContent = source.email_address;
    const folderCell = document.createElement("td");
    folderCell.textContent = source.folder;
    const statusCell = document.createElement("td");
    const status = document.createElement("span");
    status.className = "state-pill";
    status.textContent = formatStatus(source.connection_status);
    statusCell.append(status);
    const runCell = document.createElement("td");
    runCell.textContent = formatLastRun(source);

    const actionCell = document.createElement("td");
    const actionGroup = document.createElement("div");
    actionGroup.className = "row-actions";
    actionGroup.style.flexWrap = "nowrap";
    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.className = "secondary-action";
    editButton.textContent = "Select";
    editButton.addEventListener("click", () => selectSource(source.source_id));
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "secondary-action";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", () => confirmDeleteSource(actionGroup, source.source_id, source.display_name));
    actionGroup.append(editButton, deleteButton);
    actionCell.append(actionGroup);

    row.append(profileCell, emailCell, folderCell, statusCell, runCell, actionCell);
    sourcesTableBody.append(row);
  });

  sourcesEmpty.hidden = true;
  sourcesTableWrap.hidden = false;
  renderSourcesPagination(pageCount);
}

function renderSourcesPagination(pageCount) {
  if (!sourcesPagination) {
    return;
  }
  sourcesPagination.replaceChildren();
  sourcesPagination.hidden = pageCount <= 1;
  if (pageCount <= 1) {
    return;
  }

  for (let page = 1; page <= pageCount; page += 1) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary-action email-page-button";
    button.textContent = String(page);
    button.setAttribute("aria-label", `Show configured mailbox page ${page}`);
    button.setAttribute("aria-current", page === sourcesPage ? "page" : "false");
    button.disabled = page === sourcesPage;
    button.addEventListener("click", () => {
      sourcesPage = page;
      renderSources();
    });
    sourcesPagination.append(button);
  }
}

function renderPagination(container, pageCount, currentPage, onPageSelected, labelPrefix) {
  if (!container) {
    return;
  }
  container.replaceChildren();
  container.hidden = pageCount <= 1;
  if (pageCount <= 1) {
    return;
  }

  for (let page = 1; page <= pageCount; page += 1) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary-action email-page-button";
    button.textContent = String(page);
    button.setAttribute("aria-label", `${labelPrefix} ${page}`);
    button.setAttribute("aria-current", page === currentPage ? "page" : "false");
    button.disabled = page === currentPage;
    button.addEventListener("click", () => onPageSelected(page));
    container.append(button);
  }
}

function selectSource(sourceId) {
  const source = emailSources.find((item) => item.source_id === sourceId);
  if (!source) {
    return;
  }
  const fields = sourceForm.elements;
  selectedSourceId = source.source_id;
  selectedSourceIdInput.value = source.source_id;
  // New source context: drop any remembered import run so "Ingest to database"
  // falls back to this source's latest import run rather than another source's.
  latestImportRunId = "";
  sourceFormTitle.textContent = `Edit ${source.display_name}`;
  fields.display_name.value = source.display_name || "";
  fields.provider.value = source.provider || "custom_imap";
  fields.email_address.value = source.email_address || "";
  fields.app_password.value = "";
  fields.app_password.placeholder = source.secret_ref ? "Saved secret will be used" : "";
  fields.secret_ref.value = source.secret_ref || "";
  fields.folder.value = source.folder || "Inbox";
  fields.imap_host.value = source.connection_settings?.imap_host || "";
  fields.sender_allowlist.value = (source.sender_allowlist || []).join(", ");
  fields.subject_contains.value = (source.subject_contains || []).join(", ");
  fields.allowed_extensions.value = (source.attachment_policy?.allowed_extensions || [".pdf"]).join(", ");
  fields.max_attachment_mb.value = Math.round((source.attachment_policy?.max_attachment_size_bytes || 26214400) / 1024 / 1024);
  fields.pdf_default_action.value = source.pdf_password_policy?.default_action || "ask_user";
  fields.pdf_password_secret_ref.value = source.pdf_password_policy?.password_secret_ref || "";
  renderPdfRules(source.pdf_password_policy?.password_rules || []);
  fields.polling_cadence.value = source.polling_schedule?.cadence || "off";
  fields.polling_time.value = source.polling_schedule?.time_of_day || "00:00";
  fields.enabled.checked = source.enabled !== false;
  updateProviderFields();
  updatePollingFields();
  updateAppPasswordHint(Boolean(source.secret_ref));
  setRunState(`Selected ${source.display_name}.`, "success");
  setEmailFormState(`Selected ${source.display_name}.`, "success");
  loadRecentRuns(source.source_id);
}

function resetForm() {
  latestImportRunId = "";
  const fields = sourceForm.elements;
  selectedSourceId = "";
  sourceForm.reset();
  selectedSourceIdInput.value = "";
  fields.folder.value = "Inbox";
  fields.provider.value = "custom_imap";
  fields.imap_host.value = "";
  fields.app_password.placeholder = "";
  fields.allowed_extensions.value = ".pdf";
  fields.max_attachment_mb.value = "25";
  fields.pdf_default_action.value = "ask_user";
  renderPdfRules([]);
  fields.polling_cadence.value = "off";
  fields.polling_time.value = "00:00";
  fields.enabled.checked = true;
  sourceFormTitle.textContent = "Add mailbox source";
  updateProviderFields();
  updatePollingFields();
  updateAppPasswordHint(false);
  setRunState("Select a source profile.", "pending");
  setEmailFormState("", "pending");
  loadRecentRuns("");
}

function confirmDeleteSource(group, sourceId, displayName) {
  // Themed inline confirmation (same button/tone classes as the rest of the page)
  // instead of the browser's native, unstyled confirm dialog.
  group.replaceChildren();
  const prompt = document.createElement("span");
  prompt.className = "table-note";
  prompt.textContent = "Delete profile?";
  const confirmButton = document.createElement("button");
  confirmButton.type = "button";
  confirmButton.className = "secondary-action";
  confirmButton.textContent = "Confirm";
  confirmButton.addEventListener("click", () => deleteSource(sourceId, displayName));
  const cancelButton = document.createElement("button");
  cancelButton.type = "button";
  cancelButton.className = "secondary-action";
  cancelButton.textContent = "Cancel";
  cancelButton.addEventListener("click", () => renderSources());
  group.append(prompt, confirmButton, cancelButton);
}

async function deleteSource(sourceId, displayName) {
  const label = displayName || sourceId;
  setEmailState(`Deleting ${label}.`, "pending");
  try {
    const response = await fetch(emailApiUrl(`/api/v1/email-ingestion-sources/${encodeURIComponent(sourceId)}`), {
      method: "DELETE",
      headers: window.statsAccess.authHeaders(),
    });
    if (!response.ok) {
      throw new Error(await errorMessageFromResponse(response, "Email source profile could not be deleted."));
    }
    setEmailState(`${label} deleted.`, "success");
    if (selectedSourceIdInput.value === sourceId) {
      resetForm();
    }
    await loadSources();
  } catch (error) {
    setEmailState(error.message || "Email source profile could not be deleted.", "error");
  }
}

async function saveSource(event) {
  event.preventDefault();
  const isUpdate = Boolean(selectedSourceIdInput.value);
  const url = isUpdate
    ? `/api/v1/email-ingestion-sources/${encodeURIComponent(selectedSourceIdInput.value)}`
    : "/api/v1/email-ingestion-sources";

  setEmailState("Saving source profile.", "pending");
  setEmailFormState("Saving source profile.", "pending");
  try {
    const payload = profilePayload();
    const response = await fetch(emailApiUrl(url), {
      method: isUpdate ? "PATCH" : "POST",
      headers: authJsonHeaders(),
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(await errorMessageFromResponse(response, "Email source profile could not be saved."));
    }
    const saved = await response.json();
    selectedSourceId = saved.source_id;
    setEmailState(`${saved.display_name} saved.`, "success");
    setEmailFormState(`${saved.display_name} saved.`, "success");
    await loadSources();
    selectSource(saved.source_id);
  } catch (error) {
    setEmailState(error.message || "Email source profile could not be saved.", "error");
    setEmailFormState(error.message || "Email source profile could not be saved.", "error");
  }
}

async function testConnection() {
  if (!selectedSourceIdInput.value) {
    setEmailState("Save the source before testing connection.", "error");
    setEmailFormState("Save the source before testing connection.", "error");
    return;
  }
  setEmailState("Testing mailbox connection.", "pending");
  setEmailFormState("Testing mailbox connection.", "pending");
  try {
    const response = await fetch(emailApiUrl(`/api/v1/email-ingestion-sources/${encodeURIComponent(selectedSourceIdInput.value)}/test-connection`), {
      method: "POST",
      headers: authJsonHeaders(),
      body: JSON.stringify({
        app_password: sourceForm.elements.app_password.value || null,
        folder: sourceForm.elements.folder.value || "Inbox",
      }),
    });
    if (!response.ok) {
      throw new Error(await errorMessageFromResponse(response, "Connection test could not be completed."));
    }
    const result = await response.json();
    setEmailState(result.message, result.status === "connected" ? "success" : "error");
    setEmailFormState(result.message, result.status === "connected" ? "success" : "error");
    await loadSources();
  } catch (error) {
    setEmailState(error.message || "Connection test could not be completed.", "error");
    setEmailFormState(error.message || "Connection test could not be completed.", "error");
  }
}

function selectedSourceFilterNote() {
  const selected = emailSources.find((item) => item.source_id === selectedSourceIdInput.value);
  const senders = selected?.sender_allowlist || [];
  const subjects = selected?.subject_contains || [];
  if (!senders.length && !subjects.length) {
    return " - no sender/subject filters set; newest attachments are retrieved";
  }
  const parts = [];
  if (senders.length) {
    parts.push(`${senders.length} sender${senders.length === 1 ? "" : "s"}`);
  }
  if (subjects.length) {
    parts.push(`${subjects.length} subject keyword${subjects.length === 1 ? "" : "s"}`);
  }
  return ` - filters: ${parts.join(", ")}`;
}

async function runIngestion(dryRun) {
  if (!selectedSourceIdInput.value) {
    setRunState("Select a source profile first.", "error");
    return;
  }
  setRunState("Connecting to the mailbox and processing messages...", "pending");
  setRunButtonsDisabled(true);
  runTableBody.replaceChildren();
  runTableWrap.hidden = true;
  runCandidates = [];
  renderRunPagination(0);

  try {
    const response = await fetch(emailApiUrl("/api/v1/email-ingestions/automated-runs"), {
      method: "POST",
      headers: authJsonHeaders(),
      body: JSON.stringify({
        source_id: selectedSourceIdInput.value,
        mode: dryRun ? "dry_run" : "handoff",
        retrieval: {
          mailbox_folder: sourceForm.elements.folder.value || "Inbox",
          max_messages: selectedRunMaxMessages(),
        },
        policy: {
          dry_run: dryRun,
          handoff_to_file_ingestion: !dryRun,
          deduplicate: true,
          detect_password_protected_pdfs: true,
        },
      }),
    });
    if (!response.ok) {
      throw new Error(await errorMessageFromResponse(response, "Email ingestion run could not be completed."));
    }
    const result = await response.json();
    renderRun(result);
    if (!dryRun) {
      latestImportRunId = result.run_id || "";
    }
    await loadSources();
    await loadRecentRuns(selectedSourceIdInput.value);
  } catch (error) {
    setRunState(error.message || "Email ingestion run could not be completed.", "error");
  } finally {
    setRunButtonsDisabled(false);
  }
}

async function ingestToDatabase() {
  if (!selectedSourceIdInput.value) {
    setRunState("Select a source profile first.", "error");
    return;
  }
  setRunState("Ingesting imported files to the database...", "pending");
  setRunButtonsDisabled(true);
  try {
    const response = await fetch(emailApiUrl("/api/v1/email-ingestions/process-imported"), {
      method: "POST",
      headers: authJsonHeaders(),
      body: JSON.stringify({
        source_id: selectedSourceIdInput.value,
        run_id: latestImportRunId || null,
      }),
    });
    if (!response.ok) {
      throw new Error(await errorMessageFromResponse(response, "Ingest to database could not be completed."));
    }
    const result = await response.json();
    if (result.status === "no_imported_files") {
      setRunState("No imported files to ingest. Run import first.", "pending");
    } else {
      setRunState(
        `${formatStatus(result.status)} - ${result.processed_count} processed, ${result.succeeded_count} saved to database, ${result.failed_count} failed (${result.saved_record_count} records, ${result.review_item_count} for review).`,
        result.status === "failed" ? "error" : "success"
      );
    }
    await loadRecentRuns(selectedSourceIdInput.value);
  } catch (error) {
    setRunState(error.message || "Ingest to database could not be completed.", "error");
  } finally {
    setRunButtonsDisabled(false);
  }
}

function renderRun(result) {
  runMetrics.messages.textContent = String(result.summary?.message_count || 0);
  runMetrics.attachments.textContent = String(result.summary?.attachment_count || 0);
  runMetrics.imported.textContent = String(result.summary?.handed_off_count || result.summary?.retrieved_count || 0);
  runMetrics.passwords.textContent = String(result.summary?.password_required_count || 0);

  runCandidates = result.candidates || [];
  runPage = 1;
  renderRunCandidates();

  const summary = result.summary || {};
  const imported = summary.handed_off_count || summary.retrieved_count || 0;
  const locked = summary.password_required_count || 0;
  const failureDetail = runFailureMessage(result);
  setRunState(
    failureDetail
      ? `${formatStatus(result.status)} - ${failureDetail}`
      : `${formatStatus(result.status)} - ${summary.attachment_count || 0} attachments, ${imported} imported, ${locked} locked.${selectedSourceFilterNote()}`,
    result.status === "failed" ? "error" : "success"
  );
}

function runFailureMessage(result) {
  if (result.status !== "failed") {
    return "";
  }
  const findings = result.findings || [];
  const finding = findings.find((item) => item.severity === "error") || findings[0];
  return finding?.message || "";
}

function renderRunCandidates() {
  runTableBody.replaceChildren();
  const pageCount = Math.ceil(runCandidates.length / RUN_PAGE_SIZE);
  runPage = pageCount > 0 ? Math.min(Math.max(1, runPage), pageCount) : 1;
  const pageStart = (runPage - 1) * RUN_PAGE_SIZE;
  const visibleCandidates = runCandidates.slice(pageStart, pageStart + RUN_PAGE_SIZE);

  visibleCandidates.forEach((candidate) => {
    const row = document.createElement("tr");
    const fileCell = document.createElement("td");
    fileCell.textContent = candidate.filename;
    const statusCell = document.createElement("td");
    const status = document.createElement("span");
    status.className = "state-pill";
    status.textContent = formatStatus(candidate.status);
    statusCell.append(status);
    const senderCell = document.createElement("td");
    senderCell.textContent = candidate.source?.sender || "";
    const findingCell = document.createElement("td");
    findingCell.textContent = (candidate.findings || []).map((finding) => finding.code).join(", ") || "None";
    row.append(fileCell, statusCell, senderCell, findingCell);
    runTableBody.append(row);
  });

  runTableWrap.hidden = !runCandidates.length;
  renderRunPagination(pageCount);
}

function renderRunPagination(pageCount) {
  renderPagination(runPagination, pageCount, runPage, (page) => {
    runPage = page;
    renderRunCandidates();
  }, "Show email ingestion result page");
}

function formatRunTime(value) {
  if (!value) {
    return "Unknown time";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return parsed.toLocaleString();
}

function runIssueText(run) {
  if (run.error_message) {
    return run.error_message;
  }
  const summary = run.summary || {};
  const parts = [];
  if (summary.duplicate_count) {
    parts.push(`${summary.duplicate_count} duplicate`);
  }
  if (summary.password_required_count) {
    parts.push(`${summary.password_required_count} locked`);
  }
  if (summary.skipped_count) {
    parts.push(`${summary.skipped_count} skipped`);
  }
  if (summary.failed_count) {
    parts.push(`${summary.failed_count} failed`);
  }
  return parts.join(", ") || "None";
}

async function loadRecentRuns(sourceId) {
  if (!recentRunsBody) {
    return;
  }
  recentRunsBody.replaceChildren();
  if (!sourceId) {
    recentRunsEmpty.hidden = false;
    recentRunsEmpty.textContent = "Select a source profile to see its recent runs.";
    recentRunsTableWrap.hidden = true;
    recentRunsCount.textContent = "0 runs";
    return;
  }
  try {
    const response = await fetch(
      emailApiUrl(`/api/v1/email-ingestions/runs?source_id=${encodeURIComponent(sourceId)}&limit=${RECENT_RUNS_LIMIT}`),
      { headers: window.statsAccess.authHeaders() }
    );
    if (!response.ok) {
      throw new Error("Recent runs could not be loaded.");
    }
    const payload = await response.json();
    const runs = payload.runs || [];
    recentRunsCount.textContent = `${runs.length} run${runs.length === 1 ? "" : "s"}`;
    if (!runs.length) {
      recentRunsEmpty.hidden = false;
      recentRunsEmpty.textContent = "No runs recorded yet.";
      recentRunsTableWrap.hidden = true;
      return;
    }

    runs.forEach((run) => {
      const summary = run.summary || {};
      const imported = summary.handed_off_count || 0;
      const row = document.createElement("tr");
      // Keep the run UUID out of the visible cells but available for traceability.
      row.title = `Run ${run.run_id}`;

      const whenCell = document.createElement("td");
      whenCell.textContent = formatRunTime(run.started_at);
      const statusCell = document.createElement("td");
      const status = document.createElement("span");
      status.className = "state-pill";
      status.textContent = formatStatus(run.status);
      statusCell.append(status);
      const attachmentsCell = document.createElement("td");
      attachmentsCell.textContent = String(summary.attachment_count || 0);
      const importedCell = document.createElement("td");
      importedCell.textContent = String(imported);
      const issueCell = document.createElement("td");
      issueCell.textContent = runIssueText(run);

      row.append(whenCell, statusCell, attachmentsCell, importedCell, issueCell);
      recentRunsBody.append(row);
    });

    recentRunsEmpty.hidden = true;
    recentRunsTableWrap.hidden = false;
  } catch (error) {
    recentRunsEmpty.hidden = false;
    recentRunsEmpty.textContent = error.message || "Recent runs could not be loaded.";
    recentRunsTableWrap.hidden = true;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.statsAccess.initPasswordVisibilityToggles();
  document.querySelector("#email-refresh-button").addEventListener("click", loadSources);
  document.querySelector("#email-new-source-button").addEventListener("click", resetForm);
  document.querySelector("#email-add-pdf-rule-button").addEventListener("click", () => addPdfRule());
  document.querySelector("#email-test-source-button").addEventListener("click", testConnection);
  dryRunButton.addEventListener("click", () => runIngestion(true));
  importRunButton.addEventListener("click", () => runIngestion(false));
  if (ingestDbButton) {
    ingestDbButton.addEventListener("click", ingestToDatabase);
  }
  runNoLimitInput.addEventListener("change", updateRunLimitControl);
  providerInput.addEventListener("change", updateProviderFields);
  pollingCadenceInput.addEventListener("change", updatePollingFields);
  sourceForm.addEventListener("submit", saveSource);
  updateProviderFields();
  updatePollingFields();
  updateRunLimitControl();
  loadSources();
});
// M12 End
