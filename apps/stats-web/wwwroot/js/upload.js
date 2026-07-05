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
const statsDataBaseUrl = document.body.dataset.statsDataBaseUrl ?? "";

window.statsAccess?.startSessionKeepAlive?.();

let selectedFile = null;
let acceptedValidation = null;
let uploadAttemptIdempotencyKey = null;
const uploadSteps = ["File accepted", "Document uploaded", "Text read", "Transactions checked"];
const fallbackTransactionSubtypeParentMap = {
  unknown: "unknown",
  card_purchase: "purchase",
  eftpos_payment: "purchase",
  merchant_purchase: "purchase",
  professional_service: "purchase",
  cash_purchase: "purchase",
  credit_card_payment: "payment",
  invoice_payment: "payment",
  bill_payment: "payment",
  loan_payment: "payment",
  bank_transfer: "transfer",
  internal_transfer: "transfer",
  external_transfer: "transfer",
  merchant_refund: "refund",
  statement_credit: "refund",
  reversal: "refund",
  late_payment_fee: "fee",
  service_fee: "fee",
  bank_fee: "fee",
  finance_charge: "interest",
  cash_advance_interest: "interest",
  atm_cash_advance: "cash_advance",
  counter_cash_advance: "cash_advance",
  credit_card_installment: "installment_amortization",
  loan_installment: "installment_amortization",
  debit_adjustment: "adjustment",
  credit_adjustment: "adjustment",
  gst_tax: "tax",
  sales_tax: "tax",
  withholding_tax: "tax",
};
const fallbackSpendingSubcategoryParentMap = {
  unknown: "uncategorized",
  clinic: "medical",
  hospital: "medical",
  laboratory: "medical",
  diagnostics: "medical",
  prescription: "pharmacy",
  chemist: "pharmacy",
  pharmacy_retail: "pharmacy",
  supermarket: "groceries",
  fresh_food: "groceries",
  market: "groceries",
  electricity: "utilities",
  water: "utilities",
  gas: "utilities",
  telecommunications: "utilities",
  internet: "utilities",
  fuel: "transport",
  public_transport: "transport",
  parking: "transport",
  rideshare: "transport",
  rent: "housing",
  mortgage: "housing",
  property: "housing",
  premium: "insurance",
  policy_payment: "insurance",
  service_fee: "banking_fees",
  late_payment_fee: "banking_fees",
  bank_charge: "banking_fees",
  immigration_services: "professional_services",
  legal_services: "professional_services",
  accounting_services: "professional_services",
  consulting_services: "professional_services",
  finance_charge: "interest",
  loan_interest: "interest",
  bank_transfer: "transfers",
  internal_transfer: "transfers",
  external_transfer: "transfers",
  restaurant: "food_dining",
  cafe: "food_dining",
  fast_food: "food_dining",
  retail: "shopping",
  general_merchandise: "shopping",
  hardware: "shopping",
  clothing: "shopping",
  salary: "income",
  refund_income: "income",
  deposit: "income",
  gst: "tax",
  sales_tax: "tax",
  withholding_tax: "tax",
};
let classificationChoices = {
  transactionSubtypeParentMap: { ...fallbackTransactionSubtypeParentMap },
  spendingSubcategoryParentMap: { ...fallbackSpendingSubcategoryParentMap },
  transactionSubtypeOptions: Object.keys(fallbackTransactionSubtypeParentMap),
  spendingSubcategoryOptions: Object.keys(fallbackSpendingSubcategoryParentMap),
  spendingCategoryOptions: orderedParentChoiceKeys(fallbackSpendingSubcategoryParentMap, "uncategorized"),
};
const transactionDirectionOptions = ["unknown", "debit", "credit"];
const addNewSpendingSubcategoryValue = "__add_new_spending_subcategory__";
const addNewSpendingCategoryValue = "__add_new_spending_category__";
const userSpendingClassificationStorageKey = "stats.userSpendingSubcategoryParentMap";
let userSpendingSubcategoryParentMap = loadUserSpendingSubcategoryChoices();

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

async function downstreamErrorMessage(response, fallbackMessage) {
  const payload = await response.json().catch(() => null);
  if (payload?.detail) {
    return typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
  }
  if (payload?.message) {
    return payload.message;
  }
  return `${fallbackMessage} (${response.status})`;
}

function findingMessages(findings = []) {
  return findings
    .map((finding) => {
      const code = finding.code ? `${finding.code}: ` : "";
      return `${code}${finding.message || "No detail provided."}`;
    })
    .filter(Boolean);
}

function ingestionFailureMessage(record) {
  const status = record?.status || "unknown";
  const reasons = findingMessages(record?.findings || []);
  if (status === "duplicate") {
    return reasons.length
      ? `This document was already uploaded. ${reasons.join(" ")}`
      : "This document was already uploaded. Choose a different file or remove the existing saved record before uploading it again.";
  }
  if (status === "queued" && !ingestionHandoffReady(record)) {
    return "Document upload stopped at ingestion. The queued record did not include a processing handoff.";
  }
  if (reasons.length) {
    return `Document upload stopped at ingestion. Status: ${status}. Reason: ${reasons.join(" ")}`;
  }
  return `Document upload stopped at ingestion. Status: ${status}. The ingestion service did not queue the file and did not return a reason.`;
}

function ingestionHandoffReady(record) {
  return Boolean(record?.handoff?.content_reference);
}

