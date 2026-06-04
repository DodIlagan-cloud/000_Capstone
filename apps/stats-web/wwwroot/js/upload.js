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

function numericValue(value) {
  const parsed = Number(String(value ?? "").replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

function transactionFieldsComplete(record) {
  return Boolean(
    record.transaction_date
      && record.description
      && Number(record.amount) > 0
      && record.currency
      && ["debit", "credit"].includes(String(record.direction || "").toLowerCase()),
  );
}

function createReviewState(result) {
  const records = (result.normalized_records || []).map((record) => ({ ...record }));
  const installments = (result.normalized_installments || []).map((installment) => ({ ...installment }));
  return {
    records,
    installments,
    acceptedRecordIds: new Set(
      records
        .filter((record) => userRecordStatus(record) === "Ready" && transactionFieldsComplete(record))
        .map((record) => record.record_id),
    ),
    acceptedInstallmentIds: new Set(
      installments
        .filter((installment) => userRecordStatus(installment) === "Ready" && installmentFieldsComplete(installment))
        .map((installment) => installment.installment_id),
    ),
  };
}

function localRecordStatus(record, reviewState) {
  if (reviewState.acceptedRecordIds.has(record.record_id) && transactionFieldsComplete(record)) {
    return "Ready";
  }
  return userRecordStatus(record);
}

function installmentFieldsComplete(installment) {
  return Boolean(
    installment.description
      && installment.currency
      && (
        Number(installment.principal_amount) > 0
        || Number(installment.current_billing_amount) > 0
        || Number(installment.remaining_balance) > 0
      ),
  );
}

function localInstallmentStatus(installment, reviewState) {
  if (reviewState.acceptedInstallmentIds.has(installment.installment_id) && installmentFieldsComplete(installment)) {
    return "Ready";
  }
  return userRecordStatus(installment);
}

function editableRecordFields(record) {
  return [
    ["transaction_date", "Date", "date"],
    ["posted_date", "Posted date", "date"],
    ["description", "Description", "text"],
    ["amount", "Amount", "number"],
    ["currency", "Currency", "text"],
    ["direction", "Direction", "select"],
  ].map(([name, label, type]) => ({ name, label, type, value: record[name] ?? "" }));
}

function editableInstallmentFields(installment) {
  return [
    ["purchase_date", "Purchase date", "date"],
    ["posted_date", "Posted date", "date"],
    ["description", "Description", "text"],
    ["principal_amount", "Principal amount", "number"],
    ["current_billing_amount", "Current billed", "number"],
    ["remaining_balance", "Remaining balance", "number"],
    ["currency", "Currency", "text"],
    ["term_text", "Term", "text"],
  ].map(([name, label, type]) => ({ name, label, type, value: installment[name] ?? "" }));
}

function fieldValueFromInput(input, fieldName) {
  if (["amount", "principal_amount", "current_billing_amount", "remaining_balance"].includes(fieldName)) {
    return Math.abs(numericValue(input.value));
  }
  if (fieldName === "currency") {
    return input.value.trim().toUpperCase() || "PHP";
  }
  return input.value.trim();
}

function applyEditedRecord(record, values) {
  Object.assign(record, values);
  record.direction = String(record.direction || "").toLowerCase();
  record.amount = Math.abs(numericValue(record.amount));
  record.signed_amount = record.direction === "credit" ? record.amount : -record.amount;
  if (transactionFieldsComplete(record) && record.quality_status === "invalid") {
    record.quality_status = "warning";
  }
}

function applyEditedInstallment(installment, values) {
  Object.assign(installment, values);
  ["principal_amount", "current_billing_amount", "remaining_balance"].forEach((fieldName) => {
    if (installment[fieldName] !== "" && installment[fieldName] !== null && installment[fieldName] !== undefined) {
      installment[fieldName] = Math.abs(numericValue(installment[fieldName]));
    }
  });
  installment.currency = String(installment.currency || "PHP").trim().toUpperCase();
  if (installmentFieldsComplete(installment) && installment.quality_status === "invalid") {
    installment.quality_status = "warning";
  }
}

function reconciliationSnapshot(reviewState, extractionResult) {
  const reconciliation = extractionResult?.reconciliation || null;
  if (!reconciliation || reconciliation.status === "not_available" || reconciliation.total_due === null || reconciliation.total_due === undefined) {
    return {
      available: false,
      matched: true,
      debitTotal: 0,
      creditTotal: 0,
      computedTotalDue: null,
      documentTotalDue: null,
      difference: null,
      currency: "PHP",
    };
  }

  const debitTotal = reviewState.records
    .filter((record) => record.direction === "debit")
    .reduce((total, record) => total + numericValue(record.amount), 0);
  const creditTotal = reviewState.records
    .filter((record) => record.direction === "credit")
    .reduce((total, record) => total + numericValue(record.amount), 0);
  const statementCreditTotal = numericValue(reconciliation.credit_total);
  const effectiveCreditTotal = statementCreditTotal > 0 ? statementCreditTotal : creditTotal;
  const previousBalance = numericValue(reconciliation.previous_balance);
  const documentTotalDue = numericValue(reconciliation.total_due);
  const computedTotalDue = previousBalance + debitTotal - effectiveCreditTotal;
  const difference = computedTotalDue - documentTotalDue;

  return {
    available: true,
    matched: Math.abs(difference) <= 0.01,
    debitTotal,
    creditTotal: effectiveCreditTotal,
    computedTotalDue,
    documentTotalDue,
    difference,
    currency: "PHP",
  };
}

function displayRowsForExtractedTable(tableGroup) {
  const rows = tableGroup.rows || [];
  if (tableGroup.table_id !== "statement_summary") {
    return rows;
  }

  const seenFields = new Set();
  return rows.filter((rowData) => {
    const values = rowData.values || {};
    const field = String(values.Field || values.FIELD || "").trim();
    const canonical = field.toLowerCase().replace(/[^a-z0-9]+/g, "");
    if (!canonical || canonical === "purchase") {
      return false;
    }
    if (seenFields.has(canonical)) {
      return false;
    }
    seenFields.add(canonical);
    return true;
  });
}

function renderExtractedDataTables(extractionResult) {
  const tables = (extractionResult?.document_tables || []).filter((tableGroup) => tableGroup.table_id !== "transactions");
  if (!tables.length) {
    return null;
  }

  const section = document.createElement("details");
  section.className = "extracted-data";
  const heading = document.createElement("summary");
  heading.textContent = "View all extracted data";
  section.append(heading);

  tables.forEach((tableGroup) => {
    const tableSection = document.createElement("section");
    tableSection.className = "extracted-data-table";

    const title = document.createElement("h5");
    title.textContent = tableGroup.title || humanizeStatus(tableGroup.table_id);
    tableSection.append(title);

    const rows = displayRowsForExtractedTable(tableGroup);
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
    installment_candidates: extractionResult.installment_candidates || [],
    reconciliation: extractionResult.reconciliation || null,
    findings: extractionResult.findings || [],
  };
}

function reviewItemRecord(reviewItem, records) {
  return (records || []).find((record) => record.record_id === reviewItem.record_id);
}

function reviewItemInstallment(reviewItem, installments) {
  return (installments || []).find((installment) => installment.installment_id === reviewItem.record_id);
}

function renderReviewItemEditor(record, onChange, options = {}) {
  const form = document.createElement("form");
  form.className = "review-edit-form";

  const inputs = new Map();
  const fields = options.kind === "installment" ? editableInstallmentFields(record) : editableRecordFields(record);
  fields.forEach((field) => {
    const label = document.createElement("label");
    label.textContent = field.label;

    let input;
    if (field.type === "select") {
      input = document.createElement("select");
      ["debit", "credit"].forEach((optionValue) => {
        const option = document.createElement("option");
        option.value = optionValue;
        option.textContent = humanizeStatus(optionValue);
        option.selected = String(field.value).toLowerCase() === optionValue;
        input.append(option);
      });
    } else {
      input = document.createElement("input");
      input.type = field.type;
      input.value = field.value;
      if (["amount", "principal_amount", "current_billing_amount", "remaining_balance"].includes(field.name)) {
        input.step = "0.01";
        input.min = "0";
      }
    }

    input.name = field.name;
    inputs.set(field.name, input);
    label.append(input);
    form.append(label);
  });

  const saveButton = document.createElement("button");
  saveButton.type = "submit";
  saveButton.textContent = "Save edit";
  form.append(saveButton);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const values = {};
    inputs.forEach((input, fieldName) => {
      values[fieldName] = fieldValueFromInput(input, fieldName);
    });
    if (options.kind === "installment") {
      applyEditedInstallment(record, values);
    } else {
      applyEditedRecord(record, values);
    }
    onChange();
  });

  return form;
}

function renderReviewItems(result, reviewState, onChange) {
  const reviewItems = (result.review_items || []).filter((item) => {
    if (!item.record_id) {
      return true;
    }
    const record = reviewItemRecord(item, reviewState.records);
    if (record) {
      return localRecordStatus(record, reviewState) !== "Ready";
    }
    const installment = reviewItemInstallment(item, reviewState.installments);
    return installment && localInstallmentStatus(installment, reviewState) !== "Ready";
  });
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

    const record = reviewItemRecord(item, reviewState.records);
    const installment = reviewItemInstallment(item, reviewState.installments);
    if (record) {
      const details = document.createElement("dl");
      [
        ["Date", record.transaction_date || "Needs review"],
        ["Description", record.description || "Needs review"],
        ["Amount", formatMoney(record.amount, record.currency)],
        ["Status", localRecordStatus(record, reviewState)],
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
    if (installment) {
      const details = document.createElement("dl");
      [
        ["Purchase date", installment.purchase_date || "Needs review"],
        ["Description", installment.description || "Needs review"],
        ["Principal", installment.principal_amount ? formatMoney(installment.principal_amount, installment.currency) : "Needs review"],
        ["Term", installment.term_text || "Needs review"],
        ["Status", localInstallmentStatus(installment, reviewState)],
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
    if (record) {
      const editButton = document.createElement("button");
      editButton.type = "button";
      editButton.textContent = "Edit";
      editButton.addEventListener("click", () => {
        const existingForm = row.querySelector(".review-edit-form");
        if (existingForm) {
          existingForm.remove();
          return;
        }
        row.append(renderReviewItemEditor(record, onChange));
      });

      const acceptButton = document.createElement("button");
      acceptButton.type = "button";
      acceptButton.textContent = "Accept";
      acceptButton.disabled = !transactionFieldsComplete(record);
      acceptButton.title = acceptButton.disabled ? "Complete transaction details before accepting this row." : "";
      acceptButton.addEventListener("click", () => {
        reviewState.acceptedRecordIds.add(record.record_id);
        record.quality_status = "valid";
        onChange();
      });

      actions.append(editButton, acceptButton);
    }
    if (installment) {
      const editButton = document.createElement("button");
      editButton.type = "button";
      editButton.textContent = "Edit";
      editButton.addEventListener("click", () => {
        const existingForm = row.querySelector(".review-edit-form");
        if (existingForm) {
          existingForm.remove();
          return;
        }
        row.append(renderReviewItemEditor(installment, onChange, { kind: "installment" }));
      });

      const acceptButton = document.createElement("button");
      acceptButton.type = "button";
      acceptButton.textContent = "Accept";
      acceptButton.disabled = !installmentFieldsComplete(installment);
      acceptButton.title = acceptButton.disabled ? "Complete installment details before accepting this row." : "";
      acceptButton.addEventListener("click", () => {
        reviewState.acceptedInstallmentIds.add(installment.installment_id);
        installment.quality_status = "valid";
        onChange();
      });

      actions.append(editButton, acceptButton);
    }
    row.append(actions);
    section.append(row);
  });

  return section;
}

function renderReconciliationStatus(snapshot, allRowsAccepted) {
  if (!snapshot.available) {
    return null;
  }

  const panel = document.createElement("section");
  panel.className = snapshot.matched && allRowsAccepted ? "reconciliation-status matched" : "reconciliation-status";
  const heading = document.createElement("h4");
  heading.textContent = snapshot.matched ? "Totals match the document" : "Totals still need review";
  const copy = document.createElement("p");
  copy.textContent = snapshot.matched
    ? "The edited transaction total aligns with the document summary."
    : `The transaction total is off by ${formatMoney(snapshot.difference, snapshot.currency)}. Review edited rows before saving.`;
  panel.append(heading, copy);

  const details = document.createElement("dl");
  [
    ["Document total due", formatMoney(snapshot.documentTotalDue, snapshot.currency)],
    ["Computed total due", formatMoney(snapshot.computedTotalDue, snapshot.currency)],
    ["Difference", formatMoney(snapshot.difference, snapshot.currency)],
  ].forEach(([label, value]) => {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = label;
    description.textContent = value;
    row.append(term, description);
    details.append(row);
  });
  panel.append(details);
  return panel;
}

function renderReadyTransactions(reviewState, reconciliationMatched, onChange) {
  const records = reviewState.records.filter((record) => localRecordStatus(record, reviewState) === "Ready");
  if (!records.length) {
    return null;
  }

  const section = document.createElement("section");
  section.className = "ready-transactions";
  const heading = document.createElement("h4");
  heading.textContent = reconciliationMatched ? "Ready transactions" : "Accepted transactions";
  section.append(heading);
  if (!reconciliationMatched) {
    const copy = document.createElement("p");
    copy.textContent = "These rows are accepted locally, but final save readiness waits for the document totals to match.";
    section.append(copy);
  }
  section.append(renderRecordsTable(records, reviewState, onChange));
  return section;
}

function renderRecordsTable(records, reviewState, onChange) {
  const tableWrap = document.createElement("div");
  tableWrap.className = "table-wrap transaction-preview";
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  ["Date", "Description", "Amount", "Status", "Actions"].forEach((label) => {
    const th = document.createElement("th");
    th.textContent = label;
    headerRow.append(th);
  });
  thead.append(headerRow);

  const tbody = document.createElement("tbody");
  records.forEach((record) => {
    const row = document.createElement("tr");
    const status = localRecordStatus(record, reviewState);
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
    const actionCell = document.createElement("td");
    actionCell.className = "row-action-cell";
    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.className = "row-edit-action";
    editButton.textContent = "Edit";
    editButton.addEventListener("click", () => {
      const nextRow = row.nextElementSibling;
      if (nextRow?.classList.contains("inline-edit-row")) {
        nextRow.remove();
        return;
      }

      const editRow = document.createElement("tr");
      editRow.className = "inline-edit-row";
      const editCell = document.createElement("td");
      editCell.colSpan = 5;
      editCell.append(renderReviewItemEditor(record, onChange));
      editRow.append(editCell);
      row.after(editRow);
    });
    actionCell.append(editButton);
    row.append(actionCell);
    tbody.append(row);
  });
  table.append(thead, tbody);
  tableWrap.append(table);
  return tableWrap;
}

function renderTransactionCheckResult(result, parsePayload, extractionResult, existingReviewState = null) {
  const reviewState = existingReviewState || createReviewState(result);
  const rerender = () => renderTransactionCheckResult(result, parsePayload, extractionResult, reviewState);
  const reconciliation = reconciliationSnapshot(reviewState, extractionResult);
  const allRowsAccepted = reviewState.records.every((record) => localRecordStatus(record, reviewState) === "Ready");
  const finalReady = allRowsAccepted && reconciliation.matched;

  parseResult.hidden = false;
  parseResult.dataset.status = result.status === "failed" ? "rejected" : "accepted";
  parseResult.replaceChildren();

  const heading = document.createElement("h3");
  heading.textContent = "Transaction check results";

  const intro = document.createElement("p");
  intro.textContent = "Review what Stats found before saving transactions.";

  const summary = result.summary || {};
  const acceptedCount = reviewState.records.filter((record) => localRecordStatus(record, reviewState) === "Ready").length;
  const unacceptedCount = reviewState.records.length - acceptedCount;
  const reconciliationReviewCount = reconciliation.available && !reconciliation.matched ? 1 : 0;
  const readyCount = finalReady ? acceptedCount : 0;
  const reviewCount = unacceptedCount + reconciliationReviewCount;

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

  const reconciliationStatus = renderReconciliationStatus(reconciliation, allRowsAccepted);
  if (reconciliationStatus) {
    parseResult.append(reconciliationStatus);
  }

  const guidedReview = renderReviewItems(result, reviewState, rerender);
  if (guidedReview) {
    parseResult.append(guidedReview);
  }

  const readyTransactions = renderReadyTransactions(reviewState, reconciliation.matched, rerender);
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
    if (reconciliationReviewCount) {
      reviewCopy.textContent = "Document totals must align before the future database save step can run.";
    } else {
      reviewCopy.textContent = duplicateCount
        ? `${duplicateCount} transaction may already appear in this upload.`
        : "Some transaction details need a quick check before saving.";
    }
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
    ["Processing result", finalReady ? "Ready for future save" : "Needs review"],
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
  saveButton.title = finalReady
    ? "Rows are ready for the future M9 database save step."
    : "Accept all rows and resolve reconciliation before the future M9 database save step.";

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
