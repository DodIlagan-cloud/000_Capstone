// M3/M4 - File Intake Module Start
// Automatically validates selected upload candidates through the merged file intake module.
const documentFileInput = document.querySelector("#document-file");
const documentDropZone = document.querySelector("#document-drop-zone");
const selectedFileSummary = document.querySelector("#selected-file-summary");
const validationResult = document.querySelector("#validation-result");
const ingestionResult = document.querySelector("#ingestion-result");
const parseResult = document.querySelector("#parse-result");
const uploadState = document.querySelector("#upload-state");
const fileValidationBaseUrl = document.body.dataset.fileValidationBaseUrl ?? "";
const fileIngestionBaseUrl = document.body.dataset.fileIngestionBaseUrl ?? fileValidationBaseUrl;
const documentParsingBaseUrl = document.body.dataset.documentParsingBaseUrl ?? "";
const transactionExtractionBaseUrl = document.body.dataset.transactionExtractionBaseUrl ?? "";
const dataValidationBaseUrl = document.body.dataset.dataValidationBaseUrl ?? "";

let selectedFile = null;
let acceptedValidation = null;
const uploadSteps = ["File accepted", "Document uploaded", "Text read", "Transactions checked"];

function formatFileSize(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return `${value.toFixed(value >= 10 ? 1 : 2)} ${units[unitIndex]}`;
}

function setValidationState(message, tone = "pending") {
  uploadState.textContent = message;
  uploadState.dataset.tone = tone;
}

function statsApiUrl(baseUrl, path) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const normalizedBase = (baseUrl || "").trim().replace(/\/+$/, "");
  return normalizedBase ? `${normalizedBase}${normalizedPath}` : normalizedPath;
}

function valueFromPath(path) {
  if (!path) {
    return "Pending";
  }

  return path;
}