function createUploadAttemptIdempotencyKey() {
  if (window.crypto?.randomUUID) {
    return `manual-upload-${window.crypto.randomUUID()}`;
  }

  const values = new Uint32Array(4);
  window.crypto?.getRandomValues?.(values);
  const randomPart = Array.from(values, (value) => value.toString(36)).join("-");
  return `manual-upload-${Date.now().toString(36)}-${randomPart || Math.random().toString(36).slice(2)}`;
}

function resetUploadPage(message = "Choose a file to validate.", tone = "pending") {
  selectedFile = null;
  acceptedValidation = null;
  uploadAttemptIdempotencyKey = null;
  if (documentFileInput) {
    documentFileInput.value = "";
  }
  selectedFileSummary.hidden = true;
  validationResult.hidden = true;
  ingestionResult.hidden = true;
  parseResult.hidden = true;
  setValidationState(message, tone);
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

function titleCaseLabel(value) {
  return humanizeStatus(value || "unknown");
}

function normalizeChoice(value, fallback = "unknown") {
  const normalized = String(value || "").trim().toLowerCase();
  return normalized || fallback;
}

function normalizeLabelKey(value, fallback = "unknown") {
  const normalized = String(value || "")
    .trim()
    .toLowerCase()
    .replaceAll("-", "_")
    .replace(/\s+/g, "_")
    .split("_")
    .filter(Boolean)
    .join("_");
  return normalized || fallback;
}

function childParentMapFromVocabulary(vocabulary, subtypesKey, suppliedMap = {}) {
  const mapping = {};
  Object.entries(suppliedMap || {}).forEach(([child, parent]) => {
    const childKey = normalizeChoice(child);
    const parentKey = normalizeChoice(parent, "");
    if (childKey && !["unknown", "uncategorized"].includes(childKey) && parentKey) {
      mapping[childKey] = parentKey;
    }
  });
  Object.entries(vocabulary?.[subtypesKey] || {}).forEach(([parent, children]) => {
    const parentKey = normalizeChoice(parent, "");
    (children || []).forEach((child) => {
      const childKey = normalizeChoice(child);
      if (childKey && !["unknown", "uncategorized"].includes(childKey) && parentKey && !mapping[childKey]) {
        mapping[childKey] = parentKey;
      }
    });
  });
  return mapping;
}

function loadUserSpendingSubcategoryChoices() {
  try {
    const saved = JSON.parse(window.localStorage?.getItem(userSpendingClassificationStorageKey) || "{}");
    const mapping = {};
    Object.entries(saved || {}).forEach(([subcategory, category]) => {
      const childKey = normalizeLabelKey(subcategory);
      const parentKey = normalizeLabelKey(category, "uncategorized");
      if (childKey !== "unknown" && !["unknown", "uncategorized"].includes(parentKey)) {
        mapping[childKey] = parentKey;
      }
    });
    return mapping;
  } catch {
    return {};
  }
}

function saveUserSpendingSubcategoryChoices() {
  try {
    window.localStorage?.setItem(userSpendingClassificationStorageKey, JSON.stringify(userSpendingSubcategoryParentMap));
  } catch {
    // Browser storage can be disabled; the in-memory choices still keep the current review usable.
  }
}

function mergeUserSpendingChoices(activeMap) {
  return {
    ...(activeMap || {}),
    ...userSpendingSubcategoryParentMap,
  };
}

function orderedChoiceKeys(mapping, defaultValue = "unknown") {
  const keys = Object.keys(mapping || {});
  const defaultKey = normalizeChoice(defaultValue);
  const remaining = keys.filter((key) => key !== defaultKey).sort();
  return [defaultKey, ...remaining.filter(Boolean)];
}

function orderedParentChoiceKeys(mapping, defaultValue = "unknown") {
  const defaultKey = normalizeChoice(defaultValue);
  const parents = new Set(Object.values(mapping || {}).map((value) => normalizeChoice(value, "")).filter(Boolean));
  parents.delete(defaultKey);
  return [defaultKey, ...Array.from(parents).sort()];
}

function applyActiveRecognitionSettings(payload) {
  const context = payload?.recognition_context || {};
  const transactionVocabulary = payload?.transaction_vocabulary || context.transaction?.vocabulary || {};
  const spendingVocabulary = payload?.spending_vocabulary || context.spending?.vocabulary || {};
  const transactionMap = childParentMapFromVocabulary(
    transactionVocabulary,
    "transaction_subtypes",
    context.transaction?.subtype_parent_map,
  );
  const spendingMap = childParentMapFromVocabulary(
    spendingVocabulary,
    "spending_subcategories",
    context.spending?.subcategory_parent_map,
  );
  const activeSpendingMap = Object.keys(spendingMap).length ? spendingMap : fallbackSpendingSubcategoryParentMap;
  const mergedSpendingMap = mergeUserSpendingChoices(activeSpendingMap);

  classificationChoices = {
    transactionSubtypeParentMap: Object.keys(transactionMap).length ? transactionMap : { ...fallbackTransactionSubtypeParentMap },
    spendingSubcategoryParentMap: mergedSpendingMap,
    transactionSubtypeOptions: orderedChoiceKeys(
      Object.keys(transactionMap).length ? transactionMap : fallbackTransactionSubtypeParentMap,
      "unknown",
    ),
    spendingSubcategoryOptions: orderedChoiceKeys(mergedSpendingMap, "unknown"),
    spendingCategoryOptions: orderedParentChoiceKeys(mergedSpendingMap, "uncategorized"),
    activeRecognitionContext: context,
  };
}

async function loadActiveRecognitionChoices() {
  try {
    const response = await fetch("/api/v1/recognition-settings/active", {
      headers: statsAuthHeaders(),
    });
    if (!response.ok) {
      return;
    }
    applyActiveRecognitionSettings(await response.json());
  } catch {
    // Static fallback choices keep local upload review usable when M9 is unavailable.
  }
}

function statsAuthHeaders() {
  return window.statsAccess?.authHeaders?.() || {};
}

async function currentStatsUser() {
  return await window.statsAccess?.currentUser?.() || {};
}

function deriveTransactionType(transactionSubtype) {
  return classificationChoices.transactionSubtypeParentMap[normalizeChoice(transactionSubtype)] || "unknown";
}

function deriveSpendingCategory(spendingSubcategory) {
  return classificationChoices.spendingSubcategoryParentMap[normalizeChoice(spendingSubcategory)] || "uncategorized";
}

function spendingSubcategoryIsKnown(spendingSubcategory) {
  const child = normalizeLabelKey(spendingSubcategory);
  return child !== "unknown" && Boolean(classificationChoices.spendingSubcategoryParentMap[child]);
}

function rememberSpendingSubcategoryChoice(spendingSubcategory, spendingCategory) {
  const child = normalizeLabelKey(spendingSubcategory);
  const parent = normalizeLabelKey(spendingCategory, "uncategorized");
  if (child === "unknown" || ["unknown", "uncategorized"].includes(parent)) {
    return false;
  }

  const existingParent = classificationChoices.spendingSubcategoryParentMap[child];
  classificationChoices.spendingSubcategoryParentMap[child] = parent;
  userSpendingSubcategoryParentMap[child] = parent;
  saveUserSpendingSubcategoryChoices();
  if (!classificationChoices.spendingSubcategoryOptions.includes(child)) {
    classificationChoices.spendingSubcategoryOptions = [...classificationChoices.spendingSubcategoryOptions, child].sort();
  }
  if (!classificationChoices.spendingCategoryOptions.includes(parent)) {
    classificationChoices.spendingCategoryOptions = [...classificationChoices.spendingCategoryOptions, parent].sort();
  }
  return existingParent !== parent;
}

function spendingCategoryOptionsWithAddNew() {
  const existing = classificationChoices.spendingCategoryOptions
    .filter((value) => !["unknown", "uncategorized"].includes(normalizeLabelKey(value, "uncategorized")));
  return ["uncategorized", ...existing, addNewSpendingCategoryValue];
}

function showSpendingSubcategoryDialog(initialSubcategory = "") {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.className = "classification-modal-backdrop";
    backdrop.setAttribute("role", "presentation");

    const panel = document.createElement("section");
    panel.className = "classification-modal";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    panel.setAttribute("aria-labelledby", "spending-subcategory-dialog-title");

    const heading = document.createElement("h4");
    heading.id = "spending-subcategory-dialog-title";
    heading.textContent = "Add spending subcategory";

    const form = document.createElement("form");
    form.className = "classification-modal-form";

    const subcategoryLabel = document.createElement("label");
    subcategoryLabel.textContent = "Spending subcategory";
    const subcategoryInput = document.createElement("input");
    subcategoryInput.name = "new_spending_subcategory";
    subcategoryInput.type = "text";
    subcategoryInput.value = initialSubcategory ? titleCaseLabel(initialSubcategory) : "";
    subcategoryLabel.append(subcategoryInput);

    const categoryLabel = document.createElement("label");
    categoryLabel.textContent = "Parent spending category";
    const categorySelect = document.createElement("select");
    categorySelect.name = "parent_spending_category";
    spendingCategoryOptionsWithAddNew().forEach((category) => {
      const option = document.createElement("option");
      option.value = category;
      option.textContent = category === addNewSpendingCategoryValue ? "Add new category..." : titleCaseLabel(category);
      categorySelect.append(option);
    });
    categoryLabel.append(categorySelect);

    const newCategoryLabel = document.createElement("label");
    newCategoryLabel.textContent = "New parent category";
    newCategoryLabel.hidden = true;
    const newCategoryInput = document.createElement("input");
    newCategoryInput.name = "new_parent_spending_category";
    newCategoryInput.type = "text";
    newCategoryLabel.append(newCategoryInput);

    const errorMessage = document.createElement("p");
    errorMessage.className = "classification-modal-error";
    errorMessage.setAttribute("role", "alert");
    errorMessage.hidden = true;

    const actions = document.createElement("div");
    actions.className = "classification-modal-actions";
    const cancelButton = document.createElement("button");
    cancelButton.type = "button";
    cancelButton.textContent = "Cancel";
    const saveButton = document.createElement("button");
    saveButton.type = "submit";
    saveButton.textContent = "Add subcategory";
    actions.append(cancelButton, saveButton);

    form.append(subcategoryLabel, categoryLabel, newCategoryLabel, errorMessage, actions);
    panel.append(heading, form);
    backdrop.append(panel);
    document.body.append(backdrop);

    const close = (value) => {
      backdrop.remove();
      resolve(value);
    };
    const showError = (message) => {
      errorMessage.textContent = message;
      errorMessage.hidden = false;
    };

    categorySelect.addEventListener("change", () => {
      newCategoryLabel.hidden = categorySelect.value !== addNewSpendingCategoryValue;
      if (!newCategoryLabel.hidden) {
        newCategoryInput.focus();
      }
    });
    cancelButton.addEventListener("click", () => close(null));
    backdrop.addEventListener("click", (event) => {
      if (event.target === backdrop) {
        close(null);
      }
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const subcategory = normalizeLabelKey(subcategoryInput.value);
      const selectedParent = categorySelect.value === addNewSpendingCategoryValue
        ? normalizeLabelKey(newCategoryInput.value, "uncategorized")
        : normalizeLabelKey(categorySelect.value, "uncategorized");
      if (subcategory === "unknown") {
        showError("Enter a spending subcategory.");
        return;
      }
      if (["unknown", "uncategorized"].includes(selectedParent)) {
        showError("Choose or add a parent spending category.");
        return;
      }
      close({ subcategory, parentCategory: selectedParent });
    });
    subcategoryInput.focus();
  });
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
      && ["debit", "credit"].includes(String(record.direction || "").toLowerCase())
      && String(record.transaction_type || "unknown").toLowerCase() !== "unknown"
      && String(record.transaction_subtype || "unknown").toLowerCase() !== "unknown"
      && !["uncategorized", "unknown"].includes(String(record.spending_category || "uncategorized").toLowerCase())
      && String(record.spending_subcategory || "unknown").toLowerCase() !== "unknown",
  );
}

