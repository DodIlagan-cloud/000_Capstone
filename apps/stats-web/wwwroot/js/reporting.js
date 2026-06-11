// Loads the safe analytics embed contract and keeps reporting currency state consistent.
const reportingCurrencyKey = "stats.reportingCurrency";
const reportingCurrencySelect = document.querySelector("#reporting-currency");
const reportingStatusPill = document.querySelector("#reporting-status-pill");
const reportingMessage = document.querySelector("#reporting-message");
const reportingLastUpdated = document.querySelector("#reporting-last-updated");
const reportingRateBasis = document.querySelector("#reporting-rate-basis");
const reportingEmbedHost = document.querySelector("#reporting-embed-host");
const reportingKpiCards = [...document.querySelectorAll("[data-kpi-card]")];
const monthlyExpenseHistory = document.querySelector("#monthly-expense-history");
const monthlyHistoryCurrency = document.querySelector("#monthly-history-currency");
const reportPageButtons = [...document.querySelectorAll("[data-report-page]")];
const selectedReportTitle = document.querySelector("#selected-report-title");
const selectedReportPurpose = document.querySelector("#selected-report-purpose");
const selectedReportDataTitle = document.querySelector("#selected-report-data-title");
const selectedReportData = document.querySelector("#selected-report-data");
const selectedReportReviewTitle = document.querySelector("#selected-report-review-title");
const selectedReportReview = document.querySelector("#selected-report-review");
let powerBiClientLoadPromise = null;
let embeddedReport = null;
let embeddedReportPages = [];

const reportPageContent = {
  "financial-overview": {
    title: "Financial overview",
    purpose: "Answers how much was spent, how spending moved across recent months, and which records influence current expenses.",
    dataTitle: "Curated transactions",
    data: "Uses saved transaction dates, debit amounts, category labels when available, and source document links from Stats Data.",
    reviewTitle: "Classification gaps",
    review: "Check uncategorized transactions, low-confidence category suggestions, duplicate-looking rows, and validation warnings.",
  },
  "spending-categories": {
    title: "Spending categories",
    purpose: "Shows where expenses are going after transactions have been classified into a stable category taxonomy.",
    dataTitle: "Classified expenses",
    data: "Uses expense transactions with assigned categories, transaction dates, selected currency, and source document references.",
    reviewTitle: "Uncategorized spend",
    review: "The key risk is uncategorized or weakly classified transactions, because category totals only become useful when classification is reliable.",
  },
  "transaction-classification": {
    title: "Transaction classification",
    purpose: "Shows classification coverage, suggested categories, confidence levels, and records that need user review before category reports are trusted.",
    dataTitle: "Classification signals",
    data: "Uses transaction descriptions, source institution, amount patterns, document type, existing category rules, and prior user corrections.",
    reviewTitle: "Human confirmation",
    review: "Ambiguous descriptions should be flagged for review instead of forced into a category. Confirmed corrections should improve future suggestions.",
  },
  "source-document-coverage": {
    title: "Source document coverage",
    purpose: "Shows whether the reporting period has enough source documents to support the financial picture.",
    dataTitle: "Document provenance",
    data: "Uses saved documents, source type, source institution, parsed transaction counts, workflow status, and saved timestamps.",
    reviewTitle: "Coverage gaps",
    review: "Missing months, rejected files, failed parsing, or documents with no extracted rows should be reviewed before relying on totals.",
  },
  "data-quality-confidence": {
    title: "Data quality and confidence",
    purpose: "Shows whether extracted records are complete, valid, and reliable enough for reporting.",
    dataTitle: "Validation findings",
    data: "Uses missing-field counts, invalid values, duplicate-looking records, OCR quality, and review-required markers.",
    reviewTitle: "Trust limits",
    review: "Financial totals should be treated with caution when validation warnings or low-confidence extraction affect included records.",
  },
  "review-exceptions": {
    title: "Review and exceptions",
    purpose: "Highlights records that need attention instead of forcing users to inspect every transaction manually.",
    dataTitle: "Exception queue",
    data: "Uses high-value records, unusual movements, missing categories, duplicate-looking rows, failed processing, and unsupported document types.",
    reviewTitle: "Action needed",
    review: "Resolve review items and classification gaps first; category and trend reports become stronger as exceptions are cleared.",
  },
};

