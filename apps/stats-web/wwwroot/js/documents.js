// M9 - Stats Data and Persistence Start
// Shows recent persisted documents and lets the user remove records saved for one uploaded file.
const documentsState = document.querySelector("#documents-state");
const documentsEmpty = document.querySelector("#documents-empty");
const documentsTableWrap = document.querySelector("#documents-table-wrap");
const documentsTableBody = document.querySelector("#documents-table-body");
const statsDataBaseUrl = document.body.dataset.statsDataBaseUrl ?? "";

function documentsApiUrl(path) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const normalizedBase = (statsDataBaseUrl || "").trim().replace(/\/+$/, "");
  return normalizedBase ? `${normalizedBase}${normalizedPath}` : normalizedPath;
}

function setDocumentsState(message, tone = "pending") {
  documentsState.textContent = message;
  documentsState.dataset.tone = tone;
}

function formatDateTime(value) {
  if (!value) {
    return "Pending";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function formatStatus(value) {
  return String(value || "unknown").replaceAll("_", " ");
}

async function loadDocuments() {
  setDocumentsState("Loading documents.", "pending");
  documentsEmpty.hidden = true;
  documentsTableWrap.hidden = true;
  documentsTableBody.replaceChildren();

  try {
    const response = await fetch(documentsApiUrl("/api/v1/documents?limit=25"), {
      headers: window.statsAccess.authHeaders(),
    });

    if (!response.ok) {
      throw new Error("Document records could not be loaded.");
    }

    const payload = await response.json();
    renderDocuments(payload.documents || []);
  } catch (error) {
    setDocumentsState(error.message || "Document records could not be loaded.", "error");
  }
}

function renderDocuments(documents) {
  documentsTableBody.replaceChildren();

  if (!documents.length) {
    documentsEmpty.hidden = false;
    documentsTableWrap.hidden = true;
    setDocumentsState("No saved documents.", "success");
    return;
  }

  documents.forEach((documentRecord) => {
    const row = document.createElement("tr");

    const fileCell = document.createElement("td");
    const fileName = document.createElement("strong");
    fileName.textContent = documentRecord.original_filename || "Uploaded document";
    const details = document.createElement("p");
    details.className = "table-note";
    details.textContent = [
      documentRecord.document_type || "unknown",
      documentRecord.source_institution || "institution pending",
    ].join(" · ");
    fileCell.append(fileName, details);

    const statusCell = document.createElement("td");
    const status = document.createElement("span");
    status.className = "state-pill";
    status.textContent = formatStatus(documentRecord.status);
    statusCell.append(status);

    const rowsCell = document.createElement("td");
    rowsCell.textContent = String(documentRecord.transaction_count || 0);

    const reviewCell = document.createElement("td");
    reviewCell.textContent = String(documentRecord.review_item_count || 0);

    const savedCell = document.createElement("td");
    savedCell.textContent = formatDateTime(documentRecord.created_at_utc);

    const actionCell = document.createElement("td");
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "secondary-action danger-action";
    deleteButton.textContent = "Remove";
    deleteButton.addEventListener("click", () => removeDocument(documentRecord, deleteButton));
    actionCell.append(deleteButton);

    row.append(fileCell, statusCell, rowsCell, reviewCell, savedCell, actionCell);
    documentsTableBody.append(row);
  });

  documentsEmpty.hidden = true;
  documentsTableWrap.hidden = false;
  setDocumentsState(`${documents.length} document${documents.length === 1 ? "" : "s"} loaded.`, "success");
}

async function removeDocument(documentRecord, button) {
  const fileName = documentRecord.original_filename || "this document";
  const confirmed = window.confirm(`Remove saved records for ${fileName}?`);
  if (!confirmed) {
    return;
  }

  button.disabled = true;
  button.textContent = "Removing";
  setDocumentsState(`Removing ${fileName}.`, "pending");

  try {
    const response = await fetch(documentsApiUrl(`/api/v1/documents/${encodeURIComponent(documentRecord.document_id)}`), {
      method: "DELETE",
      headers: window.statsAccess.authHeaders(),
    });

    if (!response.ok) {
      throw new Error("Document records could not be removed.");
    }

    const result = await response.json();
    setDocumentsState(`Removed ${fileName}. Deleted document rows: ${result.deleted_counts?.stats_documents || 0}.`, "success");
    await loadDocuments();
  } catch (error) {
    button.disabled = false;
    button.textContent = "Remove";
    setDocumentsState(error.message || "Document records could not be removed.", "error");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadDocuments();
});
// M9 End