function transactionCoreFieldsComplete(record) {
  return Boolean(
    record.transaction_date
      && record.description
      && Number(record.amount) > 0
      && record.currency
      && ["debit", "credit"].includes(String(record.direction || "").toLowerCase()),
  );
}

function createReviewState(result) {
  const records = (result.normalized_records || []).map((record) => normalizeReviewRecord({ ...record }));
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

function normalizeReviewRecord(record) {
  record.transaction_subtype = normalizeLabelKey(record.transaction_subtype);
  record.spending_subcategory = normalizeLabelKey(record.spending_subcategory);
  const derivedTransactionType = deriveTransactionType(record.transaction_subtype);
  const derivedSpendingCategory = deriveSpendingCategory(record.spending_subcategory);
  record.transaction_type = derivedTransactionType !== "unknown"
    ? derivedTransactionType
    : normalizeLabelKey(record.transaction_type, "unknown");
  record.spending_category = derivedSpendingCategory !== "uncategorized"
    ? derivedSpendingCategory
    : normalizeLabelKey(record.spending_category, "uncategorized");
  record.category = record.spending_category === "uncategorized" ? "Unknown" : titleCaseLabel(record.spending_category);
  return record;
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
  const transactionSubtypes = withSuggestedOption(classificationChoices.transactionSubtypeOptions, record.suggested_transaction_subtype);
  const spendingSubcategories = withSuggestedOption(classificationChoices.spendingSubcategoryOptions, record.suggested_spending_subcategory);
  return [
    ["transaction_date", "Date", "date"],
    ["posted_date", "Posted date", "date"],
    ["description", "Description", "text"],
    ["amount", "Amount", "number"],
    ["currency", "Currency", "text"],
    ["direction", "Direction", "select", transactionDirectionOptions],
    ["transaction_subtype", "Transaction subtype", "select", transactionSubtypes],
    ["spending_subcategory", "Spending subcategory", "selectAddNew", spendingSubcategories],
  ].map(([name, label, type, options]) => ({ name, label, type, options: options || [], value: record[name] ?? "" }));
}

function withSuggestedOption(options, suggestedValue) {
  const suggested = String(suggestedValue || "").trim().toLowerCase();
  if (!suggested || options.includes(suggested)) {
    return options;
  }
  return [...options, suggested];
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
  if (fieldName === "direction") {
    return normalizeChoice(input.value);
  }
  if (["transaction_subtype", "spending_subcategory"].includes(fieldName)) {
    return normalizeLabelKey(input.value);
  }
  if (fieldName === "spending_category") {
    return normalizeLabelKey(input.value, "uncategorized");
  }
  return input.value.trim();
}

async function applyEditedRecord(record, values) {
  let nextSpendingSubcategory = normalizeLabelKey(values.spending_subcategory);
  if (nextSpendingSubcategory === normalizeLabelKey(addNewSpendingSubcategoryValue)) {
    const newClassification = await showSpendingSubcategoryDialog();
    if (!newClassification) {
      return false;
    }
    nextSpendingSubcategory = newClassification.subcategory;
    rememberSpendingSubcategoryChoice(newClassification.subcategory, newClassification.parentCategory);
    record.classification_user_added_spending_subcategory = true;
  }
  let nextSpendingCategory = deriveSpendingCategory(nextSpendingSubcategory);
  let spendingRelationshipChanged = false;
  if (nextSpendingSubcategory !== "unknown" && !spendingSubcategoryIsKnown(nextSpendingSubcategory)) {
    const newClassification = await showSpendingSubcategoryDialog(nextSpendingSubcategory);
    if (!newClassification) {
      return false;
    }
    nextSpendingSubcategory = newClassification.subcategory;
    nextSpendingCategory = newClassification.parentCategory;
    spendingRelationshipChanged = rememberSpendingSubcategoryChoice(nextSpendingSubcategory, nextSpendingCategory);
  }

  Object.assign(record, values);
  record.direction = String(record.direction || "").toLowerCase();
  record.transaction_subtype = normalizeLabelKey(record.transaction_subtype);
  record.spending_subcategory = nextSpendingSubcategory;
  if (spendingRelationshipChanged) {
    record.classification_user_added_spending_subcategory = true;
  }
  record.transaction_type = deriveTransactionType(record.transaction_subtype);
  record.spending_category = nextSpendingCategory;
  record.category = record.spending_category === "uncategorized" ? "Unknown" : titleCaseLabel(record.spending_category);
  record.amount = Math.abs(numericValue(record.amount));
  record.signed_amount = record.direction === "credit" ? record.amount : -record.amount;
  if (transactionFieldsComplete(record) && record.quality_status === "invalid") {
    record.quality_status = "warning";
  }
  return true;
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
  const hasStatementCreditTotal = Object.prototype.hasOwnProperty.call(reconciliation, "credit_total")
    && reconciliation.credit_total !== null
    && reconciliation.credit_total !== undefined;
  const statementCreditTotal = numericValue(reconciliation.credit_total);
  const effectiveCreditTotal = hasStatementCreditTotal ? statementCreditTotal : creditTotal;
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
  uploadAttemptIdempotencyKey = null;

  if (!file) {
    resetUploadPage();
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
      headers: statsAuthHeaders(),
      body: formData,
    });

    if (!response.ok) {
      throw new Error(await downstreamErrorMessage(response, "Validation service did not accept the request."));
    }

    const result = await response.json();
    renderValidationResult(result);

    if (result.status === "accepted") {
      acceptedValidation = result;
      uploadAttemptIdempotencyKey = createUploadAttemptIdempotencyKey();
      renderProcessingProgress(1, "Processing document", "The file is accepted. Stats is uploading it for processing.");
      setValidationState("File accepted. Sending it to processing.", "pending");
      await sendAcceptedFileToProcessing();
      return;
    }

    resetUploadPage("File rejected. Choose another file to continue.", "error");
  } catch (error) {
    resetUploadPage(error.message || "File validation failed.", "error");
  }
}