function formatMoney(amount, currency = "PHP") {
  const numericAmount = Number(amount || 0);
  return `${currency || "PHP"} ${numericAmount.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function humanizeStatus(value) {
  const normalized = String(value || "").replaceAll("_", " ");
  return normalized ? normalized.charAt(0).toUpperCase() + normalized.slice(1) : "Pending";
}

function documentClassificationLabel(classification = {}, fallbackType = "unknown") {
  const subtype = classification.document_subtype;
  if (subtype && subtype !== "unknown") {
    return humanizeStatus(subtype);
  }

  return humanizeStatus(classification.document_type || fallbackType || "unknown");
}

function userRecordStatus(record) {
  if (record.duplicate_of) {
    return "Possible duplicate";
  }
  if (record.quality_status === "invalid") {
    return "Needs review";
  }
  if (record.quality_status === "warning") {
    return "Needs review";
  }
  return "Ready";
}

function formatTableCell(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function renderExtractedDataTables(extractionResult) {
  const tables = extractionResult?.document_tables || [];
  if (!tables.length) {
    return null;
  }

  const section = document.createElement("section");
  section.className = "extracted-data";
  const heading = document.createElement("h4");
  heading.textContent = "Extracted data";
  section.append(heading);

  tables.forEach((tableGroup) => {
    const tableSection = document.createElement("section");
    tableSection.className = "extracted-data-table";

    const title = document.createElement("h5");
    title.textContent = tableGroup.title || humanizeStatus(tableGroup.table_id);
    tableSection.append(title);

    const rows = tableGroup.rows || [];
    if (!rows.length) {
      const empty = document.createElement("p");
      empty.textContent = "No rows found.";
      tableSection.append(empty);
      section.append(tableSection);
      return;
    }

    const tableWrap = document.createElement("div");
    tableWrap.className = "table-wrap";
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    (tableGroup.columns || []).forEach((label) => {
      const th = document.createElement("th");
      th.textContent = label;
      headerRow.append(th);
    });
    thead.append(headerRow);

    const tbody = document.createElement("tbody");
    rows.forEach((rowData) => {
      const row = document.createElement("tr");
      const values = rowData.values || {};
      (tableGroup.columns || []).forEach((column) => {
        const cell = document.createElement("td");
        const value = values[column];
        if (column.toLowerCase() === "status") {
          const pill = document.createElement("span");
          const status = formatTableCell(value);
          pill.className = status === "Ready" || status === "extracted" ? "state-pill" : "state-pill pending";
          pill.textContent = status;
          cell.append(pill);
        } else {
          cell.textContent = formatTableCell(value);
        }
        row.append(cell);
      });
      tbody.append(row);
    });
    table.append(thead, tbody);
    tableWrap.append(table);
    tableSection.append(tableWrap);
    section.append(tableSection);
  });

  return section;
}

function renderProcessingProgress(activeIndex, title = "Processing document", message = "Stats is checking the document.") {
  parseResult.hidden = false;
  parseResult.dataset.status = "accepted";
  parseResult.replaceChildren();

  const heading = document.createElement("h3");
  heading.textContent = title;

  const copy = document.createElement("p");
  copy.textContent = message;

  const steps = document.createElement("ol");
  steps.className = "processing-steps";
  uploadSteps.forEach((label, index) => {
    const item = document.createElement("li");
    const marker = document.createElement("span");
    marker.className = "step-marker";

    if (index < activeIndex) {
      item.dataset.state = "done";
      marker.textContent = "Done";
    } else if (index === activeIndex) {
      item.dataset.state = "active";
      marker.textContent = "Now";
    } else {
      item.dataset.state = "pending";
      marker.textContent = "Next";
    }

    const text = document.createElement("span");
    text.textContent = label;
    item.append(marker, text);
    steps.append(item);
  });

  parseResult.append(heading, copy, steps);
}

function renderSelectedFile(file) {
  selectedFileSummary.hidden = false;
  selectedFileSummary.replaceChildren();

  const filename = document.createElement("strong");
  filename.textContent = file.name;

  const details = document.createElement("span");
  details.textContent = `${file.type || "Unknown type"} - ${formatFileSize(file.size)}`;

  selectedFileSummary.append(filename, details);
}

function renderValidationResult(result) {
  validationResult.hidden = true;
  validationResult.dataset.status = result.status;
  validationResult.replaceChildren();

  const findings = result.findings || [];
  const metadata = result.metadata || {};
  const heading = document.createElement("h3");
  heading.textContent = result.status === "accepted" ? "File checked" : "File needs review";

  const metadataList = document.createElement("dl");
  [
    ["Detected type", metadata.detected_mime_type || "Unknown"],
    ["Size", formatFileSize(metadata.size_bytes || 0)],
    ["Extension", metadata.extension || "None"],
  ].forEach(([label, value]) => {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = label;
    description.textContent = value;
    row.append(term, description);
    metadataList.append(row);
  });

  validationResult.append(heading, metadataList);

  if (findings.length) {
    const findingList = document.createElement("ul");
    findings.forEach((finding) => {
      const item = document.createElement("li");
      item.textContent = finding.message;
      findingList.append(item);
    });
    validationResult.append(findingList);
    return;
  }

  const noFindings = document.createElement("p");
  noFindings.textContent = "No validation issues found.";
  validationResult.append(noFindings);
}

function validateFileCandidate(file) {
  validationResult.hidden = true;
  ingestionResult.hidden = true;
  parseResult.hidden = true;
  selectedFile = file || null;
  acceptedValidation = null;

  if (!file) {
    selectedFileSummary.hidden = true;
    setValidationState("Choose a file to validate.");
    return;
  }

  renderSelectedFile(file);
  validateSelectedFile(file);
}

async function validateSelectedFile(file) {
  const formData = new FormData();
  formData.append("file", file);

  validationResult.hidden = true;
  ingestionResult.hidden = true;
  parseResult.hidden = true;
  setValidationState("Validating file.", "pending");
  renderProcessingProgress(0, "Checking document", "Stats is checking whether this file can be processed.");

  try {
    const response = await fetch(statsApiUrl(fileValidationBaseUrl, "/api/v1/files/validate"), {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error("Validation service did not accept the request.");
    }

    const result = await response.json();
    renderValidationResult(result);

    if (result.status === "accepted") {
      acceptedValidation = result;
      renderProcessingProgress(1, "Processing document", "The file is accepted. Stats is uploading it for processing.");
      setValidationState("File accepted. Sending it to processing.", "pending");
      await sendAcceptedFileToProcessing();
      return;
    }

    setValidationState("File rejected. Choose another file to continue.", "error");
  } catch (error) {
    setValidationState(error.message || "File validation failed.", "error");
  }
}

function renderIngestionResult(record) {
  ingestionResult.hidden = true;
  ingestionResult.dataset.status = record.status === "queued" ? "accepted" : "rejected";
  ingestionResult.replaceChildren();

  const heading = document.createElement("h3");
  heading.textContent = record.status === "queued" ? "Document uploaded" : "Document upload needs review";

  const handoff = record.handoff || {};
  const source = record.source || {};
  const details = document.createElement("dl");
  [
    ["Ingestion id", record.ingestion_id],
    ["Status", record.status],
    ["Submitted by", source.submitted_by || "Current browser session"],
    ["Processing file", valueFromPath(handoff.content_reference)],
    ["Workflow", handoff.workflow || record.options?.workflow || "Default"],
  ].forEach(([label, value]) => {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = label;
    description.textContent = value || "-";
    row.append(term, description);
    details.append(row);
  });

  ingestionResult.append(heading, details);

  const findings = record.findings || [];
  if (findings.length) {
    const findingList = document.createElement("ul");
    findings.forEach((finding) => {
      const item = document.createElement("li");
      item.textContent = finding.message;
      findingList.append(item);
    });
    ingestionResult.append(findingList);
  }
}

function renderParseResult(result) {
  parseResult.hidden = false;
  parseResult.dataset.status = result.status === "failed" ? "rejected" : "accepted";
  parseResult.replaceChildren();

  const heading = document.createElement("h3");
  heading.textContent = result.status === "failed" ? "Document needs review" : "Processing document";

  const documentInfo = result.document || {};
  const classification = result.classification || {};
  const documentTypeLabel = documentClassificationLabel(classification, documentInfo.document_type);
  const details = document.createElement("dl");
  [
    ["File", documentInfo.original_filename || selectedFile?.name || "Selected document"],
    ["Document type", documentTypeLabel],
    ["Text read", result.status === "failed" ? "Needs review" : "Yes"],
  ].forEach(([label, value]) => {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = label;
    description.textContent = String(value ?? "-");
    row.append(term, description);
    details.append(row);
  });

  parseResult.append(heading, details);

  const findings = result.findings || [];
  if (findings.length) {
    const findingList = document.createElement("ul");
    findings.forEach((finding) => {
      const item = document.createElement("li");
      item.textContent = finding.message || finding.code || "Parsing finding";
      findingList.append(item);
    });
    parseResult.append(findingList);
  }

}

function buildExtractionRequest(parseResultPayload) {
  const documentInfo = parseResultPayload.document || {};
  const classification = parseResultPayload.classification || {};
  return {
    parse_id: parseResultPayload.parse_id,
    document: {
      original_filename: documentInfo.original_filename,
      normalized_filename: documentInfo.normalized_filename,
      ingestion_id: documentInfo.ingestion_id,
      source_type: documentInfo.source_type,
      source_id: documentInfo.source_id,
      sha256: documentInfo.sha256,
    },
    document_type: classification.document_type || documentInfo.document_type || "unknown",
    classification_confidence: classification.confidence,
    classification,
    text: parseResultPayload.text || "",
    pages: parseResultPayload.pages || [],
    metadata: parseResultPayload.metadata || {},
    quality: parseResultPayload.quality,
    findings: parseResultPayload.findings || [],
  };
}

function buildValidationRequest(extractionResult) {
  return {
    extraction_id: extractionResult.extraction_id,
    parse_id: extractionResult.parse_id,
    document: extractionResult.document,
    document_type: extractionResult.document_type,
    transaction_candidates: extractionResult.transaction_candidates || [],
    financial_field_candidates: extractionResult.financial_field_candidates || [],
    section_candidates: extractionResult.section_candidates || [],
    entity_candidates: extractionResult.entity_candidates || [],
    reference_candidates: extractionResult.reference_candidates || [],
    line_item_candidates: extractionResult.line_item_candidates || [],
    reconciliation: extractionResult.reconciliation || null,
    findings: extractionResult.findings || [],
  };
}

function reviewItemRecord(reviewItem, records) {
  return (records || []).find((record) => record.record_id === reviewItem.record_id);
}

function renderReviewItems(result) {
  const reviewItems = result.review_items || [];
  if (!reviewItems.length) {
    return null;
  }

  const section = document.createElement("section");
  section.className = "guided-review";
  const heading = document.createElement("h4");
  heading.textContent = "Needs review";
  const copy = document.createElement("p");
  copy.textContent = "Stats found a few items that need attention before everything is saved.";
  section.append(heading, copy);

  reviewItems.forEach((item) => {
    const row = document.createElement("article");
    row.className = "review-item";
    const title = document.createElement("h5");
    title.textContent = item.title || "Review item";
    const message = document.createElement("p");
    message.textContent = item.message || "This item needs review.";
    row.append(title, message);

    const record = reviewItemRecord(item, result.normalized_records);
    if (record) {
      const details = document.createElement("dl");
      [
        ["Date", record.transaction_date || "Needs review"],
        ["Description", record.description || "Needs review"],
        ["Amount", formatMoney(record.amount, record.currency)],
        ["Status", userRecordStatus(record)],
      ].forEach(([label, value]) => {
        const itemRow = document.createElement("div");
        const term = document.createElement("dt");
        const description = document.createElement("dd");
        term.textContent = label;
        description.textContent = value;
        itemRow.append(term, description);
        details.append(itemRow);
      });
      row.append(details);
    }

    const actions = document.createElement("div");
    actions.className = "review-actions";
    ["Edit", "Accept", "Exclude"].forEach((label) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.disabled = true;
      button.title = "Review actions will be enabled when save workflow is connected.";
      actions.append(button);
    });
    row.append(actions);
    section.append(row);
  });

  return section;
}

function renderReadyTransactions(result) {
  const records = (result.normalized_records || []).filter((record) => userRecordStatus(record) === "Ready");
  if (!records.length) {
    return null;
  }

  const section = document.createElement("section");
  section.className = "ready-transactions";
  const heading = document.createElement("h4");
  heading.textContent = "Ready transactions";
  section.append(heading);
  section.append(renderRecordsTable(records));
  return section;
}

function renderRecordsTable(records) {
  const tableWrap = document.createElement("div");
  tableWrap.className = "table-wrap transaction-preview";
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  ["Date", "Description", "Amount", "Status"].forEach((label) => {
    const th = document.createElement("th");
    th.textContent = label;
    headerRow.append(th);
  });
  thead.append(headerRow);

  const tbody = document.createElement("tbody");
  records.forEach((record) => {
    const row = document.createElement("tr");
    const status = userRecordStatus(record);
    [
      record.transaction_date || "Needs review",
      record.description || "Needs review",
      formatMoney(record.amount, record.currency),
      status,
    ].forEach((value, index) => {
      const cell = document.createElement("td");
      if (index === 3) {
        const pill = document.createElement("span");
        pill.className = status === "Ready" ? "state-pill" : "state-pill pending";
        pill.textContent = value;
        cell.append(pill);
      } else {
        cell.textContent = value;
      }
      row.append(cell);
    });
    tbody.append(row);
  });
  table.append(thead, tbody);
  tableWrap.append(table);
  return tableWrap;
}

function renderTransactionCheckResult(result, parsePayload, extractionResult) {
  parseResult.hidden = false;
  parseResult.dataset.status = result.status === "failed" ? "rejected" : "accepted";
  parseResult.replaceChildren();

  const heading = document.createElement("h3");
  heading.textContent = "Transaction check results";

  const intro = document.createElement("p");
  intro.textContent = "Review what Stats found before saving transactions.";

  const summary = result.summary || {};
  const readyCount = summary.valid_record_count ?? 0;
  const reviewCount = summary.review_item_count ?? ((summary.warning_record_count ?? 0) + (summary.invalid_record_count ?? 0));

  const steps = document.createElement("ol");
  steps.className = "processing-steps";
  ["File accepted", "Document uploaded", "Text read", "Transactions checked"].forEach((label) => {
    const item = document.createElement("li");
    item.textContent = label;
    steps.append(item);
  });

  const metrics = document.createElement("div");
  metrics.className = "result-metrics";
  [
    ["Transactions found", summary.normalized_record_count ?? 0],
    ["Ready to save", readyCount],
    ["Needs review", reviewCount],
    ["Saved", 0],
  ].forEach(([label, value]) => {
    const metric = document.createElement("div");
    const valueElement = document.createElement("strong");
    const labelElement = document.createElement("span");
    valueElement.textContent = String(value);
    labelElement.textContent = label;
    metric.append(valueElement, labelElement);
    metrics.append(metric);
  });

  parseResult.append(heading, intro, steps, metrics);

  const guidedReview = renderReviewItems(result);
  if (guidedReview) {
    parseResult.append(guidedReview);
  }

  const readyTransactions = renderReadyTransactions(result);
  if (readyTransactions) {
    parseResult.append(readyTransactions);
  }

  const extractedTables = renderExtractedDataTables(extractionResult);
  if (extractedTables) {
    parseResult.append(extractedTables);
  }

  const findings = result.findings || [];
  if (reviewCount > 0 || findings.length) {
    const reviewPanel = document.createElement("div");
    reviewPanel.className = "review-callout";
    const reviewHeading = document.createElement("h4");
    reviewHeading.textContent = `${reviewCount || findings.length} item${(reviewCount || findings.length) === 1 ? "" : "s"} need review`;
    const reviewCopy = document.createElement("p");
    const duplicateCount = summary.duplicate_record_count ?? 0;
    reviewCopy.textContent = duplicateCount
      ? `${duplicateCount} transaction may already appear in this upload.`
      : "Some transaction details need a quick check before saving.";
    reviewPanel.append(reviewHeading, reviewCopy);
    parseResult.append(reviewPanel);
  }

  const parseDocument = parsePayload.document || {};
  const parseClassification = parsePayload.classification || {};
  const documentTypeLabel = documentClassificationLabel(parseClassification, result.document_type);
  const documentSummary = document.createElement("dl");
  documentSummary.className = "document-summary";
  [
    ["File", parseDocument.original_filename || selectedFile?.name || "Selected document"],
    ["Document type", documentTypeLabel],
    ["Text read", parsePayload.status === "failed" ? "Needs review" : "Yes"],
    ["Processing result", reviewCount > 0 ? "Needs review" : "Ready to save"],
  ].forEach(([label, value]) => {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = label;
    description.textContent = value;
    row.append(term, description);
    documentSummary.append(row);
  });
  parseResult.append(documentSummary);

  const actions = document.createElement("div");
  actions.className = "next-actions";
  const saveButton = document.createElement("button");
  saveButton.type = "button";
  saveButton.className = "primary-action";
  saveButton.textContent = "Save ready transactions";
  saveButton.disabled = true;
  saveButton.title = "This will be enabled when database saving is connected.";

  const reviewButton = document.createElement("button");
  reviewButton.type = "button";
  reviewButton.textContent = "Review transactions";
  reviewButton.disabled = !reviewCount;

  const uploadAnotherButton = document.createElement("button");
  uploadAnotherButton.type = "button";
  uploadAnotherButton.textContent = "Upload another document";
  uploadAnotherButton.addEventListener("click", () => {
    documentFileInput.value = "";
    validateFileCandidate(null);
  });

  actions.append(saveButton, reviewButton, uploadAnotherButton);
  parseResult.append(actions);

  const jsonDetails = document.createElement("details");
  jsonDetails.className = "json-output";

  const jsonSummary = document.createElement("summary");
  jsonSummary.textContent = "Developer details";

  const jsonOutput = document.createElement("pre");
  jsonOutput.textContent = JSON.stringify(
    {
      extraction: {
        status: extractionResult.status,
        transaction_candidate_count: extractionResult.summary?.transaction_candidate_count ?? 0,
        financial_field_candidate_count: extractionResult.summary?.financial_field_candidate_count ?? 0,
      },
      validation: result,
    },
    null,
    2,
  );

  jsonDetails.append(jsonSummary, jsonOutput);
  parseResult.append(jsonDetails);
}

async function sendAcceptedFileToProcessing() {
  if (!selectedFile || !acceptedValidation) {
    setValidationState("Choose an accepted file before processing.", "error");
    return;
  }

  const metadata = acceptedValidation.metadata || {};
  const formData = new FormData();
  formData.append("file", selectedFile);
  formData.append("validation_status", acceptedValidation.status);
  formData.append("validation_sha256", metadata.sha256 || "");
  formData.append("detected_mime_type", metadata.detected_mime_type || selectedFile.type || "");
  formData.append("source_type", "manual_upload");
  formData.append("source_id", "stats-web-upload");

  try {
    setValidationState("Sending accepted file to processing.", "pending");
    renderProcessingProgress(1, "Processing document", "Uploading the accepted document.");

    const user = await window.statsAccess.currentUser();
    formData.append("submitted_by", user.email);

    const response = await fetch(statsApiUrl(fileIngestionBaseUrl, "/api/v1/ingestions"), {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error("Ingestion service did not accept the request.");
    }

    const record = await response.json();
    renderIngestionResult(record);

    if (record.status === "queued" || record.status === "duplicate") {
      renderProcessingProgress(2, "Reading document", "The document is uploaded. Stats is reading the text.");
      setValidationState("Document ingested. Parsing document.", "pending");
      await parseAcceptedFile(record);
      return;
    }

    setValidationState("Document was not queued. Review the ingestion result.", "error");
  } catch (error) {
    setValidationState(error.message || "File ingestion failed.", "error");
  }
}

async function parseAcceptedFile(record) {
  const metadata = acceptedValidation.metadata || {};
  const formData = new FormData();
  formData.append("file", selectedFile);
  formData.append("ingestion_id", record.ingestion_id || "");
  formData.append("source_type", "manual_upload");
  formData.append("source_id", "stats-web-upload");
  formData.append("sha256", metadata.sha256 || "");

  try {
    renderProcessingProgress(2, "Reading document", "Stats is reading the document text. This may take a little while for images.");
    const response = await fetch(statsApiUrl(documentParsingBaseUrl, "/api/v1/parses"), {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error("Document parsing service did not accept the request.");
    }

    const result = await response.json();

    if (result.status === "failed") {
      renderParseResult(result);
      setValidationState("Document parsing needs review.", "error");
      return;
    }

    renderProcessingProgress(3, "Checking transactions", "Text was read. Stats is checking transaction candidates.");
    setValidationState("Document parsed. Extracting transaction candidates.", "pending");
    const extraction = await extractTransactions(result);
    setValidationState("Transaction candidates extracted. Validating data.", "pending");
    const validation = await validateExtractedData(extraction);
    renderTransactionCheckResult(validation, result, extraction);
    setValidationState("Transactions checked. Review the results before saving.", "success");
  } catch (error) {
    setValidationState(error.message || "Document parsing failed.", "error");
  }
}

async function extractTransactions(parseResultPayload) {
  const response = await fetch(statsApiUrl(transactionExtractionBaseUrl, "/api/v1/extractions"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildExtractionRequest(parseResultPayload)),
  });

  if (!response.ok) {
    throw new Error("Transaction extraction service did not accept the request.");
  }

  return response.json();
}

async function validateExtractedData(extractionResult) {
  const response = await fetch(statsApiUrl(dataValidationBaseUrl, "/api/v1/validations"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildValidationRequest(extractionResult)),
  });

  if (!response.ok) {
    throw new Error("Data validation service did not accept the request.");
  }

  return response.json();
}

documentFileInput?.addEventListener("change", () => {
  const [file] = documentFileInput.files || [];
  validateFileCandidate(file);
});

documentDropZone?.addEventListener("click", (event) => {
  if (event.target === documentFileInput) {
    return;
  }

  documentFileInput?.click();
});

documentDropZone?.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    documentFileInput?.click();
  }
});

["dragenter", "dragover"].forEach((eventName) => {
  documentDropZone?.addEventListener(eventName, (event) => {
    event.preventDefault();
    documentDropZone.dataset.dragging = "true";
  });
});

["dragleave", "drop"].forEach((eventName) => {
  documentDropZone?.addEventListener(eventName, (event) => {
    event.preventDefault();
    delete documentDropZone.dataset.dragging;
  });
});

documentDropZone?.addEventListener("drop", (event) => {
  const [file] = event.dataTransfer?.files || [];
  if (!file) {
    validateFileCandidate(null);
    return;
  }

  const transfer = new DataTransfer();
  transfer.items.add(file);
  documentFileInput.files = transfer.files;
  validateFileCandidate(file);
});

// M3/M4 End
