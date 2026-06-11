// M2/M5/M7/M11 - Classification Administration Start
// Guards the recognition settings page and switches its admin tabs.
const classificationAccessMessage = document.querySelector("#classification-access-message");
const classificationWorkspace = document.querySelector("#classification-workspace");
const classificationLogoutButton = document.querySelector("#logout-button");
let classificationTabs = [];
let classificationPanels = [];

function setClassificationMessage(message, tone = "error") {
  classificationAccessMessage.textContent = message;
  classificationAccessMessage.dataset.tone = tone;
}

function setSaveMessage(message, tone = "success") {
  const saveMessage = document.querySelector("#classification-save-message");
  if (!saveMessage) {
    return;
  }

  saveMessage.textContent = message;
  saveMessage.dataset.tone = tone;
}

function selectClassificationTab(tabName) {
  classificationTabs.forEach((tab) => {
    const selected = tab.dataset.classificationTab === tabName;
    tab.setAttribute("aria-selected", String(selected));
  });

  classificationPanels.forEach((panel) => {
    panel.hidden = panel.dataset.classificationPanel !== tabName;
  });
}

function tabForSection(sectionName) {
  if (sectionName === "transaction" || sectionName === "spending") {
    return "transaction-rules";
  }

  return "document-rules";
}

function openSection(sectionName) {
  const details = Array.from(document.querySelectorAll("details.classification-management"));
  const target = details.find((item) => item.dataset.classificationSection === sectionName);
  if (target) {
    target.open = true;
  }
}

async function refreshWorkbench(sectionName, message) {
  const response = await fetch(window.location.pathname, {
    headers: {
      "X-Requested-With": "fetch",
    },
  });
  if (!response.ok) {
    throw new Error("Recognition settings were saved, but the page could not be refreshed.");
  }

  const html = await response.text();
  const parser = new DOMParser();
  const documentCopy = parser.parseFromString(html, "text/html");
  const nextWorkbench = documentCopy.querySelector(".classification-workbench");
  const currentWorkbench = document.querySelector(".classification-workbench");
  if (!nextWorkbench || !currentWorkbench) {
    throw new Error("Recognition settings were saved, but the refreshed page was incomplete.");
  }

  currentWorkbench.replaceWith(nextWorkbench);
  bindClassificationInteractions();
  selectClassificationTab(tabForSection(sectionName));
  openSection(sectionName);
  setSaveMessage(message, "success");
}

async function classificationErrorMessage(response) {
  if (response.status === 403) {
    return "Administrator access is required.";
  }

  if (response.status === 404) {
    return "This review item is no longer available. Refresh the items to review and try again.";
  }

  const fallback = "Recognition setting could not be saved. Refresh the page and try again.";
  let payload = "";
  try {
    payload = await response.text();
  } catch {
    return fallback;
  }

  if (!payload) {
    return fallback;
  }

  try {
    const parsed = JSON.parse(payload);
    const detail = parsed.detail || parsed.message || parsed.title;
    return friendlyClassificationMessage(detail || fallback);
  } catch {
    return friendlyClassificationMessage(payload);
  }
}

function friendlyClassificationMessage(message) {
  const text = String(message || "").trim();
  const lower = text.toLowerCase();
  if (!text) {
    return "Recognition setting could not be saved. Refresh the page and try again.";
  }

  if (lower.includes("not found") || lower.includes("404")) {
    return "This review item is no longer available. Refresh the items to review and try again.";
  }

  if (lower.includes("already") && lower.includes("review")) {
    return "This review item has already been reviewed. Refresh the items to review to see the current list.";
  }

  if (text.startsWith("{") || lower.includes("httprequestexception") || lower.includes("traceback")) {
    return "Recognition setting could not be saved. Refresh the page and try again.";
  }

  return text;
}

async function saveClassificationForm(form) {
  const sectionName = form.dataset.classificationSection || "document";
  if (form.dataset.confirmMessage && !window.confirm(form.dataset.confirmMessage)) {
    return;
  }

  const submitter = document.querySelector(`button[form="${CSS.escape(form.id)}"]`);
  if (submitter) {
    submitter.disabled = true;
  }
  setSaveMessage("Saving.", "success");

  try {
    const actionUrl = form.getAttribute("action") || window.location.href;
    const response = await fetch(actionUrl, {
      method: form.method || "POST",
      body: new FormData(form),
      headers: {
        "X-Stats-Async-Save": "true",
      },
    });

    if (!response.ok) {
      throw new Error(await classificationErrorMessage(response));
    }

    const result = await response.json();
    if (!result.ok) {
      throw new Error(friendlyClassificationMessage(result.message || "Recognition setting could not be saved."));
    }

    await refreshWorkbench(sectionName, result.message || "Recognition setting saved.");
  } catch (error) {
    setSaveMessage(error.message || "Recognition setting could not be saved.", "error");
  } finally {
    if (submitter) {
      submitter.disabled = false;
    }
  }
}

function bindClassificationInteractions() {
  classificationTabs = Array.from(document.querySelectorAll("[data-classification-tab]"));
  classificationPanels = Array.from(document.querySelectorAll("[data-classification-panel]"));

  classificationTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      selectClassificationTab(tab.dataset.classificationTab);
    });
  });

  document.querySelectorAll("[data-async-classification-form]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      saveClassificationForm(form);
    });
  });
}

async function startClassificationPage() {
  if (!window.statsAccess.token()) {
    window.location.assign("/Login");
    return;
  }

  const user = await window.statsAccess.currentUser();
  if (user.must_change_password) {
    window.location.assign("/Login");
    return;
  }

  if (user.role !== "admin") {
    setClassificationMessage("Administrator access is required.");
    return;
  }

  classificationWorkspace.hidden = false;
  setClassificationMessage(`Signed in as ${user.email}.`, "success");
}

classificationLogoutButton.addEventListener("click", () => {
  window.statsAccess.signOut();
});

bindClassificationInteractions();
startClassificationPage().catch((error) => {
  setClassificationMessage(error.message || "Could not load recognition settings.");
});
// M2/M5/M7/M11 End