function renderIngestionResult(record) {
  ingestionResult.hidden = false;
  ingestionResult.dataset.status = record.status === "queued" ? "accepted" : "rejected";
  ingestionResult.replaceChildren();

  const heading = document.createElement("h3");
  heading.textContent = record.status === "queued"
    ? "Document uploaded"
    : record.status === "duplicate" ? "Document already uploaded" : "Document upload needs review";

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
  const classification = extractionResult.classification || {};
  return {
    extraction_id: extractionResult.extraction_id,
    parse_id: extractionResult.parse_id,
    document: extractionResult.document,
    document_type: extractionResult.document_type,
    document_type_confidence: classification.confidence,
    document_type_status: classification.status,
    document_type_reason_codes: classification.reason_codes || [],
    document_recognition_suggestion_id: classification.recognition_suggestion_id,
    document_recognition_suggestion_status: classification.recognition_suggestion_status || "none",
    suggested_document_type: classification.suggested_document_type,
    suggested_document_subtype: classification.suggested_document_subtype,
    document_suggestion_confidence: classification.suggestion_confidence,
    document_suggestion_reason_codes: classification.suggestion_reason_codes || [],
    document_suggestion_source: classification.suggestion_source,
    document_suggestion_evidence_ref: classification.suggestion_evidence_ref,
    transaction_candidates: extractionResult.transaction_candidates || [],
    financial_field_candidates: extractionResult.financial_field_candidates || [],
    section_candidates: extractionResult.section_candidates || [],
    entity_candidates: extractionResult.entity_candidates || [],
    reference_candidates: extractionResult.reference_candidates || [],
    line_item_candidates: extractionResult.line_item_candidates || [],
    installment_candidates: extractionResult.installment_candidates || [],
    reconciliation: extractionResult.reconciliation || null,
    active_recognition_context: classificationChoices.activeRecognitionContext || {},
    findings: extractionResult.findings || [],
  };
}

