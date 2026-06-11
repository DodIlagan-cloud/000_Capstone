// M9 - Stats Data and Persistence Start
// Shows recent persisted documents and lets the user remove records saved for one uploaded file.
const documentsState = document.querySelector("#documents-state");
const documentsEmpty = document.querySelector("#documents-empty");
const documentsTableWrap = document.querySelector("#documents-table-wrap");
const documentsTableBody = document.querySelector("#documents-table-body");
const documentsTotalCount = document.querySelector("#documents-total-count");
const documentsTransactionCount = document.querySelector("#documents-transaction-count");
const documentsReviewCount = document.querySelector("#documents-review-count");
const documentsTypeSummary = document.querySelector("#documents-type-summary");
const documentsSourceSummary = document.querySelector("#documents-source-summary");
const documentsStatusSummary = document.querySelector("#documents-status-summary");
const statsDataBaseUrl = document.body.dataset.statsDataBaseUrl ?? "";
let currentDocuments = [];

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

function addCount(map, key) {
  const normalizedKey = formatStatus(key || "unknown");
  map.set(normalizedKey, (map.get(normalizedKey) || 0) + 1);
}

function renderSummaryList(list, counts) {
  list.replaceChildren();

  if (!counts.size) {
    const item = document.createElement("li");
    item.textContent = "No saved source data.";
    list.append(item);
    return;
  }

  [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, 5)
    .forEach(([label, count]) => {
      const item = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = label;
      const value = document.createElement("strong");
      value.textContent = String(count);
      item.append(name, value);
      list.append(item);
    });
}

function renderProvenanceSummary(documents) {
  const typeCounts = new Map();
  const sourceCounts = new Map();
  const statusCounts = new Map();
  let transactionCount = 0;
  let reviewCount = 0;

  documents.forEach((documentRecord) => {
    transactionCount += Number(documentRecord.transaction_count || 0);
    reviewCount += Number(documentRecord.review_item_count || 0);
    addCount(typeCounts, documentRecord.document_type);
    addCount(sourceCounts, documentRecord.source_institution || documentRecord.source_type);
    addCount(statusCounts, documentRecord.status);
  });

  documentsTotalCount.textContent = String(documents.length);
  documentsTransactionCount.textContent = String(transactionCount);
  documentsReviewCount.textContent = String(reviewCount);
  renderSummaryList(documentsTypeSummary, typeCounts);
  renderSummaryList(documentsSourceSummary, sourceCounts);
  renderSummaryList(documentsStatusSummary, statusCounts);
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
  currentDocuments = documents;
  documentsTableBody.replaceChildren();
  renderProvenanceSummary(documents);

  if (!documents.length) {
    documentsEmpty.hidden = false;
    documentsTableWrap.hidden = true;
    setDocumentsState("No saved documents.", "success");
    return;
  }

  documents.forEach((documentRecord) => {
    const row = document.createElement("tr");
    row.dataset.documentId = documentRecord.document_id;

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
    deleteButton.addEventListener("click", () => showRemoveConfirmation(documentRecord, actionCell, deleteButton));
    actionCell.append(deleteButton);

    row.append(fileCell, statusCell, rowsCell, reviewCell, savedCell, actionCell);
    documentsTableBody.append(row);
  });

  documentsEmpty.hidden = true;
  documentsTableWrap.hidden = false;
  setDocumentsState(`${documents.length} document${documents.length === 1 ? "" : "s"} loaded.`, "success");
}

function showRemoveConfirmation(documentRecord, actionCell, button) {
  const originalControls = [button];
  const confirmWrap = document.createElement("div");
  confirmWrap.className = "row-confirm-actions";

  const confirmButton = document.createElement("button");
  confirmButton.type = "button";
  confirmButton.className = "secondary-action danger-action";
  confirmButton.textContent = "Confirm";

  const cancelButton = document.createElement("button");
  cancelButton.type = "button";
  cancelButton.className = "secondary-action";
  cancelButton.textContent = "Cancel";

  confirmButton.addEventListener("click", () => removeDocument(documentRecord, confirmButton));
  cancelButton.addEventListener("click", () => actionCell.replaceChildren(...originalControls));
  confirmWrap.append(confirmButton, cancelButton);
  actionCell.replaceChildren(confirmWrap);
}

async function removeDocument(documentRecord, button) {
  const fileName = documentRecord.original_filename || "this document";

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
    currentDocuments = currentDocuments.filter((document) => document.document_id !== documentRecord.document_id);
    const row = documentsTableBody.querySelector(`tr[data-document-id="${CSS.escape(documentRecord.document_id)}"]`);
    row?.remove();
    renderProvenanceSummary(currentDocuments);
    if (!currentDocuments.length) {
      documentsEmpty.hidden = false;
      documentsTableWrap.hidden = true;
      setDocumentsState("No saved documents.", "success");
    }
  } catch (error) {
    renderDocuments(currentDocuments);
    setDocumentsState(error.message || "Document records could not be removed.", "error");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadDocuments();
});
// M9 End