function selectedReportingCurrency() {
  const stored = sessionStorage.getItem(reportingCurrencyKey);
  return (reportingCurrencySelect?.value || stored || "NZD").toUpperCase();
}

function setReportingCurrency(value) {
  const normalized = String(value || "NZD").toUpperCase();
  sessionStorage.setItem(reportingCurrencyKey, normalized);
  if (reportingCurrencySelect) {
    reportingCurrencySelect.value = normalized;
  }
  return normalized;
}

function reportingApiUrl(currency) {
  const surface = reportingEmbedHost?.dataset.reportingSurface || document.body?.dataset.reportingSurface || "";
  const parameters = new URLSearchParams({ currency });
  if (surface) {
    parameters.set("surface", surface);
  }
  return `/api/v1/reporting/embed-config?${parameters.toString()}`;
}

function reportingKpiApiUrl(currency) {
  return `/api/v1/reporting/kpis?currency=${encodeURIComponent(currency)}`;
}

function formatReportingLabel(value) {
  return String(value || "transaction_date")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatReportingDate(value) {
  if (!value) {
    return "Refresh metadata unavailable";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function normalizeReportPageName(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

async function selectEmbeddedReportPage(pageKey) {
  if (!embeddedReport || !embeddedReportPages.length) {
    return;
  }

  const page = embeddedReportPages.find((candidate) => (
    normalizeReportPageName(candidate.displayName) === pageKey
    || normalizeReportPageName(candidate.name) === pageKey
  ));
  if (page && typeof page.setActive === "function") {
    await page.setActive();
  }
}

function setSelectedReportPage(pageKey) {
  const key = reportPageContent[pageKey] ? pageKey : "financial-overview";
  const content = reportPageContent[key];

  reportPageButtons.forEach((button) => {
    const selected = button.dataset.reportPage === key;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", selected ? "true" : "false");
  });

  if (selectedReportTitle) {
    selectedReportTitle.textContent = content.title;
  }
  if (selectedReportPurpose) {
    selectedReportPurpose.textContent = content.purpose;
  }
  if (selectedReportDataTitle) {
    selectedReportDataTitle.textContent = content.dataTitle;
  }
  if (selectedReportData) {
    selectedReportData.textContent = content.data;
  }
  if (selectedReportReviewTitle) {
    selectedReportReviewTitle.textContent = content.reviewTitle;
  }
  if (selectedReportReview) {
    selectedReportReview.textContent = content.review;
  }

  selectEmbeddedReportPage(key).catch(() => {
    // Context selection remains useful even when the embedded report has no matching page yet.
  });
}

function hasPowerBiClient() {
  return Boolean(powerBiModels() && typeof window.powerbi?.embed === "function");
}

function powerBiModels() {
  return window.powerbi?.models || window["powerbi-client"]?.models || null;
}

function ensurePowerBiClient() {
  if (hasPowerBiClient()) {
    return Promise.resolve(true);
  }

  if (powerBiClientLoadPromise) {
    return powerBiClientLoadPromise;
  }

  powerBiClientLoadPromise = new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = `/js/powerbi.min.js?retry=${Date.now()}`;
    script.async = true;
    script.onload = () => resolve(hasPowerBiClient());
    script.onerror = () => resolve(false);
    document.head.append(script);
  });

  return powerBiClientLoadPromise;
}

function setReportingStatus(status, message) {
  if (reportingStatusPill) {
    reportingStatusPill.classList.toggle("pending", status !== "configured");
    reportingStatusPill.classList.toggle("error", status === "unavailable");
    reportingStatusPill.textContent = status === "configured"
      ? "Connected"
      : status === "unavailable"
        ? "Unavailable"
        : "Not connected";
  }

  if (reportingMessage) {
    const isHomeKpiSurface = reportingKpiCards.length > 0 && !reportingEmbedHost;
    if (isHomeKpiSurface && status === "configured") {
      reportingMessage.hidden = true;
      reportingMessage.textContent = "";
    } else {
      reportingMessage.hidden = false;
      reportingMessage.textContent = message || "Analytics reporting is not connected yet.";
    }
  }

  if (reportingEmbedHost) {
    reportingEmbedHost.dataset.status = status;
  }
}

function safeReportingErrorMessage() {
  return "Financial report could not be rendered.";
}

function formatMoney(value, currency) {
  if (value === null || value === undefined || value === "") {
    return "No data";
  }

  const numericValue = Number(value);
  if (Number.isNaN(numericValue)) {
    return String(value);
  }

  return new Intl.NumberFormat(undefined, {
    currency,
    currencyDisplay: "code",
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
    style: "currency",
  }).format(numericValue);
}

function renderKpiCards(cards, currency) {
  const cardMap = new Map((cards || []).map((card) => [card.id, card]));
  reportingKpiCards.forEach((element) => {
    const payload = cardMap.get(element.dataset.kpiCard);
    const value = element.querySelector("[data-kpi-value]");
    const detail = element.querySelector("[data-kpi-detail]");
    element.dataset.status = payload ? "configured" : "unavailable";
    if (value) {
      value.textContent = payload ? formatMoney(payload.amount, currency) : "No data";
    }
    if (detail) {
      detail.textContent = payload?.detail || "Analytics has not returned this KPI yet.";
    }
  });
}

function formatMonthLabel(value) {
  const [year, month] = String(value || "").split("-").map((part) => Number(part));
  if (!year || !month) {
    return value || "Month";
  }

  return new Date(year, month - 1, 1).toLocaleDateString(undefined, {
    month: "short",
    year: "2-digit",
  });
}

function monthKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function completeMonthlyHistory(history) {
  const rows = Array.isArray(history) ? history : [];
  const rowMap = new Map(rows.map((row) => [String(row.month || ""), row]));
  const latestDataMonth = rows
    .map((row) => String(row.month || ""))
    .filter(Boolean)
    .sort()
    .at(-1);
  const [latestYear, latestMonth] = String(latestDataMonth || "").split("-").map((part) => Number(part));
  const endDate = latestYear && latestMonth
    ? new Date(latestYear, latestMonth - 1, 1)
    : new Date();
  const completedRows = [];

  for (let offset = 5; offset >= 0; offset -= 1) {
    const date = new Date(endDate.getFullYear(), endDate.getMonth() - offset, 1);
    const key = monthKey(date);
    completedRows.push(rowMap.get(key) || { amount: 0, month: key });
  }

  return completedRows;
}

function renderMonthlyHistory(history, currency) {
  if (!monthlyExpenseHistory) {
    return;
  }

  const rows = Array.isArray(history) ? history : [];
  monthlyExpenseHistory.replaceChildren();
  if (monthlyHistoryCurrency) {
    monthlyHistoryCurrency.textContent = currency;
  }

  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "panel-copy";
    empty.textContent = "No monthly expense history is available yet.";
    monthlyExpenseHistory.append(empty);
    return;
  }

  const completedRows = completeMonthlyHistory(rows);
  const maxAmount = Math.max(...completedRows.map((row) => Number(row.amount) || 0), 1);
  completedRows.forEach((row) => {
    const amount = Number(row.amount) || 0;
    const column = document.createElement("div");
    column.className = "history-column";

    const value = document.createElement("span");
    value.className = "history-value";
    value.textContent = formatMoney(amount, currency);

    const bar = document.createElement("span");
    bar.className = "history-bar";
    bar.style.setProperty("--bar-height", `${amount > 0 ? Math.max(12, Math.round((amount / maxAmount) * 100)) : 7}%`);

    const label = document.createElement("span");
    label.className = "history-label";
    label.textContent = formatMonthLabel(row.month);

    column.append(value, bar, label);
    monthlyExpenseHistory.append(column);
  });
}

async function loadReportingKpis() {
  if (!reportingKpiCards.length) {
    return false;
  }

  const currency = setReportingCurrency(selectedReportingCurrency());
  try {
    setReportingStatus("pending", "Loading financial KPI cards.");
    const response = await fetch(reportingKpiApiUrl(currency), {
      headers: window.statsAccess?.authHeaders?.() || {},
    });
    const payload = await response.json();
    const status = payload.status || (response.ok ? "configured" : "unavailable");
    setReportingStatus(status, payload.message);
    renderKpiCards(payload.cards, payload.selected_currency || currency);
    renderMonthlyHistory(payload.monthly_history, payload.selected_currency || currency);

    if (reportingLastUpdated) {
      reportingLastUpdated.textContent = status === "configured"
        ? formatReportingDate(payload.last_refreshed_at_utc || new Date().toISOString())
        : "Not connected";
    }

    if (reportingRateBasis) {
      reportingRateBasis.textContent = formatReportingLabel(payload.rate_basis);
    }
  } catch (error) {
    setReportingStatus("unavailable", error.message || "Financial KPI cards are temporarily unavailable.");
    renderKpiCards([], currency);
    renderMonthlyHistory([], currency);
    if (reportingLastUpdated) {
      reportingLastUpdated.textContent = "Unavailable";
    }
  }

  return true;
}

async function renderPowerBiReport(payload) {
  if (!reportingEmbedHost || !payload?.embed_url || !payload?.access_token || !payload?.report_id) {
    return;
  }

  setReportingStatus("configured", "Loading financial report.");
  const clientReady = await ensurePowerBiClient();
  if (!clientReady) {
    setReportingStatus("unavailable", "The report viewer is not available.");
    return;
  }

  const models = powerBiModels();
  const embedConfig = {
    type: "report",
    id: payload.report_id,
    embedUrl: payload.embed_url,
    accessToken: payload.access_token,
    tokenType: models.TokenType.Embed,
    permissions: models.Permissions.Read,
    settings: {
      panes: {
        filters: { visible: false },
        pageNavigation: { visible: payload.surface !== "home" },
      },
      background: models.BackgroundType.Transparent,
    },
  };

  if (payload.default_page_name) {
    embedConfig.pageName = payload.default_page_name;
  }

  reportingEmbedHost.replaceChildren();
  reportingEmbedHost.classList.add("is-embedded");
  window.powerbi.reset(reportingEmbedHost);
  const report = window.powerbi.embed(reportingEmbedHost, embedConfig);
  embeddedReport = report;

  report.on("loaded", () => {
    setReportingStatus("configured", "Financial report loaded.");
    if (typeof report.getPages === "function") {
      report.getPages()
        .then((pages) => {
          embeddedReportPages = Array.isArray(pages) ? pages : [];
          const selectedButton = reportPageButtons.find((button) => button.getAttribute("aria-pressed") === "true");
          if (selectedButton) {
            return selectEmbeddedReportPage(selectedButton.dataset.reportPage);
          }
          return null;
        })
        .catch(() => {
          embeddedReportPages = [];
        });
    }
  });

  report.on("error", (event) => {
    if (event?.detail?.message) {
      console.warn("Power BI embed error occurred.");
    }
    setReportingStatus("unavailable", safeReportingErrorMessage());
  });
}

async function loadReportingConfig() {
  if (!reportingStatusPill && !reportingCurrencySelect && !reportingEmbedHost) {
    return;
  }

  if (await loadReportingKpis()) {
    return;
  }

  const currency = setReportingCurrency(selectedReportingCurrency());
  try {
    const response = await fetch(reportingApiUrl(currency), {
      headers: window.statsAccess?.authHeaders?.() || {},
    });
    const payload = await response.json();
    const status = payload.status || (response.ok ? "configured" : "unavailable");

    setReportingStatus(status, payload.message);

    if (reportingLastUpdated) {
      reportingLastUpdated.textContent = status === "configured"
        ? formatReportingDate(payload.last_refreshed_at_utc)
        : "Not connected";
    }

    if (reportingRateBasis) {
      reportingRateBasis.textContent = formatReportingLabel(payload.rate_basis);
    }

    if (status === "configured") {
      await renderPowerBiReport(payload);
    }
  } catch (error) {
    setReportingStatus("unavailable", error.message || "Financial reporting is temporarily unavailable.");
    if (reportingLastUpdated) {
      reportingLastUpdated.textContent = "Unavailable";
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  reportPageButtons.forEach((button) => {
    button.addEventListener("click", () => {
      setSelectedReportPage(button.dataset.reportPage);
    });
  });

  if (reportPageButtons.length) {
    const selectedButton = reportPageButtons.find((button) => button.getAttribute("aria-pressed") === "true");
    setSelectedReportPage(selectedButton?.dataset.reportPage || "financial-overview");
  }

  if (reportingCurrencySelect) {
    setReportingCurrency(selectedReportingCurrency());
    reportingCurrencySelect.addEventListener("change", () => {
      setReportingCurrency(reportingCurrencySelect.value);
      loadReportingConfig();
    });
  }

  loadReportingConfig();
});