function buildSaveValidationResult(validationResult, reviewState) {
  const acceptedRecordIds = reviewState.acceptedRecordIds;
  const acceptedInstallmentIds = reviewState.acceptedInstallmentIds;
  const normalizedRecords = reviewState.records.map((record) => {
    const accepted = acceptedRecordIds.has(record.record_id) && transactionFieldsComplete(record);
    const saveRecord = normalizeReviewRecord(accepted ? acceptedClassificationRecord(record) : { ...record });
    const userAddedClassification = hasUserAddedClassification(saveRecord);
    return {
      ...saveRecord,
      category: saveRecord.spending_category && saveRecord.spending_category !== "uncategorized"
        ? titleCaseLabel(saveRecord.spending_category)
        : saveRecord.category || "Unknown",
      classification_source: accepted
        ? (userAddedClassification ? "user_confirmed_classification" : confirmedClassificationSource(saveRecord))
        : saveRecord.classification_source,
      classification_review_required: accepted ? false : Boolean(saveRecord.classification_review_required),
      classification_review_reason_codes: accepted ? [] : saveRecord.classification_review_reason_codes || [],
      classification_human_confirmed: accepted || Boolean(saveRecord.classification_human_confirmed),
      classification_confirmation_mode: accepted
        ? "upload_transaction_review"
        : saveRecord.classification_confirmation_mode,
      classification_vocabulary_status: accepted && userAddedClassification
        ? "outside_vocabulary_proposal"
        : saveRecord.classification_vocabulary_status,
      recognition_suggestion_status: accepted ? "confirmed_by_upload_review" : saveRecord.recognition_suggestion_status,
      suggested_spending_category: saveRecord.suggested_spending_category || (userAddedClassification ? saveRecord.spending_category : undefined),
      suggested_spending_subcategory: saveRecord.suggested_spending_subcategory || (userAddedClassification ? saveRecord.spending_subcategory : undefined),
      quality_status: accepted
        ? (transactionFieldsComplete(saveRecord) ? "valid" : "warning")
        : saveRecord.quality_status,
    };
  });
  const normalizedInstallments = reviewState.installments.map((installment) => ({
    ...installment,
    quality_status: acceptedInstallmentIds.has(installment.installment_id) && installmentFieldsComplete(installment)
      ? "valid"
      : installment.quality_status,
  }));
  const validRecordCount = normalizedRecords.filter((record) => record.quality_status === "valid").length;
  const warningRecordCount = normalizedRecords.filter((record) => record.quality_status === "warning").length;
  const invalidRecordCount = normalizedRecords.filter((record) => record.quality_status === "invalid").length;

  return {
    ...validationResult,
    normalized_records: normalizedRecords,
    normalized_installments: normalizedInstallments,
    summary: {
      ...(validationResult.summary || {}),
      valid_record_count: validRecordCount,
      warning_record_count: warningRecordCount,
      invalid_record_count: invalidRecordCount,
      document_review_status: warningRecordCount || invalidRecordCount ? "needs_review" : "ready",
      recommended_action: warningRecordCount || invalidRecordCount ? "review_items" : "save_ready_transactions",
    },
  };
}

function acceptedClassificationRecord(record) {
  return { ...record };
}

function confirmedClassificationSource(record) {
  const source = String(record.classification_source || "unknown").toLowerCase();
  if (source.includes("ai")) {
    return "user_confirmed_ai_suggestion";
  }
  return "user_confirmed_classification";
}

function hasUserAddedClassification(record) {
  return Boolean(record.classification_user_added_spending_subcategory);
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
    if (field.type === "select" || field.type === "selectAddNew") {
      input = document.createElement("select");
      field.options.forEach((optionValue) => {
        const option = document.createElement("option");
        option.value = optionValue;
        option.textContent = titleCaseLabel(optionValue);
        option.selected = String(field.value).toLowerCase() === optionValue;
        input.append(option);
      });
      if (field.type === "selectAddNew") {
        const addOption = document.createElement("option");
        addOption.value = addNewSpendingSubcategoryValue;
        addOption.textContent = "Add new subcategory...";
        input.append(addOption);
      }
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

  const spendingSubcategoryInput = inputs.get("spending_subcategory");
  if (spendingSubcategoryInput?.tagName === "SELECT") {
    spendingSubcategoryInput.addEventListener("change", async () => {
      if (spendingSubcategoryInput.value !== addNewSpendingSubcategoryValue) {
        return;
      }
      const previousValue = normalizeLabelKey(record.spending_subcategory);
      const newClassification = await showSpendingSubcategoryDialog();
      if (!newClassification) {
        spendingSubcategoryInput.value = previousValue;
        return;
      }
      rememberSpendingSubcategoryChoice(newClassification.subcategory, newClassification.parentCategory);
      record.classification_user_added_spending_subcategory = true;

      const option = document.createElement("option");
      option.value = newClassification.subcategory;
      option.textContent = titleCaseLabel(newClassification.subcategory);
      const addNewOption = Array.from(spendingSubcategoryInput.options).find((item) => item.value === addNewSpendingSubcategoryValue);
      spendingSubcategoryInput.insertBefore(option, addNewOption || null);
      spendingSubcategoryInput.value = newClassification.subcategory;
    });
  }

  const saveButton = document.createElement("button");
  saveButton.type = "submit";
  saveButton.textContent = "Save edit";
  form.append(saveButton);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = {};
    inputs.forEach((input, fieldName) => {
      values[fieldName] = fieldValueFromInput(input, fieldName);
    });
    if (options.kind === "installment") {
      applyEditedInstallment(record, values);
    } else {
      const applied = await applyEditedRecord(record, values);
      if (!applied) {
        return;
      }
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
    const header = document.createElement("div");
    header.className = "review-item-header";
    const headerText = document.createElement("div");
    const title = document.createElement("h5");
    title.textContent = item.title || "Review item";
    const message = document.createElement("p");
    message.textContent = item.message || "This item needs review.";
    headerText.append(title, message);
    header.append(headerText);
    row.append(header);

    const record = reviewItemRecord(item, reviewState.records);
    const installment = reviewItemInstallment(item, reviewState.installments);
    if (record) {
      const details = document.createElement("dl");
      details.className = "review-details review-details-transaction";
      [
        ["Date", record.transaction_date || "Needs review"],
        ["Description", record.description || "Needs review"],
        ["Amount", formatMoney(record.amount, record.currency)],
        ["Direction", titleCaseLabel(record.direction || "unknown")],
        ["Status", localRecordStatus(record, reviewState)],
        ["Transaction type", titleCaseLabel(record.transaction_type || "unknown")],
        ["Transaction subtype", titleCaseLabel(record.transaction_subtype || "unknown")],
        ["Spending category", titleCaseLabel(record.spending_category || "uncategorized")],
        ["Spending subcategory", titleCaseLabel(record.spending_subcategory || "unknown")],
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
      details.className = "review-details review-details-installment";
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
      acceptButton.title = acceptButton.disabled ? "Complete date, description, amount, currency, direction, transaction subtype, and spending subcategory before accepting this row." : "";
      acceptButton.addEventListener("click", () => {
        reviewState.acceptedRecordIds.add(record.record_id);
        record.quality_status = transactionFieldsComplete(record) ? "valid" : "warning";
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
    header.append(actions);
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
  ["Date", "Description", "Amount", "Transaction type", "Spending category", "Status", "Actions"].forEach((label) => {
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
      titleCaseLabel(record.transaction_type || "unknown"),
      titleCaseLabel(record.spending_category || "uncategorized"),
      status,
    ].forEach((value, index) => {
      const cell = document.createElement("td");
      if (index === 5) {
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
      editCell.colSpan = 7;
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
  const finalReady = reviewState.records.length > 0 && allRowsAccepted && reconciliation.matched;

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
  saveButton.disabled = !finalReady;
  saveButton.title = finalReady
    ? "Save reviewed transactions."
    : "Accept all rows and resolve reconciliation before saving.";
  saveButton.addEventListener("click", async () => {
    saveButton.disabled = true;
    saveButton.textContent = "Checking duplicates";
    try {
      const duplicateCheck = await checkDuplicateTransactions(result, reviewState);
      if (duplicateCheck.status !== "ready") {
        const existingDuplicatePanel = parseResult.querySelector(".duplicate-review");
        if (existingDuplicatePanel) {
          existingDuplicatePanel.remove();
        }
        parseResult.insertBefore(renderDuplicateCheckPanel(duplicateCheck), actions);
        saveButton.disabled = false;
        saveButton.textContent = "Save ready transactions";
        setValidationState(duplicateCheckMessage(duplicateCheck), "error");
        return;
      }
      saveButton.textContent = "Saving transactions";
      const saveResult = await saveReadyTransactions(result, reviewState);
      resetUploadPage("Transactions saved. Choose another file to continue.", "success");
      saveButton.textContent = "Transactions saved";
      saveButton.title = `Saved ${saveResult.saved_record_count || 0} transaction rows.`;
    } catch (error) {
      saveButton.disabled = false;
      saveButton.textContent = "Save ready transactions";
      setValidationState(error.message || "Transaction save failed.", "error");
    }
  });

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
  formData.append("idempotency_key", uploadAttemptIdempotencyKey || createUploadAttemptIdempotencyKey());

  try {
    setValidationState("Sending accepted file to processing.", "pending");
    renderProcessingProgress(1, "Processing document", "Uploading the accepted document.");

    const user = await currentStatsUser();
    formData.append("submitted_by", user.email || "");

    const response = await fetch(statsApiUrl(fileIngestionBaseUrl, "/api/v1/ingestions"), {
      method: "POST",
      headers: statsAuthHeaders(),
      body: formData,
    });

    if (!response.ok) {
      throw new Error(await downstreamErrorMessage(response, "Ingestion service did not accept the request."));
    }

    const record = await response.json();
    renderIngestionResult(record);

    if (record.status === "queued" && ingestionHandoffReady(record)) {
      renderProcessingProgress(2, "Reading document", "The document is uploaded. Stats is reading the text.");
      setValidationState("Document ingested. Parsing document.", "pending");
      await startAcceptedFileProcessingJob(record);
      return;
    }

    renderProcessingProgress(1, "Document upload stopped", ingestionFailureMessage(record));
    setValidationState(ingestionFailureMessage(record), "error");
  } catch (error) {
    resetUploadPage(error.message || "File ingestion failed.", "error");
  }
}

async function startAcceptedFileProcessingJob(record) {
  const metadata = acceptedValidation.metadata || {};
  const formData = new FormData();
  formData.append("file", selectedFile);
  formData.append("ingestion_id", record.ingestion_id || "");
  const user = await currentStatsUser();
  formData.append("uploaded_by_user_id", user.id || "");
  formData.append("source_type", "manual_upload");
  formData.append("source_id", "stats-web-upload");
  formData.append("sha256", metadata.sha256 || "");
  formData.append("detected_mime_type", metadata.detected_mime_type || selectedFile.type || "");
  formData.append("allow_ocr_fallback", "true");
  formData.append("classification_threshold", "0.1");

  try {
    renderProcessingProgress(2, "Reading document", "Stats is reading the document text. You can keep this page open while it works.");
    const response = await fetch("/api/v1/upload-processing-jobs", {
      method: "POST",
      headers: statsAuthHeaders(),
      body: formData,
    });

    if (!response.ok) {
      throw new Error(await downstreamErrorMessage(response, "Document processing could not be started."));
    }

    const job = await response.json();
    await pollProcessingJob(job.job_id);
  } catch (error) {
    resetUploadPage(error.message || "Document processing failed.", "error");
  }
}

async function pollProcessingJob(jobId) {
  if (!jobId) {
    throw new Error("Document processing did not return a job identifier.");
  }

  const startedAt = Date.now();
  const maxWaitMs = 30 * 60 * 1000;

  while (Date.now() - startedAt < maxWaitMs) {
    const response = await fetch(`/api/v1/upload-processing-jobs/${encodeURIComponent(jobId)}`, {
      headers: statsAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(await downstreamErrorMessage(response, "Document processing status could not be read."));
    }

    const job = await response.json();
    renderProcessingJobProgress(job);

    if (job.status === "completed") {
      const payload = job.result_payload || {};
      const parseResultPayload = payload.parse_result;
      const extraction = payload.extraction_result;
      const validation = payload.validation_result;
      if (!parseResultPayload || !extraction || !validation) {
        throw new Error("Document processing completed without the expected review output.");
      }

      await loadActiveRecognitionChoices();
      validation.processing_job_id = job.job_id;
      renderTransactionCheckResult(validation, parseResultPayload, extraction);
      setValidationState("Transactions checked. Review the results before saving.", "success");
      return;
    }

    if (job.status === "failed") {
      resetUploadPage(job.message || job.error_detail || "Document processing failed. Choose another file to continue.", "error");
      return;
    }

    await sleep(2500);
  }

  throw new Error("Document processing is still running. Refresh the page and check the upload again.");
}

function renderProcessingJobProgress(job) {
  const stage = job.stage || "parsing";
  const stageIndex = {
    uploaded: 1,
    parsing: 2,
    extracting: 3,
    validating: 3,
    completed: 4,
    failed: 2,
  }[stage] ?? 2;

  const title = stage === "completed" ? "Transactions checked" : "Processing document";
  const message = job.message || "Stats is checking the document.";
  renderProcessingProgress(stageIndex, title, message);
  setValidationState(message, stage === "failed" ? "error" : "pending");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function extractTransactions(parseResultPayload) {
  const response = await fetch(statsApiUrl(transactionExtractionBaseUrl, "/api/v1/extractions"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...statsAuthHeaders(),
    },
    body: JSON.stringify(buildExtractionRequest(parseResultPayload)),
  });

  if (!response.ok) {
    throw new Error(await downstreamErrorMessage(response, "Transaction extraction service did not accept the request."));
  }

  return response.json();
}

async function validateExtractedData(extractionResult) {
  await loadActiveRecognitionChoices();
  const response = await fetch(statsApiUrl(dataValidationBaseUrl, "/api/v1/validations"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...statsAuthHeaders(),
    },
    body: JSON.stringify(buildValidationRequest(extractionResult)),
  });

  if (!response.ok) {
    throw new Error(await downstreamErrorMessage(response, "Data validation service did not accept the request."));
  }

  return response.json();
}

async function saveReadyTransactions(validationResult, reviewState) {
  const user = await currentStatsUser();
  const response = await fetch(statsApiUrl(statsDataBaseUrl, "/api/v1/transactions/batches"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...statsAuthHeaders(),
    },
    body: JSON.stringify({
      validation_result: buildSaveValidationResult(validationResult, reviewState),
      uploaded_by_user_id: user.id,
      saved_by_user_id: user.id,
      user_email: user.email,
      processing_job_id: validationResult.processing_job_id || null,
    }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Stats Data did not save the transactions.");
  }

  const payload = await response.json();
  await loadActiveRecognitionChoices();
  return payload;
}

async function checkDuplicateTransactions(validationResult, reviewState) {
  const user = await currentStatsUser();
  const response = await fetch(statsApiUrl(statsDataBaseUrl, "/api/v1/transactions/duplicate-checks"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...statsAuthHeaders(),
    },
    body: JSON.stringify({
      validation_result: buildSaveValidationResult(validationResult, reviewState),
      uploaded_by_user_id: user.id,
      saved_by_user_id: user.id,
      user_email: user.email,
      processing_job_id: validationResult.processing_job_id || null,
    }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Stats Data could not check for duplicates.");
  }

  return response.json();
}

function duplicateCheckMessage(duplicateCheck) {
  const summary = duplicateCheck.summary || {};
  const exact = Number(summary.exact_file_duplicates || 0) + Number(summary.exact_transaction_duplicates || 0);
  const possible = Number(summary.possible_document_duplicates || 0)
    + Number(summary.possible_transaction_duplicates || 0)
    + Number(summary.within_batch_duplicates || 0);
  if (exact) {
    return `${exact} saved item already matches this upload. Review duplicates before saving.`;
  }
  if (possible) {
    return `${possible} possible duplicate item needs review before saving.`;
  }
  return "Duplicate review is not ready yet.";
}

function renderDuplicateCheckPanel(duplicateCheck) {
  const summary = duplicateCheck.summary || {};
  const panel = document.createElement("section");
  panel.className = "duplicate-review";

  const heading = document.createElement("h4");
  heading.textContent = duplicateCheck.status === "blocked" ? "Duplicate save blocked" : "Possible duplicates need review";
  const copy = document.createElement("p");
  copy.textContent = duplicateCheck.status === "blocked"
    ? "Stats found saved data that already matches this upload. Review the matches before trying to save again."
    : "Stats found possible matches in saved data. Check these before saving so the database does not get duplicate records.";
  panel.append(heading, copy);

  const metrics = document.createElement("dl");
  metrics.className = "duplicate-review-metrics";
  [
    ["Transactions checked", summary.total_checked ?? 0],
    ["Already saved", Number(summary.exact_file_duplicates || 0) + Number(summary.exact_transaction_duplicates || 0)],
    ["Possible matches", Number(summary.possible_document_duplicates || 0) + Number(summary.possible_transaction_duplicates || 0)],
    ["Same upload duplicates", summary.within_batch_duplicates ?? 0],
  ].forEach(([label, value]) => {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = label;
    description.textContent = String(value);
    row.append(term, description);
    metrics.append(row);
  });
  panel.append(metrics);

  const results = [
    ...(duplicateCheck.document_results || []),
    ...(duplicateCheck.transaction_results || []),
  ];
  if (results.length) {
    const list = document.createElement("ul");
    list.className = "duplicate-review-list";
    results.forEach((item) => {
      const row = document.createElement("li");
      const title = document.createElement("strong");
      title.textContent = duplicateMatchLabel(item);
      const message = document.createElement("span");
      message.textContent = item.message || "This item may already be saved.";
      row.append(title, message);
      list.append(row);
    });
    panel.append(list);
  }

  return panel;
}

function duplicateMatchLabel(item) {
  const labels = {
    exact_file_duplicate: "Same file already uploaded",
    possible_same_document: "Similar document already saved",
    within_batch_duplicate: "Duplicate row in this upload",
    exact_transaction_duplicate: "Transaction already saved",
    possible_transaction_duplicate: "Similar transaction already saved",
  };
  const prefix = labels[item.match_type] || "Possible duplicate";
  return item.record_id ? `${prefix}: ${item.record_id}` : prefix;
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
